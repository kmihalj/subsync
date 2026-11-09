"""Persistent user-selected grants for the optional sandbox distribution.

The public distribution is an absolute pass-through: no path normalization,
native framework loading, registry reads or writes. A path supplied in YAML
is never itself a grant. Only remember() following a native user selection
records access; the OS remains the authority over each security-scoped URL.
"""
import base64
from contextlib import AbstractContextManager
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import uuid

from .mode import is_appstore_build
from .native import CoreFoundation

logger = logging.getLogger(__name__)


class FileAccessError(PermissionError):
    pass


class BookmarkStoreError(FileAccessError):
    pass


def _canonical(path):
    return os.path.realpath(os.path.abspath(os.fspath(path)))


class Lease(AbstractContextManager):
    def __init__(self, path, release=None):
        self.path, self._release = path, release

    def close(self):
        release, self._release = self._release, None
        if release is not None:
            release()

    def __enter__(self):
        return self.path

    def __exit__(self, kind, error, traceback):
        try:
            self.close()
        except Exception:
            if error is None:
                raise
            logger.warning('Could not release file access after an error', exc_info=True)


class AccessGroup(AbstractContextManager):
    """Acquire several paths atomically and release in reverse order."""
    def __init__(self, registry, paths):
        self.paths, self._leases = [], []
        try:
            for path, write in paths:
                lease = registry.acquire(path, write=write)
                self._leases.append(lease)
                self.paths.append(lease.path)
        except Exception:
            self.close(suppress_errors=True)
            raise

    def close(self, suppress_errors=False):
        leases, self._leases = self._leases, []
        first = None
        for lease in reversed(leases):
            try:
                lease.close()
            except Exception as error:
                first = first or error
                logger.warning('Could not release a file-access lease', exc_info=True)
        if first is not None and not suppress_errors:
            raise first

    def __enter__(self):
        return self.paths

    def __exit__(self, kind, error, traceback):
        self.close(suppress_errors=error is not None)


class BookmarkRegistry:
    def __init__(self, profile=None, *, enabled=False, backend=None):
        self.enabled = enabled
        self._backend = backend
        self._lock = threading.RLock()
        self._entries = None
        self._active = {}
        self._unavailable = set()
        self.store = Path(profile) / 'file-bookmarks.json' if enabled and profile else None
        if enabled and self.store is None:
            raise ValueError('Sandbox file access requires a private profile directory')

    def _native(self):
        if self._backend is None:
            self._backend = CoreFoundation()
        return self._backend

    def _load(self):
        if self._entries is not None:
            return
        if not self.store.exists():
            self._entries = []
            return
        try:
            if self.store.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Bookmark store is too large')
            value = json.loads(self.store.read_text(encoding='utf-8'))
            if (not isinstance(value, dict) or value.get('version') != 1
                    or not isinstance(value.get('bookmarks'), list)):
                raise ValueError('Unsupported bookmark store')
            entries, identifiers = [], set()
            for entry in value['bookmarks']:
                if (not isinstance(entry, dict) or not isinstance(entry.get('id'), str)
                        or entry['id'] in identifiers or not isinstance(entry.get('path'), str)
                        or not os.path.isabs(entry['path'])
                        or type(entry.get('directory')) is not bool
                        or type(entry.get('writable')) is not bool):
                    raise ValueError('Malformed bookmark entry')
                aliases = entry.get('aliases', [])
                if not isinstance(aliases, list) or not all(
                        isinstance(path, str) and os.path.isabs(path) for path in aliases):
                    raise ValueError('Malformed bookmark aliases')
                data = base64.b64decode(entry['data'], validate=True)
                if not data or len(data) > 1024 * 1024:
                    raise ValueError('Malformed bookmark data')
                identifiers.add(entry['id'])
                entries.append(dict(entry, aliases=aliases))
            self._entries = entries
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise BookmarkStoreError('Saved file permissions could not be read') from error

    def _save(self, entries):
        self.store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix='.file-bookmarks-', dir=self.store.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump({'version': 1, 'bookmarks': entries}, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.store)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        self._entries = entries

    def remember(self, path, *, write=False, directory=False):
        """Record an existing native-panel/drop grant; this grants nothing by itself."""
        if not self.enabled:
            return path
        canonical = _canonical(path)
        with self._lock:
            try:
                self._load()
                previous = self._entries
            except BookmarkStoreError:
                # An explicit new native selection can recover a corrupt
                # registry; the unreadable file never authorizes any path.
                logger.warning('Replacing unreadable permissions after a new selection')
                previous = []
            data = self._native().create_bookmark(canonical, read_only=not write, directory=directory)
            if not isinstance(data, bytes) or not data or len(data) > 1024 * 1024:
                raise FileAccessError('Cannot store invalid bookmark data')
            entry = {'id': uuid.uuid4().hex, 'path': canonical, 'aliases': [],
                     'directory': bool(directory), 'writable': bool(write),
                     'data': base64.b64encode(data).decode('ascii')}
            entries = [old for old in previous if old['id'] not in self._unavailable and not (
                old['path'] == canonical and old['directory'] == bool(directory)
                and old['writable'] == bool(write))]
            self._save(entries + [entry])
        return path

    def _choose(self, path, write, directory=False):
        candidates = []
        for entry in self._entries:
            if entry['id'] in self._unavailable:
                continue
            if write and not entry['writable']:
                continue
            if directory and not entry['directory']:
                continue
            for alias in (entry['path'], *entry['aliases']):
                if path == alias:
                    candidates.append((len(alias), not entry['writable'], entry, ''))
                elif entry['directory'] and Path(path).is_relative_to(alias):
                    candidates.append((len(alias), not entry['writable'], entry,
                                       os.path.relpath(path, alias)))
        if not candidates:
            raise FileAccessError('Select this file or its containing folder to allow access')
        _, _, entry, relative = max(candidates, key=lambda item: item[:2])
        return entry, relative

    def has_grant(self, path, *, write=False, directory=False):
        """Check saved selection metadata; acquire() still verifies OS access."""
        if not self.enabled:
            return True
        canonical = _canonical(path)
        if Path(canonical).is_relative_to(_canonical(self.store.parent)):
            return True
        with self._lock:
            try:
                self._load()
                self._choose(canonical, write, directory)
                return True
            except FileAccessError:
                return False

    def acquire(self, path, *, write=False):
        if not self.enabled:
            return Lease(path)
        canonical = _canonical(path)
        # Container-owned settings/models need no security-scoped bookmark.
        if Path(canonical).is_relative_to(_canonical(self.store.parent)):
            return Lease(canonical)
        with self._lock:
            self._load()
            entry, relative = self._choose(canonical, write)
            identifier = entry['id']
            active = self._active.get(identifier)
            if active is None:
                try:
                    url = self._native().resolve_bookmark(base64.b64decode(entry['data']))
                except Exception:
                    self._unavailable.add(identifier)
                    raise
                started = False
                try:
                    started = url.start()
                    if not started:
                        raise FileAccessError('Saved access is no longer available; select the file again')
                    base = _canonical(url.path)
                    if url.stale or base not in (entry['path'], *entry['aliases']):
                        updated = dict(entry)
                        updated['data'] = base64.b64encode(url.bookmark(
                            read_only=not entry['writable'])).decode('ascii')
                        updated['aliases'] = list(dict.fromkeys([*entry['aliases'], base]))
                        self._save([updated if old['id'] == identifier else old for old in self._entries])
                    active = {'url': url, 'base': base, 'count': 0}
                except Exception:
                    self._unavailable.add(identifier)
                    try:
                        if started:
                            url.stop()
                    finally:
                        url.close()
                    raise
                self._active[identifier] = active
            resolved = _canonical(os.path.join(active['base'], relative)) if relative else active['base']
            if entry['directory'] and not Path(resolved).is_relative_to(active['base']):
                if active['count'] == 0:
                    self._dispose(identifier)
                raise FileAccessError('The selected folder does not grant access outside that folder')
            active['count'] += 1
            return Lease(resolved, lambda: self._release(identifier))

    def _dispose(self, identifier):
        active = self._active.pop(identifier)
        try:
            active['url'].stop()
        finally:
            active['url'].close()

    def _release(self, identifier):
        with self._lock:
            active = self._active[identifier]
            active['count'] -= 1
            if active['count'] == 0:
                self._dispose(identifier)

    def acquire_many(self, paths):
        return AccessGroup(self, paths)


_registry = None
_public = BookmarkRegistry(enabled=False)


def registry():
    if not is_appstore_build():
        return _public
    from subsync import config
    global _registry
    if _registry is None:
        _registry = BookmarkRegistry(config.configdir, enabled=True)
    return _registry


def remember(path, *, write=False, directory=False):
    return registry().remember(path, write=write, directory=directory)


def access(path, *, write=False):
    return registry().acquire(path, write=write)


def access_many(paths):
    return registry().acquire_many(paths)
