import wx


class ChoiceCustomLang(wx.Choice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def addSortedLangs(self, langs):
        for name in sorted(langs):
            self.Append(name, langs[name])

    def SetValue(self, lang):
        if lang == wx.NOT_FOUND:
            self.SetSelection(lang)
            return False

        elif lang != None:
            lang = lang.lower()
            for i in range(1, self.GetCount()):
                if self.GetClientData(i) == lang:
                    self.SetSelection(i)
                    return True

        self.SetSelection(0)
        return False

    def GetValue(self):
        i = self.GetSelection()
        if i != wx.NOT_FOUND:
            return self.GetClientData(i)


class ChoiceLang(ChoiceCustomLang):
    def __init__(self, *args, **kwargs):
        from subsync.data.languages import languages

        super().__init__(*args, **kwargs)
        self.Append(_('<other>'), None)
        self.addSortedLangs({ lang.name: lang.code3 for lang in languages })


class ChoiceGuiLang(ChoiceCustomLang):
    def __init__(self, *args, **kwargs):
        from subsync.data.uilanguages import NAMES
        from subsync.translations import listLanguages as langs

        super().__init__(*args, **kwargs)
        self.Append(_('default'), None)
        self.addSortedLangs({ NAMES[x]: x for x in langs() })

    def SetValue(self, lang):
        from subsync.data.uilanguages import normalize
        if isinstance(lang, str):
            lang = normalize(lang)
        return super().SetValue(lang)
