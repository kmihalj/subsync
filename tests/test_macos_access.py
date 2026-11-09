"""Sandbox boundary tests without GUI, media libraries or paid signing.

The package alias keeps these tests independent from subsync's media-engine
imports. Native path marshalling is additionally exercised on macOS; grant
lifetimes use a deterministic backend and private disposable fixtures.
"""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NAME = '_subsync_macos_boundary_tests'
spec = importlib.util.spec_from_file_location(
    NAME, ROOT / 'subsync/macos/__init__.py',
    submodule_search_locations=[str(ROOT / 'subsync/macos')])
package = importlib.util.module_from_spec(spec)
sys.modules[NAME] = package
spec.loader.exec_module(package)
access = importlib.import_module(NAME + '.access')
native = importlib.import_module(NAME + '.native')
mode = importlib.import_module(NAME + '.mode')


class FakeURL:
    def __init__(self, backend, data):
        self.backend, self.spec = backend, backend.data[data]
        self.path = self.spec['path']
        self.stale = self.spec.get('stale', False)
        self.starts = self.stops = self.closes = 0

    def start(self):
        self.starts += 1
        return self.spec.get('allowed', True)

    def stop(self):
        self.stops += 1
        if self.spec.get('stop_error'):
            raise OSError('simulated stop failure')

    def close(self):
        self.closes += 1

    def bookmark(self, read_only):
        return self.backend.create_bookmark(self.path, read_only)


class FakeBackend:
    def __init__(self):
        self.data, self.urls, self.creations = {}, [], []

    def create_bookmark(self, path, read_only=True, directory=False):
        data = ('grant-' + str(len(self.data))).encode()
        self.data[data] = {'path': str(path)}
        self.creations.append((str(path), read_only, directory))
        return data

    def resolve_bookmark(self, data):
        if self.data[data].get('resolve_error'):
            raise OSError('revoked or inaccessible bookmark')
        result = FakeURL(self, data)
        self.urls.append(result)
        return result


class AccessTests(unittest.TestCase):
    def setUp(self):
        build = ROOT / '.build/file-access-tests'
        build.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=build)
        self.root = Path(self.temporary.name)
        self.media = self.root / 'media'
        self.media.mkdir()
        self.file = self.media / 'example.srt'
        self.file.write_text('private disposable fixture')
        self.backend = FakeBackend()
        self.registry = access.BookmarkRegistry(
            self.root / 'profile', enabled=True, backend=self.backend)

    def tearDown(self):
        self.temporary.cleanup()

    def remember(self, path=None, **options):
        return self.registry.remember(path or self.file, **options)

    def test_public_mode_does_not_normalize_load_native_or_write(self):
        class UntouchablePath:
            def __fspath__(self):
                raise AssertionError('Public mode touched a path')
        value = UntouchablePath()
        public = access.BookmarkRegistry(self.root / 'unused', enabled=False)
        with patch.object(access, 'CoreFoundation', side_effect=AssertionError('framework loaded')):
            self.assertIs(public.remember(value), value)
            with public.acquire(value) as actual:
                self.assertIs(actual, value)
            with public.acquire_many([(value, True), (value, False)]) as paths:
                self.assertEqual(paths, [value, value])
        self.assertFalse((self.root / 'unused').exists())

    def test_nested_leases_start_once_and_last_close_stops_once(self):
        self.remember()
        first = self.registry.acquire(self.file)
        second = self.registry.acquire(self.file)
        self.assertEqual(len(self.backend.urls), 1)
        url = self.backend.urls[0]
        first.close()
        self.assertEqual((url.starts, url.stops), (1, 0))
        second.close()
        second.close()
        self.assertEqual((url.starts, url.stops, url.closes), (1, 1, 1))

    def test_failed_group_releases_earlier_resources(self):
        self.remember()
        with self.assertRaises(access.FileAccessError):
            self.registry.acquire_many([(self.file, False), (self.root / 'not-selected', False)])
        self.assertEqual((self.backend.urls[0].stops, self.backend.urls[0].closes), (1, 1))
        self.assertFalse(self.registry._active)

    def test_read_only_grant_does_not_authorize_writes(self):
        self.remember()
        with self.assertRaises(access.FileAccessError):
            self.registry.acquire(self.file, write=True)
        self.assertFalse(self.backend.urls)

    def test_directory_grants_new_children_but_not_sibling_prefix(self):
        self.remember(self.media, directory=True, write=True)
        output = self.media / 'new.srt'
        with self.registry.acquire(output, write=True) as resolved:
            self.assertEqual(resolved, str(output))
        with self.assertRaises(access.FileAccessError):
            self.registry.acquire(self.root / 'media-private' / 'hidden.srt')

    def test_directory_symlink_cannot_escape_authorized_root(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.media / 'link').symlink_to(outside, target_is_directory=True)
        self.remember(self.media, directory=True, write=True)
        with self.assertRaises(access.FileAccessError):
            self.registry.acquire(self.media / 'link' / 'new.srt', write=True)

    def test_stale_moved_file_refreshes_and_survives_new_registry(self):
        self.remember()
        data = next(iter(self.backend.data))
        moved = self.media / 'renamed.srt'
        self.file.rename(moved)
        self.backend.data[data].update(path=str(moved), stale=True)
        with self.registry.acquire(self.file) as resolved:
            self.assertEqual(resolved, str(moved))
        self.assertEqual(self.backend.urls[0].stops, 1)
        reloaded = access.BookmarkRegistry(
            self.root / 'profile', enabled=True, backend=self.backend)
        with reloaded.acquire(moved) as resolved:
            self.assertEqual(resolved, str(moved))
        self.assertEqual(len(self.backend.creations), 2)

    def test_stale_refresh_storage_failure_releases_scope(self):
        self.remember()
        self.backend.data[next(iter(self.backend.data))]['stale'] = True
        original = self.registry.store.read_bytes()
        with patch.object(self.registry, '_save', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.registry.acquire(self.file)
        url = self.backend.urls[0]
        self.assertEqual((url.stops, url.closes), (1, 1))
        self.assertEqual(self.registry.store.read_bytes(), original)
        self.assertFalse(self.registry._active)

    def test_revoked_and_failed_start_are_closed_without_false_stop(self):
        self.remember()
        data = next(iter(self.backend.data))
        self.backend.data[data]['allowed'] = False
        with self.assertRaises(access.FileAccessError):
            self.registry.acquire(self.file)
        self.assertEqual((self.backend.urls[0].stops, self.backend.urls[0].closes), (0, 1))
        self.backend.data[data]['resolve_error'] = True
        with self.assertRaises(OSError):
            self.registry.acquire(self.file)
        self.assertFalse(self.registry._active)

    def test_private_atomic_store_and_corruption_fail_closed(self):
        self.remember()
        self.assertEqual(stat.S_IMODE(self.registry.store.stat().st_mode), 0o600)
        self.registry.store.write_text('[]')
        reloaded = access.BookmarkRegistry(self.root / 'profile', enabled=True, backend=self.backend)
        with self.assertRaises(access.BookmarkStoreError):
            reloaded.acquire(self.file)

    def test_parallel_jobs_share_one_native_scope(self):
        self.remember()
        ready, finish = threading.Barrier(3), threading.Barrier(3)
        def job():
            with self.registry.acquire(self.file):
                ready.wait(timeout=5)
                finish.wait(timeout=5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(job) for _ in range(2)]
            ready.wait(timeout=5)
            self.assertEqual(len(self.backend.urls), 1)
            self.assertEqual(self.backend.urls[0].starts, 1)
            finish.wait(timeout=5)
            for future in futures:
                future.result(timeout=5)
        self.assertEqual(self.backend.urls[0].stops, 1)

    def test_job_exception_and_cleanup_failure_do_not_mask_original(self):
        self.remember()
        self.backend.data[next(iter(self.backend.data))]['stop_error'] = True
        with self.assertLogs(access.logger, level='WARNING'):
            with self.assertRaisesRegex(RuntimeError, 'job cancelled'):
                with self.registry.acquire_many([(self.file, False)]):
                    raise RuntimeError('job cancelled')
        self.assertEqual(self.backend.urls[0].closes, 1)
        self.assertFalse(self.registry._active)

    def test_container_owned_profile_requires_no_native_grant(self):
        internal = self.registry.store.parent / 'assets/speech/model'
        with self.registry.acquire(internal) as resolved:
            self.assertEqual(resolved, str(internal))
        self.assertFalse(self.backend.urls)
        self.assertFalse(self.registry.store.exists())


class DistributionTests(unittest.TestCase):
    def test_frozen_public_artifact_ignores_external_store_flag(self):
        self.assertEqual(mode.distribution_name(
            frozen=True, bundle_info={}, environ={'SUBSYNC_DISTRIBUTION': 'appstore'}), 'public')

    def test_signed_bundle_metadata_and_source_opt_in(self):
        self.assertEqual(mode.distribution_name(
            frozen=True, bundle_info={'SubSyncDistribution': 'appstore'}), 'appstore')
        self.assertEqual(mode.distribution_name(
            frozen=False, environ={'SUBSYNC_DISTRIBUTION': 'appstore'}), 'appstore')

    @unittest.skipUnless(sys.platform == 'darwin', 'Public Apple frameworks require macOS')
    def test_public_native_url_and_container_directory_marshalling(self):
        backend = native.CoreFoundation()
        path = '/tmp/SubSync–žluťoučký.srt'
        with backend.file_url(path) as url:
            self.assertEqual(url.path, path)
        self.assertIsNone(url.value)
        value = backend.application_support_directory('SubSync-ReadOnly-API-Probe')
        self.assertTrue(Path(value).is_absolute())
        self.assertEqual(Path(value).name, 'SubSync-ReadOnly-API-Probe')
        self.assertFalse(Path(value).exists())


if __name__ == '__main__':
    unittest.main()
