import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from zorya_rgb import hardware, setup


class SetupTests(unittest.TestCase):
    def test_usb_fixture_identifies_circle_and_both_dongles(self):
        devices = hardware.parse_usb('Bus 001 Device 002: ID 1cbe:a021 lianli-H2-1.0\nBus 001 Device 003: ID 0416:8040 SLV3TX_V1.6\nBus 001 Device 004: ID 0416:8041 SLV3RX_V1.6\nBus 002 Device 007: ID 1234:5678 Unknown')
        self.assertEqual([d['kind'] for d in devices], ['lianli-aio', 'lianli-tx', 'lianli-rx'])
        self.assertEqual(devices[0]['model'], 'HydroShift II LCD-C')

    def test_adoption_parses_systemd_show_and_requires_real_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'lianli-daemon-rgb'
            exe.write_text('#!/bin/sh\n'); exe.chmod(0o755)
            info = hardware.parse_service('Id=lianli-rgb.service\nActiveState=active\nExecStart={ path='+str(exe)+' ; argv[]='+str(exe)+' --rgb-only --radiator-fans --config /tmp/fans.json ; ignore_errors=no ; }\n')
            self.assertEqual(info['executable'], str(exe))
            self.assertTrue(info['preserves_cooling'])
            self.assertEqual(info['config'], '/tmp/fans.json')

    def test_dry_run_has_no_side_effects_and_never_contains_shell_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'zorya_rgb'
            report = setup.install('lianli', dry_run=True, data_home=root)
            self.assertTrue(report['ok'])
            self.assertFalse(root.exists())
            self.assertTrue(any('build-hardware.py' in ' '.join(a['argv']) for a in report['plan']))
            self.assertTrue(all(isinstance(a['argv'], list) for a in report['plan']))

    def test_invalid_component_rejected(self):
        self.assertFalse(setup.install('arbitrary;command', dry_run=True)['ok'])

    def test_resume_waits_for_restart_before_readiness(self):
        calls=[]
        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv,0,'','')
        def ready():
            self.assertIn('restart', calls[0]); calls.append(['ready']); return True
        result = setup.recovery(services=['zorya-lianli.service','zorya-openrgb.service'], run=runner, readiness=ready)
        self.assertTrue(result['ok'])
        self.assertEqual(calls[0], ['systemctl','--user','restart','zorya-lianli.service','zorya-openrgb.service'])
        self.assertEqual(calls[-1], ['ready'])

    def test_recovery_rejects_unmanaged_unit(self):
        self.assertFalse(setup.recovery(services=['ssh.service'])['ok'])

    def test_failed_restart_does_not_restore(self):
        def runner(argv, **kwargs):
            raise subprocess.CalledProcessError(1,argv,stderr='failed unit')
        result=setup.recovery(services=['zorya-openrgb.service'],run=runner,readiness=lambda:self.fail('readiness called'))
        self.assertFalse(result['ok'])
        self.assertIn('failed unit',result['error'])

    def test_migration_keeps_original_and_maps_legacy_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'legacy.json'; src.write_text(json.dumps({'color':'#123456','brightness':94,'enabled':False}))
            target=Path(folder)/'new.json'
            result=setup.migrate(source=src,destination=target)
            self.assertTrue(result['ok']); self.assertTrue(src.exists())
            self.assertEqual(json.loads(target.read_text())['on'],False)

    def test_uninstall_preserves_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'data';root.mkdir();(root/'state.json').write_text('{}')
            result=setup.uninstall_plugin(dry_run=True,data_home=root)
            self.assertTrue(result['preserves_state']);self.assertTrue((root/'state.json').exists())

if __name__=='__main__': unittest.main()

class SetupSafetyTests(unittest.TestCase):
    def test_duplicate_legacy_device_names_are_not_silently_merged(self):
        class Backend:
            def connect(self):return True
            def devices(self, selected):return [{'id':'one','name':'Fan'},{'id':'two','name':'Fan'}]
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'old.json';src.write_text(json.dumps({'devices':['Fan'],'color':'#ff0099'}))
            result=setup.migrate(source=src,destination=Path(folder)/'new.json',backend=Backend())
            self.assertTrue(result['ok'])
            self.assertEqual(result['state']['devices'],[])
            self.assertEqual(result['ambiguous_names'],['Fan'])

    def test_migration_rejects_invalid_brightness_without_creating_destination(self):
        class Backend:
            def connect(self):return False
            def devices(self,selected):return []
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'old.json';src.write_text(json.dumps({'brightness':200}))
            dst=Path(folder)/'new.json'
            result=setup.migrate(source=src,destination=dst,backend=Backend())
            self.assertFalse(result['ok']);self.assertFalse(dst.exists())

    def test_both_managed_sdk_endpoints_are_checked_after_restart(self):
        from unittest.mock import patch
        checked=[]
        def runner(argv,**kw):return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(setup,'_metadata',return_value={'hardware_units':['zorya-lianli.service','zorya-openrgb.service']}):
            result=setup.recovery(run=runner,probe=lambda port:checked.append(port) or True)
        self.assertTrue(result['ok']);self.assertEqual(checked,[6743,6742])

    def test_systemd_unit_argument_cannot_inject_another_directive(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('zorya_builder',setup.ROOT/'scripts/build-hardware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.assertRaises(ValueError):module.unit_quote('program\nExecStartPost=evil')

class PluginLayoutTests(unittest.TestCase):
    def test_installed_plugin_has_executable_regular_launcher_and_stable_sources(self):
        import importlib.util
        import os
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('zorya_installer',setup.ROOT/'scripts/install-plugin.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            with patch.dict(os.environ,{'HOME':str(home),'XDG_CONFIG_HOME':str(home/'config'),'XDG_DATA_HOME':str(home/'share')}),patch.object(module,'run',lambda *a,**k:None),patch.object(module.shutil,'which',return_value='/usr/bin/omarchy'):
                data=home/'share/omarchy-zorya-rgb'
                import contextlib,io
                with contextlib.redirect_stdout(io.StringIO()):module.install(data)
                launcher=home/'config/omarchy/plugins/vondervuflya.zorya-rgb/bin/zorya-rgb'
                self.assertTrue(launcher.is_file(),'QML relative launcher is missing')
                self.assertFalse(launcher.is_symlink(),'Omarchy forbids plugin symlinks')
                self.assertFalse(any(p.is_symlink() for p in launcher.parent.parent.rglob('*')))
                self.assertTrue(os.access(launcher,os.X_OK))
                self.assertIn('exec ',launcher.read_text())
                self.assertTrue((data/'app/scripts/build-hardware.py').exists())
                self.assertTrue((data/'app/manifest.json').exists())
                self.assertIn('sys.path.insert', (data/'bin/zorya-rgb').read_text())

class ServiceSelectionTests(unittest.TestCase):
    def test_adoption_disables_enabled_but_inactive_service(self):
        import importlib.util,os
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('zorya_lifecycle_builder',setup.ROOT/'scripts/build-hardware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        commands=[]
        old={'unit':'custom-openrgb.service','active':False,'available':True,'executable':'/usr/bin/openrgb','argv':['/usr/bin/openrgb'],'config':None}
        report={'components':{'lianli':{'detected':False}},'services':[old]}
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'HOME':folder,'XDG_CONFIG_HOME':folder+'/config'}),patch.object(module.hardware,'doctor',return_value=report),patch.object(module,'execute',lambda argv,**kw:commands.append([str(a) for a in argv])),patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
            import contextlib,io
            with contextlib.redirect_stdout(io.StringIO()):module.setup('openrgb',Path(folder)/'data',True)
            self.assertIn(['systemctl','--user','disable','--now','custom-openrgb.service'],commands)
            meta=json.loads((Path(folder)/'data/installation.json').read_text())
            self.assertFalse(meta['adopted'][0]['active']);self.assertTrue(meta['adopted'][0]['enabled'])

    def test_uninstall_restores_enablement_without_starting_formerly_inactive_unit(self):
        from unittest.mock import patch
        commands=[]
        def runner(argv,**kw):commands.append(argv);return subprocess.CompletedProcess(argv,0,'','')
        with tempfile.TemporaryDirectory() as folder,patch.object(Path,'home',return_value=Path(folder)),patch.object(setup,'_metadata',return_value={'adopted':[{'unit':'old-openrgb.service','enabled':True,'active':False}]}):
            with patch.object(setup,'_paths',return_value=(Path(folder),Path(folder),Path(folder))):
                self.assertTrue(setup.uninstall_plugin(run=runner)['ok'])
        self.assertIn(['systemctl','--user','enable','old-openrgb.service'],commands)
        self.assertFalse(any('start' in c and 'old-openrgb.service' in c for c in commands))

class PairingTests(unittest.TestCase):
    unbound='wireless-unbound:00:11:22:33:44:55'
    bound='wireless:00:11:22:33:44:55'

    def test_invalid_id_is_rejected_without_ipc(self):
        for identity in ('wireless:00:11:22:33:44:55','wireless-unbound:$(evil)','wireless-unbound:00:11:22','other'):
            result=setup.pair_device(identity,ipc=lambda *a,**k:self.fail('IPC called for malformed identity'))
            self.assertFalse(result['ok'])

    def test_unlisted_device_never_binds(self):
        calls=[]
        def ipc(method,params=None):calls.append((method,params));return []
        result=setup.pair_device(self.unbound,ipc=ipc)
        self.assertFalse(result['ok']);self.assertEqual(calls,[('ListDevices',None)])

    def test_pair_uses_literal_protocol_arguments_and_waits_for_bound_state(self):
        calls=[];lists=0
        def ipc(method,params=None):
            nonlocal lists
            calls.append((method,params))
            if method=='BindWirelessDevice':return {'message':'queued'}
            lists+=1
            return [{'device_id':self.unbound,'is_unbound_wireless':True}] if lists==1 else [{'device_id':self.bound,'is_unbound_wireless':False}]
        result=setup.pair_device(self.unbound,ipc=ipc)
        self.assertTrue(result['ok'])
        self.assertIn(('BindWirelessDevice',{'mac':'00:11:22:33:44:55'}),calls)

    def test_repeated_pair_is_safe_and_does_not_bind_again(self):
        calls=[]
        def ipc(method,params=None):calls.append(method);return [{'device_id':self.bound,'is_unbound_wireless':False}]
        result=setup.pair_device(self.unbound,ipc=ipc)
        self.assertTrue(result['already_paired']);self.assertEqual(calls,['ListDevices'])

    def test_ipc_failure_is_reported(self):
        def ipc(*args,**kwargs):raise OSError('daemon offline')
        self.assertIn('daemon offline',setup.pair_device(self.unbound,ipc=ipc)['error'])

    def test_queued_response_is_not_claimed_as_success_without_convergence(self):
        def ipc(method,params=None):return [{'device_id':self.unbound,'is_unbound_wireless':True}] if method=='ListDevices' else {'message':'queued'}
        result=setup.pair_device(self.unbound,ipc=ipc,timeout=0)
        self.assertFalse(result['ok']);self.assertIn('timed out',result['error'])

class LianLiIpcTests(unittest.TestCase):
    def test_private_socket_exchange_uses_newline_json(self):
        import socket,threading,os
        requests=[]
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder);path=runtime/'lianli-daemon.sock'
            server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            server.bind(str(path));path.chmod(0o600);server.listen(1)
            def respond():
                with server:
                    connection,_=server.accept()
                    with connection:
                        data=b''
                        while b'\n' not in data:data+=connection.recv(4096)
                        requests.append(json.loads(data))
                        connection.sendall(b'{"status":"ok","data":[]}\n')
            thread=threading.Thread(target=respond,daemon=True);thread.start()
            result=hardware._lianli_ipc('ListDevices',runtime_dir=runtime)
            thread.join(2)
            self.assertEqual(result,[]);self.assertEqual(requests,[{'method':'ListDevices'}])

    def test_non_socket_and_shared_runtime_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder);(runtime/'lianli-daemon.sock').write_text('not a socket')
            with self.assertRaises(PermissionError):hardware._lianli_ipc('ListDevices',runtime_dir=runtime)
            runtime.chmod(0o755)
            with self.assertRaises(PermissionError):hardware._lianli_ipc('ListDevices',runtime_dir=runtime)

    def test_symlink_runtime_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);actual=root/'real';actual.mkdir(mode=0o700)
            link=root/'link';link.symlink_to(actual)
            with self.assertRaises(PermissionError):hardware._lianli_ipc('ListDevices',runtime_dir=link)


class ResumeCoordinationTests(unittest.TestCase):
    def test_automatic_resume_does_not_race_bridge_self_restart(self):
        from unittest.mock import patch
        calls=[]
        def run(argv,**kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(setup,'_metadata',return_value={'hardware_units':['zorya-openrgb.service','zorya-lianli.service']}),patch.object(setup.time,'sleep'):
            result=setup.recovery(run=run,probe=lambda port:True)
        self.assertTrue(result['ok'])
        self.assertEqual(calls,[['systemctl','--user','restart','zorya-openrgb.service']])

    def test_empty_openrgb_scan_is_redetected_once_without_restarting_bridge(self):
        from unittest.mock import patch
        calls=[];probes=[]
        def run(argv,**kw):
            calls.append(argv);return subprocess.CompletedProcess(argv,0,'','')
        def probe(port):
            probes.append(port)
            return port!=6742 or len(calls)>1
        with patch.object(setup,'_metadata',return_value={'hardware_units':['zorya-openrgb.service','zorya-lianli.service']}),patch.object(setup.time,'sleep'):
            result=setup.recovery(run=run,probe=probe,timeout=0)
        self.assertTrue(result['ok'])
        self.assertEqual(calls,[['systemctl','--user','restart','zorya-openrgb.service']]*2)
        self.assertIn(6743,probes)

    def test_listening_sdk_with_zero_controllers_is_not_ready(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import sys
        closed=[]
        client=SimpleNamespace(devices=[],update=lambda:None,disconnect=lambda:closed.append(True))
        with patch.dict(sys.modules,{'openrgb':SimpleNamespace(OpenRGBClient=lambda **kw:client)}):
            self.assertFalse(setup._sdk_ready(6742))
        self.assertEqual(closed,[True])

    def test_partial_scan_is_redetected_once_when_selected_devices_are_missing(self):
        from unittest.mock import patch
        calls=[]
        def run(argv,**kw):
            calls.append(argv);return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(setup,'_metadata',return_value={'hardware_units':['zorya-openrgb.service','zorya-lianli.service']}),patch.object(setup.time,'sleep'):
            result=setup.recovery(run=run,probe=lambda port:True,readiness=lambda:len(calls)>1,timeout=0)
        self.assertTrue(result['ok'],'A partially populated SDK must trigger a real hardware rescan')
        self.assertEqual(calls,[['systemctl','--user','restart','zorya-openrgb.service']]*2)

    def test_empty_and_partial_discovery_share_one_redetection_budget(self):
        from unittest.mock import patch
        calls=[]
        def run(argv,**kw):
            calls.append(argv);return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(setup,'_metadata',return_value={'hardware_units':['zorya-openrgb.service','zorya-lianli.service']}),patch.object(setup.time,'sleep'):
            result=setup.recovery(run=run,probe=lambda port:port!=6742 or len(calls)>1,readiness=lambda:False,timeout=0)
        self.assertFalse(result['ok'])
        self.assertEqual(calls,[['systemctl','--user','restart','zorya-openrgb.service']]*2)
