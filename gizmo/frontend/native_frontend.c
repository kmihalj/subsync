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
    int pending_frames;
    int pending_offset;
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
    if (strcmp(warp,"inverse_linear") && strcmp(warp,"affine") && strcmp(warp,"piecewise_linear")) return 0;
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
int ss_frontend_process(struct ss_frontend *fe,const int16_t *pcm,size_t count,
        ss_cep_callback output,void *context)
{
    while (count) {
        int32 frames=fe->buffer_frames-fe->pending_frames,offset=0;
        const size_t before=count;
        if (fe_process_frames(fe->fe,&pcm,&count,fe->mfcc+fe->pending_frames,&frames,&offset)<0)
            return -1;
        if (offset>0) fe->pending_offset=offset;
        fe->pending_frames+=frames;
        /* Normalization sees fixed feature batches, independent of how the
         * media decoder happens to divide PCM into packets. */
        if (fe->pending_frames==fe->buffer_frames) {
            fe_mfcc_to_float(fe->fe,fe->mfcc,fe->floats,fe->pending_frames);
            if (output(context,fe->floats,fe->pending_frames,fe->pending_offset)<0) return -1;
            fe->pending_frames=0;
            fe->pending_offset=0;
        }
        if (before==count && frames==0) return -2;
    }
    return 0;
}
int ss_frontend_end_utt(struct ss_frontend *fe,ss_cep_callback output,void *context)
{
    int32 frames=0;
    if (fe_end_utt(fe->fe,fe->mfcc[fe->pending_frames],&frames)<0) return -1;
    fe->pending_frames+=frames;
    if (fe->pending_frames) {
        fe_mfcc_to_float(fe->fe,fe->mfcc,fe->floats,fe->pending_frames);
        if (output(context,fe->floats,fe->pending_frames,fe->pending_offset)<0) return -1;
        fe->pending_frames=0;
        fe->pending_offset=0;
    }
    return 0;
}
int ss_frontend_start_utt(struct ss_frontend *fe)
{
    fe->pending_frames=0;
    fe->pending_offset=0;
    return fe_start_utt(fe->fe);
}
void ss_frontend_start_stream(struct ss_frontend *fe) {fe_start_stream(fe->fe);}
int ss_frontend_in_speech(struct ss_frontend *fe) {return fe_get_vad_state(fe->fe);}
int ss_frontend_ceplen(struct ss_frontend *fe) {return fe_get_output_size(fe->fe);}
int ss_frontend_frame_shift(struct ss_frontend *fe)
{
    int shift=0;
    fe_get_input_size(fe->fe,&shift,NULL);
    return shift;
}
