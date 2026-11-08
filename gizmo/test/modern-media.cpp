// Integration regressions for the PS5 endpointer and FFmpeg channel-layout port.
#include "media/speechrec.h"
#include "media/resampler.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <cmath>
#include <stdexcept>
using namespace std;

static void check(bool value, const char *message) {
    if (!value) throw runtime_error(message);
}
static vector<int16_t> readRaw(const string &path) {
    ifstream input(path, ios::binary);
    check(bool(input), "missing upstream goforward.raw fixture");
    vector<char> bytes((istreambuf_iterator<char>(input)), istreambuf_iterator<char>());
    vector<int16_t> samples(bytes.size()/2);
    memcpy(samples.data(), bytes.data(), samples.size()*2);
    return samples;
}
static void feed(SpeechRecognition &rec, const vector<int16_t> &samples, int64_t offset) {
    // Awkward decoder chunk sizes exercise residual VAD-frame buffering.
    for (size_t pos=0; pos<samples.size(); pos+=997) {
        AVFrame frame = {};
        frame.data[0] = reinterpret_cast<uint8_t*>(const_cast<int16_t*>(samples.data()+pos));
        frame.nb_samples = min(size_t(997), samples.size()-pos);
        frame.sample_rate = 16000;
        frame.format = AV_SAMPLE_FMT_S16;
        frame.pts = offset + pos;
        rec.feed(&frame);
    }
}
static void configure(SpeechRecognition &rec, const string &model) {
    rec.setParam("-hmm", model+"/en-us");
    rec.setParam("-lm", model+"/en-us.lm.bin");
    rec.setParam("-dict", model+"/cmudict-en-us.dict");
    rec.setParam("-logfn", "/dev/null");
    // Existing SubSync speech assets can disable the legacy noise estimator.
    rec.setParam("-remove_noise", "no");
    rec.setMinWordProb(0.0);
}
struct Sink : AVOutput {
    vector<int16_t> samples;
    bool flushed=false;
    void start(const AVStream*) override {}
    void stop() override {}
    void discontinuity() override {}
    void flush() override { flushed=true; }
    void feed(const AVFrame *frame) override {
        const int16_t *data=reinterpret_cast<const int16_t*>(frame->data[0]);
        samples.insert(samples.end(),data,data+frame->nb_samples);
    }
};
int main(int argc,char **argv) {
    try {
        check(argc==3,"usage: modern-media-test MODEL_DIRECTORY GOFORWARD_RAW");
        const auto speech=readRaw(argv[2]);
        AVStream stream={};
        stream.time_base={1,16000};
        SpeechRecognition rec;
        configure(rec,argv[1]);
        vector<Word> words;
        rec.addWordsListener([&](const Word &word){words.push_back(word);});
        rec.start(&stream);
        feed(rec,vector<int16_t>(16000),160000);
        rec.flush();
        check(words.empty(),"silence produced words");
        rec.discontinuity();
        vector<int16_t> two=speech;
        two.resize(two.size()+16000,0);
        const double separation=two.size()/16000.0;
        two.insert(two.end(),speech.begin(),speech.end());
        two.resize(two.size()+16000,0);
        feed(rec,two,160000);
        rec.flush();
        vector<float> forwards;
        for(const auto &word:words) if(word.text=="forward") forwards.push_back(word.time);
        check(forwards.size()==2,"both speech utterances must be recognized");
        check(forwards[0]>=10 && forwards[0]<12,"first utterance lost media PTS offset");
        check(abs(forwards[1]-forwards[0]-separation)<0.12,
                "second utterance lost its per-utterance timestamp offset");
        const auto before=words.size();
        rec.flush();
        check(words.size()==before,"double flush duplicated words");
        rec.discontinuity();
        words.clear();
        feed(rec,two,1600000);
        rec.flush();
        check(!words.empty() && words.front().time>=100 && words.front().time<102,
                "seek/discontinuity retained old timestamp origin");
        rec.stop();
        rec.start(&stream);
        words.clear();
        vector<int16_t> partial=speech;
        partial.resize(min(partial.size(),size_t(16000*2.1)));
        feed(rec,partial,0);
        check(words.empty(),"truncated fixture unexpectedly ended before EOF");
        rec.flush();
        check(!words.empty(),"EOF did not drain pending speech");
        rec.stop();
        cout<<"PASS silence, utterance offsets, double flush, seek reset, EOF speech drain\n";

        const auto sink=make_shared<Sink>();
        Resampler resampler;
        resampler.connectOutput(sink,AudioFormat(AV_SAMPLE_FMT_S16,16000,AV_CH_LAYOUT_MONO));
        resampler.setChannelMap({{{AV_CH_FRONT_LEFT,AV_CH_FRONT_CENTER},0.5},
                                  {{AV_CH_FRONT_RIGHT,AV_CH_FRONT_CENTER},0.5}});
        stream.time_base={1,48000};
        resampler.start(&stream);
        vector<int16_t> stereo(4800*2);
        for(size_t i=0;i<4800;i++){stereo[2*i]=1000;stereo[2*i+1]=3000;}
        for(int n=0;n<3;n++) {
            AVFrame frame={};
            frame.data[0]=reinterpret_cast<uint8_t*>(stereo.data());
            frame.extended_data=frame.data;
            frame.linesize[0]=stereo.size()*2;
            frame.nb_samples=4800;
            frame.sample_rate=48000;
            frame.format=AV_SAMPLE_FMT_S16;
            frame.pts=4800*n;
            av_channel_layout_from_mask(&frame.ch_layout,AV_CH_LAYOUT_STEREO);
            resampler.feed(&frame);
        }
        resampler.flush();
        resampler.stop();
        check(sink->flushed,"resampler failed to flush downstream speech output");
        check(sink->samples.size()==4800,"resampler lost buffered samples at EOF");
        for(size_t i=100;i+100<sink->samples.size();i++)
            check(abs(sink->samples[i]-2000)<=1,"custom stereo-to-mono matrix is incorrect");
        cout<<"PASS custom channel matrix, 48k-to-16k conversion, resampler EOF drain\n";

        const auto customSink=make_shared<Sink>();
        Resampler customResampler;
        customResampler.connectOutput(customSink,
                AudioFormat(AV_SAMPLE_FMT_S16,16000,AV_CH_LAYOUT_MONO));
        customResampler.setChannelMap({{{AV_CH_FRONT_RIGHT,AV_CH_FRONT_CENTER},1.0},
                                       {{AV_CH_FRONT_LEFT,AV_CH_FRONT_CENTER},0.0}});
        customResampler.start(&stream);
        for(size_t i=0;i<4800;i++){stereo[2*i]=3000;stereo[2*i+1]=1000;}
        AVFrame customFrame={};
        customFrame.data[0]=reinterpret_cast<uint8_t*>(stereo.data());
        customFrame.extended_data=customFrame.data;
        customFrame.linesize[0]=stereo.size()*2;
        customFrame.nb_samples=4800;
        customFrame.sample_rate=48000;
        customFrame.format=AV_SAMPLE_FMT_S16;
        check(av_channel_layout_custom_init(&customFrame.ch_layout,2)==0,
                "cannot construct custom-order regression fixture");
        customFrame.ch_layout.u.map[0].id=AV_CHAN_FRONT_RIGHT;
        customFrame.ch_layout.u.map[1].id=AV_CHAN_FRONT_LEFT;
        check(AudioFormat(&customFrame).channelLayout==AV_CH_LAYOUT_STEREO,
                "custom layout metadata lost its speaker set");
        customResampler.feed(&customFrame);
        av_channel_layout_uninit(&customFrame.ch_layout);
        customResampler.flush();
        customResampler.stop();
        check(customSink->samples.size()==1600,"custom layout lost samples at EOF");
        for(size_t i=100;i+100<customSink->samples.size();i++)
            check(abs(customSink->samples[i]-3000)<=1,
                    "custom layout mixed LEFT instead of RIGHT");
        cout<<"PASS reversed custom channel order, named channel selection, EOF drain\n";
    } catch(const exception &e) { cerr<<"FAIL "<<e.what()<<'\n';return 1; }
}
