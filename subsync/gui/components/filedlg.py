import wx
import os
from subsync.settings import settings
from subsync.macos import access as file_access
from subsync.macos.mode import is_appstore_build


def showOpenFileDlg(parent, multiple=False, **args):
    style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
    if multiple:
        style |= wx.FD_MULTIPLE

    if 'defaultFile' not in args:
        args['defaultDir'] = settings().lastdir

    with wx.FileDialog(parent, _('Select file'), style=style, **args) as fileDialog:
        if fileDialog.ShowModal() == wx.ID_OK:
            if multiple:
                paths = fileDialog.GetPaths()
                if paths:
                    for path in paths:
                        file_access.remember(path)
                    settings().set(lastdir=os.path.dirname(paths[0]))
                return paths
            else:
                path = fileDialog.GetPath()
                file_access.remember(path)
                settings().set(lastdir=os.path.dirname(path))
                return path


def appendExtensionToPath(dlg):
    wildcard = dlg.GetWildcard().split('|')
    path = dlg.GetPath()
    i = 2 * dlg.GetFilterIndex() + 1

    if i >= 0 and i < len(wildcard):
        exts = wildcard[i].split(';')
        if len(exts) == 0:
            return path

        for ext in exts:
            if ext == '*.*' or ext == '*' or path.lower().endswith(ext[1:]):
                return path
        return path + ext[1:]
    else:
        return path


def showSaveFileDlg(parent, **args):
    style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    if 'defaultFile' not in args:
        args['defaultDir'] = settings().lastdir

    with wx.FileDialog(parent, _('Select file'), style=style, **args) as fileDialog:
        if fileDialog.ShowModal() == wx.ID_OK:
            path = appendExtensionToPath(fileDialog)
            if is_appstore_build():
                # Existing collision-avoidance and batch patterns can create
                # sibling names. Obtain an explicit directory grant rather
                # than treating the Save panel's exact file grant as one.
                directory = ensureOutputDirectory(parent, os.path.dirname(path))
                if directory is None:
                    return None
                path = os.path.join(directory, os.path.basename(path))
            settings().set(lastdir=os.path.dirname(path))
            return path


def showDirectoryDlg(parent, title=None, defaultPath='', *, write=False):
    style = wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
    with wx.DirDialog(parent, title or _('Select directory'), defaultPath, style) as dialog:
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            file_access.remember(path, write=write, directory=True)
            return path


def ensureOutputDirectory(parent, directory):
    if not is_appstore_build():
        return directory
    if _verifiedGrant(directory, write=True, directory=True):
        return directory
    return showDirectoryDlg(parent, _('Select output directory'), directory, write=True)


def _verifiedGrant(path, *, write=False, directory=False):
    permissions = file_access.registry()
    if not permissions.has_grant(path, write=write, directory=directory):
        return False
    try:
        with permissions.acquire(path, write=write):
            return True
    except OSError:
        return False


def authorizeTaskData(parent, data):
    """A YAML selection grants the YAML file, not files named inside it."""
    if not is_appstore_build() or not isinstance(data, list):
        return True
    for task in data:
        if not isinstance(task, dict):
            continue  # Existing deserialization reports malformed tasks.
        for kind in ('sub', 'ref'):
            item = task.get(kind)
            path = item.get('path') if isinstance(item, dict) else None
            if path and not _verifiedGrant(path):
                if showDirectoryDlg(parent, _('Select directory'), os.path.dirname(path)) is None:
                    return False
                if not _verifiedGrant(path):
                    return False
    return True

