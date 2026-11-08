#ifndef SUBSYNC_SPEECH_SEGMENTER_H
#define SUBSYNC_SPEECH_SEGMENTER_H

#include <algorithm>
#include <cstdint>
#include <deque>
#include <functional>
#include <vector>

// Buffer original PCM around voice activity, independently of ASR. Sample
// indices describe the original stream and a sample is emitted at most once.
class SpeechSegmenter
{
public:
    typedef std::function<void(const int16_t*, size_t, uint64_t, bool, bool)> Output;

    SpeechSegmenter(size_t prespeechFrames, size_t startFrames, size_t postFrames,
            Output output) :
        m_prespeechFrames(std::max(prespeechFrames, startFrames)),
        m_startFrames(std::max(size_t(1), startFrames)),
        m_postFrames(std::max(size_t(1), postFrames)), m_output(output)
    { reset(); }

    void reset()
    {
        m_pending.clear();
        m_nextSample = 0;
        m_voiceFrames = m_silenceFrames = 0;
        m_active = false;
    }

    void push(const int16_t *pcm, size_t count, bool speech)
    {
        if (count == 0)
            return;
        const uint64_t first = m_nextSample;
        m_nextSample += count;
        if (m_active) {
            m_silenceFrames = speech ? 0 : m_silenceFrames + 1;
            const bool end = m_silenceFrames >= m_postFrames;
            m_output(pcm, count, first, false, end);
            if (end) {
                m_active = false;
                m_voiceFrames = m_silenceFrames = 0;
            }
            return;
        }

        m_pending.push_back({std::vector<int16_t>(pcm, pcm + count), first});
        if (m_pending.size() > m_prespeechFrames)
            m_pending.pop_front();
        m_voiceFrames = speech ? m_voiceFrames + 1 : 0;
        if (m_voiceFrames < m_startFrames)
            return;
        m_active = true;
        bool begin = true;
        for (const Frame &frame : m_pending) {
            m_output(frame.pcm.data(), frame.pcm.size(), frame.first, begin, false);
            begin = false;
        }
        m_pending.clear();
        m_voiceFrames = m_silenceFrames = 0;
    }

    void flush()
    {
        if (m_active)
            m_output(NULL, 0, m_nextSample, false, true);
        m_active = false;
        m_pending.clear();
        m_voiceFrames = m_silenceFrames = 0;
    }

private:
    struct Frame { std::vector<int16_t> pcm; uint64_t first; };
    size_t m_prespeechFrames, m_startFrames, m_postFrames;
    Output m_output;
    std::deque<Frame> m_pending;
    uint64_t m_nextSample;
    size_t m_voiceFrames, m_silenceFrames;
    bool m_active;
};
#endif
