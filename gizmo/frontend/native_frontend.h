#ifndef SUBSYNC_NATIVE_FRONTEND_H
#define SUBSYNC_NATIVE_FRONTEND_H
/* Owned signal-processing frontend. Decoder configuration and search remain
 * in the current PocketSphinx public API; no legacy library is linked. */
#include <stddef.h>
#include <stdint.h>
#include <pocketsphinx.h>
#ifdef __cplusplus
extern "C" {
#endif
struct ss_frontend;
typedef int (*ss_cep_callback)(void *, float **, int, int);
struct ss_frontend *ss_frontend_create_config(ps_config_t *config, int buffer_frames);
void ss_frontend_free(struct ss_frontend *fe);
int ss_frontend_process(struct ss_frontend *fe, const int16_t *pcm, size_t count,
        ss_cep_callback output, void *context);
int ss_frontend_end_utt(struct ss_frontend *fe, ss_cep_callback output, void *context);
int ss_frontend_start_utt(struct ss_frontend *fe);
void ss_frontend_start_stream(struct ss_frontend *fe);
int ss_frontend_in_speech(struct ss_frontend *fe);
int ss_frontend_ceplen(struct ss_frontend *fe);
#ifdef __cplusplus
}
#endif
#endif
