import json
import tempfile
import unittest
from pathlib import Path
from zorya_rgb.state import StateStore, validate_patch, DEFAULT_STATE
from zorya_rgb.effects import frame

class StateTests(unittest.TestCase):
    def test_invalid_patch_rejected_without_mutation(self):
        for patch in ({'brightness':101},{'color':'red'},{'speed':float('nan')},{'effect':'bad'},{'on':1},{'devices':['x','x']},{'unknown':True},{'presets':[]}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_patch(DEFAULT_STATE,patch)
    def test_state_and_presets_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; store=StateStore(path)
            store.update({'color':'#ab12ef','brightness':30})
            preset=store.save_preset('Desk')
            store.update({'color':'#000000'})
            store.apply_preset(preset['id'])
            self.assertEqual(StateStore(path).snapshot()['color'],'#AB12EF')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            store.delete_preset(preset['id']); self.assertEqual(store.snapshot()['presets'],[])
    def test_saving_same_preset_name_updates_snapshot_and_preserves_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json'); first=store.save_preset('Desk')
            store.update({'brightness':33}); second=store.save_preset('Desk')
            self.assertEqual(first['id'],second['id']); self.assertEqual(len(store.snapshot()['presets']),1)
            store.update({'brightness':90}); store.apply_preset(first['id'])
            self.assertEqual(store.snapshot()['brightness'],33)
    def test_failed_write_does_not_change_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            store._write=lambda state: (_ for _ in ()).throw(OSError('disk full'))
            with self.assertRaises(OSError): store.update({'brightness':22})
            self.assertEqual(store.snapshot()['brightness'],100)
    def test_state_size_limit_preserves_previous_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json')
            store.update({'devices':['x'*250+str(i) for i in range(100)]})
            store.save_preset('One')
            with self.assertRaises(ValueError): store.save_preset('Two')
            self.assertEqual(len(store.snapshot()['presets']),1)
    def test_corrupt_state_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; path.write_text('{bad')
            store=StateStore(path); self.assertTrue(store.error)
            self.assertEqual(store.snapshot()['color'],'#FFFFFF')
    def test_effect_frames_are_deterministic_and_bounded(self):
        for effect in ('static','pulse','rainbow','gradient'):
            state=dict(DEFAULT_STATE,effect=effect,color='#FF0000',secondary_color='#0000FF')
            a=frame(state,8,1.5); self.assertEqual(a,frame(state,8,1.5))
            self.assertEqual(len(a),8)
            self.assertTrue(all(0<=v<=255 for c in a for v in c))
        self.assertEqual(frame(dict(DEFAULT_STATE,on=False),4,0),[(0,0,0)]*4)
        self.assertEqual(frame(dict(DEFAULT_STATE,color='#FF0000',brightness=50),1,0),[(128,0,0)])
    def test_gradient_and_rainbow_have_spatial_variation(self):
        self.assertGreater(len(set(frame(dict(DEFAULT_STATE,effect='gradient'),8,0))),1)
        self.assertGreater(len(set(frame(dict(DEFAULT_STATE,effect='rainbow'),8,0))),1)

if __name__=='__main__': unittest.main()
