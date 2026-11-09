"""UI locales are independent of supported subtitle/speech languages.

The requested set is the union of the 45 subtitle chooser languages and the
24 official EU languages: 46 languages, including Irish. Native names keep
the selector recognizable even when the current interface is unfamiliar.
"""

NAMES = {
    'ar': 'العربية', 'be': 'Беларуская', 'bg': 'Български', 'ca': 'Català',
    'cs': 'Čeština', 'da': 'Dansk', 'de': 'Deutsch', 'el': 'Ελληνικά',
    'en': 'English', 'es': 'Español', 'et': 'Eesti', 'fa': 'فارسی',
    'fi': 'Suomi', 'fo': 'Føroyskt', 'fr': 'Français', 'ga': 'Gaeilge',
    'gd': 'Gàidhlig', 'gl': 'Galego', 'he': 'עברית', 'hr': 'Hrvatski',
    'hu': 'Magyar', 'id': 'Bahasa Indonesia', 'is': 'Íslenska', 'it': 'Italiano',
    'ja': '日本語', 'ko': '한국어', 'la': 'Latina', 'lt': 'Lietuvių',
    'lv': 'Latviešu', 'mg': 'Malagasy', 'ms': 'Bahasa Melayu', 'mt': 'Malti',
    'nl': 'Nederlands', 'no': 'Norsk (bokmål)', 'pl': 'Polski', 'pt': 'Português',
    'ro': 'Română', 'ru': 'Русский', 'sk': 'Slovenčina', 'sl': 'Slovenščina',
    'sq': 'Shqip', 'sr': 'Српски', 'sv': 'Svenska', 'tr': 'Türkçe',
    'uk': 'Українська', 'zh': '简体中文',
}

RIGHT_TO_LEFT = frozenset(('ar', 'fa', 'he'))

# Accept existing three-letter settings/CLI spellings without coupling UI
# support to media-language metadata or changing its encodings/tokenization.
ALIASES = dict(zip(
    ('ara bel bul cat cze dan ger gre eng spa est per fin fao fre gle gla glg '
     'heb hrv hun ind ice ita jpn kor lat lit lav mlg may mlt dut nor pol por '
     'rum rus slo slv alb srp swe tur ukr chi').split(),
    ('ar be bg ca cs da de el en es et fa fi fo fr ga gd gl he hr hu id is it '
     'ja ko la lt lv mg ms mt nl no pl pt ro ru sk sl sq sr sv tr uk zh').split()))
ALIASES.update({'nb': 'no', 'nn': 'no', 'iw': 'he', 'in': 'id', 'cmn': 'zh',
                'chs': 'zh', 'cht': 'zh', 'nld': 'nl', 'sqi': 'sq', 'deu': 'de',
                'fra': 'fr', 'ces': 'cs', 'ell': 'el', 'isl': 'is', 'slk': 'sk',
                'ron': 'ro', 'zho': 'zh', 'pob': 'pt', 'fas': 'fa', 'msa': 'ms'})


def normalize(value):
    if not isinstance(value, str):
        return None
    base = value.strip().lower().replace('_', '-').split('.', 1)[0]
    base = base.split('@', 1)[0].split('-', 1)[0]
    base = ALIASES.get(base, base)
    return base if base in NAMES else None
