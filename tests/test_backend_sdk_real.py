"""Run with the optional hardware extra to verify the actual SDK serializer."""
import unittest
from zorya_rgb.openrgb_backend import normalize_mode
try:
    from openrgb.utils import ModeData,ModeFlags,ModeColors,RGBColor
except ImportError:
    ModeData=None

@unittest.skipIf(ModeData is None,'openrgb-python hardware extra not installed')
class ActualSdkTests(unittest.TestCase):
    def test_redundant_gpu_palette_is_valid_for_sdk_pack(self):
        original=ModeData(0,'Static',1,ModeFlags(32|64|16|256),0,0,1,10,1,8,0,10,None,ModeColors.PER_LED,[])
        normalized=normalize_mode(original)
        self.assertTrue(normalized.pack(4))
        self.assertFalse(int(normalized.flags)&64)
        self.assertTrue(int(normalized.flags)&256)
        self.assertTrue(int(original.flags)&64)
    def test_native_mode_palette_is_preserved_and_serializable(self):
        original=ModeData(0,'Static',1,ModeFlags(64|16),None,None,0,100,1,1,None,50,None,ModeColors.MODE_SPECIFIC,[RGBColor(128,0,0)])
        normalized=normalize_mode(original)
        self.assertTrue(normalized.pack(4)); self.assertEqual(len(normalized.colors),1)
