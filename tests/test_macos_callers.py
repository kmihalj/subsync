"""Permission integration tests with disposable data and deterministic jobs."""
from pathlib import Path
import tempfile
import types
import unittest
import time
from unittest.mock import patch, MagicMock

from test_macos_access import ROOT, FakeBackend, access

# Application imports load its existing native extension, not user profiles.
from subsync.macos import access as actual_access
from subsync.synchro import controller, task as task_module
from subsync.gui.components import filedlg
from subsync import subtitle
from subsync.gui.syncwin import SyncWin
from subsync.gui.batchwin import BatchWin
from subsync.gui import syncwin, batchwin, busydlg
from subsync.synchro.output import OutputFile
from subsync.assets import mgr as asset_manager


class CallerTests(unittest.TestCase):
    def setUp(self):
        build = ROOT / '.build/file-access-tests'
        build.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=build)
        self.root = Path(self.tmp.name)
        self.sub = self.root / 'input.srt'
        self.ref = self.root / 'audio.wav'
        self.sub.write_text('1\n00:00:01,000 --> 00:00:02,000\nA test subtitle.\n')
        self.ref.write_bytes(b'private test placeholder, never decoded')
        self.backend = FakeBackend()
        self.registry = access.BookmarkRegistry(self.root / 'profile', enabled=True, backend=self.backend)
        self.scope_patch = patch.object(actual_access, 'registry', return_value=self.registry)
        self.scope_patch.start()
        self.events = []

    def tearDown(self):
        self.scope_patch.stop()
        self.tmp.cleanup()

    def selected_inputs(self):
        self.registry.remember(self.sub)
        self.registry.remember(self.ref)

    def fake_task(self, output=None):
        return types.SimpleNamespace(sub=types.SimpleNamespace(path=str(self.sub)),
                                     ref=types.SimpleNamespace(path=str(self.ref)), out=output)

    def fake_engine(self, fail=None):
        owner = self
        class Engine:
            def __init__(self, *args):
                if fail == 'construct':
                    raise OSError('construction failed')
            def init(self, *args, **kwargs):
                owner.assertEqual(len(owner.registry._active), 2)
                if fail == 'init':
                    raise OSError('initialization failed')
            def start(self):
                owner.events.append('start')
            def getStatus(self):
                return controller.SyncStatus(True, 0, 1, 1, 20, None, 1)
            def isRunning(self):
                return False
            def stop(self, force):
                owner.assertEqual(len(owner.registry._active), 2)
            def destroy(self):
                owner.assertEqual(len(owner.registry._active), 2)
                owner.events.append('destroy')
                if fail == 'destroy':
                    raise RuntimeError('destruction failed')
        return Engine

    def run_job(self, fail=None, cancelled=False, output=None):
        results = []
        job = controller.SyncController(onError=lambda *args: self.events.append('error'),
                                        onJobEnd=lambda task, status, result: results.append(result))
        job._terminated = cancelled
        with patch('subsync.synchro.synchronizer.Synchronizer', self.fake_engine(fail)):
            job._runTask(self.fake_task(output), None, output is None)
        return results

    def test_job_grants_outlive_engine_stop_and_destroy(self):
        self.selected_inputs()
        self.assertTrue(self.run_job()[0].success)
        self.assertEqual(self.events, ['start', 'destroy'])
        self.assertFalse(self.registry._active)
        self.assertTrue(all(url.stops == 1 and url.closes == 1 for url in self.backend.urls))

    def test_job_cancel_and_initialization_error_release_every_grant(self):
        for failure in (None, 'construct', 'init'):
            with self.subTest(failure=failure):
                self.selected_inputs()
                self.assertFalse(self.run_job(failure, cancelled=True)[0].success)
                self.assertFalse(self.registry._active)

    def test_partial_authorization_reports_failure_without_engine_access(self):
        self.registry.remember(self.sub)
        results = []
        job = controller.SyncController(onError=lambda *args: None,
                                       onJobEnd=lambda task, status, result: results.append(result))
        with patch('subsync.synchro.synchronizer.Synchronizer') as engine:
            job._runTask(self.fake_task(), None, True)
        self.assertFalse(results[0].success)
        engine.assert_not_called()
        self.assertFalse(self.registry._active)

    def test_destroy_error_still_releases_both_input_grants(self):
        self.selected_inputs()
        with self.assertRaisesRegex(RuntimeError, 'destruction failed'):
            self.run_job('destroy')
        self.assertFalse(self.registry._active)

    def test_error_callback_cannot_bypass_engine_and_scope_cleanup(self):
        self.selected_inputs()
        def failed_error_handler(*args):
            raise RuntimeError('error callback failed')
        job = controller.SyncController(onError=failed_error_handler)
        with patch('subsync.synchro.synchronizer.Synchronizer', self.fake_engine('init')):
            with self.assertRaisesRegex(RuntimeError, 'error callback failed'):
                job._runTask(self.fake_task(), None, True)
        self.assertIn('destroy', self.events)
        self.assertFalse(self.registry._active)
        self.assertTrue(all(url.stops == 1 and url.closes == 1 for url in self.backend.urls))

    def test_missing_status_finishes_interactive_failure_and_unlocks(self):
        window = MagicMock()
        window.startTime = time.monotonic()
        window.onJobUpdate.side_effect = lambda *args: SyncWin.onJobUpdate.__wrapped__(window, *args)
        with patch.dict(syncwin.__dict__, {'_': lambda value: value}):
            SyncWin.onJobEnd.__wrapped__(window, self.fake_task(), None,
                                        controller.SyncJobResult(False, False, None))
        window.m_buttonSave.Enable.assert_not_called()
        window.m_textStatus.SetLabel.assert_called_with("Couldn't synchronize")
        window.suspendBlocker.unlock.assert_called_once()

    def test_revoked_output_directory_can_be_reselected(self):
        self.registry.remember(self.root, directory=True, write=True)
        self.backend.data[next(iter(self.backend.data))]['allowed'] = False
        def reselect(*args, **kwargs):
            self.registry.remember(self.root, directory=True, write=True)
            return str(self.root)
        with patch.dict(filedlg.__dict__, {'_': lambda value: value}), \
                patch.object(filedlg, 'is_appstore_build', return_value=True), \
                patch.object(filedlg, 'showDirectoryDlg', side_effect=reselect) as picker:
            self.assertEqual(filedlg.ensureOutputDirectory(None, str(self.root)), str(self.root))
        picker.assert_called_once()
        with self.registry.acquire(self.root / 'new.srt', write=True):
            pass

    def test_revoked_yaml_file_grant_can_be_replaced_by_selected_parent(self):
        self.registry.remember(self.sub)
        self.backend.data[next(iter(self.backend.data))]['allowed'] = False
        def reselect(*args, **kwargs):
            self.registry.remember(self.root, directory=True)
            return str(self.root)
        with patch.dict(filedlg.__dict__, {'_': lambda value: value}), \
                patch.object(filedlg, 'is_appstore_build', return_value=True), \
                patch.object(filedlg, 'showDirectoryDlg', side_effect=reselect) as picker:
            self.assertTrue(filedlg.authorizeTaskData(None, [{'sub': {'path': str(self.sub)}}]))
        picker.assert_called_once()
        self.assertEqual(len(self.registry._entries), 1)

    def test_batch_remap_preserves_literal_braces_in_folder_and_filename(self):
        sub = types.SimpleNamespace(path=str(self.root / 'input {notes}.hr.srt'), no=0, lang='hrv')
        ref = types.SimpleNamespace(path=str(self.ref), no=0, lang='eng')
        task = types.SimpleNamespace(sub=sub, ref=ref,
            out=OutputFile(path='{sub_dir}/{sub_name}.synced.srt'))
        task.getOutputPath = lambda: task.out.getPath(sub, ref)
        window = MagicMock()
        window.m_items.getTasks.return_value = [task]
        selected = str(self.root / 'output {selected}')
        with patch.object(batchwin.validator, 'validateTasks'), \
                patch('subsync.macos.mode.is_appstore_build', return_value=True), \
                patch.object(batchwin.filedlg, 'ensureOutputDirectory', return_value=selected), \
                patch.object(batchwin.assetsdlg, 'validateAssets', return_value=False):
            BatchWin.start(window)
        self.assertEqual(task.getOutputPath(), str(Path(selected) / 'input {notes}.hr.synced.srt'))

    def test_yaml_paths_do_not_grant_access_to_referenced_files(self):
        path = self.root / 'tasks.yaml'
        path.write_text('- sub:\n    path: ' + str(self.sub) + '\n')
        self.registry.remember(path)
        with self.assertRaises(access.FileAccessError):
            task_module.SyncTaskList.load(path)
        self.assertFalse(self.registry._active)

    def test_yaml_authorization_cancel_preserves_no_partial_tasks(self):
        path = self.root / 'tasks.yaml'
        path.write_text('- sub:\n    path: ' + str(self.sub) + '\n')
        self.registry.remember(path)
        self.assertIsNone(task_module.SyncTaskList.load(path, authorize=lambda data: False))
        self.assertFalse(self.registry._active)

    def test_output_directory_grant_preserves_collision_avoidance(self):
        output = self.root / 'out'
        output.mkdir()
        original = output / 'result.srt'
        original.write_text('must remain unchanged')
        self.registry.remember(output, directory=True, write=True)
        subs = subtitle.Subtitles()
        subs.add(1, 2, 'private disposable subtitle')
        saved = subs.save(str(original))
        self.assertEqual(Path(saved).name, 'result.1.srt')
        self.assertEqual(original.read_text(), 'must remain unchanged')
        self.assertIn('private disposable subtitle', Path(saved).read_text())
        self.assertFalse(self.registry._active)


class DialogTests(unittest.TestCase):
    class Dialog:
        def __init__(self, path, result, wildcard='*.srt|*.srt'):
            self.path, self.result, self.wildcard = path, result, wildcard
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ShowModal(self): return self.result
        def GetPath(self): return self.path
        def GetWildcard(self): return self.wildcard
        def GetFilterIndex(self): return 0

    def test_public_save_keeps_legacy_extension_and_no_extra_prompt(self):
        settings = types.SimpleNamespace(lastdir='/tmp', set=lambda **kwargs: None)
        dialog = self.Dialog('/tmp/example', filedlg.wx.ID_OK)
        with patch.dict(filedlg.__dict__, {'_': lambda value: value}), \
                patch.object(filedlg, 'settings', return_value=settings), \
                patch.object(filedlg.wx, 'FileDialog', return_value=dialog), \
                patch.object(filedlg, 'is_appstore_build', return_value=False), \
                patch.object(filedlg, 'ensureOutputDirectory') as extra:
            self.assertEqual(filedlg.showSaveFileDlg(None), '/tmp/example.srt')
            extra.assert_not_called()

    def test_sandbox_save_cancelled_folder_does_not_return_output(self):
        settings = types.SimpleNamespace(lastdir='/old', set=lambda **kwargs: None)
        dialog = self.Dialog('/tmp/example', filedlg.wx.ID_OK)
        with patch.dict(filedlg.__dict__, {'_': lambda value: value}), \
                patch.object(filedlg, 'settings', return_value=settings), \
                patch.object(filedlg.wx, 'FileDialog', return_value=dialog), \
                patch.object(filedlg, 'is_appstore_build', return_value=True), \
                patch.object(filedlg, 'ensureOutputDirectory', return_value=None):
            self.assertIsNone(filedlg.showSaveFileDlg(None))
            self.assertEqual(settings.lastdir, '/old')

    def test_busy_dialog_timer_uses_integer_milliseconds(self):
        for seconds, expected in ((.1, 100), (.025, 25), (.00001, 1)):
            dialog = MagicMock()
            timer = MagicMock()
            with patch.object(busydlg.wx, 'Timer', return_value=timer):
                busydlg.BusyDlg.ShowModalWhile(dialog, lambda: True, seconds)
            timer.Start.assert_called_once_with(expected)
            self.assertIs(type(timer.Start.call_args.args[0]), int)


class StoreAssetsTests(unittest.TestCase):
    def manager(self):
        import threading
        manager = object.__new__(asset_manager.AssetManager)
        manager._assets = {}
        manager._assetsLock = threading.RLock()
        manager.getAsset = MagicMock()
        return manager

    def test_store_catalog_allows_data_assets_and_never_app_updater(self):
        manager = self.manager()
        remote = {'speech/eng': {}, 'dict/eng-hrv': {},
                  'subsync/macos': {}, 'other/executable': {}}
        with patch.object(asset_manager, 'is_appstore_build', return_value=True), \
                patch.object(asset_manager.item, 'validateRemoteData', return_value=True):
            manager._updateAssetsRemoteData(remote)
            self.assertIsNone(manager.getSelfUpdaterAsset())
            self.assertIsNone(manager.runSelfUpdater())
        self.assertEqual({call.args[0] for call in manager.getAsset.call_args_list},
                         {'speech/eng', 'dict/eng-hrv'})
        self.assertEqual(set(remote), {'speech/eng', 'dict/eng-hrv',
                                      'subsync/macos', 'other/executable'})

    def test_public_catalog_retains_existing_asset_types(self):
        manager = self.manager()
        remote = {'speech/eng': {}, 'dict/eng-hrv': {}, 'subsync/macos': {}}
        with patch.object(asset_manager, 'is_appstore_build', return_value=False), \
                patch.object(asset_manager.item, 'validateRemoteData', return_value=True):
            manager._updateAssetsRemoteData(remote)
        self.assertEqual({call.args[0] for call in manager.getAsset.call_args_list}, set(remote))


if __name__ == '__main__':
    unittest.main()
