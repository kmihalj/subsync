// Timing invariants for identical PCM through fresh PocketSphinx recognizers.
// Recognition is compared only within one preprocessing configuration: adding
// silence or reusing a recognizer can legitimately change its adaptation state.
#include "media/speechrec.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

extern "C" {
#include <libavutil/mathematics.h>
}

using namespace std;

enum class Noise { Default, Enabled, Disabled };

static void require(bool condition, const string &message)
{
    if (!condition)
        throw runtime_error(message);
}

static vector<int16_t> readPcm(const string &path)
{
    ifstream input(path, ios::binary);
    require(bool(input), "Missing upstream goforward.raw fixture: " + path);
    const vector<char> bytes((istreambuf_iterator<char>(input)),
            istreambuf_iterator<char>());
    require(!bytes.empty() && bytes.size() % sizeof(int16_t) == 0,
            "Invalid signed-16-bit PCM fixture");
    vector<int16_t> samples(bytes.size() / sizeof(int16_t));
    memcpy(samples.data(), bytes.data(), bytes.size());
    return samples;
}

static vector<Word> recognize(const string &model, const vector<int16_t> &pcm,
        Noise noise, size_t chunkSize, int64_t origin)
{
    // The stream time base intentionally differs from the 16 kHz samples,
    // as it does after a real 48 kHz stream has been resampled for recognition.
    const AVRational timeBase = {1, 48000}, sampleTimeBase = {1, 16000};
    AVStream stream = {};
    stream.time_base = timeBase;
    SpeechRecognition recognition;
    recognition.setParam("-hmm", model + "/en-us");
    recognition.setParam("-lm", model + "/en-us.lm.bin");
    recognition.setParam("-dict", model + "/cmudict-en-us.dict");
    recognition.setParam("-logfn", "/dev/null");
    if (noise != Noise::Default)
        recognition.setParam("-remove_noise", noise == Noise::Enabled ? "yes" : "no");
    recognition.setMinWordProb(0.0f);
    vector<Word> words;
    recognition.addWordsListener([&words](const Word &word) { words.push_back(word); });
    recognition.start(&stream);
    for (size_t position = 0; position < pcm.size(); position += chunkSize) {
        AVFrame frame = {};
        frame.data[0] = reinterpret_cast<uint8_t*>(
                const_cast<int16_t*>(pcm.data() + position));
        frame.nb_samples = static_cast<int>(min(chunkSize, pcm.size() - position));
        frame.sample_rate = 16000;
        frame.format = AV_SAMPLE_FMT_S16;
        av_channel_layout_from_mask(&frame.ch_layout, AV_CH_LAYOUT_MONO);
        frame.pts = origin + av_rescale_q(static_cast<int64_t>(position),
                sampleTimeBase, timeBase);
        recognition.feed(&frame);
    }
    recognition.flush();
    recognition.stop();
    require(words.size() >= 4, "Insufficient recognized words to check timing invariants");
    for (const auto &word : words)
        require(isfinite(word.time) && isfinite(word.score),
                "Non-finite recognized word timestamp or probability");
    return words;
}

static double compare(const vector<Word> &reference, const vector<Word> &candidate,
        double timeOffset, const string &label)
{
    require(reference.size() == candidate.size(), label + ": changed word count");
    double maxError = 0.0;
    for (size_t index = 0; index < reference.size(); ++index) {
        const string at = label + ": word " + to_string(index);
        require(reference[index].text == candidate[index].text,
                at + " changed text");
        // The exact same samples reach the decoder in the same VAD frames;
        // media timestamps and decoder packet boundaries cannot affect scores.
        require(reference[index].score == candidate[index].score,
                at + " changed probability");
        const double error = abs(static_cast<double>(candidate[index].time)
                - static_cast<double>(reference[index].time) - timeOffset);
        require(error <= 0.001, at + " changed timing by "
                + to_string(error * 1000.0) + " ms");
        maxError = max(maxError, error);
    }
    return maxError;
}

int main(int argc, char **argv)
{
    try {
        require(argc == 3, "Usage: speech-invariance-test MODEL_DIRECTORY GOFORWARD_RAW");
        const vector<int16_t> utterance = readPcm(argv[2]);
        vector<int16_t> pcm = utterance;
        pcm.resize(pcm.size() + 11696, 0);
        pcm.insert(pcm.end(), utterance.begin(), utterance.end());
        pcm.resize(pcm.size() + 6608, 0);
        // Neither silence boundary nor total PCM length is VAD-frame aligned.
        const int64_t origin = 1782000;       // 37.125 seconds at 48 kHz.
        const int64_t shift = 5922000;        // Exactly 123.375 seconds.
        const double shiftSeconds = static_cast<double>(shift) / 48000.0;
        cout << fixed << setprecision(6);
        for (const Noise noise : {Noise::Default, Noise::Disabled}) {
            const string label = noise == Noise::Default
                ? "default remove_noise=yes" : "explicit remove_noise=no";
            const auto reference = recognize(argv[1], pcm, noise, 997, origin);
            const auto shifted = recognize(argv[1], pcm, noise, 997, origin + shift);
            const double shiftError = compare(reference, shifted, shiftSeconds,
                    label + " / media PTS offset");
            double chunkError = 0.0;
            for (const size_t chunk : {size_t(320), size_t(4096)})
                chunkError = max(chunkError, compare(reference,
                        recognize(argv[1], pcm, noise, chunk, origin), 0.0,
                        label + " / chunk " + to_string(chunk)));
            if (noise == Noise::Default)
                compare(reference, recognize(argv[1], pcm, Noise::Enabled, 997, origin),
                        0.0, "default versus explicit remove_noise=yes");
            cout << "PASS " << label << ": " << reference.size()
                 << " identical words and probabilities; PTS shift "
                 << shiftSeconds << " s (maximum error " << shiftError * 1000.0
                 << " ms); chunks 997/320/4096 (maximum error "
                 << chunkError * 1000.0 << " ms)\n";
        }
    }
    catch (const exception &error) {
        cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
    return 0;
}
