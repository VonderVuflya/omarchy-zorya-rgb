"""Validated, atomically persisted user state. No hardware dependencies."""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid

DEFAULT_STATE = {'on': True, 'color': '#FFFFFF', 'brightness': 100, 'effect': 'static',
                 'speed': 1.0, 'secondary_color': '#0088FF', 'devices': [], 'presets': []}
SETTINGS = frozenset(DEFAULT_STATE) - {'presets'}


def state_path():
    return Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'zorya-rgb'/'state.json'


def validate_patch(state, patch):
    if not isinstance(patch, dict):
        raise ValueError('Settings must be a JSON object')
    unknown = set(patch)-SETTINGS
    if unknown:
        raise ValueError('Unknown settings: '+', '.join(sorted(unknown)))
    result = copy.deepcopy(state)
    for key, value in patch.items():
        if key == 'on':
            if type(value) is not bool: raise ValueError('on must be a boolean')
        elif key in ('color', 'secondary_color'):
            if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
                raise ValueError(key+' must be #RRGGBB')
            value = value.upper()
        elif key == 'brightness':
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError('brightness must be an integer from 0 to 100')
        elif key == 'speed':
            if type(value) not in (int,float) or not math.isfinite(value) or not .1 <= value <= 5:
                raise ValueError('speed must be a finite number from 0.1 to 5')
            value = float(value)
        elif key == 'effect':
            if value not in ('static','pulse','rainbow','gradient'):
                raise ValueError('effect must be static, pulse, rainbow or gradient')
        elif key == 'devices':
            if not isinstance(value,list) or len(value)>256 or any(not isinstance(x,str) or not x or len(x)>256 for x in value):
                raise ValueError('devices must be an array of device IDs')
            if len(set(value)) != len(value): raise ValueError('devices must not contain duplicate IDs')
        result[key] = value
    return result


class StateStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else state_path()
        self.lock = threading.RLock()
        self.error = None
        self._state = copy.deepcopy(DEFAULT_STATE)
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                if not isinstance(raw,dict): raise ValueError('state must be an object')
                self._state = validate_patch(DEFAULT_STATE,{k:v for k,v in raw.items() if k != 'presets'})
                presets = raw.get('presets',[])
                if not isinstance(presets,list) or len(presets)>64: raise ValueError('invalid presets')
                seen=set()
                for preset in presets:
                    if not isinstance(preset,dict) or not isinstance(preset.get('id'),str) or preset['id'] in seen:
                        raise ValueError('invalid preset identity')
                    self._name(preset.get('name'))
                    snapshot=validate_patch(DEFAULT_STATE,preset.get('state'))
                    preset['state']={k:snapshot[k] for k in SETTINGS}
                    seen.add(preset['id'])
                self._state['presets']=presets
            except (OSError,ValueError,TypeError) as exc:
                self._state=copy.deepcopy(DEFAULT_STATE)
                self.error='Cannot read saved state: '+str(exc)

    def snapshot(self):
        with self.lock: return copy.deepcopy(self._state)

    def _write(self, state):
        if len(json.dumps(state,allow_nan=False).encode()) > 64*1024:
            raise ValueError("Saved state and presets exceed the 64 KiB limit")
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,name=tempfile.mkstemp(prefix='.state-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as out:
                json.dump(state,out,allow_nan=False,sort_keys=True)
                out.write('\n'); out.flush(); os.fsync(out.fileno())
            os.replace(name,self.path)
            dirfd=os.open(self.path.parent,os.O_RDONLY)
            try: os.fsync(dirfd)
            finally: os.close(dirfd)
        finally:
            if os.path.exists(name): os.unlink(name)

    def _commit(self, state):
        self._write(state)
        self._state=state; self.error=None
        return self.snapshot()

    def update(self, patch):
        with self.lock: return self._commit(validate_patch(self._state,patch))

    @staticmethod
    def _name(name):
        if not isinstance(name,str) or not name.strip() or len(name)>128 or any(ord(c)<32 for c in name):
            raise ValueError('Preset name must contain 1–128 printable characters')
        return name.strip()

    def save_preset(self,name):
        name=self._name(name)
        with self.lock:
            state=self.snapshot()
            existing=next((p for p in state['presets'] if p['name'].casefold()==name.casefold()),None)
            if existing is None and len(state['presets'])>=64:
                raise ValueError('At most 64 presets are supported')
            preset={'id':existing['id'] if existing else uuid.uuid4().hex,'name':name,
                    'state':{k:copy.deepcopy(state[k]) for k in SETTINGS}}
            if existing is None: state['presets'].append(preset)
            else: state['presets'][state['presets'].index(existing)]=preset
            self._commit(state)
            return copy.deepcopy(preset)

    def apply_preset(self,identity):
        with self.lock:
            preset=next((p for p in self._state['presets'] if p['id']==identity),None)
            if preset is None: raise ValueError('Preset not found')
            return self.update(preset['state'])

    def delete_preset(self,identity):
        with self.lock:
            state=self.snapshot(); presets=[p for p in state['presets'] if p['id']!=identity]
            if len(presets)==len(state['presets']): raise ValueError('Preset not found')
            state['presets']=presets; return self._commit(state)
