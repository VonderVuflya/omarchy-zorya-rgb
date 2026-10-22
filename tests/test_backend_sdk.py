import copy
import types
import unittest
from zorya_rgb.openrgb_backend import OpenRGBBackend, normalize_mode
from zorya_rgb.state import DEFAULT_STATE

class Device:
    def __init__(self,name='GPU',location='PCI:1',serial='',fail=False):
        self.name=name; self.location=location; self.serial=serial; self.colors=[None]*4; self.leds=[None]*4
        self.modes=[types.SimpleNamespace(name='Static',id=0,flags=32|16|256,color_mode=1,colors_min=1,colors_max=8,colors=[],speed_min=0,speed_max=0,speed=0,brightness_min=1,brightness_max=10,brightness=10),types.SimpleNamespace(name='Direct',id=1,flags=32,color_mode=1,colors_min=1,colors_max=8,colors=[],speed_min=0,speed_max=0,speed=0,brightness_min=0,brightness_max=0,brightness=0)]
        self.active_mode=0; self.fail=fail; self.writes=[]; self.mode_writes=[]; self.saves=0
    def set_mode(self,mode):
        if self.fail: raise OSError('device unavailable')
        self.active_mode=mode.id; self.mode_writes.append(copy.deepcopy(mode))
    def set_colors(self,colors,fast=False):
        if self.fail: raise OSError('device unavailable')
        self.writes.append(colors)
    def save_mode(self): self.saves+=1
class Client:
    def __init__(self,devices): self.devices=devices
    def update(self): pass
    def disconnect(self): pass

class BackendTests(unittest.TestCase):
    def backend(self,devices):
        b=OpenRGBBackend(client_factory=lambda:Client(devices),color_factory=lambda *c:c); self.assertTrue(b.connect()); return b
    def test_duplicate_names_have_distinct_stable_ids(self):
        b=self.backend([Device(location='PCI:2'),Device(location='PCI:1')]); ids={d['location']:d['id'] for d in b.devices([])}
        b2=self.backend([Device(location='PCI:1'),Device(location='PCI:2')]); self.assertEqual(ids,{d['location']:d['id'] for d in b2.devices([])})
        self.assertEqual(len(set(ids.values())),2)
    def test_device_failure_does_not_block_other_device(self):
        bad=Device(fail=True); good=Device(location='PCI:2'); b=self.backend([bad,good])
        state=dict(DEFAULT_STATE,devices=[x['id'] for x in b.devices([])]); result=b.apply(state,0); self.assertTrue(result['errors']); self.assertTrue(good.writes)
    def test_normalization_clears_unsupported_palette_without_mutating_original(self):
        original=Device().modes[0]; mode=normalize_mode(original)
        self.assertIsNone(mode.colors); self.assertIsNone(mode.colors_min); self.assertIsNone(mode.speed)
        self.assertEqual(original.colors,[])
    def test_per_led_mode_clears_redundant_mode_palette_flag(self):
        original=Device().modes[0]; original.flags |= 64
        mode=normalize_mode(original)
        self.assertFalse(int(mode.flags)&64); self.assertIsNone(mode.colors)
        self.assertTrue(int(original.flags)&64)
    def test_animation_does_not_write_mode_every_frame(self):
        d=Device(); b=self.backend([d]); state=dict(DEFAULT_STATE,effect='rainbow',devices=[x['id'] for x in b.devices([])])
        for t in (0,.5,1): b.apply(state,t)
        self.assertEqual(len(d.mode_writes),1); self.assertEqual(len(d.writes),3); self.assertEqual(d.saves,0)
    def test_static_never_persists_hardware_and_selection_limits_writes(self):
        first=Device(); second=Device(location='PCI:2'); b=self.backend([first,second]); selected=b.devices([])[1]['id']
        state=dict(DEFAULT_STATE,devices=[selected]); b.apply(state,0); b.apply(state,.1)
        self.assertEqual(first.writes,[]); self.assertEqual(second.saves,0); self.assertEqual(len(second.writes),1)
    def test_empty_selection_does_not_write_and_missing_selection_is_reported(self):
        d=Device(); b=self.backend([d]); self.assertTrue(b.apply(DEFAULT_STATE,0)['applied'])
        self.assertEqual(d.mode_writes,[])
        result=b.apply(dict(DEFAULT_STATE,devices=['gone']),0)
        self.assertIn('gone',result['errors'])
    def test_failed_device_has_backoff_while_healthy_device_animates(self):
        class Failing(Device):
            def __init__(self): super().__init__(); self.attempts=0
            def set_mode(self,mode): self.attempts+=1; raise OSError('failed')
        bad=Failing(); good=Device(location='PCI:2'); b=self.backend([bad,good])
        state=dict(DEFAULT_STATE,devices=[d['id'] for d in b.devices([])],effect='rainbow')
        for t in (0,.5,1): b.apply(state,t)
        self.assertEqual(bad.attempts,1); self.assertEqual(len(good.writes),3)
    def test_native_pulse_uses_capabilities_and_no_frame_stream(self):
        d=Device(); pulse=copy.deepcopy(d.modes[0]); pulse.id=2; pulse.name='Pulse'
        pulse.flags=32|16|1; pulse.speed_min=1; pulse.speed_max=6; pulse.speed=3
        d.modes.append(pulse); b=self.backend([d]); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']],effect='pulse',brightness=50)
        for t in (0,.5,1): b.apply(state,t)
        self.assertEqual(len(d.mode_writes),1); self.assertEqual(d.mode_writes[0].name,'Pulse')
        self.assertEqual(len(d.writes),1); self.assertGreater(d.mode_writes[0].brightness,1)
        self.assertEqual(d.writes[0],[(255,255,255)]*4)
    def test_data_metadata_identity_is_independent_of_sdk_order(self):
        first=Device(); second=Device()
        del first.location; del first.serial; del second.location; del second.serial
        first.data=types.SimpleNamespace(metadata=types.SimpleNamespace(location='PCI:2',serial='one'))
        second.data=types.SimpleNamespace(metadata=types.SimpleNamespace(location='PCI:1',serial='two'))
        a=self.backend([first,second]); b=self.backend([second,first])
        self.assertEqual({d['location']:d['id'] for d in a.devices([])},{d['location']:d['id'] for d in b.devices([])})
        self.assertEqual(set(d['location'] for d in a.devices([])),{'PCI:1','PCI:2'})
    def test_ram_mode_palette_static_and_native_pulse(self):
        d=Device(name='RAM'); mode=d.modes[0]; mode.flags=64|16|256; mode.color_mode=2
        mode.colors_min=mode.colors_max=1; mode.colors=[(0,0,0)]
        pulse=copy.deepcopy(mode); pulse.name='Breath'; pulse.id=2; pulse.flags |= 1|32
        pulse.speed_min=10; pulse.speed_max=1; pulse.speed=3; d.modes.append(pulse)
        b=self.backend([d]); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']],color='#FF0000',brightness=50)
        b.apply(state,0)
        self.assertEqual(d.mode_writes[0].name,'Static'); self.assertEqual(d.mode_writes[0].colors,[(128,0,0)])
        self.assertEqual(d.writes,[]); self.assertEqual(d.saves,0)
        state['effect']='pulse'; b.apply(state,1); b.apply(state,2)
        self.assertEqual(len(d.mode_writes),2); self.assertEqual(d.mode_writes[-1].name,'Breath')
        self.assertEqual(d.mode_writes[-1].colors,[(255,0,0)]); self.assertEqual(d.writes,[])
    def test_partial_endpoint_returns_after_startup_failure(self):
        first=Client([Device(location='PCI:1')]); later=Client([Device(name='Li',location='RF:one')]); attempts=[]
        def factory():
            attempts.append(True)
            if len(attempts)==1:return first
            if len(attempts)==2:raise OSError('Li still discovering')
            return later
        b=OpenRGBBackend(client_factory=factory,endpoints=[('127.0.0.1',6742),('127.0.0.1',6743)])
        self.assertTrue(b.connect()); self.assertEqual(len(b.devices([])),1)
        b.refresh(); self.assertEqual(len(b.devices([])),2)
        self.assertIs(b.clients[0][1],first); self.assertEqual(b.endpoint_errors,{})
    def test_linux_bus_renumbering_keeps_ids_and_addresses_distinct(self):
        a=self.backend([Device(location='I2C: NVIDIA adapter 1 /dev/i2c-2, address 0x75'),Device(location='I2C: NVIDIA adapter 1 /dev/i2c-2, address 0x76'),Device(name='USB',location='/dev/hidraw3 port 2')])
        b=self.backend([Device(location='I2C: NVIDIA adapter 1 /dev/i2c-19, address 0x75'),Device(location='I2C: NVIDIA adapter 1 /dev/i2c-19, address 0x76'),Device(name='USB',location='/dev/hidraw22 port 2')])
        self.assertEqual([d['id'] for d in a.devices([])],[d['id'] for d in b.devices([])])
        self.assertEqual(len(set(d['id'] for d in a.devices([]))),3)
    def test_serial_identity_survives_location_changes(self):
        a=self.backend([Device(serial='unit-1',location='USB: bus 3 address 4')])
        b=self.backend([Device(serial='unit-1',location='USB: bus 5 address 9')])
        self.assertEqual(a.devices([])[0]['id'],b.devices([])[0]['id'])
    def test_placeholder_serial_does_not_merge_different_locations(self):
        b=self.backend([Device(serial='00000000',location='/dev/i2c-2, address 0x61'),Device(serial='00000000',location='/dev/i2c-2, address 0x63')])
        self.assertEqual(len(set(d['id'] for d in b.devices([]))),2)
    def test_indistinguishable_duplicates_have_explicit_warning(self):
        b=self.backend([Device(location='/dev/i2c-2, address 0x75'),Device(location='/dev/i2c-2, address 0x75')])
        self.assertEqual(len(b.devices([])),2)
        self.assertTrue(all(d.get('identity_warning') for d in b.devices([])))
    def test_reconnected_controller_with_same_id_receives_saved_static_state(self):
        old=Device(location='PCI:1'); replacement=Device(location='PCI:1')
        first=Client([old]); later=Client([replacement]); clients=iter([first,later])
        b=OpenRGBBackend(client_factory=lambda:next(clients),color_factory=lambda *c:c)
        self.assertTrue(b.connect()); identity=b.devices([])[0]['id']
        state=dict(DEFAULT_STATE,devices=[identity],color='#22AA11')
        b.apply(state,0); self.assertEqual(len(old.writes),1)
        first.update=lambda:(_ for _ in ()).throw(OSError('server restarted'))
        b.refresh(); self.assertEqual(b.devices([])[0]['id'],identity)
        b.apply(state,.1)
        self.assertEqual(len(replacement.mode_writes),1)
        self.assertEqual(replacement.writes, [[(34,170,17)]*4])
    def test_healthy_in_place_sdk_refresh_does_not_reapply_static_state(self):
        d=Device(); b=self.backend([d]); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']])
        b.apply(state,0); b.refresh(); b.apply(state,.1)
        self.assertEqual(len(d.mode_writes),1); self.assertEqual(len(d.writes),1)
    def test_runtime_sdk_socket_uses_bounded_timeout(self):
        values=[]; client=Client([Device()])
        client.comms=types.SimpleNamespace(sock=types.SimpleNamespace(settimeout=values.append))
        b=OpenRGBBackend(client_factory=lambda:client)
        self.assertTrue(b.connect()); self.assertEqual(values,[3.0])
    def test_native_gpu_pulse_without_brightness_scales_color_and_never_streams(self):
        d=Device(); pulse=copy.deepcopy(d.modes[0]); pulse.id=2; pulse.name='Pulse'
        pulse.flags=289; pulse.speed_min=1; pulse.speed_max=6; pulse.speed=3
        d.modes.append(pulse); b=self.backend([d]); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']],effect='pulse',brightness=27,color='#FF8040')
        for elapsed in (0,.5,1): b.apply(state,elapsed)
        self.assertEqual([m.name for m in d.mode_writes],['Pulse'])
        self.assertEqual(d.writes,[[(69,35,17)]*4]); self.assertEqual(d.saves,0)
    def test_native_palette_pulse_without_brightness_scales_palette(self):
        d=Device(); pulse=copy.deepcopy(d.modes[0]); pulse.id=2; pulse.name='Breath'
        pulse.flags=65; pulse.color_mode=2; pulse.colors_min=pulse.colors_max=1
        pulse.speed_min=10; pulse.speed_max=1; pulse.speed=3
        d.modes.append(pulse); b=self.backend([d]); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']],effect='pulse',brightness=27,color='#FF8040')
        for elapsed in (0,.5,1): b.apply(state,elapsed)
        self.assertEqual([m.name for m in d.mode_writes],['Breath'])
        self.assertEqual(d.mode_writes[0].colors,[(69,35,17)]); self.assertEqual(d.writes,[])
    def test_onboard_pulse_uploads_once_and_reuploads_changed_state(self):
        d=Device(name='Lian Li Wireless',location='RF:unit'); calls=[]
        def onboard(device,state):
            self.assertTrue(device.mode_writes); calls.append(state.copy()); return True
        b=OpenRGBBackend(client_factory=lambda:Client([d]),color_factory=lambda *c:c,onboard_pulse=onboard)
        b.connect(); state=dict(DEFAULT_STATE,devices=[b.devices([])[0]['id']],effect='pulse')
        b.apply(state,0); b.apply(state,.1); self.assertEqual(len(calls),1); self.assertEqual(d.writes,[])
        state['brightness']=27; b.apply(state,.2); self.assertEqual(len(calls),2)
        state['effect']='static'; b.apply(state,.3); self.assertEqual(len(calls),2); self.assertEqual(len(d.writes),1)
        replacement=Device(name=d.name,location=d.location)
        b.clients[0][1].devices=[replacement]; b.refresh(); state['effect']='pulse'; b.apply(state,.4)
        self.assertEqual(len(calls),3); self.assertEqual(replacement.writes,[])
    def test_explicit_usb_fallback_streams_faster_but_i2c_and_rf_are_capped(self):
        usb=Device(name='Keyboard',location='HID: /dev/hidraw2')
        i2c=Device(location='I2C: adapter address 0x75'); rf=Device(name='Lian',location='USB: Wireless RF unit')
        b=self.backend([usb,i2c,rf]); state=dict(DEFAULT_STATE,devices=[d['id'] for d in b.devices([])],effect='rainbow')
        for elapsed in (0,.04,.08): b.apply(state,elapsed)
        self.assertEqual(len(usb.writes),3); self.assertEqual(len(i2c.writes),1); self.assertEqual(len(rf.writes),1)
    def test_known_aorus_5080_pulse_streams_direct_at_30fps(self):
        known=Device(name='Gigabyte AORUS GeForce RTX 5080 MASTER ICE',location='I2C: NVIDIA i2c adapter 1 at 1:00.0 (/dev/i2c-2), address 0x75')
        unknown=Device(name='Different GPU',location='I2C: NVIDIA i2c adapter 1 at 2:00.0 (/dev/i2c-3), address 0x75')
        for device in (known,unknown):
            pulse=copy.deepcopy(device.modes[0]); pulse.id=2; pulse.name='Pulse'; pulse.flags=289
            pulse.speed_min=1; pulse.speed_max=6; pulse.speed=3; device.modes.append(pulse)
        b=self.backend([known,unknown]); state=dict(DEFAULT_STATE,devices=[d['id'] for d in b.devices([])],effect='pulse',brightness=27,color='#FF8040')
        for elapsed in (0,.04,.08): b.apply(state,elapsed)
        self.assertEqual([m.name for m in known.mode_writes],['Direct'])
        self.assertEqual(len(known.writes),3)
        self.assertEqual([m.name for m in unknown.mode_writes],['Pulse'])
        self.assertEqual(len(unknown.writes),1)
    def test_aorus_name_on_smbus_has_no_fast_direct_exception(self):
        device=Device(name='Gigabyte AORUS GeForce RTX 5080 MASTER',location='I2C: SMBus PIIX4 adapter port 0, address 0x75')
        self.assertEqual(OpenRGBBackend._frame_interval(device),.5)
    def test_offline_is_visible(self):
        b=OpenRGBBackend(client_factory=lambda:(_ for _ in ()).throw(OSError('no server')))
        self.assertFalse(b.connect()); self.assertFalse(b.connected); self.assertIn('no server',b.error)

if __name__=='__main__': unittest.main()


class SharedSocketTests(unittest.TestCase):
    def test_dropped_shared_socket_reconnects_without_penalizing_other_devices(self):
        sock=types.SimpleNamespace(settimeout=lambda value:None); comms=types.SimpleNamespace(sock=sock)
        class Dropping(Device):
            def set_mode(self,mode): comms.sock=None; raise OSError('send failed')
        bad=Dropping(); good=Device(location='PCI:2'); clients=[]
        def factory():
            client=Client([bad,good] if not clients else [Device(location='PCI:1'),Device(location='PCI:2')])
            client.comms=comms if not clients else types.SimpleNamespace(sock=sock)
            clients.append(client); return client
        b=OpenRGBBackend(client_factory=factory,color_factory=lambda *c:c); self.assertTrue(b.connect())
        ids=[d['id'] for d in b.devices([])]; state=dict(DEFAULT_STATE,devices=ids)
        result=b.apply(state,0)
        self.assertTrue(b.refresh_requested); self.assertEqual(good.writes,[])
        self.assertNotIn(ids[1],b._retry_after); self.assertIn('reconnecting',result['errors'][ids[1]])
        clients[0].update=lambda:(_ for _ in ()).throw(OSError('closed'))
        b.refresh(); self.assertFalse(b.refresh_requested); self.assertEqual(len(clients),2)
        b.apply(state,.1); self.assertTrue(b.controllers[ids[1]].writes)
