#!/usr/bin/env python3
"""Check real catalogs and locale selection; --gui also builds the settings UI."""
import argparse
import gettext
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['SUBSYNC_CONFIG_DIR'] = str(ROOT / '.build/localization-test-profile')
from subsync import config, translations
from subsync.data.uilanguages import NAMES, normalize

spec = importlib.util.spec_from_file_location('catalog_tools', Path(__file__).with_name('localization.py'))
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
RUN_GUI = '--gui' in sys.argv
if RUN_GUI:
    sys.argv.remove('--gui')


class CatalogTests(unittest.TestCase):
    def test_requested_union(self):
        from subsync.data.languages import languages
        eu = set('bg hr cs da nl en et fi fr de el hu ga it lv lt mt pl pt ro sk sl es sv'.split())
        self.assertEqual(set(NAMES), {language.code2 for language in languages} | eu)
        self.assertEqual(len(NAMES), 46)
        self.assertEqual(len(set(NAMES.values())), 46)

    def test_all_actual_catalogs_and_mo_roundtrip(self):
        messages = catalog.source_messages()
        self.assertEqual(len(messages), 393)
        self.assertEqual(set(translations.listLanguages()), set(NAMES))
        for code in sorted(set(NAMES) - {'en'}):
            with self.subTest(locale=code):
                path = catalog.LOCALES / code / 'LC_MESSAGES/messages.po'
                entries = catalog.parse_po(path)
                catalog.validate(code, entries)
                self.assertEqual(path.with_suffix('.mo').read_bytes(), catalog.compile_mo(entries))
                loaded = gettext.GNUTranslations(io.BytesIO(path.with_suffix('.mo').read_bytes()))
                for original in messages:
                    self.assertEqual(loaded.gettext(original), entries[original])

    def test_reject_damaged_format_tokens_and_newlines(self):
        entries = {'': 'Language: hr\nContent-Type: text/plain; charset=UTF-8\n'}
        entries.update((message, message) for message in catalog.source_messages())
        for original, replacement in [('{} min', 'min'), ('{sub_path}', '{putanja}'),
                                      ('Subtitle\nSpeech\nSynchronizer', 'Subtitle Speech Synchronizer')]:
            with self.subTest(message=original):
                damaged = dict(entries, **{original: replacement})
                with self.assertRaises(ValueError):
                    catalog.validate('hr', damaged)

    def test_reject_duplicate_input_keys(self):
        with self.assertRaises(ValueError):
            json.loads('{"0":"one","0":"two"}', object_pairs_hook=catalog.unique_object)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.override = patch.object(config, 'localedir', self.directory.name)
        self.override.start()
        for code, word in [('pl', 'Ustawienia'), ('hr', 'Postavke'), ('ja', '設定')]:
            path = Path(self.directory.name) / code / 'LC_MESSAGES/messages.mo'
            path.parent.mkdir(parents=True)
            path.write_bytes(catalog.compile_mo({'': 'Content-Type: text/plain; charset=UTF-8\n',
                                                'Settings': word}))

    def tearDown(self):
        self.override.stop()
        self.directory.cleanup()
        translations.setLanguage('en')

    def test_normalize_region_case_and_existing_codes(self):
        for value, expected in [('HR_hr.UTF-8', 'hr'), ('ja-JP', 'ja'), ('eng', 'en'),
                                ('gle', 'ga'), ('nb_NO', 'no'), ('cmn-CN', 'zh'),
                                ('iw_IL', 'he'), ('sr_Latn', 'sr'), ('C', None),
                                ('../../hr', None), ('nonsense', None)]:
            self.assertEqual(normalize(value), expected)

    def test_explicit_english_ignores_environment_and_previous_language(self):
        with patch.dict(os.environ, {'LANGUAGE': 'pl'}):
            translations.setLanguage('pl')
            self.assertEqual(translations._('Settings'), 'Ustawienia')
            translations.setLanguage('en')
            self.assertEqual(translations._('Settings'), 'Settings')

    def test_automatic_chain_uses_first_available(self):
        with patch.object(translations, 'systemLanguages', return_value=iter(['xx', 'hr-HR', 'pl'])):
            self.assertEqual(translations.setLanguage(None), 'hr')
        self.assertEqual(translations._('Settings'), 'Postavke')

    def test_unknown_and_missing_locale_fall_back_to_english(self):
        translations.setLanguage('ja')
        self.assertEqual(translations._('Settings'), '設定')
        for value in ['bad-locale', 'fr-FR']:
            self.assertEqual(translations.setLanguage(value), 'en')
            self.assertEqual(translations._('Settings'), 'Settings')

    def test_corrupt_catalog_falls_back_cleanly(self):
        (Path(self.directory.name) / 'pl/LC_MESSAGES/messages.mo').write_bytes(b'broken')
        with self.assertLogs('subsync.translations', level='WARNING'):
            self.assertEqual(translations.setLanguage('pl'), 'en')
        self.assertEqual(translations._('Settings'), 'Settings')


@unittest.skipUnless(RUN_GUI, 'Pass --gui for native widget checks')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.App(False)

    def test_autonym_selector_roundtrip_and_settings_fit_all_languages(self):
        import wx
        from subsync.gui.settingswin import SettingsWin
        dimensions = []
        for code in sorted(NAMES):
            translations.setLanguage(code)
            with self.subTest(locale=code):
                dialog = SettingsWin(None)
                selector = dialog.m_language
                self.assertEqual(selector.GetCount(), 47)
                for value in NAMES:
                    self.assertTrue(selector.SetValue(value))
                    self.assertEqual(selector.GetValue(), value)
                selector.SetValue(None)
                self.assertIsNone(selector.GetValue())
                for index in range(dialog.m_notebook.GetPageCount()):
                    dialog.m_notebook.SetSelection(index)
                    dialog.Layout()
                dimensions.append((code, dialog.GetSize().width, dialog.GetSize().height))
                self.assertGreater(dialog.GetSize().width, 0)
                self.assertGreater(dialog.GetSize().height, 0)
                dialog.Destroy()
        translations.setLanguage('en')
        print('Native settings dimensions:', dimensions)


if __name__ == '__main__':
    unittest.main(verbosity=2)
