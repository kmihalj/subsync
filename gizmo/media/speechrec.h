#ifndef __SPHINX_H__
#define __SPHINX_H__

#include "avout.h"
#include "text/words.h"
#include <pocketsphinx.h>
#include "frontend/native_frontend.h"
#include <string>
#include <vector>


class SpeechRecognition : public AVOutput
{
	public:
		SpeechRecognition();
		virtual ~SpeechRecognition();

		SpeechRecognition(const SpeechRecognition&) = delete;
		SpeechRecognition(SpeechRecognition&&) = delete;
		SpeechRecognition& operator= (const SpeechRecognition&) = delete;
		SpeechRecognition& operator= (SpeechRecognition&&) = delete;

		virtual void start(const AVStream *stream);
		virtual void stop();

		void setParam(const std::string &key, const std::string &val);

		void addWordsListener(WordsListener listener);
		bool removeWordsListener(WordsListener listener);

		void setMinWordProb(float minProb);
		void setMinWordLen(unsigned minLen);

		virtual void feed(const AVFrame *frame);
		virtual void flush();
		virtual void discontinuity();

	private:
		void parseUtterance();
		void createFrontend();
		int processCep(float **cep, int frames, int streamFrame);
		static int cepCallback(void *context, float **cep, int frames, int streamFrame);
		void endUtterance();

	private:
		ps_decoder_t *m_ps;
		ps_config_t *m_config;
		ss_frontend *m_frontend;
		bool m_decoderOpen;

		bool m_utteranceStarted;
		bool m_haveTimestamp;
		bool m_flushed;

		double m_framePeriod;
		double m_deltaTime;
		double m_utteranceTime;
		double m_timeBase;

		WordsNotifier m_wordsNotifier;
		float m_minProb;
		unsigned m_minLen;
};

#endif
