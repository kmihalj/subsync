#!/usr/bin/env python3
"""Import, validate and compile complete gettext UI catalogs without pip tools.

GNU msgfmt is an additional independent check when installed. The bundled
compiler supports the singular, context-free catalogs used by SubSync; it
rejects unsupported PO syntax rather than silently losing messages.
"""
import argparse
import ast
from collections import Counter
from functools import lru_cache
import gettext
import io
import importlib.util
import json
from pathlib import Path
import re
import shutil
import string
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
registry_spec = importlib.util.spec_from_file_location('ui_locale_registry',
        ROOT / 'subsync/data/uilanguages.py')
registry = importlib.util.module_from_spec(registry_spec)
registry_spec.loader.exec_module(registry)
NAMES = registry.NAMES

SOURCE = Path(__file__).with_name('localization-messages.json')
LOCALES = ROOT / 'subsync/locale'


@lru_cache(maxsize=1)
def source_messages():
    messages = json.loads(SOURCE.read_text())
    if len(messages) != len(set(messages)) or not all(messages):
        raise ValueError('Duplicate or empty source message')
    extracted = set()
    for path in (ROOT / 'subsync').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == '_' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                extracted.add(node.args[0].value)
    if extracted != set(messages):
        raise ValueError(f'UI source catalog is stale: {len(extracted-set(messages))} new, '
                         f'{len(set(messages)-extracted)} removed messages')
    return messages


def parse_po(path):
    entries, fields, flags, current = {}, {}, set(), None

    def flush():
        if not fields:
            return
        if set(fields) != {'msgid', 'msgstr'}:
            raise ValueError(f'{path}: incomplete or unsupported PO entry')
        key = fields['msgid']
        if key in entries:
            raise ValueError(f'{path}: duplicate msgid {key!r}')
        if 'fuzzy' in flags:
            raise ValueError(f'{path}: fuzzy entry {key!r}')
        entries[key] = fields['msgstr']

    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines() + [''], 1):
        if not line.strip():
            flush()
            fields, flags, current = {}, set(), None
        elif line.startswith('#,'):
            flags.update(x.strip() for x in line[2:].split(','))
        elif line.startswith('#'):
            continue
        elif line.startswith('msgid ') or line.startswith('msgstr '):
            current, value = line.split(' ', 1)
            if current in fields:
                raise ValueError(f'{path}:{number}: repeated {current}')
            fields[current] = ast.literal_eval(value)
        elif line.startswith('"') and current:
            fields[current] += ast.literal_eval(line)
        else:
            raise ValueError(f'{path}:{number}: unsupported PO syntax')
    return entries


def literal(message):
    return bool(re.fullmatch(r'\{(?:if(?:_not)?:[^{}]+|(?:ref|sub)_[a-z0-9]+)\}', message))


def placeholders(message):
    # Each anonymous field receives its actual positional argument index.
    result, position, automatic, numbered = [], 0, False, False
    for _, field, spec, conversion in string.Formatter().parse(message):
        if field is not None:
            if field == '':
                automatic = True
                field = str(position)
                position += 1
            elif field.partition('.')[0].partition('[')[0].isdigit():
                numbered = True
            result.append((field, spec, conversion))
    if automatic and numbered:
        raise ValueError('Mixed automatic and numbered format fields')
    return Counter(result)


def match_spacing(original, translated):
    prefix = re.match(r'^\s*', original).group()
    suffix = re.search(r'\s*$', original).group()
    return prefix + translated.strip() + suffix


def validate(locale, entries):
    expected = set(source_messages())
    actual = set(entries) - {''}
    if actual != expected:
        raise ValueError(f'{locale}: missing {len(expected-actual)}, stale {len(actual-expected)} messages')
    header = entries.get('', '')
    if f'Language: {locale}\n' not in header or 'charset=UTF-8' not in header:
        raise ValueError(f'{locale}: invalid Language/UTF-8 header')
    for original in expected:
        translated = entries[original]
        if not translated or not translated.strip():
            raise ValueError(f'{locale}: empty translation {original!r}')
        if '\0' in translated or any(ord(c) < 32 and c not in '\n\t\r' for c in translated):
            raise ValueError(f'{locale}: control character in {original!r}')
        if literal(original):
            if translated != original:
                raise ValueError(f'{locale}: output-pattern token changed: {original!r}')
        elif placeholders(original) != placeholders(translated):
            raise ValueError(f'{locale}: format fields changed: {original!r}')
        if original.count('\n') != translated.count('\n'):
            raise ValueError(f'{locale}: line breaks changed: {original!r}')
        if original.count('&') != translated.count('&'):
            raise ValueError(f'{locale}: menu accelerator count changed: {original!r}')
        if match_spacing(original, translated) != translated:
            raise ValueError(f'{locale}: message boundary whitespace changed: {original!r}')
        if 'Michał Szymaniak' in original and 'Michał Szymaniak' not in translated:
            raise ValueError(f'{locale}: original author credit changed')


def compile_mo(entries):
    pairs = sorted((key.encode('utf-8'), value.encode('utf-8')) for key, value in entries.items())
    count = len(pairs)
    originals = b''.join(key + b'\0' for key, _ in pairs)
    translated = b''.join(value + b'\0' for _, value in pairs)
    base = 28 + 16 * count
    original_table, translated_table = [], []
    start, end = base, base + len(originals)
    for key, value in pairs:
        original_table.append(struct.pack('<2I', len(key), start))
        translated_table.append(struct.pack('<2I', len(value), end))
        start += len(key) + 1
        end += len(value) + 1
    data = (struct.pack('<7I', 0x950412de, 0, count, 28, 28 + 8 * count, 0, 0)
            + b''.join(original_table) + b''.join(translated_table) + originals + translated)
    loaded = gettext.GNUTranslations(io.BytesIO(data))
    for key, value in entries.items():
        if key and loaded.gettext(key) != value:
            raise ValueError(f'MO round trip failed: {key!r}')
    return data


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'Duplicate JSON key {key}')
        result[key] = value
    return result


def import_catalog(locale, path):
    if locale not in NAMES or locale == 'en':
        raise ValueError(f'Unsupported translation locale: {locale}')
    messages = source_messages()
    supplied = json.loads(path.read_text(), object_pairs_hook=unique_object)
    if isinstance(supplied, list):
        supplied = dict(zip(map(str, range(len(supplied))), supplied))
    if set(supplied) != set(map(str, range(len(messages)))):
        raise ValueError(f'{locale}: expected all {len(messages)} indexed translations')
    header = ('Project-Id-Version: SubSync macOS ARM\n'
              'Report-Msgid-Bugs-To: https://github.com/kmihalj/subsync/issues\n'
              'PO-Revision-Date: 2026-11-09 00:00+0100\n'
              'Last-Translator: SubSync contributors\n'
              f'Language-Team: {NAMES[locale]}\n'
              f'Language: {locale}\n'
              'MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\n'
              'Content-Transfer-Encoding: 8bit\n'
              'X-Translation-Review: Machine-assisted draft; linguistic review pending\n')
    entries = {'': header}
    if not all(isinstance(value, str) for value in supplied.values()):
        raise ValueError(f'{locale}: translation must be text')
    entries.update((message, match_spacing(message, supplied[str(i)]))
                   for i, message in enumerate(messages))
    validate(locale, entries)
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['# SubSync UI translation. GPL-3.0-or-later, as the application.',
             '# Machine-assisted draft; native-language review is welcome.',
             'msgid ""', 'msgstr ' + quote(header), '']
    for original in messages:
        if literal(original):
            lines.append('#. Literal filename-pattern token; do not translate.')
        lines.extend(['msgid ' + quote(original), 'msgstr ' + quote(entries[original]), ''])
    target = LOCALES / locale / 'LC_MESSAGES/messages.po'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines), encoding='utf-8')
    print(f'{locale}: imported {len(messages)} messages')


def compile_catalogs(selected, check_only=False):
    msgfmt = shutil.which('msgfmt')
    results = []
    for locale in selected:
        if locale == 'en':
            continue
        path = LOCALES / locale / 'LC_MESSAGES/messages.po'
        entries = parse_po(path)
        validate(locale, entries)
        data = compile_mo(entries)
        if msgfmt:
            subprocess.run([msgfmt, '--check', '--check-format', '-o', '/dev/null', str(path)], check=True)
        if not check_only:
            path.with_suffix('.mo').write_bytes(data)
        elif path.with_suffix('.mo').read_bytes() != data:
            raise ValueError(f'{locale}: compiled MO is stale')
        results.append({'locale': locale, 'messages': len(entries)-1, 'mo_bytes': len(data),
                        'identity_messages': sum(key == value for key, value in entries.items())})
    print(json.dumps({'catalogs': results, 'gnu_msgfmt_check': bool(msgfmt)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('locale')
    importer.add_argument('json', type=Path)
    for command in ('compile', 'check'):
        sub = commands.add_parser(command)
        sub.add_argument('locales', nargs='*', choices=sorted(set(NAMES)-{'en'}))
    args = parser.parse_args()
    if args.command == 'import':
        import_catalog(args.locale, args.json)
    else:
        compile_catalogs(args.locales or sorted(NAMES), args.command == 'check')


if __name__ == '__main__':
    main()
