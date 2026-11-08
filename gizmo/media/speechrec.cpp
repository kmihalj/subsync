#include "speechrec.h"
#include "text/utf8.h"
#include "general/exception.h"
#include <cstring>
#include <cstdint>

using namespace std;

SpeechRecognition::SpeechRecognition() :
    m_ps(NULL), m_config(NULL), m_endpointer(NULL),
    m_utteranceStarted(false), m_haveTimestamp(false), m_flushed(false),
    m_framePeriod(0.0), m_deltaTime(0.0), m_utteranceTime(0.0),
    m_timeBase(0.0), m_minProb(1.0f), m_minLen(0)
{
    m_config = ps_config_init(NULL);
    if (m_config == NULL)
        throw EXCEPTION("can't init Sphinx configuration")
            .module("SpeechRecognition", "ps_config_init");
}

SpeechRecognition::~SpeechRecognition()
{
    // Destructors must also release resources after a failed/cancelled start.
    ps_endpointer_free(m_endpointer);
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

void SpeechRecognition::resetEndpointer()
{
    ps_endpointer_free(m_endpointer);
    m_endpointer = ps_endpointer_init(0.0, 0.0, PS_VAD_LOOSE,
            static_cast<int>(ps_config_int(m_config, "samprate")), 0.0);
    if (m_endpointer == NULL)
        throw EXCEPTION("can't init speech endpointer")
            .module("SpeechRecognition", "ps_endpointer_init");
    m_samples.clear();
    m_flushed = false;
}

void SpeechRecognition::start(const AVStream *stream)
{
    if (m_ps)
        stop();
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
    resetEndpointer();
}

void SpeechRecognition::endUtterance()
{
    if (!m_utteranceStarted)
        return;
    if (ps_end_utt(m_ps) < 0)
        throw EXCEPTION("can't end utterance")
            .module("SpeechRecognition", "ps_end_utt");
    m_utteranceStarted = false;
    parseUtterance();
}

void SpeechRecognition::stop()
{
    if (m_ps) {
        flush();
        ps_free(m_ps);
        m_ps = NULL;
    }
    ps_endpointer_free(m_endpointer);
    m_endpointer = NULL;
    m_samples.clear();
}

void SpeechRecognition::processSpeech(const int16_t *samples, size_t count)
{
    if (samples == NULL || count == 0)
        return;
    if (!m_utteranceStarted) {
        if (ps_start_utt(m_ps) < 0)
            throw EXCEPTION("can't start utterance")
                .module("SpeechRecognition", "ps_start_utt");
        m_utteranceStarted = true;
        // PS5 segmentation frame indices restart for each utterance.
        m_utteranceTime = ps_endpointer_speech_start(m_endpointer);
    }
    if (ps_process_raw(m_ps, samples, count, FALSE, FALSE) < 0)
        throw EXCEPTION("speech recognition error")
            .module("SpeechRecognition", "ps_process_raw");
    if (!ps_endpointer_in_speech(m_endpointer))
        endUtterance();
}

void SpeechRecognition::feed(const AVFrame *frame)
{
    if (!m_haveTimestamp) {
        m_deltaTime = frame->pts == AV_NOPTS_VALUE ? 0.0 : m_timeBase * frame->pts;
        m_haveTimestamp = true;
    }
    const int16_t *data = reinterpret_cast<const int16_t*>(frame->data[0]);
    m_samples.insert(m_samples.end(), data, data + frame->nb_samples);
    const size_t frameSize = ps_endpointer_frame_size(m_endpointer);
    size_t consumed = 0;
    while (m_samples.size() - consumed >= frameSize) {
        const int16_t *speech = ps_endpointer_process(m_endpointer,
                m_samples.data() + consumed);
        processSpeech(speech, frameSize);
        consumed += frameSize;
    }
    m_samples.erase(m_samples.begin(), m_samples.begin() + consumed);
}

void SpeechRecognition::flush()
{
    if (m_endpointer == NULL || m_flushed)
        return;
    size_t count = 0;
    // Pass a valid pointer even for an empty final frame (the API may memcpy 0).
    const int16_t empty = 0;
    const int16_t *speech = ps_endpointer_end_stream(m_endpointer,
            m_samples.empty() ? &empty : m_samples.data(), m_samples.size(), &count);
    processSpeech(speech, count);
    endUtterance();
    m_samples.clear();
    m_flushed = true;
}

void SpeechRecognition::discontinuity()
{
    flush();
    m_deltaTime = 0.0;
    m_haveTimestamp = false;
    // The compatibility function returns -1 when noise removal is disabled
    // (as it is in existing CMUSphinx assets): there are no stats to reset.
    if (m_ps && ps_config_bool(m_config, "remove_noise") && ps_start_stream(m_ps) < 0)
        throw EXCEPTION("can't reset speech recognition engine")
            .module("SpeechRecognition", "ps_start_stream");
    if (m_ps)
        resetEndpointer();
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

