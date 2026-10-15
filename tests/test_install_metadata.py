import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

class InstallationMetadataTests(unittest.TestCase):
    def test_first_plugin_install_initializes_partial_metadata_without_losing_plugin(self):
        source=Path(__file__).resolve().parents[1]/'scripts/build-hardware.py'
        spec=importlib.util.spec_from_file_location('hardware_metadata',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir()
            metadata=data/'installation.json';metadata.write_text(json.dumps({'plugin_id':'vondervuflya.zorya-rgb'}))
            report={'services':[],'components':{'lianli':{'detected':False}}}
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(root/'config')}), patch.object(module.hardware,'doctor',return_value=report), patch.object(module,'execute'), patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
                module.setup('openrgb',data,adopt_only=True)
            result=json.loads(metadata.read_text())
            self.assertEqual(result['plugin_id'],'vondervuflya.zorya-rgb')
            self.assertEqual(result['hardware_units'],[])
            self.assertEqual(result['adopted'],[])

if __name__=='__main__':unittest.main()

class MigrationApplicationTests(unittest.TestCase):
    def test_migration_applies_saved_state_to_running_daemon(self):
        from zorya_rgb.cli import execute, parser
        calls=[]
        report={'ok':True,'state':{'color':'#00E5FF','on':True,'brightness':80,'devices':['memory'],'presets':[]}}
        with patch('zorya_rgb.setup.migrate',return_value=report):
            result=execute(parser().parse_args(['migrate']),rpc=lambda request:calls.append(request) or {'connected':True})
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['command'],'set')
        self.assertEqual(calls[0]['patch']['devices'],['memory'])
        self.assertNotIn('presets',calls[0]['patch'])
        self.assertTrue(result['applied_to_running_daemon'])
