/* Regression for the public PS5 streaming CEP API: preserve every final frame.
 * Runs around both feature lookahead and ring boundaries, and repeats each
 * utterance on one decoder to cover reset as well as end padding. */
#include <pocketsphinx.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    const int sizes[] = {0, 1, 2, 3, 4, 7, 11, 12, 13, 31, 127, 128, 129, 255, 512, 513};
    char hmm[4096], lm[4096], dict[4096];
    int failures = 0;
    if (argc != 2) return 2;
    if (snprintf(hmm, sizeof(hmm), "%s/en-us", argv[1]) >= (int)sizeof(hmm)
        || snprintf(lm, sizeof(lm), "%s/en-us.lm.bin", argv[1]) >= (int)sizeof(lm)
        || snprintf(dict, sizeof(dict), "%s/cmudict-en-us.dict", argv[1]) >= (int)sizeof(dict)) return 2;
    ps_config_t *config = ps_config_init(NULL);
    ps_config_set_str(config, "hmm", hmm);
    ps_config_set_str(config, "lm", lm);
    ps_config_set_str(config, "dict", dict);
    ps_config_set_str(config, "logfn", "/dev/null");
    ps_decoder_t *decoder = ps_init(config);
    if (!decoder) return 3;
    int dimension = ps_config_int(config, "ceplen");
    for (unsigned i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
        int count = sizes[i];
        float **cep = calloc(count ? count : 1, sizeof(*cep));
        if (!cep) return 4;
        for (int frame = 0; frame < count; ++frame) {
            cep[frame] = calloc(dimension, sizeof(**cep));
            if (!cep[frame]) return 4;
            cep[frame][0] = 40.0f;
        }
        for (int chunk = 1; chunk <= 9; chunk += 8) {
            for (int repeat = 0; repeat < 2; ++repeat) {
                if (ps_start_utt(decoder) < 0) return 5;
                for (int frame = 0; frame < count; frame += chunk) {
                    int available = count - frame < chunk ? count - frame : chunk;
                    if (ps_process_cep(decoder, cep + frame, available, 0, 0) < 0) return 6;
                }
                if (ps_end_utt(decoder) < 0) return 7;
                double speech, cpu, wall;
                ps_get_utt_time(decoder, &speech, &cpu, &wall);
                int searched = (int)llround(speech * ps_config_int(config, "frate"));
                if (searched != count) {
                    fprintf(stderr, "input=%d chunk=%d repeat=%d searched=%d\n",
                            count, chunk, repeat, searched);
                    ++failures;
                }
            }
        }
        for (int frame = 0; frame < count; ++frame) free(cep[frame]);
        free(cep);
    }
    ps_free(decoder);
    ps_config_free(config);
    printf("CEP tail/reset: %d failures in 64 cases\n", failures);
    return failures ? 1 : 0;
}
