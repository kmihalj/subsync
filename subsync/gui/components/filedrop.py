import wx
import os
from subsync.macos import access as file_access
from subsync.macos.mode import is_appstore_build


class FileDropTarget(wx.FileDropTarget):
    def __init__(self, **kwargs):
        wx.FileDropTarget.__init__(self)

        self.onFile = kwargs.pop('OnDropFile', None)
        self.onFiles = kwargs.pop('OnDropFiles', None)
        for key, val in kwargs.items():
            setattr(self, key, val)

    def OnDropFiles(self, x, y, filenames):
        selected = filenames if self.onFiles else filenames[:1]
        if is_appstore_build():
            for path in selected:
                file_access.remember(path, directory=os.path.isdir(path))
        if self.onFiles:
            return self.onFiles(x, y, filenames)
        if self.onFile and filenames:
            return self.onFile(x, y, filenames[0])
        return False


def setFileDropTarget(target, children=True, **kwargs):
    target.SetDropTarget(FileDropTarget(**kwargs))

    if children:
        for child in target.GetChildren():
            if isinstance(child, wx.Window):
                # separate instance of FileDropTarget since will take ownership
                # of it and will destroy it at close
                child.SetDropTarget(FileDropTarget(**kwargs))

