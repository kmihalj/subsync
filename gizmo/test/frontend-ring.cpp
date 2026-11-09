// Independent legacy acmod ring reference, exercised against the native FE.
// Reference scheduling follows CMU PocketSphinx acmod.c (last-pre-1.0),
// acmod_process_raw/acmod_process_mfcbuf/acmod_start_utt/acmod_end_utt.
// The old DSP is loaded only by this test; recognition and configuration use
// public PS5 APIs. No private data or old library is part of a shipping app.
#include "frontend/native_frontend.h"
#include <pocketsphinx.h>
#include <dlfcn.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int capacity = 7;
void check(bool ok, const std::string &message) { if (!ok) throw std::runtime_error(message); }
template<class Fn> Fn load(void *handle, const char *name) {
    dlerror(); void *address = dlsym(handle, name); const char *error = dlerror();
    check(address && !error, std::string("Missing old public DSP symbol: ") + name);
    return reinterpret_cast<Fn>(address);
}
// Public legacy arg_t layout, kept separate from current PS5's definitions.
struct OldArg { const char *name; int32_t type; const char *defaultValue; const char *description; };
struct OldFunctions {
    const OldArg *(*arguments)();
    void *(*parse)(void *, const OldArg *, int32_t, char **, int32_t);
    int (*freeConfig)(void *);
    void *(*init)(void *);
    int (*destroy)(void *);
    int (*size)(void *);
    uint8_t (*vad)(void *);
    int (*process)(void *, const int16_t **, size_t *, float **, int32_t *, int32_t *);
    int (*convert)(void *, float **, float **, int32_t);
    int (*end)(void *, float *, int32_t *);
    int (*start)(void *);
    void (*stream)(void *);
    explicit OldFunctions(void *handle) {
        arguments = load<decltype(arguments)>(handle,"fe_get_args");
        parse = load<decltype(parse)>(handle,"cmd_ln_parse_r");
        freeConfig = load<decltype(freeConfig)>(handle,"cmd_ln_free_r");
        init = load<decltype(init)>(handle,"fe_init_auto_r");
        destroy = load<decltype(destroy)>(handle,"fe_free");
        size = load<decltype(size)>(handle,"fe_get_output_size");
        vad = load<decltype(vad)>(handle,"fe_get_vad_state");
        process = load<decltype(process)>(handle,"fe_process_frames");
        convert = load<decltype(convert)>(handle,"fe_mfcc_to_float");
        end = load<decltype(end)>(handle,"fe_end_utt");
        start = load<decltype(start)>(handle,"fe_start_utt");
        stream = load<decltype(stream)>(handle,"fe_start_stream");
        load<void (*)(FILE *)>(handle,"err_set_logfp")(nullptr);
    }
};
std::vector<std::string> oldArguments(const OldFunctions &api, ps_config_t *config) {
    std::vector<std::string> result{"frontend-ring-reference"};
    for (const OldArg *arg = api.arguments(); arg->name; ++arg) {
        const std::string key = arg->name[0]=='-' ? arg->name+1 : arg->name;
        const ps_type_t type = ps_config_typeof(config,key.c_str());
        if (!type) continue; // Keep original defaults for removed VAD arguments.
        std::string value;
        if (type & ARG_BOOLEAN) value=ps_config_bool(config,key.c_str())?"yes":"no";
        else if (type & ARG_INTEGER) {
            long number=ps_config_int(config,key.c_str());
            if (key=="nfft" && number==0) {
                const double samples=ps_config_int(config,"samprate")*ps_config_float(config,"wlen");
                number=1; while (number<samples) number*=2;
            }
            value=std::to_string(number);
        }
        else if (type & ARG_FLOATING) {
            std::ostringstream out; out<<std::setprecision(17)<<ps_config_float(config,key.c_str()); value=out.str();
        }
        else if (type & ARG_STRING) {
            const char *text=ps_config_str(config,key.c_str()); if (!text) continue; value=text;
        }
        else continue;
        result.push_back(arg->name); result.push_back(value);
    }
    return result;
}

struct Batch { int frames, offset, vad; std::vector<uint32_t> bits; };
struct Capture {
    int ceplen;
    std::vector<Batch> batches;
    bool invalid=false;
    uint64_t frames=0, callbacks=0, hash=14695981039346656037ULL;
    void integer(uint32_t value) {
        for (int byte=0;byte<4;++byte) { hash^=(value>>(byte*8))&255; hash*=1099511628211ULL; }
    }
    void append(float **values,int count,int offset,int vad) {
        if (count<0 || count>capacity || (count && !values)) {invalid=true;return;}
        Batch batch{count,offset,vad,{}};
        integer(count);integer(offset);integer(vad);
        for (int row=0;row<count;++row) {
            if (!values[row]) {invalid=true;return;}
            for (int col=0;col<ceplen;++col) {
                const float value=values[row][col]; uint32_t bits;
                if (!std::isfinite(value)) invalid=true;
                std::memcpy(&bits,&value,sizeof(bits));batch.bits.push_back(bits);integer(bits);
            }
        }
        frames+=count;++callbacks;batches.push_back(std::move(batch));
    }
};

// This object uses the unmodified old FE through its public interface. Its
// cursor logic is independently derived from the original acmod ring, not
// from native_frontend.c. The frozen old library has float32 mfcc_t.
class Reference {
    const OldFunctions &api; void *fe=nullptr;
    int out=0, occupied=0, startOffset=0, columns=0;
    std::vector<float> storage, converted;
    std::vector<float *> rows, outputRows;
    void read(Capture &capture,int count) {
        if (!count) return;
        check(api.convert(fe,rows.data()+out,outputRows.data(),count)>=0,"Old MFCC conversion failed");
        capture.append(outputRows.data(),count,startOffset,vad());startOffset=0;
        occupied-=count;out=(out+count)%capacity;
    }
    void dispatch(Capture &capture) {
        const int count=occupied;
        if (out+count>capacity) { const int first=capacity-out;read(capture,first);read(capture,count-first); }
        else read(capture,count);
    }
public:
    Reference(const OldFunctions &functions,ps_config_t *config):api(functions) {
        auto args=oldArguments(api,config);std::vector<char *> argv;
        for (auto &arg:args) argv.push_back(&arg[0]);
        void *parsed=api.parse(nullptr,api.arguments(),static_cast<int32_t>(argv.size()),argv.data(),1);
        check(parsed,"Old FE public argument parse failed");fe=api.init(parsed);api.freeConfig(parsed);
        check(fe,"Old FE initialization failed");columns=api.size(fe);
        check(columns>0 && columns<=256,"Old FE coefficient count invalid");
        // Old FE's prespeech fast path relies on the contiguous allocation
        // guaranteed by ckd_calloc_2d, not merely an array of separate rows.
        storage.assign(capacity*columns,0);converted=storage;
        for (int index=0;index<capacity;++index) {
            rows.push_back(storage.data()+index*columns);
            outputRows.push_back(converted.data()+index*columns);
        }
    }
    ~Reference(){if(fe)api.destroy(fe);}
    int size()const{return columns;}
    int vad()const{return api.vad(fe);}
    void stream(){startOffset=0;api.stream(fe);}
    int start(){out=occupied=startOffset=0;return api.start(fe);}
    int process(const int16_t *samples,size_t remaining,Capture &capture) {
        while (remaining) {
            const size_t before=remaining;const int wasOccupied=occupied;
            int room=capacity-occupied,write=(out+occupied)%capacity;
            bool exhausted=false;
            // acmod_process_raw: write through the physical ring boundary
            // before exposing either contiguous read batch to the consumer.
            while (write+room>capacity) {
                int32_t count=capacity-write,offset=0;
                if(api.process(fe,&samples,&remaining,rows.data()+write,&count,&offset)<0)return -1;
                if(offset>0)startOffset=offset;
                occupied+=count;room-=count;write=(write+count)%capacity;
                if(!count){exhausted=true;break;}
            }
            if(!exhausted) {
                int32_t count=room,offset=0;
                if(api.process(fe,&samples,&remaining,rows.data()+write,&count,&offset)<0)return -1;
                if(offset>0)startOffset=offset;
                occupied+=count;
            }
            if(before==remaining && wasOccupied==occupied)return -2;
            // acmod_process_mfcbuf: split read batches at outidx wrap.
            dispatch(capture);
        }
        return 0;
    }
    int end(Capture &capture) {
        if(occupied>=capacity)return -2;
        int32_t count=0;const int write=(out+occupied)%capacity;
        if(api.end(fe,rows[write],&count)<0)return -1;
        occupied+=count;dispatch(capture);return 0;
    }
};

struct NativeCapture { ss_frontend *fe; Capture *capture; };
int nativeOutput(void *context,float **values,int count,int offset) {
    auto &record=*static_cast<NativeCapture *>(context);
    record.capture->append(values,count,offset,ss_frontend_in_speech(record.fe));
    return record.capture->invalid?-1:0;
}
void equal(Capture &old,Capture &native,size_t step) {
    const std::string where=" at input step "+std::to_string(step);
    check(!old.invalid && !native.invalid,"Nonfinite/capacity-invalid callback"+where);
    check(old.batches.size()==native.batches.size(),"MFCC batch count differs"+where);
    for(size_t index=0;index<old.batches.size();++index) {
        const Batch &a=old.batches[index],&b=native.batches[index];
        check(a.frames==b.frames && a.offset==b.offset && a.vad==b.vad,
              "Frame counts/offset/VAD differ"+where+" callback "+std::to_string(index));
        check(a.bits==b.bits,"MFCC float bits differ"+where+" callback "+std::to_string(index));
    }
    check(old.hash==native.hash,"MFCC event hash differs"+where);
    old.batches.clear();native.batches.clear();
}
std::vector<int16_t> pcmFile(const char *path) {
    std::ifstream stream(path,std::ios::binary);check(stream.good(),"Cannot open PCM file");
    std::vector<char> bytes((std::istreambuf_iterator<char>(stream)),{});
    check(!bytes.empty() && bytes.size()%2==0,"Expected signed16 little-endian mono PCM");
    std::vector<int16_t> result;result.reserve(bytes.size()/2);
    for(size_t i=0;i<bytes.size();i+=2)result.push_back(static_cast<int16_t>(
        static_cast<unsigned char>(bytes[i])|(static_cast<unsigned char>(bytes[i+1])<<8)));
    return result;
}
std::vector<size_t> profileFile(const char *path) {
    std::ifstream stream(path);check(stream.good(),"Cannot open recorded chunk profile");
    std::vector<size_t> result;size_t count;
    while(stream>>count){check(count>0 && count<=1048576,"Invalid recorded chunk size");result.push_back(count);}
    check(stream.eof() && !result.empty(),"Invalid recorded chunk profile");return result;
}

void run(const OldFunctions &api,ps_config_t *config,const std::vector<int16_t> &input,
         const std::vector<size_t> &profile,const std::string &name,bool longMode,bool noise) {
    Reference reference(api,config);ss_frontend *raw=ss_frontend_create_config(config,capacity);
    check(raw,"Native frontend creation failed");
    std::unique_ptr<ss_frontend,void(*)(ss_frontend*)> native(raw,ss_frontend_free);
    check(reference.size()==ss_frontend_ceplen(raw),"Coefficient count differs");
    Capture old{reference.size(),{},false,0,0,14695981039346656037ULL};
    Capture current{reference.size(),{},false,0,0,14695981039346656037ULL};
    NativeCapture callback{raw,&current};size_t step=0;
    uint64_t vadHash=14695981039346656037ULL;
    auto state=[&](){check(reference.vad()==ss_frontend_in_speech(raw),"Per-step VAD differs");vadHash^=reference.vad();vadHash*=1099511628211ULL;};
    auto start=[&](bool stream){
        if(stream){reference.stream();ss_frontend_start_stream(raw);state();}
        check(reference.start()==ss_frontend_start_utt(raw),"Start status differs");state();
    };
    auto feed=[&](const std::vector<int16_t>&data){
        size_t position=0,index=0;
        while(position<data.size()) {
            check(index<profile.size() || profile.size()==1,"Recorded chunk profile ended before PCM");
            const size_t count=std::min(profile[profile.size()==1?0:index],data.size()-position);
            const int a=reference.process(data.data()+position,count,old);
            const int b=ss_frontend_process(raw,data.data()+position,count,nativeOutput,&callback);
            check(a==b && a>=0,"Process status differs/fails");equal(old,current,step++);state();
            position+=count;++index;
        }
        if(longMode && profile.size()>1)check(index==profile.size(),"Recorded chunk profile exceeds PCM");
    };
    auto end=[&](){const int a=reference.end(old),b=ss_frontend_end_utt(raw,nativeOutput,&callback);
        check(a==b && a>=0,"EOF status differs/fails");equal(old,current,step++);state();};
    if(longMode){start(true);feed(input);end();}
    else {
        std::vector<int16_t> joined(5333,0);joined.insert(joined.end(),input.begin(),input.end());
        joined.insert(joined.end(),20317,0);joined.insert(joined.end(),input.begin(),input.end());joined.insert(joined.end(),1091,0);
        start(true);feed(joined);end();
        std::vector<int16_t> partial(input.begin(),input.begin()+std::min<size_t>(997,input.size()));partial.insert(partial.end(),57,0);
        start(false);feed(partial);end();
        std::vector<int16_t> restarted(3200,0);restarted.insert(restarted.end(),input.begin(),input.end());restarted.insert(restarted.end(),137,0);
        start(true);feed(restarted);end();
    }
    check(old.frames && old.frames==current.frames && old.callbacks==current.callbacks,"No/mismatched final frames");
    std::cout<<"{\"mode\":\""<<(longMode?"long":"short")<<"\",\"profile\":\""<<name
        <<"\",\"remove_noise\":"<<(noise?"true":"false")<<",\"frames\":"<<current.frames
        <<",\"callbacks\":"<<current.callbacks<<",\"steps\":"<<step<<",\"mfcc_event_fnv1a64\":\""
        <<std::hex<<std::setw(16)<<std::setfill('0')<<current.hash<<"\",\"vad_fnv1a64\":\""
        <<std::setw(16)<<vadHash<<std::dec<<"\",\"exact_equal\":true}\n"<<std::flush;
}
} // namespace

int main(int argc,char **argv) {
    if(argc<6){std::cerr<<"Usage: frontend-ring OLD_SPHINXBASE_DYLIB HMM LM DICT RAW [--long] [--profile COUNTS]\n";return 2;}
    try {
        bool longMode=false;const char *profilePath=nullptr;
        for(int i=6;i<argc;++i){const std::string arg=argv[i];if(arg=="--long")longMode=true;
            else if(arg=="--profile" && i+1<argc)profilePath=argv[++i];else throw std::runtime_error("Unknown option");}
        void *handle=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);const char *error=dlerror();
        check(handle,std::string("Cannot load test-only old DSP: ")+(error?error:"unknown"));
        std::unique_ptr<void,int(*)(void*)> library(handle,dlclose);OldFunctions old(handle);
        const auto input=pcmFile(argv[5]);
        ps_config_t *config=ps_config_init(nullptr);check(config,"Cannot create PS5 configuration");
        std::unique_ptr<ps_config_t,int(*)(ps_config_t*)> configOwner(config,ps_config_free);
        ps_config_set_str(config,"hmm",argv[2]);ps_config_set_str(config,"lm",argv[3]);ps_config_set_str(config,"dict",argv[4]);
        ps_config_set_int(config,"samprate",16000);ps_config_set_int(config,"ds",2);ps_config_set_int(config,"maxhmmpf",500);
        ps_config_set_str(config,"logfn","/dev/null");ps_decoder_t *ps=ps_init(config);check(ps,"Actual model initialization failed");
        std::unique_ptr<ps_decoder_t,int(*)(ps_decoder_t*)> decoder(ps,ps_free);ps_config_t *model=ps_get_config(ps);
        std::cout<<"{\"geometry\":{\"alpha\":"<<std::setprecision(17)<<ps_config_float(model,"alpha")
            <<",\"nfilt\":"<<ps_config_int(model,"nfilt")<<",\"nfft_config\":"<<ps_config_int(model,"nfft")
            <<",\"wlen\":"<<ps_config_float(model,"wlen")<<",\"lowerf\":"<<ps_config_float(model,"lowerf")
            <<",\"upperf\":"<<ps_config_float(model,"upperf")<<",\"lifter\":"<<ps_config_int(model,"lifter")
            <<",\"ncep\":"<<ps_config_int(model,"ncep")<<"}}\n"<<std::flush;
        for(bool noise:{true,false}) {
            ps_config_set_bool(model,"remove_noise",noise);
            if(profilePath)run(old,model,input,profileFile(profilePath),"recorded",longMode,noise);
            else if(longMode)run(old,model,input,{341},"341",true,noise);
            else for(size_t chunk:{size_t(1),size_t(160),size_t(997),size_t(4096),size_t(32768)})
                run(old,model,input,{chunk},std::to_string(chunk),false,noise);
        }
        return 0;
    }catch(const std::exception &error){std::cerr<<"frontend-ring: "<<error.what()<<'\n';return 1;}
}
