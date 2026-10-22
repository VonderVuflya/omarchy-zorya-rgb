"""Release updater tests: every filesystem mutation stays in a temporary XDG tree."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from zorya_rgb import updates


def release(version='0.3.0', **extra):
    return dict(tag_name='v'+version, draft=False, prerelease=False,
                html_url='https://github.com/VonderVuflya/omarchy-zorya-rgb/releases/tag/v'+version, **extra)


def source(path, version='0.2.0'):
    path.mkdir(parents=True, exist_ok=True)
    (path/'zorya_rgb').mkdir(exist_ok=True)
    (path/'zorya_rgb/__init__.py').write_text('__version__ = '+repr(version)+'\n')
    (path/'manifest.json').write_text(json.dumps({'id':'vondervuflya.zorya-rgb','version':version,'entryPoints':{'barWidget':'BarWidget.qml'}}))
    (path/'BarWidget.qml').write_text('// '+version)
    (path/'pyproject.toml').write_text('[project]\nname="omarchy-zorya-rgb"\nversion="'+version+'"\nrequires-python=">=3.11"\ndependencies=[]\n[project.optional-dependencies]\nhardware=["openrgb-python==0.3.6"]\n')
    (path/'bin').mkdir(exist_ok=True)
    (path/'bin/zorya-rgb').write_text('#!/bin/sh\n')


class UpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'data';self.plugin=self.root/'plugin';self.app=self.data/'app'
        source(self.plugin);source(self.app)
        self.env=patch.dict(os.environ, {'XDG_CACHE_HOME':str(self.root/'cache')});self.env.start();self.addCleanup(self.env.stop)
        self.paths=patch.object(updates,'_paths',return_value=(self.data,self.plugin,self.app));self.paths.start();self.addCleanup(self.paths.stop)
        self.fetch=patch.object(updates,'_fetch_release',return_value=release());self.fetch.start();self.addCleanup(self.fetch.stop)

    def test_only_newer_stable_release_is_available(self):
        self.assertTrue(updates.check(force=True)['update_available'])
        for version in ('0.2.0','0.1.99'):
            with patch.object(updates,'_fetch_release',return_value=release(version)):
                self.assertFalse(updates.check(force=True)['update_available'])

    def test_mixed_installation_never_downgrades_either_component_fresh_or_cached(self):
        for ahead, behind in ((self.app,self.plugin),(self.plugin,self.app)):
            source(ahead,'0.4.0');source(behind,'0.2.0')
            for force in (True,False):
                result=updates.check(force=force)
                self.assertFalse(result['update_available'])
                self.assertTrue(result['version_mismatch'])
                self.assertIn('older',result['hint'])
            with patch.object(updates,'_clone_release') as clone:
                self.assertFalse(updates.apply('v0.3.0')['ok']);clone.assert_not_called()

    def test_apply_rechecks_components_before_accepting_check_result(self):
        source(self.app,'0.4.0')
        with patch.object(updates,'check',return_value={'ok':True,'tag':'v0.3.0','update_available':True}),patch.object(updates,'_clone_release') as clone:
            self.assertFalse(updates.apply('v0.3.0')['ok']);clone.assert_not_called()

    def test_bad_release_metadata_is_a_nonfatal_error(self):
        for payload in ({},release('0.3.0-rc1'),dict(release(),draft=True),dict(release(),prerelease=True),dict(release(),html_url='https://evil.invalid')):
            with self.subTest(payload=payload),patch.object(updates,'_fetch_release',return_value=payload):
                result=updates.check(force=True)
                self.assertFalse(result['ok']);self.assertFalse(result['update_available'])

    def test_cache_success_and_network_failure_backoff(self):
        with patch.object(updates,'_fetch_release',side_effect=TimeoutError('timed out')) as fetch:
            self.assertFalse(updates.check()['ok']);self.assertFalse(updates.check()['ok']);self.assertEqual(fetch.call_count,1)
        with patch.object(updates,'_fetch_release',return_value=release()) as fetch:
            self.assertTrue(updates.check(force=True)['ok']);self.assertTrue(updates.check()['cached']);self.assertEqual(fetch.call_count,1)

    def test_expired_and_corrupt_caches_trigger_fresh_bounded_check(self):
        with patch.object(updates.time,'time',return_value=100000):updates.check()
        with patch.object(updates.time,'time',return_value=100000+updates.CACHE_TTL+1),patch.object(updates,'_fetch_release',return_value=release('0.4.0')):
            self.assertEqual(updates.check()['latest_version'],'0.4.0')
        updates._cache_path().write_text('{broken')
        self.assertTrue(updates.check()['ok'])
        (self.plugin/'manifest.json').write_text('{broken')
        result=updates.check(force=True)
        self.assertTrue(result['ok']);self.assertIsNone(result['plugin_version'])

    def test_copy_failure_preserves_both_installations(self):
        with patch.object(updates,'_clone_release',side_effect=self.clone),patch.object(updates,'_run'),patch.object(updates.shutil,'copytree',side_effect=OSError('disk full')):
            result=updates.apply('v0.3.0')
        self.assertFalse(result['ok'])
        for path in (self.plugin,self.app):
            self.assertEqual(json.loads((path/'manifest.json').read_text())['version'],'0.2.0')

    def test_second_directory_swap_failure_rolls_back_first(self):
        rename=Path.rename
        def fail(path,target):
            if path==self.app:raise OSError('app rename failed')
            return rename(path,target)
        with patch.object(Path,'rename',fail):result=self.apply()
        self.assertFalse(result['ok'])
        for path in (self.plugin,self.app):
            self.assertEqual(json.loads((path/'manifest.json').read_text())['version'],'0.2.0')

    def test_mismatched_runtime_and_plugin_are_reported(self):
        source(self.plugin,'0.3.0')
        result=updates.check(force=True)
        self.assertEqual(result['plugin_version'],'0.3.0');self.assertEqual(result['runtime_version'],'0.2.0')
        self.assertTrue(result['update_available'])

    def test_successful_update_prunes_old_backups_and_failed_copies_only_for_this_install(self):
        old_plugin=self.plugin.parent/'.plugin.before-update-.zorya-update-old'
        old_app=self.data/'.app.before-update-.zorya-update-old'
        failed_old=self.data/'.app.failed-update-.zorya-update-f1'
        failed_new=self.data/'.app.failed-update-.zorya-update-f2'
        unrelated=(self.data/'.app-backup-keep',self.data/'.other.before-update-x',self.data/'app.before-update-x',self.plugin.parent/'.plugin-keep')
        for path in (old_plugin,old_app,failed_old,failed_new,*unrelated):
            path.mkdir();(path/'marker').write_text('x')
        os.utime(failed_old,(1000,1000));os.utime(failed_new,(2000,2000))
        self.assertTrue(self.apply()['ok'])
        self.assertFalse(old_plugin.exists());self.assertFalse(old_app.exists())
        self.assertFalse(failed_old.exists());self.assertTrue(failed_new.exists())
        for path in unrelated:self.assertTrue(path.exists())
        for folder,prefix in ((self.plugin.parent,'.plugin.before-update-'),(self.data,'.app.before-update-')):
            self.assertEqual(len([p for p in folder.iterdir() if p.name.startswith(prefix)]),1)

    def clone(self,tag,destination):
        source(destination,'0.3.0')
        subprocess.run(['/usr/bin/git','init','-q',str(destination)],check=True)

    def apply(self,runner=None,verifier=None):
        with patch.object(updates,'_verify_runtime',side_effect=verifier),patch.object(updates,'_clone_release',side_effect=self.clone),patch.object(updates,'_run',side_effect=runner or (lambda argv,timeout=60: subprocess.CompletedProcess(argv,0,stdout='',stderr=''))):
            return updates.apply('v0.3.0')

    def test_apply_synchronizes_versions_preserves_state_and_git(self):
        state=self.data/'state.json';state.write_text('{"color":"#FFFFFF"}')
        calls=[]
        result=self.apply(lambda argv,timeout=60:calls.append(argv) or subprocess.CompletedProcess(argv,0,stdout='',stderr=''))
        self.assertTrue(result['ok'],result)
        self.assertTrue(result['reload_required'])
        self.assertEqual(json.loads((self.plugin/'manifest.json').read_text())['version'],'0.3.0')
        self.assertEqual(json.loads((self.app/'manifest.json').read_text())['version'],'0.3.0')
        self.assertEqual(state.read_text(),'{"color":"#FFFFFF"}')
        self.assertTrue((self.plugin/'.git').is_dir())
        self.assertEqual([p for p in self.plugin.parent.iterdir() if not p.name.startswith('.') and (p/'manifest.json').is_file()],[self.plugin])
        self.assertEqual([c for c in calls if c[0]=='systemctl'],[['systemctl','--user','restart','zorya-rgb.service'],['systemctl','--user','is-active','--quiet','zorya-rgb.service']])

    def test_release_mismatch_and_unsafe_tag_do_not_clone(self):
        with patch.object(updates,'_clone_release') as clone:
            for tag in ('v0.2.1','--upload-pack=evil','v0.3.0; touch /tmp/no'):
                self.assertFalse(updates.apply(tag)['ok'])
            clone.assert_not_called()

    def test_manifest_validator_failure_keeps_existing_install(self):
        calls=[]
        def validate(argv,timeout=60):
            calls.append(argv)
            if argv[:3]==['omarchy','plugin','validate']:
                raise subprocess.CalledProcessError(1,argv)
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
        result=self.apply(validate)
        self.assertFalse(result['ok'])
        self.assertFalse(any(argv[0]=='systemctl' for argv in calls))
        self.assertEqual(json.loads((self.plugin/'manifest.json').read_text())['version'],'0.2.0')

    def test_inactive_daemon_after_restart_rolls_back_and_hides_failed_copy(self):
        def inactive(argv,timeout=60):
            if 'is-active' in argv:raise subprocess.CalledProcessError(3,argv)
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
        result=self.apply(inactive)
        self.assertFalse(result['ok'])
        self.assertEqual(json.loads((self.app/'manifest.json').read_text())['version'],'0.2.0')
        self.assertEqual([p for p in self.plugin.parent.iterdir() if not p.name.startswith('.') and (p/'manifest.json').is_file()],[self.plugin])

    def test_wrong_runtime_after_restart_rolls_back_both_sources(self):
        def stale(version):raise ValueError('daemon still reports previous version')
        result=self.apply(verifier=stale)
        self.assertFalse(result['ok'])
        for path in (self.plugin,self.app):
            self.assertEqual(json.loads((path/'manifest.json').read_text())['version'],'0.2.0')

    def test_restart_failure_rolls_back_both_sources(self):
        def fail(argv,timeout=60):
            if argv[0]=='systemctl':raise subprocess.CalledProcessError(1,argv)
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
        result=self.apply(fail)
        self.assertFalse(result['ok'])
        for path in (self.plugin,self.app):self.assertEqual(json.loads((path/'manifest.json').read_text())['version'],'0.2.0')

    def test_bad_source_and_new_dependencies_do_not_replace_sources(self):
        for corrupt in ('manifest','dependencies'):
            def clone(tag,destination):
                self.clone(tag,destination)
                if corrupt=='manifest':(destination/'manifest.json').write_text('{}')
                else:
                    path=destination/'pyproject.toml';path.write_text(path.read_text().replace('dependencies=[]','dependencies=["new-package"]'))
            with patch.object(updates,'_clone_release',side_effect=clone):
                self.assertFalse(updates.apply('v0.3.0')['ok'])
            self.assertEqual(json.loads((self.app/'manifest.json').read_text())['version'],'0.2.0')

    def test_dirty_git_installation_is_preserved(self):
        subprocess.run(['/usr/bin/git','init','-q',str(self.plugin)],check=True)
        subprocess.run(['/usr/bin/git','-C',str(self.plugin),'add','.'],check=True)
        subprocess.run(['/usr/bin/git','-C',str(self.plugin),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
        (self.plugin/'BarWidget.qml').write_text('// local work')
        with patch.object(updates,'_clone_release') as clone:
            self.assertFalse(updates.apply('v0.3.0')['ok']);clone.assert_not_called()
        self.assertEqual((self.plugin/'BarWidget.qml').read_text(),'// local work')

class ReleaseTransportTests(unittest.TestCase):
    def test_response_is_bounded_and_api_is_fixed_https(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=b'x'*(updates.MAX_RESPONSE+1)
        opener=MagicMock();opener.open.return_value=response
        with patch.object(updates.urllib.request,'build_opener',return_value=opener):
            with self.assertRaises(ValueError):updates._fetch_release_payload()
        response.read.assert_called_once_with(updates.MAX_RESPONSE+1)
        self.assertEqual(opener.open.call_args.args[0].full_url,updates.API)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],10)

    def test_entire_check_has_process_deadline_and_safe_fixed_code(self):
        with patch.object(updates.subprocess,'run',side_effect=subprocess.TimeoutExpired('python',15)) as run:
            with self.assertRaises(ValueError):updates._fetch_release()
        self.assertEqual(run.call_args.kwargs['timeout'],15)
        self.assertNotIn('shell',run.call_args.kwargs)
        self.assertIn('-I',run.call_args.args[0])

    def test_child_result_must_be_bounded_valid_json(self):
        for payload in (b'not json',b'x'*(updates.MAX_RESPONSE*6+1)):
            with patch.object(updates.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=payload,stderr=b'')):
                with self.assertRaises(ValueError):updates._fetch_release()
        with patch.object(updates.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=json.dumps(release()).encode(),stderr=b'')):
            self.assertEqual(updates._fetch_release()['tag_name'],'v0.3.0')

    def test_api_redirects_are_rejected(self):
        with self.assertRaises(ValueError):
            updates._NoRedirect().redirect_request(None,None,302,'redirect',{},'http://evil.invalid')

class RuntimeHealthTests(unittest.TestCase):
    def test_matching_version_succeeds_while_hardware_is_offline(self):
        with patch.object(updates,'_runtime_status',return_value={'runtime_version':'0.3.0','connected':False}):
            updates._verify_runtime('0.3.0')

    def test_starting_or_stale_daemon_is_retried_until_new_runtime_answers(self):
        responses=[ConnectionError('starting'),{'runtime_version':'0.2.0'}, {'runtime_version':'0.3.0'}]
        with patch.object(updates,'_runtime_status',side_effect=responses),patch.object(updates.time,'sleep'):
            updates._verify_runtime('0.3.0')

    def test_missing_stale_and_crashed_daemons_fail_with_bounded_retries(self):
        for response in ({}, {'runtime_version':'0.2.0'}, ConnectionError('crashed')):
            with self.subTest(response=response),patch.object(updates,'_runtime_status',side_effect=[response]*12) as status,patch.object(updates.time,'sleep'):
                with self.assertRaises(ValueError):updates._verify_runtime('0.3.0')
                self.assertLessEqual(status.call_count,12)

    def test_deadline_stops_retries_even_before_attempt_limit(self):
        with patch.object(updates.time,'monotonic',side_effect=[0,7]),patch.object(updates,'_runtime_status') as status:
            with self.assertRaises(ValueError):updates._verify_runtime('0.3.0')
            status.assert_not_called()
