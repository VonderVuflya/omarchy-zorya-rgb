import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class RuntimeStabilityTests(unittest.TestCase):
    def test_runtime_uses_resolved_system_python_and_copies(self):
        from zorya_rgb import runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); data=root/'data';data.mkdir()
            calls=[]
            runtime.prepare(data,root/'app',lambda args,timeout=600:calls.append([str(x) for x in args]))
            create=next(c for c in calls if 'venv' in c)
            self.assertEqual(create[0],str(Path('/usr/bin/python3').resolve()))
            self.assertIn('--copies',create)
            self.assertIn('-I',create)

    def test_old_symlinked_environment_is_preserved_and_restored_on_failure(self):
        from zorya_rgb import runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';(data/'venv/bin').mkdir(parents=True)
            outside=root/'managed-python';outside.write_text('external interpreter unchanged')
            (data/'venv/bin/python').symlink_to(outside)
            def run(args,timeout=600):
                args=[str(x) for x in args]
                if 'venv' in args:
                    self.assertFalse((data/'venv').exists())
                    (data/'venv').mkdir()
                if 'pip' in args:raise RuntimeError('fixture install failure')
            with self.assertRaisesRegex(RuntimeError,'fixture install failure'):
                runtime.prepare(data,root/'app',run)
            self.assertTrue((data/'venv/bin/python').is_symlink())
            self.assertEqual(outside.read_text(),'external interpreter unchanged')

    def test_resolved_base_does_not_follow_latest_switch(self):
        from zorya_rgb import runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stable=Path('/usr/bin/python3').resolve()
            alias=root/'latest';alias.symlink_to(stable)
            with patch.object(runtime,'SYSTEM_PYTHON',alias):selected=runtime.base_python()
            alias.unlink();alias.symlink_to(root/'different-version')
            self.assertEqual(selected,stable)

    def test_checkout_launcher_ignores_foreign_pythonpath(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); plugin=root/'plugin';(plugin/'bin').mkdir(parents=True)
            shutil.copy2(ROOT/'bin/zorya-rgb',plugin/'bin/zorya-rgb')
            (plugin/'zorya_rgb').mkdir();(plugin/'zorya_rgb/__init__.py').write_text('')
            (plugin/'zorya_rgb/cli.py').write_text('import json\ndef main():\n print(json.dumps({"ok":True}));return 0\n')
            foreign=root/'foreign';foreign.mkdir();(foreign/'json.py').write_text('raise RuntimeError("foreign Python module")')
            env=dict(os.environ,HOME=str(root),XDG_DATA_HOME=str(root/'data'),PYTHONPATH=str(foreign),PATH='/usr/bin:/bin')
            result=subprocess.run([str(plugin/'bin/zorya-rgb'),'status'],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])

    def test_existing_daemon_is_restarted_before_prepare_returns(self):
        from zorya_rgb import runtime
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory);(data/'venv').mkdir();calls=[]
            runtime.prepare(data,data/'app',lambda args,timeout=600:calls.append([str(x) for x in args]))
            self.assertEqual(calls[-1],['systemctl','--user','start','zorya-rgb.service'])

    def test_installed_launcher_recovers_from_broken_private_python(self):
        from zorya_rgb import runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=root/'app with spaces';(app/'zorya_rgb').mkdir(parents=True)
            (app/'zorya_rgb/__init__.py').write_text('')
            (app/'zorya_rgb/cli.py').write_text('import json,sys\ndef main():\n print(json.dumps(sys.argv[1:]));return 0\n')
            broken=root/'python';broken.write_text('#!/bin/sh\nexit 1\n');broken.chmod(0o755)
            launcher=root/'launch';launcher.write_text(runtime.launcher(broken,app));launcher.chmod(0o755)
            env=dict(os.environ,PYTHONHOME='/nonexistent',PYTHONPATH='/nonexistent',PATH='/usr/bin:/bin')
            result=subprocess.run([str(launcher),'status','argument with spaces'],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),['status','argument with spaces'])
