import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class BridgeUpgradeTests(unittest.TestCase):
    def test_explicit_setup_updates_old_bridge_and_preserves_cooling_args(self):
        spec=importlib.util.spec_from_file_location('pulse_builder',ROOT/'scripts/build-hardware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'old.json'
            cooling={'fans':{'speeds':[{'device_id':'test','speeds':[45]}]},'rgb':{}}
            config.write_text(json.dumps(cooling))
            service={'unit':'old-lianli.service','active':True,'available':True,
                     'executable':'/old/lianli-daemon','config':str(config),
                     'argv':['/old/lianli-daemon','--rgb-only','--radiator-fans','--config',str(config)]}
            report={'services':[service],'components':{'lianli':{'detected':True}}}
            with patch.dict(os.environ,{'HOME':folder,'XDG_CONFIG_HOME':folder+'/config'}),\
                 patch.object(module.hardware,'doctor',return_value=report),\
                 patch.object(module,'build_lianli',return_value=Path('/new/lianli-daemon-rgb')) as build,\
                 patch.object(module,'privileged_rules'),patch.object(module,'execute'),\
                 patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0)):
                module.setup('lianli',root/'data')
            build.assert_called_once()
            unit=(root/'config/systemd/user/zorya-lianli.service').read_text()
            self.assertIn('/new/lianli-daemon-rgb',unit)
            self.assertIn('--radiator-fans',unit)
            self.assertNotIn('--rgb-only',unit,'The wrapper already adds RGB-only')
            settings=json.loads((root/'config/omarchy-zorya-rgb/lianli-adopted.json').read_text())
            self.assertEqual(settings['fans'],cooling['fans'])
