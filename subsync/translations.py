"""Deterministic gettext selection for the independently defined UI locales."""
import builtins
import gettext
import locale
import logging
import os
import struct
import sys
from pathlib import Path

from subsync import config
from subsync.data.uilanguages import normalize

logger = logging.getLogger(__name__)
initialized = False
active_language = 'en'


def listLanguages():
    from subsync.data.uilanguages import NAMES
    root = Path(config.localedir)
    return sorted(code for code in NAMES if code == 'en' or
                  (root / code / 'LC_MESSAGES/messages.mo').is_file())


def systemLanguages():
    # Read native Mac language without starting a GUI in headless mode.
    wx = sys.modules.get('wx')
    if sys.platform == 'darwin' and wx is not None and wx.GetApp() is not None:
        try:
            info = wx.Locale.GetLanguageInfo(wx.Locale.GetSystemLanguage())
            if info:
                yield info.CanonicalName
        except (AttributeError, RuntimeError):
            logger.debug('Could not read the native UI language', exc_info=True)
    for variable in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        value = os.environ.get(variable)
        if value:
            yield from value.split(':')
    try:
        value = locale.getlocale()[0]
        if value:
            yield value
    except (TypeError, ValueError):
        pass


def init():
    setLanguage(None)


def setLanguage(language):
    available = set(listLanguages())
    candidates = systemLanguages() if language is None else [language]
    chosen = 'en'
    for candidate in candidates:
        code = normalize(candidate)
        if code in available:
            chosen = code
            break
    # Explicit English must not inherit LANGUAGE=pl: gettext.install's
    # environment lookup used to keep the Polish translation selected.
    translation = gettext.NullTranslations()
    if chosen != 'en':
        try:
            translation = gettext.translation('messages', localedir=config.localedir,
                                              languages=[chosen], fallback=False)
        except (OSError, EOFError, UnicodeError, ValueError, struct.error) as error:
            logger.warning('Cannot load UI locale %s: %s; using English', chosen, error)
            chosen = 'en'
    translation.install()
    global initialized, active_language
    initialized, active_language = True, chosen
    logger.info('UI language: %s', chosen)

    # Reload eagerly translated labels only if already imported, avoiding
    # circular imports during early command-line argument parsing.
    import importlib
    for name in ('subsync.data.languages', 'subsync.data.descriptions'):
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)
    return chosen


def _(message):
    if initialized:
        translator = builtins.__dict__.get('_')
        if translator is not None:
            return translator(message)
    return message
