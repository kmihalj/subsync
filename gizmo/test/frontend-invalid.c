/* Boundary regressions for the owned native frontend.
 * Long warp strings and the oversized-FFT WAV reproduce PocketSphinx 5.1.1
 * test_fe_warp_overflow / test_fe_fft_overflow through our public boundary.
 * Each malformed configuration runs separately so a signal or E_FATAL is a
 * failed test, rather than accidentally being accepted as clean rejection.
 */
#include "frontend/native_frontend.h"
#include <pocketsphinx/err.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

enum value_kind { INTEGER, FLOATING, STRING, CAPACITY };
struct invalid_case {
    const char *name;
    enum value_kind kind;
    long integer;
    double floating;
    const char *string;
};
#define I(name, value) {name, INTEGER, value, 0, NULL}
#define F(name, value) {name, FLOATING, 0, value, NULL}
#define S(name, value) {name, STRING, 0, 0, value}
static const struct invalid_case cases[] = {
    {"buffer_frames", CAPACITY, 0, 0, NULL},
    {"buffer_frames", CAPACITY, 4097, 0, NULL},
    I("samprate", 0), I("samprate", -1), I("samprate", 192001),
    I("samprate", LONG_MAX),
    I("frate", 0), I("frate", -1), I("frate", 8001),
    I("nfft", -1), I("nfft", 1), I("nfft", 3), I("nfft", 32768),
    I("nfft", LONG_MAX), I("nfft", 128),
    I("ncep", 0), I("ncep", 256), I("ncep", LONG_MAX),
    I("nfilt", 0), I("nfilt", 4097), I("nfilt", LONG_MAX),
    F("wlen", 0), F("wlen", -1), F("wlen", NAN),
    F("wlen", INFINITY), F("wlen", 1e300), F("wlen", 1e-300),
    F("alpha", NAN), F("alpha", INFINITY), F("alpha", 1e300),
    F("lowerf", NAN), F("lowerf", INFINITY), F("lowerf", -1),
    F("upperf", NAN), F("upperf", INFINITY), F("upperf", 129),
    F("upperf", 9000),
    S("transform", NULL), S("transform", "invalid"),
    S("input_endian", NULL), S("warp_type", NULL),
    S("warp_type", "invalid")
};

static int invalid_child(const struct invalid_case *test)
{
    ps_config_t *config = ps_config_init(NULL);
    struct ss_frontend *frontend;
    int capacity = 64;
    if (!config) return 1;
    ps_config_set_int(config, "samprate", 16000);
    switch (test->kind) {
    case INTEGER: ps_config_set_int(config, test->name, test->integer); break;
    case FLOATING: ps_config_set_float(config, test->name, test->floating); break;
    case STRING: ps_config_set_str(config, test->name, test->string); break;
    case CAPACITY: capacity = (int)test->integer; break;
    }
    frontend = ss_frontend_create_config(config, capacity);
    ss_frontend_free(frontend);
    ps_config_free(config);
    return frontend != NULL;
}

static int check_invalid(void)
{
    unsigned failures = 0;
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        int status;
        pid_t child = fork();
        if (child == 0) _exit(invalid_child(&cases[i]));
        if (child < 0 || waitpid(child, &status, 0) != child
                || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
            fprintf(stderr, "FAIL invalid case %zu: %s\n", i, cases[i].name);
            ++failures;
        }
    }
    return (int)failures;
}

static int check_long_warp(void)
{
    const char *types[] = {"affine", "inverse_linear", "piecewise_linear"};
    char text[512];
    int failures = 0;
    for (size_t i = 0; i < sizeof(text) - 1; ++i) text[i] = '0' + (i % 10);
    text[sizeof(text) - 1] = '\0';
    for (size_t i = 0; i < sizeof(types) / sizeof(types[0]); ++i) {
        ps_config_t *config = ps_config_init(NULL);
        struct ss_frontend *frontend;
        ps_config_set_int(config, "samprate", 16000);
        ps_config_set_str(config, "warp_type", types[i]);
        ps_config_set_str(config, "warp_params", text);
        frontend = ss_frontend_create_config(config, 64);
        if (!frontend) {
            fprintf(stderr, "FAIL long warp: %s\n", types[i]);
            ++failures;
        }
        ss_frontend_free(frontend);
        ps_config_free(config);
    }
    return failures;
}

static int check_awful_wav(const char *path)
{
    ps_config_t *config = ps_config_init(NULL);
    struct ss_frontend *frontend;
    FILE *input = fopen(path, "rb");
    if (!input || !config || ps_config_wavfile(config, input, path) != 0) {
        fprintf(stderr, "FAIL reading oversized-FFT upstream WAV\n");
        if (input) fclose(input);
        ps_config_free(config);
        return 1;
    }
    fclose(input);
    frontend = ss_frontend_create_config(config, 64);
    ss_frontend_free(frontend);
    ps_config_free(config);
    if (frontend) fprintf(stderr, "FAIL oversized-FFT upstream WAV accepted\n");
    return frontend != NULL;
}

int main(int argc, char **argv)
{
    int failures;
    err_set_loglevel(ERR_FATAL);
    failures = check_invalid() + check_long_warp();
    if (argc > 1) failures += check_awful_wav(argv[1]);
    if (failures) {
        fprintf(stderr, "%d frontend boundary checks failed\n", failures);
        return 1;
    }
    printf("Frontend boundary checks passed: %zu invalid inputs, 3 long warps%s\n",
            sizeof(cases) / sizeof(cases[0]), argc > 1 ? ", oversized WAV" : "");
    return 0;
}
