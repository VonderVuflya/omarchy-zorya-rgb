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


class TolerantLoadTests(unittest.TestCase):
    def store(self,content):
        directory=tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        path=Path(directory.name)/'state.json'; path.write_text(content if isinstance(content,str) else json.dumps(content))
        return path,StateStore(path)

    def test_unknown_key_and_effect_from_newer_release_keep_presets(self):
        preset={'id':'a','name':'Evening','state':dict(DEFAULT_STATE,color='#112233',effect='aurora',glow=3)}
        path,store=self.store(dict(DEFAULT_STATE,color='#00FF00',effect='aurora',future_key=1,presets=[preset]))
        state=store.snapshot()
        self.assertEqual(state['color'],'#00FF00'); self.assertEqual(state['effect'],'static')
        self.assertEqual([p['name'] for p in state['presets']],['Evening'])
        self.assertEqual(state['presets'][0]['state']['color'],'#112233'); self.assertIsNone(store.error)

    def test_one_invalid_preset_is_dropped_and_others_kept(self):
        good={'id':'a','name':'Good','state':dict(DEFAULT_STATE)}
        path,store=self.store(dict(DEFAULT_STATE,presets=[good,{'id':5},{'id':'a','name':'Dup','state':{}}]))
        self.assertEqual([p['name'] for p in store.snapshot()['presets']],['Good'])
        self.assertIn('2 saved scenes',store.error)

    def test_corrupt_file_is_kept_aside_before_first_write(self):
        path,store=self.store('{not json')
        self.assertIn('Cannot read saved state',store.error); self.assertEqual(path.read_text(),'{not json')
        store.update({'color':'#FF0000'})
        backups=list(path.parent.glob('state.json.corrupt-*'))
        self.assertEqual(len(backups),1); self.assertEqual(backups[0].read_text(),'{not json')
        self.assertEqual(json.loads(path.read_text())['color'],'#FF0000')

    def test_set_commands_stay_strict(self):
        path,store=self.store(dict(DEFAULT_STATE))
        with self.assertRaises(ValueError): store.update({'future_key':1})
        with self.assertRaises(ValueError): store.update({'effect':'aurora'})
