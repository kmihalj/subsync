#include "speechrec.h"
#include "text/utf8.h"
#include "general/exception.h"
#include <cstring>
#include <cstdint>
#include <cmath>
#include <limits>
#include <sstream>
#include <iomanip>

using namespace std;

SpeechRecognition::SpeechRecognition() :
    m_ps(NULL), m_config(NULL), m_frontend(NULL), m_decoderOpen(false),
    m_utteranceStarted(false), m_haveTimestamp(false), m_flushed(false),
    m_framePeriod(0.0), m_deltaTime(0.0), m_utteranceTime(0.0),
    m_timeBase(0.0), m_minProb(1.0f), m_minLen(0)
{
    m_config = ps_config_init(NULL);
    if (m_config == NULL)
        throw EXCEPTION("can't init Sphinx configuration")
            .module("SpeechRecognition", "ps_config_init");
    // Preserve SphinxBase's original preprocessing default. Asset parameters
    // passed later through setParam() can explicitly disable it.
    ps_config_set_bool(m_config, "remove_noise", TRUE);
    // Original CMN initialization supplied a mean without synthetic history.
    // Later .speech asset parameters can explicitly select another history.
    if (!ps_config_set_int(m_config,"cmninit_frames",0)) {
        ps_config_free(m_config);
        m_config=NULL;
        throw EXCEPTION("PocketSphinx initial-history option is unavailable")
            .module("SpeechRecognition","ps_config_set_int");
    }
}

SpeechRecognition::~SpeechRecognition()
{
    // Destructors must also release resources after a failed/cancelled start.
    ss_frontend_free(m_frontend);
    ps_free(m_ps);
    ps_config_free(m_config);
}

void SpeechRecognition::setParam(const string &key, const string &val)
{
    // Existing .speech assets use the command-line spelling ("-hmm", etc.).
    const string name = !key.empty() && key[0] == '-' ? key.substr(1) : key;
    const int type = ps_config_typeof(m_config, name.c_str());
    const anytype_t *result = NULL;
    if (type & ARG_INTEGER)
        result = ps_config_set_int(m_config, name.c_str(), stol(val));
    else if (type & ARG_FLOATING)
        result = ps_config_set_float(m_config, name.c_str(), stod(val));
    else if (type & ARG_STRING)
        result = ps_config_set_str(m_config, name.c_str(), val.c_str());
    else if (type & ARG_BOOLEAN)
        result = ps_config_set_bool(m_config, name.c_str(),
                !(val.empty() || val == "0" || val == "no" || val == "false"));
    if (result == NULL)
        throw EXCEPTION("parameter not supported")
            .module("SpeechRecognition", "setParameter")
            .add("parameter", key).add("value", val);
}

void SpeechRecognition::addWordsListener(WordsListener listener)
{
    m_wordsNotifier.addListener(listener);
}

bool SpeechRecognition::removeWordsListener(WordsListener listener)
{
    return m_wordsNotifier.removeListener(listener);
}

void SpeechRecognition::setMinWordProb(float minProb) { m_minProb = minProb; }
void SpeechRecognition::setMinWordLen(unsigned minLen) { m_minLen = minLen; }

void SpeechRecognition::createFrontend()
{
    ss_frontend_free(m_frontend);
    m_frontend = NULL;
    ps_config_t *configuration=ps_get_config(m_ps);
    // Match the original 1s_c_d_dd frontend buffer, while feature extraction
    // and search use the current decoder through its public CEP interface.
    m_frontend=ss_frontend_create_config(configuration,7);
    if (!m_frontend)
        throw EXCEPTION("can't initialize compatibility frontend")
            .module("SpeechRecognition","createFrontend");
    if (ss_frontend_ceplen(m_frontend)!=ps_config_int(configuration,"ceplen"))
        throw EXCEPTION("compatibility frontend feature dimensions differ")
            .module("SpeechRecognition","createFrontend");
}

void SpeechRecognition::start(const AVStream *stream)
{
    if (m_ps)
        stop();
    // Original cmd_ln_float32_r narrowed these configuration values before
    // logmath/acoustic/search initialization.  PS5's generic float accessor
    // returns doubles. Preserve that public option's original numeric value,
    // including explicit asset overrides; retain full precision for FLOAT64
    // beam options. The pinned origin table is in frontend/fe/origins.json.
    static const char *const originalFloat32[]={
        "pl_pip","lw","fwdflatlw","bestpathlw","ascale","wip","nwpen",
        "pip","uw","silprob","fillprob","tmatfloor","varfloor",
        "mixwfloor","logbase"
    };
    for (const char *name:originalFloat32) {
        const double value=ps_config_float(m_config,name);
        if (!isfinite(value) || abs(value)>numeric_limits<float>::max())
            throw EXCEPTION("invalid original floating-point parameter")
                .module("SpeechRecognition","numericCompatibility")
                .add("parameter",name);
        ps_config_set_float(m_config,name,static_cast<double>(static_cast<float>(value)));
    }
    m_ps = ps_init(m_config);
    if (m_ps == NULL)
        throw EXCEPTION("can't init Sphinx engine")
            .module("SpeechRecognition", "ps_init");
    const long frate = ps_config_int(m_config, "frate");
    if (frate <= 0)
        throw EXCEPTION("can't get frame rate value")
            .module("SpeechRecognition", "ps_config_int");
    m_framePeriod = 1.0 / static_cast<double>(frate);
    m_timeBase = av_q2d(stream->time_base);
    m_deltaTime = 0.0;
    m_utteranceTime = 0.0;
    m_haveTimestamp = false;
    m_utteranceStarted = false;
    createFrontend();
    if (ps_start_utt(m_ps)<0)
        throw EXCEPTION("can't start speech recognition")
            .module("SpeechRecognition","ps_start_utt");
    m_decoderOpen=true;
    m_flushed=false;
}

int SpeechRecognition::cepCallback(void *context,float **cep,int frames,int streamFrame)
{
    return static_cast<SpeechRecognition*>(context)->processCep(cep,frames,streamFrame);
}

int SpeechRecognition::processCep(float **cep,int frames,int streamFrame)
{
    if (streamFrame>0)
        m_utteranceTime=streamFrame*m_framePeriod;
    return ps_process_cep(m_ps,cep,frames,FALSE,FALSE);
}

void SpeechRecognition::endUtterance()
{
    if (!m_decoderOpen) return;
    if (ss_frontend_end_utt(m_frontend,cepCallback,this)<0)
        throw EXCEPTION("can't drain compatibility frontend")
            .module("SpeechRecognition","frontendEndUtterance");
    if (ps_end_utt(m_ps)<0)
        throw EXCEPTION("can't end utterance")
            .module("SpeechRecognition","ps_end_utt");
    m_decoderOpen=false;
    if (m_utteranceStarted) parseUtterance();
    m_utteranceStarted=false;
}

void SpeechRecognition::stop()
{
    if (m_ps) {
        flush();
        ps_free(m_ps);
        m_ps=NULL;
    }
    ss_frontend_free(m_frontend);
    m_frontend=NULL;
}

void SpeechRecognition::feed(const AVFrame *frame)
{
    if (!m_haveTimestamp) {
        m_deltaTime=frame->pts==AV_NOPTS_VALUE?0.0:m_timeBase*frame->pts;
        m_haveTimestamp=true;
    }
    const int16_t *data=reinterpret_cast<const int16_t*>(frame->data[0]);
    if (ss_frontend_process(m_frontend,data,frame->nb_samples,cepCallback,this)<0)
        throw EXCEPTION("compatibility frontend processing error")
            .module("SpeechRecognition","frontendProcess");
    const bool speech=ss_frontend_in_speech(m_frontend);
    if (speech && !m_utteranceStarted)
        m_utteranceStarted=true;
    if (!speech && m_utteranceStarted) {
        endUtterance();
        if (ss_frontend_start_utt(m_frontend)<0 || ps_start_utt(m_ps)<0)
            throw EXCEPTION("can't start utterance")
                .module("SpeechRecognition","startUtterance");
        m_decoderOpen=true;
    }
}

void SpeechRecognition::flush()
{
    if (!m_ps || m_flushed) return;
    endUtterance();
    m_flushed=true;
}

void SpeechRecognition::discontinuity()
{
    if (!m_ps) return;
    flush();
    m_deltaTime=0.0;
    m_utteranceTime=0.0;
    m_haveTimestamp=false;
    ss_frontend_start_stream(m_frontend);
    if (ss_frontend_start_utt(m_frontend)<0 || ps_start_utt(m_ps)<0)
        throw EXCEPTION("can't restart speech recognition")
            .module("SpeechRecognition","discontinuity");
    m_decoderOpen=true;
    m_flushed=false;
}

void SpeechRecognition::parseUtterance()
{
	for (ps_seg_t *it=ps_seg_iter(m_ps); it!=NULL; it=ps_seg_next(it))
	{
		const char *text = ps_seg_word(it);
		if (text && text[0] != '<' && text[0] != '[')
		{
			string word = text;
			if ((word.size() > 3) && (word.back() == ')'))
			{
				size_t pos = word.size() - 2;
				while (word[pos] >= '0' && word[pos] <= '9' && pos > 0)
					pos--;

				if (pos <= word.size()-3 && word[pos] == '(')
					word.resize(pos);
			}

			int begin, end;
			ps_seg_frames(it, &begin, &end);
			const double time = ((double)begin+(double)end) * m_framePeriod / 2.0;

			const int pprob = ps_seg_prob(it, NULL, NULL, NULL);
			const float prob = logmath_exp(ps_get_logmath(m_ps), pprob);

			if (Utf8::size(word) >= m_minLen && prob >= m_minProb)
				m_wordsNotifier.notify(Word(word, time + m_deltaTime + m_utteranceTime, 0.0f, prob));
		}
	}
}

