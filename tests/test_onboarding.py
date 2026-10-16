"""Guided setup never changes hardware during diagnosis or verification."""
import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

from zorya_rgb import cli


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        from zorya_rgb import onboarding
        self.module = onboarding
        self.report = {'ok': True, 'components': {'openrgb': {'available': True},
                       'lianli': {'detected': False}}, 'services': [], 'error': None}
        self.doctor = patch.object(onboarding.hardware, 'doctor', return_value=self.report).start()
        self.runtime = patch.object(onboarding, '_runtime_ready', return_value=True).start()
        self.probe = patch.object(onboarding, '_probe', side_effect=lambda port: {
            'ok': True, 'devices': [{'id': str(port), 'name': 'RGB', 'selected': False}], 'error': None}).start()
        self.rpc = patch.object(onboarding, 'request', return_value={'setup': {'daemon': True}}).start()
        self.install = patch.object(onboarding.setup, 'install').start()
        self.run = patch.object(onboarding.subprocess, 'run').start()
        self.addCleanup(patch.stopall)

    def steps(self, report):
        return {s['id']: s for s in report['steps']}

    def test_plan_is_read_only_and_preserves_empty_selection(self):
        report = self.module.plan()
        self.assertTrue(report['ready'])
        self.assertTrue(all(not d['selected'] for d in report['devices']))
        self.assertEqual(self.steps(report)['lianli']['status'], 'skipped')
        self.install.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(self.rpc.call_args.args, ({'command': 'status'},))

    def test_missing_private_runtime_is_needed(self):
        self.runtime.return_value = False
        report = self.module.plan()
        self.assertFalse(report['ready'])
        self.assertEqual(self.steps(report)['runtime']['status'], 'needed')

    def test_installed_binary_without_sdk_service_is_not_ready(self):
        self.probe.return_value = {'ok': False, 'devices': [], 'error': 'Connection refused'}
        self.probe.side_effect = None
        report = self.module.plan()
        self.assertEqual(self.steps(report)['openrgb']['status'], 'needed')
        self.assertFalse(report['ready'])

    def test_healthy_external_full_mode_lianli_is_reused(self):
        self.full_mode()
        report = self.module.plan()
        self.assertEqual(self.steps(report)['lianli']['status'], 'ready')
        self.assertTrue(self.module.run_step('lianli')['ok'])
        self.install.assert_not_called()
        self.run.assert_not_called()

    def full_mode(self):
        self.report['components']['lianli']['detected'] = True
        self.report['services'] = [{'unit': 'existing.service', 'available': True, 'active': True,
                                   'executable': '/usr/bin/lianli-daemon', 'argv': ['lianli-daemon']}]

    def test_lian_only_inventory_can_verify_without_installing_openrgb(self):
        self.full_mode()
        self.probe.side_effect = lambda port: dict(ok=port == 6743,
            devices=[{'id': 'lianli', 'name': 'Wireless', 'selected': False}] if port == 6743 else [],
            error=None if port == 6743 else 'No OpenRGB devices')
        report = self.module.plan()
        self.assertTrue(report['ready'])
        self.assertEqual(self.steps(report)['openrgb']['status'], 'skipped')
        self.assertFalse(self.steps(report)['openrgb']['required'])
        self.assertTrue(self.module.run_step('openrgb')['ok'])
        self.assertTrue(self.module.run_step('verify')['ok'])
        self.install.assert_not_called()

    def test_incompatible_full_mode_blocks_only_lianli(self):
        self.full_mode()
        self.probe.side_effect = lambda port: {'ok': port == 6742, 'devices': [], 'error': 'No compatible SDK'}
        report = self.module.plan()
        self.assertEqual(self.steps(report)['openrgb']['status'], 'ready')
        self.assertEqual(self.steps(report)['lianli']['status'], 'blocked')
        self.assertIn('cooling', report['error'])
        self.assertFalse(self.module.run_step('lianli')['ok'])
        self.install.assert_not_called()

    def test_retry_healthy_step_does_not_reinstall(self):
        self.assertTrue(self.module.run_step('openrgb')['ok'])
        self.assertTrue(self.module.run_step('runtime')['ok'])
        self.install.assert_not_called()
        self.run.assert_not_called()

    def test_unknown_step_is_rejected_without_diagnosis(self):
        self.assertFalse(self.module.run_step('all')['ok'])
        self.doctor.assert_not_called()
        self.install.assert_not_called()

    def test_runtime_only_install_captures_subprocess_output(self):
        self.runtime.return_value = False
        self.run.return_value = subprocess.CompletedProcess([], 0, 'installation log', '')
        result = self.module.run_step('runtime')
        self.assertTrue(result['ok'])
        args, kwargs = self.run.call_args
        self.assertIn('--runtime-only', [str(v) for v in args[0]])
        self.assertTrue(kwargs['capture_output'])
        self.install.assert_not_called()

    def test_install_only_requested_missing_component(self):
        self.probe.side_effect = lambda port: {'ok': False, 'devices': [], 'error': 'offline'}
        self.install.return_value = {'ok': True, 'error': None}
        self.assertTrue(self.module.run_step('openrgb')['ok'])
        self.install.assert_called_once_with('openrgb')
        self.run.assert_not_called()

    def test_verify_failure_is_actionable_and_does_not_write(self):
        self.probe.side_effect = lambda port: {'ok': False, 'devices': [], 'error': 'SDK timed out'}
        result = self.module.run_step('verify')
        self.assertFalse(result['ok'])
        self.assertIn('SDK timed out', result['error'])
        self.assertIn('hint', result)
        self.install.assert_not_called()
        self.run.assert_not_called()

    def test_cli_prints_one_json_report(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = cli.main(['onboarding', 'plan'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stream.getvalue())['ready'])
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = cli.main(['onboarding', 'run', '--step', 'verify'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stream.getvalue())['ok'])

    def test_offline_daemon_keeps_runtime_and_verification_pending(self):
        self.rpc.side_effect = FileNotFoundError('offline')
        report = self.module.plan()
        self.assertFalse(report['ready'])
        self.assertEqual(self.steps(report)['runtime']['status'], 'needed')
        self.assertFalse(self.module.run_step('verify')['ok'])

    def test_failed_runtime_install_returns_captured_error(self):
        self.runtime.return_value = False
        self.run.side_effect = subprocess.CalledProcessError(1, ['installer'], stderr='pip failed')
        result = self.module.run_step('runtime')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'pip failed')
        self.assertIn('hint', result)

    def test_probe_disconnect_error_does_not_hide_inventory_report(self):
        from unittest.mock import Mock
        from zorya_rgb.onboarding import _probe_local
        client = Mock()
        client.devices = []
        client.disconnect.side_effect = OSError('already closed')
        with patch('zorya_rgb.sdk_transport.connect_client', return_value=client):
            result = _probe_local(6742)
        self.assertFalse(result['ok'])
        self.assertIn('no devices', result['error'])

    def test_probe_reports_connection_failure(self):
        from zorya_rgb.onboarding import _probe_local
        with patch('zorya_rgb.sdk_transport.connect_client', side_effect=TimeoutError('bounded SDK deadline')):
            result = _probe_local(6742)
        self.assertFalse(result['ok'])
        self.assertIn('bounded SDK deadline', result['error'])

    def test_probe_closes_without_hardware_color_or_selection_writes(self):
        from unittest.mock import Mock
        from zorya_rgb.onboarding import _probe_local
        client = Mock()
        client.devices = []
        with patch('zorya_rgb.sdk_transport.connect_client', return_value=client):
            result = _probe_local(6742)
        self.assertFalse(result['ok'])
        client.disconnect.assert_called_once()
        self.assertEqual([c[0] for c in client.mock_calls], ['disconnect'])


class RuntimeInstallerTests(unittest.TestCase):
    def test_runtime_install_leaves_plugin_and_hardware_untouched(self):
        import importlib.util
        import os
        from pathlib import Path
        import tempfile
        source = Path(__file__).resolve().parents[1]/'scripts/install-plugin.py'
        spec = importlib.util.spec_from_file_location('runtime_installer', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root/'checkout'
            (checkout/'systemd').mkdir(parents=True)
            (checkout/'manifest.json').write_text('{"id":"test.zorya"}')
            (checkout/'systemd/zorya-rgb.service.in').write_text('ExecStart=@ZORYA_LAUNCHER@')
            with patch.object(module, 'ROOT', checkout), patch.object(module, 'run') as run, \
                 patch.object(Path, 'home', return_value=root), \
                 patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root/'config')}), \
                 contextlib.redirect_stdout(io.StringIO()):
                module.install(root/'data', runtime_only=True)
            calls = [[str(arg) for arg in call.args[0]] for call in run.call_args_list]
            self.assertTrue(any('pip' in args for args in calls))
            self.assertTrue(any('zorya-rgb.service' in args for args in calls))
            self.assertFalse(any('build-hardware.py' in ' '.join(args) for args in calls))
            self.assertFalse(any(args[0] in ('omarchy', 'omarchy-shell') for args in calls))
            self.assertFalse((root/'config/omarchy/plugins/test.zorya').exists())


if __name__ == '__main__':
    unittest.main()
