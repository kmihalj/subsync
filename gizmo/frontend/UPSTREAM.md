# Owned streaming audio frontend

The experimental application links PocketSphinx 5.1.1 through its public
configuration and `ps_process_cep` APIs. It does not link SphinxBase, SphinxAD,
the old PocketSphinx decoder, or private PocketSphinx structures/functions.

The frontend is compiled into SubSync as a namespaced static archive. Its
FFT, filterbank, cepstral, warp and utility implementations derive from the
current PocketSphinx release. SubSync maintains the additional energy/SNR
speech detection, prespeech context and stream frame accounting needed to
reproduce the original application's preprocessing. Those portions derive
from the historical BSD-licensed frontend, rather than introducing the
deprecated SphinxBase package as a dependency. This compatibility code is
now part of this fork's maintenance scope.

`fe/origins.json` and `util/UPSTREAM.json` record file provenance and source
hashes. `LICENSE.pocketsphinx` and `LICENSE.compatibility` retain the required
copyright notices. The private `util/cmd_ln.h` is a small typed adapter to
the public `ps_config_*` API, not the old command-line parser or ABI.

Validation compares frontend output with an isolated historical reference
used only in developer tests, checks invalid configurations under sanitizers,
and compares complete synchronizations with immutable application snapshots.
Neither reference libraries, copied speech models nor private film fixtures
belong in the released app or source repository.
