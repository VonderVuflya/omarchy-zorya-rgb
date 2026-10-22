"""Hardware build script tests: git, pacman and metadata are mocked or confined to a temporary tree."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('build_hardware', ROOT/'scripts/build-hardware.py')
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

PIN = build.PINS['openrgb'][1]


def completed(argv, returncode=0, stdout=''):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr='')


class ArchDependencyTests(unittest.TestCase):
    GROUPS = {'base-devel': ['gcc', 'make']}

    def setUp(self):
        self.calls = []
        self.tools = {'git', 'make', 'cc', 'pkg-config', 'gcc'}
        self.installed = set(build.PACKAGES['arch']) - {'base-devel', 'clang', 'rustup'} | {'gcc', 'make', 'systemd', 'python'}
        for patcher in (
            patch.object(build.shutil, 'which', side_effect=self.which),
            patch.object(build.subprocess, 'run', side_effect=self.fake_run),
            patch.object(build, 'execute', side_effect=self.execute),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def which(self, name):
        if name == 'pacman':
            return '/usr/bin/pacman'
        if name == 'pkexec':
            return '/usr/bin/pkexec'
        return '/usr/bin/'+name if name in self.tools else None

    def fake_run(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[0] == 'pacman' and argv[1] == '-Qq':
            return completed(argv, 0 if argv[2] in self.installed else 1)
        if argv[0] == 'pacman' and argv[1] == '-Sgq':
            members = self.GROUPS.get(argv[2])
            return completed(argv, 0 if members else 1, '\n'.join(members or []) + '\n')
        return completed(argv, 0)

    def execute(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[:3] == ['pkexec', 'pacman', '-S']:
            self.tools.update({'rustup', 'cargo', 'clang'})

    def install_calls(self):
        return [c for c in self.calls if c[:2] == ['pkexec', 'pacman']]

    def test_only_missing_packages_are_requested_and_groups_are_expanded(self):
        self.installed -= {'rustup', 'clang'}
        build.dependencies('lianli')
        self.assertEqual(self.install_calls(), [['pkexec', 'pacman', '-S', '--needed', '--noconfirm', 'rustup', 'clang']])

    def test_base_devel_members_are_checked_instead_of_the_group_name(self):
        self.installed -= {'rustup', 'clang', 'gcc'}
        build.dependencies('lianli')
        self.assertEqual(sorted(self.install_calls()[0][5:]), ['clang', 'gcc', 'rustup'])
        self.assertNotIn('base-devel', self.install_calls()[0])

    def test_core_packages_are_not_part_of_the_install_list(self):
        self.assertNotIn('systemd', build.PACKAGES['arch'])
        self.assertNotIn('python', build.PACKAGES['arch'])

    def test_missing_core_package_is_reported_without_installing(self):
        self.installed -= {'systemd', 'rustup'}
        with self.assertRaisesRegex(RuntimeError, 'systemd'):
            build.dependencies('lianli')
        self.assertEqual(self.install_calls(), [])

    def test_no_pacman_call_when_every_package_is_present_but_a_tool_is_not_on_path(self):
        self.installed |= {'rustup', 'clang'}
        with self.assertRaisesRegex(RuntimeError, 'Still missing'):
            build.dependencies('lianli')
        self.assertEqual(self.install_calls(), [])


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)/'source'
        self.calls = []
        self.head_valid = False
        for patcher in (
            patch.object(build, 'execute', side_effect=lambda argv, **kw: self.calls.append([str(a) for a in argv])),
            patch.object(build, 'capture', return_value=PIN),
            patch.object(build.subprocess, 'run', side_effect=self.fake_run),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_run(self, argv, **kwargs):
        if 'rev-parse' in argv:
            return completed(argv, 0 if self.head_valid else 128)
        if 'get-url' in argv:
            return completed(argv, 1)
        return completed(argv, 0)

    def test_fresh_directory_is_initialized_and_fetched_at_the_pin(self):
        build.checkout('openrgb', self.target)
        self.assertEqual(self.calls[0], ['git', 'init', str(self.target)])
        self.assertIn(['git', '-C', str(self.target), 'fetch', '--depth=1', 'origin', PIN], self.calls)
        self.assertIn(['git', '-C', str(self.target), 'checkout', '--detach', PIN], self.calls)

    def test_git_dir_without_valid_head_is_refetched_not_rejected(self):
        (self.target/'.git').mkdir(parents=True)
        build.checkout('openrgb', self.target)
        self.assertFalse(any(c[:2] == ['git', 'init'] for c in self.calls))
        self.assertIn(['git', '-C', str(self.target), 'fetch', '--depth=1', 'origin', PIN], self.calls)
        self.assertIn(['git', '-C', str(self.target), 'checkout', '--detach', PIN], self.calls)

    def test_valid_head_is_not_refetched(self):
        (self.target/'.git').mkdir(parents=True)
        self.head_valid = True
        build.checkout('openrgb', self.target)
        self.assertFalse(any('fetch' in c for c in self.calls))

    def test_pin_mismatch_still_fails_for_a_valid_checkout(self):
        (self.target/'.git').mkdir(parents=True)
        self.head_valid = True
        with patch.object(build, 'capture', return_value='0' * 40):
            with self.assertRaisesRegex(RuntimeError, 'pin mismatch'):
                build.checkout('openrgb', self.target)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.path = self.data/'installation.json'

    def test_missing_metadata_defaults_to_empty_inventory(self):
        self.assertEqual(build.read_metadata(self.path), {'hardware_units': [], 'adopted': []})

    def test_corrupt_metadata_is_reported_and_left_in_place(self):
        self.path.write_text('{broken')
        with self.assertRaisesRegex(RuntimeError, 'installation.json'):
            build.read_metadata(self.path)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_non_utf8_metadata_is_reported_as_corrupt(self):
        self.path.write_bytes(b'\xff\xfe\x00')
        with self.assertRaisesRegex(RuntimeError, 'Corrupt'):
            build.read_metadata(self.path)

    def test_write_is_atomic_private_and_leaves_no_temporary_files(self):
        build.write_metadata(self.path, {'hardware_units': ['zorya-openrgb.service']})
        self.assertEqual(json.loads(self.path.read_text()), {'hardware_units': ['zorya-openrgb.service']})
        self.assertEqual(oct(self.path.stat().st_mode & 0o777), '0o600')
        self.assertEqual([p.name for p in self.data.iterdir()], ['installation.json'])

    def test_failed_replace_keeps_previous_metadata_and_removes_temporary_file(self):
        self.path.write_text('{"hardware_units": []}')
        with patch.object(build.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                build.write_metadata(self.path, {'hardware_units': ['new']})
        self.assertEqual(self.path.read_text(), '{"hardware_units": []}')
        self.assertEqual([p.name for p in self.data.iterdir()], ['installation.json'])

    def test_write_flushes_to_disk_before_replacing(self):
        with patch.object(build.os, 'fsync', wraps=os.fsync) as fsync:
            build.write_metadata(self.path, {})
        fsync.assert_called_once()


if __name__ == '__main__':
    unittest.main()
