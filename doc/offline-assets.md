# Offline language data

The Offline DMG includes speech models for English, French, German, Greek,
Italian, Mandarin Chinese, Dutch, Russian and Spanish, plus 217 bilingual dictionaries.
The dictionary pairs and SHA-256 digests of their original archives are listed
in the [pinned inventory](https://github.com/kmihalj/subsync/blob/1.0.3/tools/macos/offline-assets.json),
also included in the app as `ARCHIVE-SHA256.json`. The app ships the
data and original notices from the [SubSync upstream assets release](https://github.com/sc0ty/subsync/releases/tag/assets).

## Speech models

- **English.** Alpha Cephei acoustic model, CMU Pronouncing Dictionary and
  CMUSphinx 5.0 US English language model. The acoustic redistribution notice
  is in the model README. [Acoustic model](https://cmusphinx.github.io/wiki/tutorialadapt/) ·
  [Pronunciation dictionary and license](https://github.com/cmusphinx/cmudict/blob/master/LICENSE) ·
  [Original language model](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/US%20English%20Generic%20Language%20Model/cmusphinx-5.0-en-us.lm.dmp/download)
- **French.** Alpha Cephei and Université du Maine notices accompany the
  CMUSphinx French model. [Original model and notices](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/French/)
- **Greek.** Alpha Cephei model with contributions from Fotis Pantazoglou.
  See the copyright and redistribution terms in its README.
  [Original model](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Greek/)
- **Mandarin Chinese.** Alpha Cephei model trained on the AISHELL corpus.
  The model README includes redistribution terms and identifies the
  CC-CEDICT-derived pronunciation data. [Original model](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Mandarin/) ·
  [AISHELL corpus and license](https://www.openslr.org/33/) · [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)
- **Dutch, Russian and Spanish.** CMUSphinx model distributions with
  GPLv3-or-later notices. The original distributions provide the model data,
  pronunciation dictionaries, available training/build materials and notices.
  [Dutch](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Dutch/) ·
  [Russian](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Russian/) ·
  [Spanish](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Spanish/) ·
  [VoxForge corpus sources](https://www.voxforge.org/home/about)
- **German.** Guenter Bartsch's VoxForge German continuous model r20171217,
  with its LGPLv3 notice. [Model and notices](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/German/) ·
  [Training tools and corpus sources](https://github.com/gooofy/zamia-speech)
- **Italian.** CMUSphinx's Italian VoxForge model, with its original README.
  The VoxForge corpus is GPL-licensed. The exact CMUSphinx model archive
  lacks an explicit redistribution notice for the assembled package.
  [CMUSphinx Italian release and training scripts](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Italian/) ·
  [VoxForge terms](https://www.voxforge.org/home/about/legal/terms-and-conditions)

## Bilingual dictionaries

Each dictionary retains its source and license headers. Upstream extracted,
converted and merged the source entries using the
[dictionary build recipes](https://github.com/sc0ty/subsync/tree/master/assets/dictmk).
The Offline bundle preserves the resulting dictionary files byte for byte.

- [Wiktionary contributors](https://www.wiktionary.org), licensed under
  [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) in the upstream extracts.
- [WikDict](https://www.wikdict.com/page/about), prepared by Karl Bartel from
  Wiktionary via [DBnary](https://kaiko.getalp.org/about-dbnary/), under CC BY-SA.
- Download IATE, European Union, 2019. [IATE download terms](https://iate.europa.eu/assets/i18n/en/static_pages/iate_dl_conditions.html).
- [CC-CEDICT contributors](https://www.mdbg.net/chinese/dictionary?page=cc-cedict), licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- The Czech–English file includes [Free English–Czech Dictionary](https://www.svobodneslovniky.cz)
  data credited to xHire and its contributors under [GNU FDL 1.1](https://www.gnu.org/licenses/old-licenses/fdl-1.1.html),
  alongside Wiktionary and IATE material. The Offline bundle retains the
  upstream file with all its notices and includes the full GNU FDL 1.1 text.
  The licensing terms for the combination are unresolved.
