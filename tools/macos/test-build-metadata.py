#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('version_metadata', Path(__file__).with_name('version_metadata.py'))
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class VersionTests(unittest.TestCase):
    def test_release_tags_have_three_apple_components(self):
        for tag, expected in [('1.0', '1.0.0'), ('v1.0.0', '1.0.0'), ('12.34.5', '12.34.5')]:
            self.assertEqual(metadata.release_version(tag), expected)

    def test_exact_three_part_tag_does_not_gain_fourth_component(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
                metadata.subprocess, 'check_output', return_value='v1.0.0-0-gabc123\n'):
            self.assertEqual(metadata.source_version(), ('v1.0.0', '1.0.0'))

    def test_development_count_is_not_a_marketing_version_component(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
                metadata.subprocess, 'check_output', return_value='1.0-4-gabc123\n'):
            long, short = metadata.source_version()
        self.assertEqual(short, '1.0.0.4')
        self.assertEqual(metadata.bundle_versions(short, '123'), ('1.0.0', '123'))

    def test_invalid_release_and_build_values_reject(self):
        for value in ['1.0.0.0', 'release', '1.0;command', '-1.0']:
            with self.assertRaises(ValueError):
                metadata.release_version(value)
        for value in ['0', '01', '10000', '1.100', '1.0.0.0', '1;command']:
            with self.assertRaises(ValueError):
                metadata.bundle_versions('1.0.0', value)

    def test_local_release_override_is_validated(self):
        with patch.dict(os.environ, {'SUBSYNC_RELEASE_VERSION': '1.0'}):
            self.assertEqual(metadata.source_version(), ('1.0', '1.0.0'))
        with patch.dict(os.environ, {'SUBSYNC_RELEASE_VERSION': 'bad'}):
            with self.assertRaises(ValueError):
                metadata.source_version()


if __name__ == '__main__':
    unittest.main(verbosity=2)
