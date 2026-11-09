/* -*- c-basic-offset: 4; indent-tabs-mode: nil -*- */
/* ====================================================================
 * Copyright (c) 2008 Carnegie Mellon University.  All rights
 * reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *
 * This work was supported in part by funding from the Defense Advanced
 * Research Projects Agency and the National Science Foundation of the
 * United States of America, and the CMU Sphinx Speech Consortium.
 *
 * THIS SOFTWARE IS PROVIDED BY CARNEGIE MELLON UNIVERSITY ``AS IS'' AND
 * ANY EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL CARNEGIE MELLON UNIVERSITY
 * NOR ITS EMPLOYEES BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * ====================================================================
 *
 */


/* Owned compatibility boundary around current PocketSphinx-derived DSP.
 * Only ps_config_* and public error reporting cross the library boundary.
 * All private signal-processing functions are namespaced and linked here. */
#include "native_frontend.h"
#include "fe/fe.h"
#include "config_adapter.h"
#include "util/ckd_alloc.h"
#include "util/err.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>

struct ss_frontend {
    fe_t *fe;
    mfcc_t **mfcc;
    float32 **floats;
    int buffer_frames;
    int output_index;
    int pending_frames;
    int pending_offset;
    int failed;
};
static int valid_configuration(ps_config_t *config,int capacity)
{
    if (!config || capacity<1 || capacity>4096) return 0;
    const char *transform=ps_config_str(config,"transform");
    const char *endian=ps_config_str(config,"input_endian");
    const char *warp=ps_config_str(config,"warp_type");
    if (!transform || !endian || !warp) return 0;
    if (strcmp(transform,"legacy") && strcmp(transform,"dct") && strcmp(transform,"htk")) return 0;
    if (strcmp(endian,"little") && strcmp(endian,"big")) return 0;
    if (strcmp(warp,"inverse_linear") && strcmp(warp,"affine") && strcmp(warp,"piecewise_linear")
            && strcmp(warp,"inverse") && strcmp(warp,"linear") && strcmp(warp,"piecewise")) return 0;
    const long rate=ps_config_int(config,"samprate");
    const long frate=ps_config_int(config,"frate");
    const long nfft=ps_config_int(config,"nfft");
    const long ncep=ps_config_int(config,"ncep");
    const long filters=ps_config_int(config,"nfilt");
    const double window=ps_config_float(config,"wlen");
    const double alpha=ps_config_float(config,"alpha");
    const double lower=ps_config_float(config,"lowerf");
    const double upper=ps_config_float(config,"upperf");
    if (rate<1 || rate>192000 || frate<1 || frate>rate/2) return 0;
    if (!isfinite(window) || window<=0 || !isfinite((float)window)
            || window*rate<2 || window*rate+0.5>16384) return 0;
    if ((double)rate/frate+0.5>32767) return 0;
    if (nfft && (nfft<2 || nfft>16384 || (nfft&(nfft-1)))) return 0;
    if (ncep<1 || ncep>255 || filters<1 || filters>4096) return 0;
    if ((ps_config_bool(config,"logspec") || ps_config_bool(config,"smoothspec"))
            && filters>255) return 0;
    if (!isfinite(alpha) || !isfinite((float)alpha) || !isfinite(lower)
            || !isfinite(upper) || lower<0 || upper<=lower || upper>rate/2.0+1.0) return 0;
    return 1;
}
struct ss_frontend *ss_frontend_create_config(ps_config_t *config,int buffer_frames)
{
    if (!valid_configuration(config,buffer_frames)) return NULL;
    struct ss_frontend *result=calloc(1,sizeof(*result));
    if (!result) return NULL;
    result->fe=fe_init_auto_r(config);
    if (!result->fe) {free(result);return NULL;}
    result->buffer_frames=buffer_frames;
    result->mfcc=(mfcc_t**)ckd_calloc_2d(buffer_frames,fe_get_output_size(result->fe),sizeof(mfcc_t));
    result->floats=(float32**)ckd_calloc_2d(buffer_frames,fe_get_output_size(result->fe),sizeof(float32));
    return result;
}
void ss_frontend_free(struct ss_frontend *fe)
{
    if (!fe) return;
    if (fe->mfcc) ckd_free_2d(fe->mfcc);
    if (fe->floats) ckd_free_2d(fe->floats);
    fe_free(fe->fe);
    free(fe);
}
/* Preserve the original streaming MFCC ring boundaries.  Live normalization
 * updates operate on each batch, so compacting every call into a new buffer
 * changes adaptation even when the coefficient sequence is identical.  This
 * is buffer scheduling only: decoding remains in public ps_process_cep(). */
static int drain_frames(struct ss_frontend *fe,ss_cep_callback output,void *context)
{
    while (fe->pending_frames) {
        const int available=fe->buffer_frames-fe->output_index;
        const int frames=fe->pending_frames<available?fe->pending_frames:available;
        fe_mfcc_to_float(fe->fe,fe->mfcc+fe->output_index,fe->floats,frames);
        if (output(context,fe->floats,frames,fe->pending_offset)<0)
            {fe->failed=1;return -1;}
        fe->pending_offset=0;
        fe->pending_frames-=frames;
        fe->output_index=(fe->output_index+frames)%fe->buffer_frames;
    }
    return 0;
}
int ss_frontend_process(struct ss_frontend *fe,const int16_t *pcm,size_t count,
        ss_cep_callback output,void *context)
{
    if (fe->failed || (!pcm && count) || !output) return -1;
    while (count) {
        int32 frames=fe->buffer_frames-fe->pending_frames;
        int input_index=(fe->output_index+fe->pending_frames)%fe->buffer_frames;
        const size_t before=count;
        const int pending_before=fe->pending_frames;
        /* Fill both sides of a wrapped ring before delivering either side,
         * matching the original frontend/acoustic-model handoff. */
        while (input_index+frames>fe->buffer_frames) {
            int32 first=fe->buffer_frames-input_index,offset=0;
            if (fe_process_frames(fe->fe,&pcm,&count,fe->mfcc+input_index,&first,&offset)<0)
                return -1;
            if (offset>0) fe->pending_offset=offset;
            fe->pending_frames+=first;
            frames-=first;
            input_index=(input_index+first)%fe->buffer_frames;
            if (first==0) goto drain;
        }
        {
            int32 offset=0;
            if (fe_process_frames(fe->fe,&pcm,&count,fe->mfcc+input_index,&frames,&offset)<0)
                return -1;
            if (offset>0) fe->pending_offset=offset;
            fe->pending_frames+=frames;
        }
drain:
        if (before==count && fe->pending_frames==pending_before) return -2;
        if (drain_frames(fe,output,context)<0) return -1;
    }
    return 0;
}
int ss_frontend_end_utt(struct ss_frontend *fe,ss_cep_callback output,void *context)
{
    int32 frames=0;
    if (fe->failed || !output) return -1;
    const int input_index=(fe->output_index+fe->pending_frames)%fe->buffer_frames;
    if (fe->pending_frames>=fe->buffer_frames) return -2;
    if (fe_end_utt(fe->fe,fe->mfcc[input_index],&frames)<0) return -1;
    fe->pending_frames+=frames;
    return drain_frames(fe,output,context);
}
int ss_frontend_start_utt(struct ss_frontend *fe)
{
    fe->output_index=0;
    fe->pending_frames=0;
    fe->pending_offset=0;
    fe->failed=0;
    return fe_start_utt(fe->fe);
}
void ss_frontend_start_stream(struct ss_frontend *fe)
{
    fe->pending_offset=0;
    fe_start_stream(fe->fe);
}
int ss_frontend_in_speech(struct ss_frontend *fe) {return fe_get_vad_state(fe->fe);}
int ss_frontend_ceplen(struct ss_frontend *fe) {return fe_get_output_size(fe->fe);}
