import types
import unittest
from zorya_rgb.state import DEFAULT_STATE
from zorya_rgb.lianli_effects import start_pulse


class OnboardPulseTests(unittest.TestCase):
    def device(self, name='UNI FAN TL Wireless', count=78):
        return types.SimpleNamespace(name=name, leds=[None]*count,
            location='HID: wireless:00:11:22:33:44:55')

    def test_uniform_pulse_upload_has_smooth_seam_and_bounded_payload(self):
        calls=[]
        def ipc(method, params=None, **kwargs):
            if method=='GetRgbAnimationSupport': return {'replay_safe':True}
            calls.append((method,params))
        state=dict(DEFAULT_STATE,effect='pulse',speed=.2,color='#FF0000',brightness=60)
        self.assertTrue(start_pulse(self.device(),state,ipc=ipc))
        method,params=calls[0]
        self.assertEqual(method,'SetRgbFrames')
        self.assertEqual(params['device_id'],'wireless:00:11:22:33:44:55')
        frames=params['frames']
        self.assertGreaterEqual(len(frames),100)
        self.assertLessEqual(len(frames)*78*3,48000)
        self.assertAlmostEqual(len(frames)*params['interval_ms'],5000,delta=100)
        levels=[f[0][0] for f in frames]
        self.assertEqual(max(levels),153)
        self.assertLessEqual(min(levels),1)
        self.assertGreater(len(set(levels)),40)
        self.assertLessEqual(max(abs(a-b) for a,b in zip(levels,levels[1:]+levels[:1])),4)
        self.assertTrue(all(len(f)==78 and all(c==f[0] for c in f) for f in frames))

    def test_only_supported_wireless_targets_are_written(self):
        calls=[]
        for name,location in [('Unknown','HID: wireless:00:11:22:33:44:55'),
                              ('UNI FAN TL Wireless','HID: /dev/hidraw1')]:
            d=self.device(name);d.location=location
            self.assertFalse(start_pulse(d,dict(DEFAULT_STATE,effect='pulse'),ipc=lambda *a,**kw:calls.append(a)))
        self.assertEqual(calls,[])

    def test_off_or_static_does_not_upload_and_bridge_errors_fall_back(self):
        def fail(*args,**kwargs): raise OSError('bridge unavailable')
        self.assertFalse(start_pulse(self.device(),dict(DEFAULT_STATE,effect='static'),ipc=fail))
        self.assertFalse(start_pulse(self.device(),dict(DEFAULT_STATE,effect='pulse',on=False),ipc=fail))
        self.assertFalse(start_pulse(self.device(),dict(DEFAULT_STATE,effect='pulse'),ipc=fail))

    def test_pump_and_extreme_speeds_have_valid_frame_counts_and_intervals(self):
        for speed in (.1,5):
            calls=[]
            self.assertTrue(start_pulse(self.device('HydroShift II LCD-C (Wireless)',24),
                dict(DEFAULT_STATE,effect='pulse',speed=speed),ipc=lambda method,params=None,**kw: {'replay_safe':True} if method=='GetRgbAnimationSupport' else calls.append(params)))
            p=calls[0]
            self.assertTrue(1<=p['interval_ms']<=65535)
            self.assertLessEqual(len(p['frames'])*24*3,48000)
            self.assertAlmostEqual(len(p['frames'])*p['interval_ms'],1000/speed,delta=100)

    def test_legacy_bridge_without_safe_replay_never_receives_animation(self):
        calls=[]
        def ipc(method,params=None,**kwargs): calls.append(method);return {}
        self.assertFalse(start_pulse(self.device(),dict(DEFAULT_STATE,effect='pulse'),ipc=ipc))
        self.assertEqual(calls,['GetRgbAnimationSupport'])
