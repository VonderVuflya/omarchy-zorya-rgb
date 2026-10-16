"""Exercise the actual plugin entrypoint without touching the user's runtime."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import shlex
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class BootstrapLauncherTests(unittest.TestCase):
    def launch(self, root, private=False):
        plugin=root/'plugin with spaces'; (plugin/'bin').mkdir(parents=True)
        shutil.copy2(ROOT/'bin/zorya-rgb',plugin/'bin/zorya-rgb')
        (plugin/'zorya_rgb').mkdir()
        (plugin/'zorya_rgb/__init__.py').write_text('')
        (plugin/'zorya_rgb/cli.py').write_text("import json,os,sys\ndef main():\n print(json.dumps({'args':sys.argv[1:],'private':os.environ.get('ZORYA_TEST_PRIVATE','no')}))\n return 0\n")
        data=root/'data with spaces'; home=root/'home';home.mkdir()
        tools=root/'tools'; tools.mkdir()
        (tools/'python3').symlink_to(Path(sys.executable).resolve())
        if private:
            python=data/'omarchy-zorya-rgb/venv/bin/python';python.parent.mkdir(parents=True)
            python.write_text('#!/bin/sh\nexport ZORYA_TEST_PRIVATE=yes\nexec '+shlex.quote(str(Path(sys.executable).resolve()))+' "$@"\n');python.chmod(0o755)
        result=subprocess.run([str(plugin/'bin/zorya-rgb'),'onboarding','plan'],env=dict(os.environ,HOME=str(home),XDG_DATA_HOME=str(data),PATH=str(tools)),text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_fresh_plugin_can_plan_without_private_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            result=self.launch(Path(folder))
            self.assertEqual(result['args'],['onboarding','plan'])
            self.assertEqual(result['private'],'no')

    def test_existing_private_python_is_used_with_plugin_source_and_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            result=self.launch(Path(folder),private=True)
            self.assertEqual(result['args'],['onboarding','plan'])
            self.assertEqual(result['private'],'yes')
