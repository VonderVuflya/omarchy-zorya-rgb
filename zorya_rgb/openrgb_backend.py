"""OpenRGB SDK adapter. SDK imports occur only when connecting to hardware."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from .effects import frame, rgb

HAS_SPEED=1; HAS_BRIGHTNESS=16; PER_LED=32; MODE_COLORS=64; MANUAL_SAVE=256


def normalize_mode(original):
    """Older SDK readers retain unused palette fields on Gigabyte GPU modes."""
    mode=copy.deepcopy(original)
    flags=int(mode.flags)
    if int(getattr(mode,"color_mode",0)) == 1 and flags & PER_LED:
        mode.flags &= ~MODE_COLORS
        flags=int(mode.flags)
    if not flags & HAS_SPEED:
        mode.speed_min=mode.speed_max=mode.speed=None
    if not flags & HAS_BRIGHTNESS:
        mode.brightness_min=mode.brightness_max=mode.brightness=None
    if not flags & MODE_COLORS:
        mode.colors_min=mode.colors_max=mode.colors=None
    return mode


def _default_onboard_pulse(device,state):
    from .lianli_effects import start_pulse
    return start_pulse(device,state)


def _metadata(device, key):
    value=getattr(device,key,None)
    if value is None: value=getattr(getattr(device,'metadata',None),key,None)
    if value is None: value=getattr(getattr(getattr(device,'data',None),'metadata',None),key,'')
    return str(value or '')


class OpenRGBBackend:
    def __init__(self,client_factory=None,color_factory=None,endpoints=None,onboard_pulse=None):
        self.onboard_pulse=onboard_pulse if onboard_pulse is not None else (_default_onboard_pulse if client_factory is None else None)
        self.client_factory=client_factory
        self._factory=None
        self.color_factory=color_factory
        self.endpoints=endpoints or ([('127.0.0.1',6742)] if client_factory else [('127.0.0.1',6742),('127.0.0.1',6743)])
        if any(host not in ('127.0.0.1','::1','localhost') for host,_ in self.endpoints):
            raise ValueError('OpenRGB endpoints must be loopback')
        self.clients=[]; self.controllers={}; self.connected=False; self.error=None
        self.endpoint_errors={}; self.device_errors={}; self.identity_warnings={}; self._prepared={}; self._last_frame={}; self._retry_after={}

    def connect(self):
        self.close(); self.endpoint_errors={}
        factory=self.client_factory
        try:
            if factory is None:
                from openrgb import OpenRGBClient
                from openrgb.utils import RGBColor
                self.color_factory=RGBColor
                factory=lambda address,port:OpenRGBClient(address=address,port=port,name='ZoryaRGB',protocol_version=1 if port==6743 else None)
            self._factory=factory
            for host,port in self.endpoints:
                try:
                    client=factory() if self.client_factory else factory(host,port)
                    sock=getattr(getattr(client,'comms',None),'sock',None)
                    if sock is not None: sock.settimeout(3.0)
                    self.clients.append(((host,port),client))
                except Exception as exc:
                    self.endpoint_errors[str(port)]=str(exc)
            self._discover()
        except Exception as exc:
            self.error=str(exc); return False
        self.connected=bool(self.clients)
        self.error=None if self.connected else '; '.join(self.endpoint_errors.values()) or 'No OpenRGB server'
        return self.connected

    def _discover(self):
        controllers={}; origins={}; counts={}; identity_ids={}
        for endpoint,client in self.clients:
            for index,device in enumerate(client.devices):
                if device is None: continue
                name=str(getattr(device,'name','Unknown device'))
                location=_metadata(device,'location'); serial=_metadata(device,'serial')
                stable_location=re.sub(r'/dev/i2c-\d+', '/dev/i2c-*',location)
                stable_location=re.sub(r'/dev/hidraw\d+', '/dev/hidraw*',stable_location)
                if location.upper().startswith('USB'):
                    stable_location=re.sub(r'(?i)\bbus\s+\d+\b','bus *',stable_location)
                    stable_location=re.sub(r'(?i)\baddress\s+\d+\b','address *',stable_location)
                serial=serial.strip()
                if serial.casefold() in ('n/a','unknown') or not serial.strip('0'):
                    serial=''
                identity=(name,serial,stable_location)
                # Remote devices forwarded by OpenRGB also appear directly on 6743.
                if (location or serial) and identity in origins and origins[identity]!=endpoint: continue
                origins[identity]=endpoint
                seed=identity if location or serial else (*identity,endpoint,index)
                digest=hashlib.sha256(json.dumps(seed,sort_keys=True).encode()).hexdigest()[:24]
                counts[digest]=counts.get(digest,0)+1
                suffix='' if counts[digest]==1 else ':'+str(counts[digest])
                identifier='openrgb:'+digest+suffix
                controllers[identifier]=device
                identity_ids.setdefault(digest,[]).append(identifier)
        self.identity_warnings={identifier:'SDK identity is ambiguous; controller ordering distinguishes these devices'
                                for identifiers in identity_ids.values() if len(identifiers)>1 for identifier in identifiers}
        # SDK updates normally mutate Device objects in place. A new object with
        # the same stable ID means reconnect/redetection, so restore its state.
        for identity,previous in self.controllers.items():
            if controllers.get(identity) is not previous:
                self._prepared.pop(identity,None)
                self._last_frame.pop(identity,None)
                self._retry_after.pop(identity,None)
                self.device_errors.pop(identity,None)
        self.controllers=controllers

    def refresh(self):
        for endpoint,client in list(self.clients):
            try: client.update()
            except Exception as exc:
                self.endpoint_errors[str(endpoint[1])]=str(exc)
                self.clients.remove((endpoint,client))
                try: client.disconnect()
                except Exception: pass
        present={endpoint for endpoint,_ in self.clients}
        for host,port in self.endpoints:
            if (host,port) in present or self._factory is None: continue
            try:
                client=self._factory() if self.client_factory else self._factory(host,port)
                sock=getattr(getattr(client,'comms',None),'sock',None)
                if sock is not None: sock.settimeout(3.0)
                self.clients.append(((host,port),client))
                self.endpoint_errors.pop(str(port),None)
            except Exception as exc:
                self.endpoint_errors[str(port)]=str(exc)
        self._discover(); self.connected=bool(self.clients)
        self.error=None if self.connected else 'OpenRGB disconnected'
        return self.connected

    def devices(self,selected):
        selected=set(selected)
        return [{'id':identity,'name':str(device.name),'selected':identity in selected,
                 'modes':[str(mode.name) for mode in device.modes],
                 'led_count':len(getattr(device,'leds',getattr(device,'colors',[]))),
                 'location':_metadata(device,'location'), 'error':self.device_errors.get(identity),
                 'identity_warning':self.identity_warnings.get(identity)}
                for identity,device in self.controllers.items()]

    def _pick_mode(self,device,state):
        modes=list(device.modes)
        effect=state['effect'] if state['on'] else 'static'
        if effect in ('pulse','rainbow') and not (effect=='pulse' and self._prefer_direct_pulse(device)):
            wanted=('pulse','breathing','breath') if effect=='pulse' else ('rainbow','color cycle','spectrum cycle')
            for mode in modes:
                flags=int(mode.flags)
                if mode.name.lower() in wanted and flags & HAS_SPEED and (effect=='pulse' or state['brightness']==100 or flags & HAS_BRIGHTNESS):
                    if effect=='pulse' and not flags & (PER_LED|MODE_COLORS): continue
                    return mode,True
        wanted=('static','direct') if effect=='static' else ('direct','static')
        for name in wanted:
            for mode in modes:
                if mode.name.lower()==name and (int(mode.flags)&PER_LED or effect=='static' and int(mode.flags)&MODE_COLORS): return mode,False
        for mode in modes:
            if int(mode.flags)&PER_LED: return mode,False
        raise ValueError('No supported per-LED color mode')

    def _prepare(self,device,state):
        original,native=self._pick_mode(device,state)
        mode=normalize_mode(original)
        if int(mode.flags)&HAS_BRIGHTNESS:
            low=mode.brightness_min; high=mode.brightness_max
            mode.brightness=round(low+(high-low)*state['brightness']/100) if native else high
        if int(mode.flags)&HAS_SPEED:
            low=mode.speed_min; high=mode.speed_max
            mode.speed=round(low+(high-low)*(state['speed']-.1)/4.9)
        if int(mode.flags)&MODE_COLORS:
            count=max(1,mode.colors_min or 1)
            color=self._native_color(state,int(mode.flags)) if native else frame(state,1,0)[0]
            mode.colors=[self._color(*color) for _ in range(count)]
        device.set_mode(mode)
        # SDK set_mode refreshes the device. Normalize refreshed modes too.
        device.modes=[normalize_mode(m) for m in device.modes]
        if state['on'] and state['effect']=='pulse' and self.onboard_pulse is not None:
            if self.onboard_pulse(device,state): return True,int(mode.flags),True
        return native,int(mode.flags),int(getattr(mode,'color_mode',0))==2

    @staticmethod
    def _native_color(state,flags):
        color=rgb(state['color'])
        if state['effect']=='pulse' and not flags & HAS_BRIGHTNESS:
            return tuple(round(value*state['brightness']/100) for value in color)
        return color

    @staticmethod
    def _prefer_direct_pulse(device):
        # This controller's built-in Pulse steps visibly. Its dedicated NVIDIA
        # channel can use Direct frames without increasing motherboard SMBus load.
        return ('gigabyte aorus geforce rtx 5080' in str(getattr(device,'name','')).lower()
                and 'nvidia i2c adapter' in _metadata(device,'location').lower()
                and any(mode.name.lower()=='direct' and int(mode.flags)&PER_LED
                        for mode in device.modes))

    @staticmethod
    def _frame_interval(device):
        if OpenRGBBackend._prefer_direct_pulse(device): return 1/30
        location=_metadata(device,'location').lower()
        descriptor=(str(getattr(device,'name',''))+' '+location).lower()
        if 'wireless' in descriptor or 'rf:' in descriptor or 'i2c' in descriptor: return .5
        return 1/30 if location.startswith(('hid:','usb:')) else .5

    def _color(self,*color):
        return self.color_factory(*color) if self.color_factory else color

    def apply(self,state,elapsed,force=False):
        selected=set(state['devices'])
        errors={identity:'Selected device unavailable: '+identity for identity in selected-self.controllers.keys()}
        signature=tuple((key,str(state[key])) for key in ('on','color','brightness','effect','speed','secondary_color'))
        for identity,device in self.controllers.items():
            if identity not in selected:
                self._prepared.pop(identity,None); self._last_frame.pop(identity,None)
                continue
            if not force and elapsed < self._retry_after.get(identity,0):
                errors[identity]=self.device_errors.get(identity,"Device retry pending")
                continue
            try:
                previous=self._prepared.get(identity)
                changed=force or previous is None or previous[0]!=signature
                if changed:
                    native,flags,palette=self._prepare(device,state)
                    self._prepared[identity]=(signature,native,flags,palette)
                else:
                    _,native,flags,palette=previous
                static=not state['on'] or state['effect']=='static'
                if not changed and (static or native): continue
                # Explicit USB/HID transports can stream; unknown buses stay capped.
                if not changed and elapsed-self._last_frame.get(identity,-1)<self._frame_interval(device): continue
                if palette:
                    self._last_frame[identity]=elapsed
                    self.device_errors.pop(identity,None); self._retry_after.pop(identity,None)
                    continue
                if native:
                    colors=[self._native_color(state,flags)]*len(device.leds)
                else:
                    colors=frame(state,len(device.leds),elapsed)
                device.set_colors([self._color(*c) for c in colors],fast=True)
                self._last_frame[identity]=elapsed
                self.device_errors.pop(identity,None)
                self._retry_after.pop(identity,None)
            except Exception as exc:
                errors[identity]=str(exc); self.device_errors[identity]=str(exc)
                self._retry_after[identity]=elapsed+5
                self._prepared.pop(identity,None)
        return {'errors':errors,'applied':not errors}

    def close(self):
        for _,client in self.clients:
            try: client.disconnect()
            except Exception: pass
        self.clients=[]; self.controllers={}; self._prepared={}; self._last_frame={}; self._retry_after={}; self.connected=False
