import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from zorya_rgb.daemon import ZoryaDaemon, request, SleepDetector
from zorya_rgb.state import StateStore

class Backend:
    def __init__(self): self.connected=False; self.error=None; self.applied=[]
    def connect(self): self.connected=True; return True
    def close(self): self.connected=False
    def refresh(self): return self.connected
    def devices(self,selected): return [{'id':'test','name':'Fake','modes':['Direct'],'led_count':1,'location':'USB','selected':'test' in selected}]
    def apply(self,state,elapsed,force=False): self.applied.append(state); return {'errors':{},'applied':True}

class DaemonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); root=Path(self.tmp.name)
        self.backend=Backend(); self.daemon=ZoryaDaemon(store=StateStore(root/'state.json'),backend=self.backend,socket_path=root/'runtime'/'socket',recovery=lambda **kwargs:{'ok':True})
        self.thread=threading.Thread(target=self.daemon.serve_forever); self.thread.start()
        for _ in range(100):
            if self.daemon.socket_path.exists(): break
            time.sleep(.01)
    def tearDown(self):
        self.daemon.stop(); self.thread.join(3); self.tmp.cleanup()
    def call(self,command,**kwargs): return request({'command':command,**kwargs},self.daemon.socket_path)
    def test_socket_permissions_and_cached_status(self):
        self.assertEqual(self.daemon.socket_path.stat().st_mode&0o777,0o600)
        status=self.call('status'); self.assertIn('connected',status); self.assertIn('presets',status)
        self.assertIn('devices',self.call('devices'))
    def test_invalid_atomic_update_and_valid_worker_apply(self):
        error=self.call('set',patch={'color':'#FF0000','brightness':101}); self.assertTrue(error['error'])
        self.assertEqual(self.call('status')['color'],'#FFFFFF')
        reply=self.call('set',patch={'color':'#123456','devices':['test']}); self.assertEqual(reply['color'],'#123456')
        for _ in range(100):
            if any(s['color']=='#123456' for s in self.backend.applied): break
            time.sleep(.01)
        self.assertTrue(any(s['color']=='#123456' for s in self.backend.applied))
    def test_preset_roundtrip_over_socket(self):
        self.call('set',patch={'brightness':42}); saved=self.call('preset_save',name='Night')
        identity=saved['presets'][0]['id']; self.call('set',patch={'brightness':80})
        self.assertEqual(self.call('preset_apply',id=identity)['brightness'],42)
        self.assertEqual(self.call('preset_delete',id=identity)['presets'],[])
    def test_second_daemon_does_not_unlink_live_socket(self):
        other=ZoryaDaemon(store=self.daemon.store,backend=Backend(),socket_path=self.daemon.socket_path)
        with self.assertRaises(RuntimeError): other.serve_forever()
        self.assertIn('color',self.call('status'))
    def test_bad_json_is_reported_and_server_stays_available(self):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.connect(str(self.daemon.socket_path)); sock.sendall(b'{bad}\n')
            self.assertTrue(json.loads(sock.recv(4096))['error'])
        self.assertIn('color',self.call('status'))
    def test_hardware_apply_cannot_block_status_ipc(self):
        entered=threading.Event(); release=threading.Event()
        def slow(state,elapsed,force=False):
            entered.set(); release.wait(1); return {'errors':{}}
        self.backend.apply=slow
        self.call('restore'); self.assertTrue(entered.wait(1))
        start=time.monotonic(); self.call('status'); duration=time.monotonic()-start
        release.set(); self.assertLess(duration,.5)
    def test_recovery_calls_coordinator_before_backend_ready(self):
        order=[]
        def recover(readiness):
            order.append('coordinator'); self.assertFalse(self.backend.connected)
            readiness(); order.append('ready'); return {'ok':True}
        self.daemon.recovery=recover; self.daemon._recover()
        self.assertEqual(order,['coordinator','ready']); self.assertTrue(self.backend.connected)
    def test_readiness_waits_for_selected_inventory_without_reconnecting(self):
        self.daemon.store.update({'devices':['test','late']})
        self.backend.connected=True
        connects=[]; self.backend.connect=lambda: connects.append(True) or True
        self.assertFalse(self.daemon._ready())
        self.backend.devices=lambda selected:[{'id':'test'},{'id':'late'}]
        self.assertTrue(self.daemon._ready()); self.assertEqual(connects,[])
        self.daemon.store.update({'devices':[]})
        self.backend.devices=lambda selected:[]
        self.assertTrue(self.daemon._ready())
    def test_sleep_detector_ignores_running_time_gap(self):
        d=SleepDetector(); self.assertFalse(d.check(10,10)); self.assertFalse(d.check(30,30))
        self.assertTrue(d.check(40,100)); self.assertFalse(d.check(41,101))

if __name__=='__main__': unittest.main()

class RecoveryBarrierTests(unittest.TestCase):
    def test_failed_resume_blocks_apply_then_recovers_without_restarting_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend=Backend(); store=StateStore(Path(tmp)/'state.json')
            store.update({'devices':['test','late']})
            coordinations=[]
            def coordinator(readiness):
                coordinations.append(True); readiness()
                return {'ok':False,'error':'selected device readiness timeout'}
            daemon=ZoryaDaemon(store=store,backend=backend,recovery=coordinator)
            with self.assertRaises(RuntimeError): daemon._recover()
            thread=threading.Thread(target=daemon._hardware_loop); thread.start()
            try:
                time.sleep(.15)
                self.assertEqual(backend.applied,[])
                backend.devices=lambda selected:[{'id':'test'},{'id':'late'}]
                daemon._next_recovery=0; daemon.wake.set()
                for _ in range(100):
                    if backend.applied: break
                    time.sleep(.01)
                self.assertTrue(backend.applied); self.assertEqual(len(coordinations),1)
            finally:
                daemon.stop(); thread.join(2)

    def test_missing_device_does_not_block_healthy_devices_after_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend=Backend(); store=StateStore(Path(tmp)/'state.json')
            store.update({'devices':['test','late']})
            daemon=ZoryaDaemon(store=store,backend=backend,recovery=lambda **kw:{'ok':False,'error':'restart timeout'})
            with self.assertLogs('zorya_rgb.daemon',level='INFO') as events:
                with self.assertRaises(RuntimeError): daemon._recover()
            self.assertTrue(any('recovery failed' in line.lower() for line in events.output))
            daemon._recovery_deadline=0; daemon._next_recovery=0
            thread=threading.Thread(target=daemon._hardware_loop); thread.start()
            try:
                for _ in range(100):
                    if backend.applied: break
                    time.sleep(.01)
                self.assertTrue(backend.applied)
                self.assertFalse(daemon.recovery_pending)
                self.assertEqual(daemon.status()['missing_devices'],['late'])
            finally: daemon.stop(); thread.join(2)
