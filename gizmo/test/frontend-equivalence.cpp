// Standalone macOS diagnostic: native frontend versus the frozen legacy-DSP
// wrapper. The decoder/model configuration comes exclusively from public PS5
// APIs; the legacy library contributes frontend features, never recognition.
#include "frontend/native_frontend.h"
#include <pocketsphinx.h>
#include <dlfcn.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr int kCapacity = 7;

void require(bool condition, const std::string &message)
{
    if (!condition) throw std::runtime_error(message);
}

template<typename Function> Function symbol(void *library, const char *name)
{
    dlerror();
    void *address = dlsym(library, name);
    const char *error = dlerror();
    require(error == nullptr && address != nullptr,
            std::string("Missing legacy diagnostic symbol: ") + name);
    return reinterpret_cast<Function>(address);
}

struct Api {
    std::function<void *(ps_config_t *)> create;
    std::function<void(void *)> destroy;
    std::function<int(void *, const int16_t *, size_t, ss_cep_callback, void *)> process;
    std::function<int(void *, ss_cep_callback, void *)> end;
    std::function<int(void *)> start;
    std::function<void(void *)> stream;
    std::function<int(void *)> speech;
    std::function<int(void *)> ceplen;
};

Api nativeApi()
{
    Api result;
    result.create = [](ps_config_t *configuration) -> void * {
        return ss_frontend_create_config(configuration, kCapacity);
    };
    result.destroy = [](void *fe) { ss_frontend_free(static_cast<ss_frontend *>(fe)); };
    result.process = [](void *fe, const int16_t *pcm, size_t count,
                        ss_cep_callback output, void *context) {
        return ss_frontend_process(static_cast<ss_frontend *>(fe), pcm, count, output, context);
    };
    result.end = [](void *fe, ss_cep_callback output, void *context) {
        return ss_frontend_end_utt(static_cast<ss_frontend *>(fe), output, context);
    };
    result.start = [](void *fe) { return ss_frontend_start_utt(static_cast<ss_frontend *>(fe)); };
    result.stream = [](void *fe) { ss_frontend_start_stream(static_cast<ss_frontend *>(fe)); };
    result.speech = [](void *fe) { return ss_frontend_in_speech(static_cast<ss_frontend *>(fe)); };
    result.ceplen = [](void *fe) { return ss_frontend_ceplen(static_cast<ss_frontend *>(fe)); };
    return result;
}

Api oldApi(void *library)
{
    using Create = void *(*)(int, char **, int);
    using ArgName = const char *(*)(size_t);
    const Create create = symbol<Create>(library, "ss_frontend_create");
    const ArgName argumentName = symbol<ArgName>(library, "ss_frontend_arg_name");
    Api result;
    result.create = [create, argumentName](ps_config_t *configuration) {
        std::vector<std::string> arguments = {"frontend-equivalence"};
        for (size_t index = 0; const char *argument = argumentName(index); ++index) {
            const std::string key = argument[0] == '-' ? argument + 1 : argument;
            const ps_type_t type = ps_config_typeof(configuration, key.c_str());
            if (!type) continue; // Removed VAD parameters use legacy FE defaults.
            std::string value;
            if (type & ARG_BOOLEAN)
                value = ps_config_bool(configuration, key.c_str()) ? "yes" : "no";
            else if (type & ARG_INTEGER) {
                long integer = ps_config_int(configuration, key.c_str());
                if (key == "nfft" && integer == 0) {
                    const double samples = ps_config_int(configuration, "samprate")
                        * ps_config_float(configuration, "wlen");
                    integer = 1;
                    while (integer < samples) integer *= 2;
                }
                value = std::to_string(integer);
            }
            else if (type & ARG_FLOATING) {
                std::ostringstream formatted;
                formatted << std::setprecision(17) << ps_config_float(configuration, key.c_str());
                value = formatted.str();
            }
            else if (type & ARG_STRING) {
                const char *text = ps_config_str(configuration, key.c_str());
                if (!text) continue;
                value = text;
            }
            else continue;
            arguments.push_back(argument);
            arguments.push_back(value);
        }
        std::vector<char *> argv;
        for (std::string &argument : arguments) argv.push_back(&argument[0]);
        return create(static_cast<int>(argv.size()), argv.data(), kCapacity);
    };
    result.destroy = symbol<void (*)(void *)>(library, "ss_frontend_free");
    using Process = int (*)(void *, const int16_t *, size_t, ss_cep_callback, void *);
    const Process process = symbol<Process>(library, "ss_frontend_process");
    require(process != reinterpret_cast<Process>(&ss_frontend_process),
            "Legacy wrapper resolved to the native function; comparison would be invalid");
    result.process = process;
    result.end = symbol<int (*)(void *, ss_cep_callback, void *)>(library, "ss_frontend_end_utt");
    result.start = symbol<int (*)(void *)>(library, "ss_frontend_start_utt");
    result.stream = symbol<void (*)(void *)>(library, "ss_frontend_start_stream");
    result.speech = symbol<int (*)(void *)>(library, "ss_frontend_in_speech");
    result.ceplen = symbol<int (*)(void *)>(library, "ss_frontend_ceplen");
    return result;
}

struct Batch {
    int phase, frames, offset, speech;
    std::vector<uint32_t> coefficients;
};

struct Step {
    int phase, operation, status, speech;
    size_t inputCount, batches;
};

struct Recording {
    const Api *api;
    void *frontend;
    int ceplen, phase = 0;
    bool invalid = false;
    std::vector<Batch> batches;
    std::vector<Step> steps;
};

int output(void *context, float **values, int frames, int offset)
{
    Recording &recording = *static_cast<Recording *>(context);
    if (frames < 0 || frames > kCapacity || (frames && values == nullptr)) {
        recording.invalid = true;
        return -1;
    }
    Batch batch{recording.phase, frames, offset,
                recording.api->speech(recording.frontend), {}};
    for (int frame = 0; frame < frames; ++frame) {
        if (values[frame] == nullptr) {
            recording.invalid = true;
            return -1;
        }
        for (int coefficient = 0; coefficient < recording.ceplen; ++coefficient) {
            const float value = values[frame][coefficient];
            if (!std::isfinite(value)) recording.invalid = true;
            uint32_t bits;
            static_assert(sizeof(bits) == sizeof(value), "Expected IEEE binary32 float");
            std::memcpy(&bits, &value, sizeof(bits));
            batch.coefficients.push_back(bits);
        }
    }
    recording.batches.push_back(std::move(batch));
    return recording.invalid ? -1 : 0;
}

void recordStep(Recording &recording, int operation, int status, size_t count = 0)
{
    require(status >= 0, "Frontend operation failed in phase " + std::to_string(recording.phase));
    recording.steps.push_back({recording.phase, operation, status,
            recording.api->speech(recording.frontend), count, recording.batches.size()});
}

void feed(Recording &recording, const std::vector<int16_t> &pcm, size_t chunk)
{
    for (size_t position = 0; position < pcm.size();) {
        const size_t count = std::min(chunk, pcm.size() - position);
        const int status = recording.api->process(recording.frontend,
                pcm.data() + position, count, output, &recording);
        recordStep(recording, 1, status, count);
        require(!recording.invalid, "Nonfinite coefficients or invalid callback capacity");
        position += count;
    }
}

Recording record(const Api &api, ps_config_t *configuration,
                 const std::vector<int16_t> &input, size_t chunk)
{
    void *frontend = api.create(configuration);
    require(frontend != nullptr, "Frontend creation failed");
    std::unique_ptr<void, std::function<void(void *)>> owner(frontend, api.destroy);
    const int ceplen = api.ceplen(frontend);
    require(ceplen > 0 && ceplen <= 256, "Unexpected frontend coefficient count");
    Recording result{&api, frontend, ceplen, 0, false, {}, {}};

    // A stream combines silence/speech, a second utterance without stream
    // reset, and then an explicit stream reset. EOF has a partial frame.
    std::vector<int16_t> combined(5333, 0);
    combined.insert(combined.end(), input.begin(), input.end());
    combined.insert(combined.end(), 20317, 0);
    combined.insert(combined.end(), input.begin(), input.end());
    combined.insert(combined.end(), 1091, 0);
    std::vector<int16_t> shortInput(input.begin(), input.begin() + std::min<size_t>(997, input.size()));
    shortInput.insert(shortInput.end(), 57, 0);
    std::vector<int16_t> restarted(3200, 0);
    restarted.insert(restarted.end(), input.begin(), input.end());
    restarted.insert(restarted.end(), 137, 0);

    result.phase = 0;
    api.stream(frontend);
    recordStep(result, 0, api.start(frontend));
    feed(result, combined, chunk);
    recordStep(result, 2, api.end(frontend, output, &result));
    result.phase = 1;
    recordStep(result, 0, api.start(frontend));
    feed(result, shortInput, chunk);
    recordStep(result, 2, api.end(frontend, output, &result));
    result.phase = 2;
    api.stream(frontend);
    recordStep(result, 0, api.start(frontend));
    feed(result, restarted, chunk);
    recordStep(result, 2, api.end(frontend, output, &result));
    require(!result.invalid, "Invalid EOF callback output");
    result.frontend = nullptr;
    return result;
}

void compare(const Recording &old, const Recording &native, size_t chunk)
{
    const std::string prefix = "chunk " + std::to_string(chunk) + ": ";
    require(old.ceplen == native.ceplen, prefix + "coefficient count differs");
    require(old.steps.size() == native.steps.size(), prefix + "step count differs");
    require(old.batches.size() == native.batches.size(), prefix + "callback count differs");
    for (size_t index = 0; index < old.steps.size(); ++index) {
        const Step &a = old.steps[index], &b = native.steps[index];
        require(a.phase == b.phase && a.operation == b.operation && a.status == b.status
                && a.speech == b.speech && a.inputCount == b.inputCount && a.batches == b.batches,
                prefix + "VAD/status/index differs at step " + std::to_string(index));
    }
    for (size_t index = 0; index < old.batches.size(); ++index) {
        const Batch &a = old.batches[index], &b = native.batches[index];
        require(a.phase == b.phase && a.frames == b.frames && a.offset == b.offset
                && a.speech == b.speech,
                prefix + "frame/offset/VAD notification differs at callback " + std::to_string(index));
        require(a.coefficients == b.coefficients,
                prefix + "MFCC float bits differ at callback " + std::to_string(index));
    }
}

std::vector<int16_t> readPcm(const char *path)
{
    std::ifstream source(path, std::ios::binary);
    require(source.good(), "Cannot open raw 16kHz mono PCM input");
    const std::vector<char> bytes((std::istreambuf_iterator<char>(source)), {});
    require(!bytes.empty() && bytes.size() % 2 == 0, "PCM must be nonempty signed little-endian16");
    std::vector<int16_t> result;
    result.reserve(bytes.size() / 2);
    for (size_t index = 0; index < bytes.size(); index += 2) {
        const uint16_t low = static_cast<unsigned char>(bytes[index]);
        const uint16_t high = static_cast<unsigned char>(bytes[index + 1]);
        result.push_back(static_cast<int16_t>(low | (high << 8)));
    }
    return result;
}

} // namespace

int main(int argc, char **argv)
{
    if (argc != 6) {
        std::cerr << "Usage: frontend-equivalence OLD_FE_DYLIB HMM_DIR LM_FILE DICT_FILE PCM_S16LE_16KHZ\n";
        return 2;
    }
    try {
        void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
        const char *error = dlerror();
        require(library != nullptr, std::string("Cannot load frozen frontend wrapper: ") + (error ? error : "unknown"));
        std::unique_ptr<void, int (*)(void *)> libraryOwner(library, dlclose);
        const std::vector<int16_t> input = readPcm(argv[5]);
        ps_config_t *configuration = ps_config_init(nullptr);
        require(configuration != nullptr, "Cannot initialize public PS5 configuration");
        std::unique_ptr<ps_config_t, int (*)(ps_config_t *)> configOwner(configuration, ps_config_free);
        ps_config_set_str(configuration, "hmm", argv[2]);
        ps_config_set_str(configuration, "lm", argv[3]);
        ps_config_set_str(configuration, "dict", argv[4]);
        ps_config_set_int(configuration, "samprate", 16000);
        ps_config_set_int(configuration, "ds", 2);
        ps_config_set_int(configuration, "maxhmmpf", 500);
        ps_config_set_str(configuration, "logfn", "/dev/null");
        ps_decoder_t *decoder = ps_init(configuration);
        require(decoder != nullptr, "PS5 model initialization failed");
        std::unique_ptr<ps_decoder_t, int (*)(ps_decoder_t *)> decoderOwner(decoder, ps_free);
        ps_config_t *modelConfiguration = ps_get_config(decoder);
        const Api old = oldApi(library), native = nativeApi();
        for (bool removeNoise : {true, false}) {
            ps_config_set_bool(modelConfiguration, "remove_noise", removeNoise);
            for (size_t chunk : {size_t(1), size_t(160), size_t(997), size_t(4096), size_t(32768)}) {
                const Recording expected = record(old, modelConfiguration, input, chunk);
                const Recording actual = record(native, modelConfiguration, input, chunk);
                compare(expected, actual, chunk);
                size_t frames = 0;
                for (const Batch &batch : actual.batches) frames += batch.frames;
                require(frames != 0, "Fixture produced no speech feature frames");
                std::cout << "{\"remove_noise\":" << (removeNoise ? "true" : "false")
                          << ",\"chunk\":" << chunk << ",\"callbacks\":" << actual.batches.size()
                          << ",\"frames\":" << frames << ",\"steps\":" << actual.steps.size()
                          << ",\"mfcc_bits_offsets_vad_equal\":true}\n";
            }
        }
        return 0;
    }
    catch (const std::exception &error) {
        std::cerr << "frontend-equivalence: " << error.what() << '\n';
        return 1;
    }
}
