#include "stream.h"
#include <string>
#include <sstream>

extern "C"
{
#include <libavcodec/avcodec.h>
}

using namespace std;


static const char *sampleFormatToName(AVSampleFormat format)
{
	switch (format)
	{
		case AV_SAMPLE_FMT_NONE: return "NONE";
		case AV_SAMPLE_FMT_U8:   return "U8";
		case AV_SAMPLE_FMT_S16:  return "S16";
		case AV_SAMPLE_FMT_S32:  return "S32";
		case AV_SAMPLE_FMT_FLT:  return "FLT";
		case AV_SAMPLE_FMT_DBL:  return "DBL";
		case AV_SAMPLE_FMT_U8P:  return "U8P";
		case AV_SAMPLE_FMT_S16P: return "S16P";
		case AV_SAMPLE_FMT_S32P: return "S32P";
		case AV_SAMPLE_FMT_FLTP: return "FLTP";
		case AV_SAMPLE_FMT_DBLP: return "DBLP";
		case AV_SAMPLE_FMT_S64:  return "S64";
		case AV_SAMPLE_FMT_S64P: return "S64P";
		default: return NULL;
	}
}


static AVCodecContext *makeCodecContext(const AVStream *stream)
{
	if (stream->codecpar == NULL)
		return NULL;

	const AVCodec *codec = avcodec_find_decoder(stream->codecpar->codec_id);
	if (codec == NULL)
		return NULL;

	AVCodecContext *ctx = avcodec_alloc_context3(codec);
	if (ctx == NULL)
		return NULL;

	avcodec_parameters_to_context(ctx, stream->codecpar);
	avcodec_open2(ctx, codec, NULL);
	return ctx;
}


/*** StreamFormat ***/

StreamFormat::StreamFormat()
{}

StreamFormat::StreamFormat(unsigned no, const AVStream *stream) : no(no)
{
	if (stream == NULL)
		return;

	if (const AVCodec *codec = avcodec_find_decoder(stream->codecpar->codec_id))
	{
		this->codec = codec->name ? codec->name : "";
	}

	frameRate = 0.0;
	if (!(stream->avg_frame_rate.den == 0.0))
		frameRate = (double)stream->avg_frame_rate.num / stream->avg_frame_rate.den;

	AVDictionaryEntry* lang = av_dict_get(stream->metadata, "language", NULL, 0);
	if (lang && lang->value)
		this->lang = lang->value;

	AVDictionaryEntry *title = av_dict_get(stream->metadata, "title", NULL, 0);
	if (title && title->value)
		this->title = title->value;

	if (stream->codecpar)
	{
		AVCodecContext *ctx = NULL;

		switch (stream->codecpar->codec_type)
		{
			case AVMEDIA_TYPE_VIDEO:
				this->type = "video";
				break;

			case AVMEDIA_TYPE_AUDIO:
				this->type = "audio";
				ctx = makeCodecContext(stream);
				audio = AudioFormat(ctx);
				break;

			case AVMEDIA_TYPE_SUBTITLE:
				this->type = "subtitle";
				ctx = makeCodecContext(stream);

				if (ctx && ctx->codec_descriptor)
				{
					int props = ctx->codec_descriptor->props;
					bool txt = props & AV_CODEC_PROP_TEXT_SUB;
					bool bmp = props & AV_CODEC_PROP_BITMAP_SUB;

					if (txt && !bmp) this->type += "/text";
					if (bmp && !txt) this->type += "/bitmap";
				}
				break;

			default:
				this->type = "other";
		}

		avcodec_free_context(&ctx);
	}
}

string StreamFormat::toString() const
{
	stringstream ss;
	ss << "<StreamFormat no=" << no << ", type=\"" << type << "\"";
	if (!codec.empty())  ss << ", codec=\"" << codec << "\"";
	if (!lang.empty())   ss << ", lang=\"" << lang << "\"";
	if (!title.empty())  ss << ", title=\"" << title << "\"";
	if (frameRate > 0.0) ss << ", frameRate=" << frameRate;
	if (type == "audio") ss << ", audio=" << audio.toString();
	ss << ">";
	return ss.str();
}


/*** AudioFormat ***/

AudioFormat::AudioFormat(const AVCodecContext *ctx)
{
	sampleFormat  = AV_SAMPLE_FMT_NONE;
	sampleRate    = 0;
	channelsNo    = 0;
	channelLayout = 0;

	if (ctx)
	{
		sampleFormat  = ctx->sample_fmt;
		sampleRate    = ctx->sample_rate;
		channelsNo    = ctx->ch_layout.nb_channels;
		channelLayout = ctx->ch_layout.order == AV_CHANNEL_ORDER_NATIVE
			? ctx->ch_layout.u.mask : 0;

		if (channelLayout == 0)
		{
			AVChannelLayout layout = {};
			av_channel_layout_default(&layout, channelsNo);
			channelLayout = layout.order == AV_CHANNEL_ORDER_NATIVE ? layout.u.mask : 0;
			av_channel_layout_uninit(&layout);
		}
	}
}

AudioFormat::AudioFormat(const AVFrame *frame)
{
	sampleFormat  = AV_SAMPLE_FMT_NONE;
	sampleRate    = 0;
	channelsNo    = 0;
	channelLayout = 0;

	if (frame)
	{
		sampleFormat  = (AVSampleFormat) frame->format;
		sampleRate    = frame->sample_rate;
		channelsNo    = frame->ch_layout.nb_channels;
		channelLayout = frame->ch_layout.order == AV_CHANNEL_ORDER_NATIVE
			? frame->ch_layout.u.mask : 0;

		if (channelLayout == 0)
		{
			AVChannelLayout layout = {};
			av_channel_layout_default(&layout, channelsNo);
			channelLayout = layout.order == AV_CHANNEL_ORDER_NATIVE ? layout.u.mask : 0;
			av_channel_layout_uninit(&layout);
		}
	}
}

AudioFormat::AudioFormat(AVSampleFormat sampleFormat, unsigned sampleRate,
		uint64_t channelLayout) :
	sampleFormat(sampleFormat),
	sampleRate(sampleRate),
	channelsNo(0),
	channelLayout(channelLayout)
{
	for (unsigned i = 0; i < 64; ++i)
	{
		const uint64_t id = 1ull << i;
		if (id & channelLayout)
			channelsNo++;
	}
}

unsigned AudioFormat::getSampleSize() const
{
	return av_get_bytes_per_sample(sampleFormat);
}

string AudioFormat::getLayoutString() const
{
	stringstream ss;
	for (int i = 0; i <= 63; i++)
	{
		const uint64_t id = 1ull << i;
		if (id & channelLayout)
		{
			if (ss.tellp()) ss << ',';

			if (const char *name = getChannelName(id))
				ss << name;
			else
				ss << id;
		}
	}

	if (ss.tellp() == 0)
		return string("EMPTY");

	return ss.str();
}

string AudioFormat::toString() const
{
	stringstream ss;
	ss << "<AudioFormat"
		<< " sampleFormat=\""   << sampleFormatToName(sampleFormat) << "\""
		<< ", sampleRate="      << sampleRate
		<< ", channelsNo="      << channelsNo
		<< ", channelLayout="   << getLayoutString() << ">";
	return ss.str();
}

const char *AudioFormat::getChannelName(uint64_t id)
{
	if (id == 0 || (id & (id - 1)))
		return NULL;
	static thread_local char name[64];
	const AVChannel channel = static_cast<AVChannel>(__builtin_ctzll(id));
	return av_channel_name(name, sizeof(name), channel) >= 0 ? name : NULL;
}

const char *AudioFormat::getChannelDescription(uint64_t id)
{
	if (id == 0 || (id & (id - 1)))
		return NULL;
	static thread_local char description[128];
	const AVChannel channel = static_cast<AVChannel>(__builtin_ctzll(id));
	return av_channel_description(description, sizeof(description), channel) >= 0
		? description : NULL;
}

uint64_t AudioFormat::getChannelIdByName(const char *name)
{
	const AVChannel channel = av_channel_from_string(name);
	return channel >= 0 && channel < 64 ? 1ull << channel : 0;
}
