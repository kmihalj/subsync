"""Small, lazy bindings to public CoreFoundation security-scoped URL APIs.

No PyObjC dependency, private API, user-profile write or framework loading at
import time. Foundation's public directory search respects App Sandbox's
container; paths must not be constructed from the account's home directory.
"""
import ctypes as C
import os
from pathlib import Path
import sys


class NativeAccessError(OSError):
    pass


class CoreFoundation:
    CREATE_SCOPE = 1 << 11
    CREATE_READ_ONLY = 1 << 12
    RESOLVE_SCOPE = 1 << 10
    RESOLVE_NO_UI = 1 << 8
    RESOLVE_NO_MOUNT = 1 << 9
    UTF8 = 0x08000100

    def __init__(self):
        if sys.platform != 'darwin':
            raise NativeAccessError('Security-scoped URLs require macOS')
        self.cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        ptr, integer, boolean = C.c_void_p, C.c_long, C.c_ubyte
        self._bind('CFRelease', [ptr], None)
        self._bind('CFURLCreateFromFileSystemRepresentation', [ptr, ptr, integer, boolean], ptr)
        self._bind('CFURLCreateBookmarkData', [ptr, ptr, C.c_ulong, ptr, ptr, C.POINTER(ptr)], ptr)
        self._bind('CFURLCreateByResolvingBookmarkData',
                   [ptr, ptr, C.c_ulong, ptr, ptr, C.POINTER(boolean), C.POINTER(ptr)], ptr)
        self._bind('CFURLStartAccessingSecurityScopedResource', [ptr], boolean)
        self._bind('CFURLStopAccessingSecurityScopedResource', [ptr], None)
        self._bind('CFURLCopyFileSystemPath', [ptr, integer], ptr)
        self._bind('CFDataCreate', [ptr, ptr, integer], ptr)
        self._bind('CFDataGetLength', [ptr], integer)
        self._bind('CFDataGetBytePtr', [ptr], ptr)
        self._bind('CFStringGetLength', [ptr], integer)
        self._bind('CFStringGetMaximumSizeForEncoding', [integer, C.c_uint32], integer)
        self._bind('CFStringGetCString', [ptr, ptr, integer, C.c_uint32], boolean)
        self._bind('CFErrorCopyDescription', [ptr], ptr)
        self._bind('CFArrayGetCount', [ptr], integer)
        self._bind('CFArrayGetValueAtIndex', [ptr, integer], ptr)

    def _bind(self, name, arguments, result):
        function = getattr(self.cf, name)
        function.argtypes, function.restype = arguments, result
        setattr(self, name, function)

    def _string(self, value):
        size = self.CFStringGetMaximumSizeForEncoding(self.CFStringGetLength(value), self.UTF8)
        if size < 0:
            raise NativeAccessError('Invalid native string length')
        buffer = C.create_string_buffer(size + 1)
        if not self.CFStringGetCString(value, buffer, len(buffer), self.UTF8):
            raise NativeAccessError('Cannot decode a native file path')
        return buffer.value.decode('utf-8')

    def _checked(self, value, error, operation):
        description = None
        if error.value:
            try:
                text = self.CFErrorCopyDescription(error)
                if text:
                    try:
                        description = self._string(text)
                    finally:
                        self.CFRelease(text)
            finally:
                self.CFRelease(error)
        if not value:
            raise NativeAccessError(description or operation)
        return value

    def file_url(self, path, directory=False):
        encoded = os.fsencode(path)
        if b'\0' in encoded:
            raise ValueError('File paths cannot contain NUL')
        value = self.CFURLCreateFromFileSystemRepresentation(None, encoded, len(encoded), directory)
        if not value:
            raise NativeAccessError('Cannot create a native file URL')
        return ScopedURL(self, value, False)

    def create_bookmark(self, path, read_only=True, directory=False):
        with self.file_url(path, directory) as url:
            return url.bookmark(read_only)

    def resolve_bookmark(self, data):
        if not isinstance(data, bytes) or not data:
            raise NativeAccessError('Empty bookmark data')
        native_data = self.CFDataCreate(None, data, len(data))
        if not native_data:
            raise NativeAccessError('Cannot allocate native bookmark data')
        try:
            stale, error = C.c_ubyte(), C.c_void_p()
            value = self.CFURLCreateByResolvingBookmarkData(
                None, native_data, self.RESOLVE_SCOPE | self.RESOLVE_NO_UI | self.RESOLVE_NO_MOUNT,
                None, None, C.byref(stale), C.byref(error))
            return ScopedURL(self, self._checked(value, error, 'Cannot resolve bookmark'), bool(stale.value))
        finally:
            self.CFRelease(native_data)

    def application_support_directory(self, component):
        if not component or component in ('.', '..') or any(c in component for c in ('/', '\0')):
            raise ValueError('Application directory must be one path component')
        # These are public Foundation/Objective-C runtime APIs. A local public
        # NSAutoreleasePool also makes this safe before wx creates its GUI pool.
        foundation = C.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
        objc = C.CDLL('/usr/lib/libobjc.A.dylib')
        objc.objc_getClass.argtypes, objc.objc_getClass.restype = [C.c_char_p], C.c_void_p
        objc.sel_registerName.argtypes, objc.sel_registerName.restype = [C.c_char_p], C.c_void_p
        send = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
        send_void = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)(('objc_msgSend', objc))
        pool = send(objc.objc_getClass(b'NSAutoreleasePool'), objc.sel_registerName(b'new'))
        if not pool:
            raise NativeAccessError('Cannot initialize a Foundation autorelease pool')
        try:
            search = foundation.NSSearchPathForDirectoriesInDomains
            search.argtypes, search.restype = [C.c_ulong, C.c_ulong, C.c_byte], C.c_void_p
            paths = search(14, 1, True)  # NSApplicationSupportDirectory, NSUserDomainMask
            if not paths or self.CFArrayGetCount(paths) < 1:
                raise NativeAccessError('Application Support directory is unavailable')
            base = self._string(self.CFArrayGetValueAtIndex(paths, 0))
            return str(Path(base) / component)
        finally:
            send_void(pool, objc.sel_registerName(b'drain'))


class ScopedURL:
    def __init__(self, backend, value, stale):
        self.backend, self.value, self.stale = backend, value, stale
        self._accesses = 0

    @property
    def path(self):
        value = self.backend.CFURLCopyFileSystemPath(self.value, 0)
        if not value:
            raise NativeAccessError('Bookmark is not a file URL')
        try:
            return self.backend._string(value)
        finally:
            self.backend.CFRelease(value)

    def start(self):
        if not self.value:
            raise NativeAccessError('Native URL has been released')
        started = bool(self.backend.CFURLStartAccessingSecurityScopedResource(self.value))
        if started:
            self._accesses += 1
        return started

    def stop(self):
        if self._accesses:
            self.backend.CFURLStopAccessingSecurityScopedResource(self.value)
            self._accesses -= 1

    def bookmark(self, read_only=True):
        options = self.backend.CREATE_SCOPE
        if read_only:
            options |= self.backend.CREATE_READ_ONLY
        error = C.c_void_p()
        data = self.backend.CFURLCreateBookmarkData(
            None, self.value, options, None, None, C.byref(error))
        data = self.backend._checked(data, error, 'Cannot create a security-scoped bookmark')
        try:
            return C.string_at(self.backend.CFDataGetBytePtr(data), self.backend.CFDataGetLength(data))
        finally:
            self.backend.CFRelease(data)

    def close(self):
        if self.value:
            while self._accesses:
                self.stop()
            self.backend.CFRelease(self.value)
            self.value = None

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def application_support_directory(component='SubSync ARM'):
    """Return the container-aware directory, without creating or writing it."""
    return CoreFoundation().application_support_directory(component)
