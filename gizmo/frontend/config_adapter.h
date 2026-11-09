/* Read-only compatibility view over public PocketSphinx 5 configuration.
 * No parser, old command-line definitions, or private PS layout is included.
 */
#ifndef SUBSYNC_FRONTEND_CONFIG_ADAPTER_H
#define SUBSYNC_FRONTEND_CONFIG_ADAPTER_H
#include <pocketsphinx.h>
#include <string.h>
#include <math.h>
#include <limits.h>

typedef ps_config_t cmd_ln_t;

static inline const char *subsync_frontend_config_name(const char *name)
{
    return name != NULL && name[0] == '-' ? name + 1 : name;
}

static inline double subsync_frontend_config_number(ps_config_t *config, const char *raw)
{
    const char *name = subsync_frontend_config_name(raw);
    ps_type_t type = ps_config_typeof(config, name);
    if (type & ARG_FLOATING)
        return ps_config_float(config, name);
    if (type & (ARG_INTEGER | ARG_BOOLEAN))
        return (double)ps_config_int(config, name);
    /* VAD controls removed from PS5 retain the original SubSync defaults. */
    if (strcmp(name, "vad_prespeech") == 0) return 20.0;
    if (strcmp(name, "vad_startspeech") == 0) return 10.0;
    if (strcmp(name, "vad_postspeech") == 0) return 50.0;
    if (strcmp(name, "vad_threshold") == 0) return 3.0;
    if (strcmp(name, "remove_silence") == 0) return 1.0;
    return 0.0;
}

static inline long subsync_frontend_config_integer(ps_config_t *config, const char *raw)
{
    const char *name = subsync_frontend_config_name(raw);
    long value = (long)subsync_frontend_config_number(config, name);
    if (strcmp(name, "nfft") == 0 && value == 0) {
        /* Old interfaces need a concrete FFT size; latest FE validates it.
         * Use the same rounded window sample count as fe->frame_size. */
        const double samples = floor(subsync_frontend_config_number(config, "samprate")
                * subsync_frontend_config_number(config, "wlen") + 0.5);
        value = 1;
        while ((double)value < samples && value <= LONG_MAX / 2)
            value *= 2;
    }
    return value;
}

static inline const char *subsync_frontend_config_string(ps_config_t *config, const char *raw)
{
    const char *name = subsync_frontend_config_name(raw);
    if (ps_config_typeof(config, name) & ARG_STRING)
        return ps_config_str(config, name);
    return NULL;
}

#define cmd_ln_retain(config) ps_config_retain(config)
#define cmd_ln_free_r(config) ps_config_free(config)
#define cmd_ln_int32_r(config, name) ((int32)subsync_frontend_config_integer(config, name))
#define cmd_ln_float32_r(config, name) ((float32)subsync_frontend_config_number(config, name))
#define cmd_ln_float64_r(config, name) ((float64)subsync_frontend_config_number(config, name))
#define cmd_ln_boolean_r(config, name) (subsync_frontend_config_number(config, name) != 0.0)
#define cmd_ln_str_r(config, name) subsync_frontend_config_string(config, name)
#endif
