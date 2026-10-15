import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zorya_rgb.cli import main
from zorya_rgb.state import StateStore

class CliTests(unittest.TestCase):
    def run_cli(self,args,**kwargs):
        out=io.StringIO()
        with contextlib.redirect_stdout(out): code=main(args,**kwargs)
        return code,json.loads(out.getvalue())
    def test_offline_status_and_devices_are_json_without_sdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            rpc=lambda payload:(_ for _ in ()).throw(FileNotFoundError('offline'))
            code,status=self.run_cli(['status'],rpc=rpc,store=store)
            self.assertEqual(code,0); self.assertFalse(status['connected']); self.assertEqual(status['color'],'#FFFFFF')
            code,devices=self.run_cli(['devices'],rpc=rpc,store=store); self.assertEqual(devices['devices'],[])
    def test_bad_json_and_unknown_arguments_have_json_error(self):
        for args in (['set','--json','{bad'],['set','--json','[]'],['nonsense']):
            code,result=self.run_cli(args,rpc=lambda p:{'ok':True})
            self.assertEqual(code,1); self.assertTrue(result['error'])
    def test_valid_set_and_preset_forward_structured_arguments(self):
        captured=[]
        def rpc(payload): captured.append(payload); return {'ok':True,'error':None}
        self.run_cli(['set','--json','{"brightness":42}'],rpc=rpc)
        self.run_cli(['preset','save','Name; quoted'],rpc=rpc)
        self.assertEqual(captured,[{'command':'set','patch':{'brightness':42}},{'command':'preset_save','name':'Name; quoted'}])
    def test_pair_calls_setup_callback_with_exact_device_id(self):
        with patch('zorya_rgb.setup.pair_device',create=True,return_value={'ok':True,'error':None}) as callback:
            code,result=self.run_cli(['pair','--device','wireless:AA:BB:CC:DD:EE:FF'])
            self.assertEqual(code,0); callback.assert_called_once_with('wireless:AA:BB:CC:DD:EE:FF')
            self.assertTrue(result['ok'])
    def test_pair_missing_or_empty_device_is_a_json_error(self):
        with patch('zorya_rgb.setup.pair_device',create=True) as callback:
            for args in (['pair'],['pair','--device',''],['pair','--device','x'*257]):
                code,result=self.run_cli(args)
                self.assertEqual(code,1); self.assertTrue(result['error'])
            callback.assert_not_called()
    def test_offline_set_does_not_mutate_saved_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            code,result=self.run_cli(['set','--json','{"color":"#FF0000"}'],store=store,rpc=lambda p:(_ for _ in ()).throw(FileNotFoundError()))
            self.assertEqual(code,1); self.assertEqual(store.snapshot()['color'],'#FFFFFF')

if __name__=='__main__': unittest.main()
