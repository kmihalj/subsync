/* Streaming buffer, EOF, reset, and consumer-error regressions for the
 * application-owned audio frontend. Uses the public upstream PCM fixture.
 */
#include "frontend/native_frontend.h"
#include <pocketsphinx/err.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

struct sink {
    int capacity, ceplen, reject, invalid;
    size_t calls;
};

static int output(void *context, float **cep, int frames, int offset)
{
    struct sink *sink = context;
    if (!cep || frames < 1 || frames > sink->capacity || offset < 0) {
        sink->invalid = 1;
        return -1;
    }
    for (int i = 0; i < frames; ++i) {
        if (!cep[i]) {
            sink->invalid = 1;
            return -1;
        }
        for (int j = 0; j < sink->ceplen; ++j) {
            if (!isfinite(cep[i][j])) {
                sink->invalid = 1;
                return -1;
            }
        }
    }
    ++sink->calls;
    return sink->reject ? -1 : 0;
}

static struct ss_frontend *create(int capacity, int noise, struct sink *sink)
{
    ps_config_t *config = ps_config_init(NULL);
    struct ss_frontend *frontend;
    if (!config) return NULL;
    ps_config_set_int(config, "samprate", 16000);
    ps_config_set_bool(config, "remove_noise", noise);
    frontend = ss_frontend_create_config(config, capacity);
    ps_config_free(config);
    if (!frontend) return NULL;
    *sink = (struct sink){capacity, ss_frontend_ceplen(frontend), 0, 0, 0};
    ss_frontend_start_stream(frontend);
    if (ss_frontend_start_utt(frontend) < 0) {
        ss_frontend_free(frontend);
        return NULL;
    }
    return frontend;
}

static int normal_case(const int16_t *pcm, size_t count, size_t chunk,
        int capacity, int noise)
{
    struct sink sink;
    struct ss_frontend *frontend = create(capacity, noise, &sink);
    int failed = 0;
    if (!frontend) return 1;
    for (size_t pos = 0; pos < count;) {
        const size_t take = count - pos < chunk ? count - pos : chunk;
        if (ss_frontend_process(frontend, pcm + pos, take, output, &sink) < 0) {
            failed = 1;
            break;
        }
        pos += take;
    }
    if (!failed && ss_frontend_end_utt(frontend, output, &sink) < 0) failed = 1;
    const size_t calls = sink.calls;
    if (!failed && (ss_frontend_end_utt(frontend, output, &sink) < 0
            || sink.calls != calls)) failed = 1;
    if (!failed && (ss_frontend_start_utt(frontend) < 0
            || ss_frontend_end_utt(frontend, output, &sink) < 0)) failed = 1;
    ss_frontend_free(frontend);
    return failed || sink.invalid;
}

static int rejected_callback(const int16_t *pcm, size_t count, int capacity)
{
    struct sink sink;
    struct ss_frontend *frontend = create(capacity, 1, &sink);
    int failed = 0;
    if (!frontend) return 1;
    sink.reject = 1;
    /* The rejection occurs when the entire MFCC queue is full. Ending the
     * utterance must return an error without indexing past that queue or
     * retrying an already rejected batch. Explicit reset permits reuse. */
    if (ss_frontend_process(frontend, pcm, count, output, &sink) >= 0
            || sink.calls != 1 || sink.invalid) failed = 1;
    if (!failed && (ss_frontend_end_utt(frontend, output, &sink) >= 0
            || sink.calls != 1)) failed = 1;
    if (!failed && (ss_frontend_process(frontend, pcm, count, output, &sink) >= 0
            || sink.calls != 1)) failed = 1;
    if (!failed && (ss_frontend_end_utt(frontend, output, &sink) >= 0
            || sink.calls != 1)) failed = 1;
    sink.reject = 0;
    ss_frontend_start_stream(frontend);
    if (!failed && ss_frontend_start_utt(frontend) < 0) failed = 1;
    if (!failed && (ss_frontend_process(frontend, pcm, count, output, &sink) < 0
            || ss_frontend_end_utt(frontend, output, &sink) < 0
            || sink.calls <= 1 || sink.invalid)) failed = 1;
    ss_frontend_free(frontend);
    return failed;
}

int main(int argc, char **argv)
{
    const int capacities[] = {1, 2, 7, 64};
    const size_t chunks[] = {1, 9, 160, 997, 4096};
    size_t lengths[] = {0, 1, 159, 160, 399, 400, 401, 513, 1000, 0};
    FILE *file;
    long bytes;
    size_t count, cases = 0;
    int16_t *pcm;
    if (argc != 2 || !(file = fopen(argv[1], "rb"))) {
        fprintf(stderr, "Usage: frontend-stream-test GOFORWARD_RAW\n");
        return 2;
    }
    if (fseek(file, 0, SEEK_END) != 0 || (bytes = ftell(file)) < 2002
            || bytes % 2 || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 2;
    }
    count = (size_t)bytes / sizeof(*pcm);
    pcm = malloc((size_t)bytes);
    if (!pcm || fread(pcm, sizeof(*pcm), count, file) != count) {
        fclose(file);
        free(pcm);
        return 2;
    }
    fclose(file);
    lengths[sizeof(lengths) / sizeof(lengths[0]) - 1] = count;
    err_set_loglevel(ERR_FATAL);
    for (size_t a = 0; a < sizeof(capacities) / sizeof(capacities[0]); ++a)
    for (size_t b = 0; b < sizeof(chunks) / sizeof(chunks[0]); ++b)
    for (size_t c = 0; c < sizeof(lengths) / sizeof(lengths[0]); ++c)
    for (int noise = 0; noise < 2; ++noise) {
        if (normal_case(pcm, lengths[c], chunks[b], capacities[a], noise)) {
            fprintf(stderr, "FAIL stream capacity=%d chunk=%zu samples=%zu noise=%d\n",
                    capacities[a], chunks[b], lengths[c], noise);
            free(pcm);
            return 1;
        }
        ++cases;
    }
    for (size_t i = 0; i < sizeof(capacities) / sizeof(capacities[0]); ++i) {
        if (rejected_callback(pcm, count, capacities[i])) {
            fprintf(stderr, "FAIL callback rejection/EOF/reset capacity=%d\n", capacities[i]);
            free(pcm);
            return 1;
        }
    }
    free(pcm);
    printf("PASS %zu streaming/partial-EOF/noise cases, double EOF, reset; "
            "callback rejection/EOF/recovery at 4 capacities\n", cases);
    return 0;
}
