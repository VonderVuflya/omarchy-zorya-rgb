import tempfile
from pathlib import Path
import unittest
from zorya_rgb.daemon import ZoryaDaemon
from zorya_rgb.state import StateStore


class ErrorCaptureTests(unittest.TestCase):
    def worker(self, unexpected):
        class Backend:
            connected=True
            error=None
            calls=0
            def devices(self, selected):return []
            def refresh(self):return True
            def close(self):pass
            def apply(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:
                    if unexpected:raise RuntimeError('USB worker fixture failure')
                    return {'errors':{'fixture':'Device rejected scene'}}
                return {'errors':{}}
        with tempfile.TemporaryDirectory() as folder:
            backend=Backend();daemon=ZoryaDaemon(store=StateStore(Path(folder)/'state.json'),backend=backend)
            class Wake:
                def clear(self):pass
                def wait(self, interval):
                    if backend.calls>=2:daemon.stopping.set()
            daemon.wake=Wake()
            daemon._hardware_loop()
            return daemon.status()

    def test_transient_device_failure_retained_after_success(self):
        status=self.worker(False)
        self.assertIsNone(status['error'])
        self.assertEqual(status['last_error']['message'],'Device rejected scene')
        self.assertIn('operation',status['last_error'])
        self.assertNotIn('last_error',StateStore().snapshot())

    def test_unexpected_exception_keeps_traceback_after_recovery(self):
        status=self.worker(True)
        self.assertIsNone(status['error'])
        self.assertIn('RuntimeError: USB worker fixture failure',status['last_error']['traceback'])
        self.assertIn('apply',status['last_error']['traceback'])

    def test_large_unicode_error_does_not_overflow_status_protocol(self):
        with tempfile.TemporaryDirectory() as folder:
            daemon=ZoryaDaemon(store=StateStore(Path(folder)/'state.json'))
            daemon.error='🔥'*4000
            daemon._remember_error('🔥'*4000,'hardware','🔥'*16000)
            import json
            self.assertLess(len(json.dumps(daemon.status()).encode()),40000)
            self.assertLess(len(json.dumps(daemon.dispatch({'command':'devices'})).encode()),10000)
            first=daemon.status()['last_error']['at']
            daemon._remember_error('🔥'*4000,'hardware','🔥'*16000)
            self.assertEqual(daemon.status()['last_error']['at'],first)

    def test_successful_first_connection_does_not_record_an_error(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            backend=Mock();backend.connected=False;backend.error=None;backend.devices.return_value=[]
            backend.connect.side_effect=lambda:setattr(backend,'connected',True)
            daemon=ZoryaDaemon(store=StateStore(Path(folder)/'state.json'),backend=backend)
            class Wake:
                def clear(self):pass
                def wait(self, interval):daemon.stopping.set()
            daemon.wake=Wake()
            daemon._hardware_loop()
            self.assertIsNone(daemon.status()['last_error'])
            self.assertIsNone(daemon.status()['error'])
