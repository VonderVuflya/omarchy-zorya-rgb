import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from zorya_rgb.daemon import ZoryaDaemon
from zorya_rgb.state import StateStore

ROOT=Path(__file__).resolve().parents[1]


class CouncilRegressions(unittest.TestCase):
    def test_throwing_discovery_does_not_bypass_resume_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=types.SimpleNamespace(connected=True)
            daemon=ZoryaDaemon(store=StateStore(Path(folder)/'state.json'),backend=backend)
            daemon.recovery_pending=True
            daemon._recovery_deadline=0
            daemon._next_recovery=0
            with patch.object(daemon,'_ready',side_effect=OSError('discovery failed')):
                self.assertTrue(daemon._retry_recovery(1))
            self.assertFalse(daemon.recovery_pending)
            self.assertTrue(daemon.force)

    def test_full_mode_bridge_is_rejected_before_any_service_or_config_mutation(self):
        spec=importlib.util.spec_from_file_location('council_builder',ROOT/'scripts/build-hardware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for adopt_only,unit_name in ((False,'old-lianli.service'),(True,'old-lianli.service'),(False,'zorya-lianli.service'),(True,'zorya-lianli.service')):
            with self.subTest(adopt_only=adopt_only,unit=unit_name),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);config=root/'old.json'
                config.write_text(json.dumps({'fans':{'speeds':[{'device_id':'test'}]},'lcds':[{'id':'test'}]}))
                original=config.read_bytes()
                report={'components':{'lianli':{'detected':True}},'services':[
                    {'unit':'old-openrgb.service','available':True,'active':True,'executable':'/old/openrgb','argv':['/old/openrgb']},
                    {'unit':unit_name,'available':True,'active':True,'executable':'/old/lianli-daemon',
                     'argv':['/old/lianli-daemon','--config',str(config)],'config':str(config)}]}
                with patch.dict(os.environ,{'HOME':folder,'XDG_CONFIG_HOME':folder+'/config'}),\
                     patch.object(module.hardware,'doctor',return_value=report),\
                     patch.object(module,'execute') as execute,patch.object(module,'build_lianli') as build,\
                     patch.object(module,'build_openrgb',return_value=Path('/old/openrgb')) as openrgb_build,\
                     patch.object(module,'write_unit') as write,patch.object(module,'privileged_rules'),\
                     patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0)):
                    with self.assertRaisesRegex(RuntimeError,'full-mode|cooling'):
                        module.setup('all',root/'data',adopt_only=adopt_only)
                self.assertEqual(config.read_bytes(),original)
                self.assertFalse((root/'data').exists())
                execute.assert_not_called();build.assert_not_called();openrgb_build.assert_not_called();write.assert_not_called()

    def test_existing_rgb_only_wrapper_is_recognized_without_execution(self):
        spec=importlib.util.spec_from_file_location('council_wrapper',ROOT/'scripts/build-hardware.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            wrapper=Path(folder)/'lianli-daemon-rgb'
            wrapper.write_text('#!/bin/sh\nexec /example/lianli-daemon --rgb-only "$@"\n')
            self.assertTrue(module.rgb_only_service({'argv':[str(wrapper)],'executable':str(wrapper)}))
            wrapper.write_text('#!/bin/sh\nexec /example/lianli-daemon "$@"\n')
            self.assertFalse(module.rgb_only_service({'argv':[str(wrapper)],'executable':str(wrapper)}))
