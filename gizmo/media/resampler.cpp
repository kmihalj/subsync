#include "resampler.h"
#include "avout.h"
#include "general/exception.h"

using namespace std;


Resampler::Resampler() :
	m_output(NULL),
	m_swr(NULL),
	m_outFrame(NULL),
	m_bufferSize(0),
	m_timeBase(0.0)
{
	m_swr = swr_alloc();
}

Resampler::~Resampler()
{
	if (m_swr)
		swr_free(&m_swr);

	if (m_outFrame)
		av_frame_free(&m_outFrame);

	m_bufferSize = 0;
}

void Resampler::connectOutput(shared_ptr<AVOutput> output,
		const AudioFormat &format, int bufferSize)
{
	if (m_outFrame)
		av_frame_free(&m_outFrame);

	m_outFrame = av_frame_alloc();
	m_outFrame->format = format.sampleFormat;
	av_channel_layout_from_mask(&m_outFrame->ch_layout, format.channelLayout);
	m_outFrame->sample_rate = format.sampleRate;
	m_outFrame->nb_samples = bufferSize;

	m_bufferSize = bufferSize;
	int res = av_frame_get_buffer(m_outFrame, 0);
	if (res < 0)
		throw EXCEPTION_FFMPEG("can't allocate output audio frame", res)
			.module("Resampler", "av_frame_get_buffer")
			.add("format", format.toString());

	m_output = output;
}

void Resampler::connectFormatChangeCallback(Resampler::FormatChangeCallback cb)
{
	m_formatChangeCb = cb;
}

void Resampler::setChannelMap(const ChannelsMap &channelsMap)
{
	m_channelsMap = channelsMap;
}

void Resampler::start(const AVStream *stream)
{
	m_timeBase = av_q2d(stream->time_base);

	if (m_output)
		m_output->start(stream);
}

void Resampler::stop()
{
	if (m_output)
		m_output->stop();

	swr_close(m_swr);
}

static vector<double> makeMixMap(const AVChannelLayout &output, const AVChannelLayout &input,
		Resampler::ChannelsMap channelsMap)
{
	vector<double> mixMap;
	mixMap.resize(input.nb_channels * output.nb_channels);

	for (const auto &ch : channelsMap)
	{
		const uint64_t inMask = get<0>(ch.first), outMask = get<1>(ch.first);
		if (!inMask || (inMask & (inMask - 1)) || !outMask || (outMask & (outMask - 1)))
			continue;
		int i = av_channel_layout_index_from_channel(&input,
				static_cast<AVChannel>(__builtin_ctzll(inMask)));
		int o = av_channel_layout_index_from_channel(&output,
				static_cast<AVChannel>(__builtin_ctzll(outMask)));

		if (i >= 0 && o >= 0)
			mixMap[o * input.nb_channels + i] = ch.second;
	}

	return mixMap;
}

void Resampler::initSwrContext(const AVFrame *outFrame, const AVFrame *inFrame)
{
	const AudioFormat out(outFrame), in(inFrame);
	if (swr_is_initialized(m_swr))
		swr_close(m_swr);

	// AudioFormat's legacy bitmask describes a set of speakers, not their
	// sample order. Preserve FFmpeg's actual CUSTOM/AMBISONIC layout here.
	int configured = swr_alloc_set_opts2(&m_swr,
			&outFrame->ch_layout, out.sampleFormat, out.sampleRate,
			&inFrame->ch_layout, in.sampleFormat, in.sampleRate, 0, NULL);

	if (configured < 0 || m_swr == NULL)
		throw EXCEPTION("can't initialize resampler context")
			.module("Resampler", "swr_alloc_set_opts2")
			.add("input", in.toString())
			.add("output", out.toString());

	if (!m_channelsMap.empty())
	{
		vector<double> mixMap = makeMixMap(outFrame->ch_layout, inFrame->ch_layout, m_channelsMap);
		int res = swr_set_matrix(m_swr, mixMap.data(), in.channelsNo);
		if (res < 0)
			throw EXCEPTION_FFMPEG("can't initialize audio mixer", res)
				.module("Resampler", "swr_set_matrix")
				.add("input", in.toString())
				.add("output", out.toString());
	}

	int res = swr_init(m_swr);
	if (res < 0)
		throw EXCEPTION_FFMPEG("can't initialize audio resampler", res)
			.module("Resampler", "swr_init")
			.add("input", in.toString())
			.add("output", out.toString());
}

void Resampler::feed(const AVFrame *frame)
{
	m_outFrame->nb_samples = m_bufferSize;
	m_outFrame->pts = frame->pts;

	if (!swr_is_initialized(m_swr))
	{
		if (m_formatChangeCb)
			m_formatChangeCb(AudioFormat(frame), AudioFormat(m_outFrame));

		initSwrContext(m_outFrame, frame);
	}

	int res = swr_convert_frame(m_swr, m_outFrame, frame);
	if (res < 0)
	{
		if (res == AVERROR_INPUT_CHANGED)
		{
			if (m_formatChangeCb)
				m_formatChangeCb(AudioFormat(frame), AudioFormat(m_outFrame));

			swr_close(m_swr);
			initSwrContext(m_outFrame, frame);
			res = swr_convert_frame(m_swr, m_outFrame, frame);
		}

		if (res < 0)
		{
			throw EXCEPTION_FFMPEG("error during audio conversion", res)
				.module("Resampler", "swr_convert")
				.add("input", AudioFormat(frame).toString())
				.add("output", AudioFormat(m_outFrame).toString())
				.add("pts", frame->pts)
				.time(m_timeBase * frame->pts);
		}
	}

	if (m_output)
		m_output->feed(m_outFrame);
}

void Resampler::flush()
{
	if (swr_is_initialized(m_swr))
	{
		while (true)
		{
			m_outFrame->nb_samples = m_bufferSize;
			int res = swr_convert_frame(m_swr, m_outFrame, NULL);

			if (res < 0)
			{
				throw EXCEPTION_FFMPEG("error during audio conversion", res)
					.module("Resampler", "swr_convert")
					.add("output", AudioFormat(m_outFrame).toString())
					.add("pts", m_outFrame->pts)
					.time(m_timeBase * m_outFrame->pts);
			}

			if (m_outFrame->nb_samples <= 0)
				break;

			if (m_output)
				m_output->feed(m_outFrame);
		}
	}
	if (m_output)
		m_output->flush();
}

void Resampler::discontinuity()
{
	// Samples buffered before a seek must never leak into the next region.
	swr_close(m_swr);
	if (m_output)
		m_output->discontinuity();
}

