"""Synthetic privacy fixtures; no real device identities or credentials."""
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from zorya_rgb import support


class SupportTests(unittest.TestCase):
    def test_scrubs_free_text_credentials_identities_and_networks(self):
        secrets = ['fixture-token-value', 'fixture-password-value', 'fixture-auth-value',
                   'fixture-serial-value', 'fixture-user', 'fixture-host',
                   '192.0.2.42', '2001:db8::42', '02:00:00:00:00:42',
                   '12345678-1234-4234-8234-123456789abc']
        text = ('token=fixture-token-value password: fixture-password-value\n'
                'Authorization:\n Bearer fixture-auth-value\n'
                'serial=fixture-serial-value /home/fixture-user/private/file\n'
                'fixture-user@fixture-host 192.0.2.42 2001:db8::42 '
                '02:00:00:00:00:42 12345678-1234-4234-8234-123456789abc '
                'driver 570.133.07')
        with patch('zorya_rgb.support.getpass.getuser', return_value='fixture-user'), patch('zorya_rgb.support.socket.gethostname', return_value='fixture-host'):
            clean = support.redact(text)
        for secret in secrets:
            self.assertNotIn(secret, clean)
        self.assertIn('570.133.07', clean)

    def test_report_partial_failures_allowlists_devices_and_saves_private_markdown(self):
        def rpc(payload, **kwargs):
            if payload['command'] == 'status':
                return {'connected': True, 'device_count': 1, 'presets': [{'name': 'private preset'}], 'error': None}
            return {'devices': [{'name': 'Synthetic RGB', 'id': 'fixture-private-id',
                                 'serial': 'fixture-private-serial', 'location': '192.0.2.42',
                                 'led_count': 12, 'modes': ['Direct'], 'selected': True}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=rpc):
            result = support.build_report(error='SDK timed out', operation='Apply color')
            self.assertTrue(result['ok'])
            body = result['body']
            for text in ('SDK timed out', 'Synthetic RGB', 'Reproduction', 'Expected', 'Actual', 'Unavailable'):
                self.assertIn(text, body)
            for secret in ('fixture-private-id', 'fixture-private-serial', 'private preset', '192.0.2.42'):
                self.assertNotIn(secret, body)
            path = Path(result['path'])
            self.assertEqual(path.read_text(), body)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(urlsplit(result['issue_url']).netloc, 'github.com')
            self.assertEqual(parse_qs(urlsplit(result['issue_url']).query)['body'][0], body)

    def test_issue_url_is_bounded_but_full_report_remains_available(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')):
            result = support.build_report(error='RGB fault 😿 ' * 1000, operation='Apply')
            self.assertLessEqual(len(result['issue_url'].encode()), 7500)
            self.assertTrue(result['issue_truncated'])
            short = parse_qs(urlsplit(result['issue_url']).query)['body'][0]
            self.assertIn('truncated', short.lower())
            self.assertGreater(len(result['body']), len(short))
            self.assertEqual(Path(result['path']).read_text(), result['body'])

    def test_probe_kills_excess_output_and_timeout(self):
        import sys
        result = support._probe([sys.executable, '-c', 'print("x" * 1000000)'], timeout=1, limit=512)
        self.assertLess(len(result), 600)
        self.assertIn('truncated', result)
        result = support._probe([sys.executable, '-c', 'import time; time.sleep(2)'], timeout=0.05)
        self.assertIn('timed out', result)

    def test_clipboard_uses_saved_report_without_arbitrary_input(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
            self.assertFalse(support.copy_report()['ok'])

    def test_sticky_traceback_is_kept_without_private_paths_or_context_fields(self):
        status = {'connected': True, 'last_error': {
            'operation': 'Apply', 'message': 'Transport failed', 'at': 123,
            'traceback': 'File "/home/fixture-user/project/driver.py", line 42\nValueError: token=fixture-token-value',
            'locals': {'password': 'fixture-private-value'}}}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=[status, {'devices': []}]):
            result = support.build_report()
        self.assertIn('Transport failed', result['body'])
        self.assertIn('ValueError', result['body'])
        self.assertIn('line 42', result['body'])
        for secret in ('fixture-user', 'fixture-token-value', 'fixture-private-value'):
            self.assertNotIn(secret, result['body'])

    def test_reports_managed_source_revisions_without_loading_private_config(self):
        def probe(argv, **kwargs):
            if 'rev-parse' in argv and 'hardware/openrgb/source' in ' '.join(argv):
                return '1234abcd5678'
            if 'rev-parse' in argv and 'hardware/lianli/source' in ' '.join(argv):
                return '9876fedc5432'
            return 'Unavailable'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', side_effect=probe), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')):
            body = support.build_report()['body']
        self.assertIn('OpenRGB managed source: 1234abcd5678', body)
        self.assertIn('Lian Li managed source: 9876fedc5432', body)

    def test_clipboard_copies_full_generated_report_instead_of_short_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            utility = directory / 'wl-copy'
            utility.write_text('#!/bin/sh\n/usr/bin/cat > "$FIXTURE_CLIPBOARD"\n')
            utility.chmod(0o700)
            clipboard = directory / 'clipboard'
            environment = {'HOME': tmp, 'PATH': tmp, 'XDG_STATE_HOME': tmp,
                           'FIXTURE_CLIPBOARD': str(clipboard)}
            with patch.dict(os.environ, environment), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')):
                report = support.build_report(error='RGB issue ' * 1500)
                self.assertTrue(support.copy_report()['ok'])
            self.assertEqual(clipboard.read_text(), report['body'])
            self.assertTrue(report['issue_truncated'])

    def test_report_removes_nonstandard_paths_and_whitespace_serials_from_preview_and_url(self):
        evidence = ('File "/mnt/private-work/driver.py", line 42, in apply\n'
                    'serial number ABCDEF123456; SN UVWXYZ654321\n'
                    'failed /srv/fixture-private/keys.json and /run/private-session/socket')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')):
            report = support.build_report(error=evidence)
        short = parse_qs(urlsplit(report['issue_url']).query)['body'][0]
        for body in (report['body'], short):
            for secret in ('/mnt/private-work', 'ABCDEF123456', 'UVWXYZ654321', '/srv/fixture-private', '/run/private-session'):
                self.assertNotIn(secret, body)
            self.assertIn('driver.py', body)
            self.assertIn('line 42', body)
            self.assertIn('in apply', body)

    def test_report_keeps_pci_model_and_active_kernel_driver(self):
        def probe(argv, **kwargs):
            if argv[0] == 'lspci':
                return '01:00.0 VGA compatible controller: Example RTX [1234:5678]\n\tKernel driver in use: nvidia\n\tKernel modules: nouveau, nvidia_drm, nvidia'
            return 'Unavailable'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', side_effect=probe), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')):
            body = support.build_report()['body']
        self.assertIn('Example RTX', body)
        self.assertIn('Kernel driver in use: nvidia', body)
        self.assertIn('Kernel modules: nouveau', body)

    def test_submission_pins_github_host_posts_full_reviewed_body_once_and_reuses_issue(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': '', 'GH_HOST': 'enterprise.example'}):
            body = '## Problem\n\nOperation: Apply color\n\n' + 'Full diagnostic evidence.\n' * 600
            support._save(body)
            fingerprint = hashlib.sha256(body.encode()).hexdigest()
            observed = []
            def create(argv, **kwargs):
                self.assertEqual(argv[1:6], ['issue', 'create', '--repo', 'https://github.com/VonderVuflya/omarchy-zorya-rgb', '--title'])
                snapshot = Path(argv[argv.index('--body-file') + 1])
                observed.append(snapshot.read_text())
                self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o600)
                self.assertEqual(kwargs['timeout'], 60)
                return {'started': True, 'exitcode': 0, 'timed_out': False, 'stdout': 'https://github.com/VonderVuflya/omarchy-zorya-rgb/issues/42\n', 'stderr': '', 'truncated': False}
            with patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'), patch.object(support, '_probe', side_effect=create):
                first = support.submit_report(fingerprint)
                second = support.submit_report(fingerprint)
            self.assertTrue(first['ok'])
            self.assertEqual(first['issue_url'], 'https://github.com/VonderVuflya/omarchy-zorya-rgb/issues/42')
            self.assertEqual(second['issue_url'], first['issue_url'])
            self.assertTrue(second['already_submitted'])
            self.assertEqual(observed, [body])

    def test_submission_rejects_tampered_or_unsafe_report_before_process(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
            path = Path(support._save('Original report'))
            fingerprint = hashlib.sha256(b'Original report').hexdigest()
            path.write_text('Tampered report')
            with patch.object(support, '_probe', side_effect=AssertionError('must not send')):
                self.assertFalse(support.submit_report(fingerprint)['ok'])
                path.write_text('Original report')
                path.chmod(0o644)
                self.assertFalse(support.submit_report(fingerprint)['ok'])
                self.assertFalse(support.submit_report('../../escape')['ok'])

    def test_submission_auth_failure_returns_browser_hint_without_receipt(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
            support._save('Report')
            fingerprint = hashlib.sha256(b'Report').hexdigest()
            with patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'), patch.object(support, '_probe', return_value={'started': True, 'exitcode': 4, 'timed_out': False, 'stdout': '', 'stderr': 'To get started with GitHub CLI, please run: gh auth login', 'truncated': False}):
                result = support.submit_report(fingerprint)
                repeated = support.submit_report(fingerprint)
            self.assertFalse(result['ok'])
            self.assertIn('gh auth login', result['error'])
            self.assertIn('browser', result['error'])
            self.assertIn('gh auth login', repeated['error'])
            self.assertFalse(list(support._report_path().parent.glob('submission-*.json')))

    def test_submission_timeout_does_not_automatically_retry_or_create_duplicate(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
            support._save('Report')
            fingerprint = hashlib.sha256(b'Report').hexdigest()
            attempts = []
            def timeout(*args, **kwargs):
                attempts.append(1)
                return {'started': True, 'exitcode': -9, 'timed_out': True, 'stdout': '', 'stderr': '', 'truncated': False}
            with patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'), patch.object(support, '_probe', side_effect=timeout):
                result = support.submit_report(fingerprint)
                repeated = support.submit_report(fingerprint)
            self.assertFalse(result['ok'])
            self.assertIn('Check GitHub', result['error'])
            self.assertFalse(repeated['ok'])
            self.assertEqual(attempts, [1])

    def test_preview_fingerprint_binds_full_body_and_checks_gh_without_auth_probe(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}), patch.object(support, '_probe', return_value='Unavailable'), patch('zorya_rgb.daemon.request', side_effect=OSError('offline')), patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'):
            report = support.build_report()
        self.assertEqual(report['fingerprint'], hashlib.sha256(report['body'].encode()).hexdigest())
        self.assertTrue(report['submit_available'])

    def test_submission_rejects_output_urls_outside_fixed_repository(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
            support._save('Report')
            fingerprint = hashlib.sha256(b'Report').hexdigest()
            with patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'), patch.object(support, '_probe', return_value={'started': True, 'exitcode': 0, 'timed_out': False, 'stdout': 'https://github.com/other/project/issues/42', 'stderr': '', 'truncated': False}):
                result = support.submit_report(fingerprint)
            self.assertFalse(result['ok'])
            self.assertNotIn('issue_url', result)
            self.assertIn('Check GitHub', result['error'])

    def test_empty_success_or_crash_output_retains_uncertain_receipt(self):
        import hashlib
        for exitcode in (0, -9):
            with self.subTest(exitcode=exitcode), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'HOME': tmp, 'PATH': ''}):
                support._save('Report')
                fingerprint = hashlib.sha256(b'Report').hexdigest()
                attempts = []
                def no_url(*args, **kwargs):
                    attempts.append(1)
                    return {'started': True, 'exitcode': exitcode, 'timed_out': False, 'stdout': '', 'stderr': '', 'truncated': False}
                with patch('zorya_rgb.support.shutil.which', return_value='/fixture/gh'), patch.object(support, '_probe', side_effect=no_url):
                    first = support.submit_report(fingerprint)
                    second = support.submit_report(fingerprint)
                self.assertIn('Check GitHub', first['error'])
                self.assertIn('Check GitHub', second['error'])
                self.assertEqual(attempts, [1])

    def test_detailed_probe_captures_exit_status_and_bounds_stderr(self):
        import sys
        result = support._probe([sys.executable, '-c', 'import sys; print("auth failed", file=sys.stderr); sys.exit(4)'], details=True)
        self.assertTrue(result['started'])
        self.assertEqual(result['exitcode'], 4)
        self.assertEqual(result['stdout'], '')
        self.assertIn('auth failed', result['stderr'])
        result = support._probe([sys.executable, '-c', 'import sys; sys.stderr.write("x" * 1000000)'], details=True, limit=512)
        self.assertTrue(result['truncated'])
        self.assertLessEqual(len(result['stderr']), 512)
