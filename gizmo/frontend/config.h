/* Local build configuration for the private, native macOS frontend archive. */
#ifndef SUBSYNC_FRONTEND_CONFIG_H
#define SUBSYNC_FRONTEND_CONFIG_H
#if !defined(__APPLE__) || !defined(__aarch64__)
#error "The private SubSync frontend is built only for macOS arm64"
#endif
#if defined(FIXED_POINT) || defined(FIXED16)
#error "The private SubSync frontend requires the original floating-point path"
#endif
#define HAVE_CONFIG_H 1
#define HAVE_STDINT_H 1
#define HAVE_LONG_LONG 1
#define SIZEOF_LONG 8
#define SIZEOF_LONG_LONG 8
#define PS_USE_THREAD_LOCAL_RNG 1
/* arm64 macOS is little-endian; WORDS_BIGENDIAN remains undefined. */
#endif
