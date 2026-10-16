"""Per-user IPC server with a separate, serialized hardware worker."""
from __future__ import annotations
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import socket
import stat
import threading
import time
import traceback
from .state import StateStore
from .openrgb_backend import OpenRGBBackend
from . import __version__

LOG=logging.getLogger(__name__)
MAX_MESSAGE=128*1024


def _bounded_error(error):
    if not error:return error
    error=str(error)
    while len(json.dumps(error).encode())>6000:error=error[:len(error)//2]
    return error


def default_socket_path():
    runtime=os.environ.get('XDG_RUNTIME_DIR')
    base=Path(runtime) if runtime else Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))
    return base/'zorya-rgb'/'socket'


def request(payload,path=None,timeout=3):
    path=Path(path) if path else default_socket_path()
    if path.exists() and path.stat().st_uid != os.getuid(): raise PermissionError('Zorya socket belongs to another user')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(timeout); client.connect(str(path))
        encoded=json.dumps(payload,allow_nan=False).encode()+b'\n'
        if len(encoded)>MAX_MESSAGE: raise ValueError('Request too large')
        client.sendall(encoded); data=b''
        while b'\n' not in data:
            part=client.recv(8192)
            if not part: raise ConnectionError('Daemon closed without a response')
            data+=part
            if len(data)>MAX_MESSAGE: raise ValueError('Response too large')
        return json.loads(data.split(b'\n',1)[0])


class SleepDetector:
    def __init__(self): self.previous=None
    def check(self,monotonic,boottime):
        pair=(monotonic,boottime); previous=self.previous; self.previous=pair
        return previous is not None and (boottime-previous[1])-(monotonic-previous[0])>2


def recover_hardware(readiness=None):
    from . import setup
    callback=getattr(setup,'recover_services',None) or getattr(setup,'recovery',None)
    return callback(readiness=readiness) if callback else {'ok':True}


class ZoryaDaemon:
    def __init__(self,store=None,backend=None,socket_path=None,recovery=None):
        self.store=store or StateStore(); self.backend=backend or OpenRGBBackend()
        self.socket_path=Path(socket_path) if socket_path else default_socket_path()
        self.recovery=recovery or recover_hardware
        self.lock=threading.RLock(); self.stopping=threading.Event(); self.wake=threading.Event()
        self.revision=0; self.force=True; self.connected=False; self.error=None; self.device_cache=[]
        self.setup={'daemon':True}; self.applying=True; self.listener=None; self.worker=None
        self.recovery_pending=False; self._next_recovery=0; self._recovery_deadline=0
        self._lock_file=None
        self.last_error=None

    def status(self):
        with self.lock:
            state=self.store.snapshot()
            error=_bounded_error(self.error or self.store.error)
            state.update(connected=self.connected,error=error,
                         setup=self.setup,device_count=len(self.device_cache),applying=self.applying,
                         missing_devices=sorted(set(state['devices'])-{d['id'] for d in self.device_cache}),
                         last_error=dict(self.last_error) if self.last_error else None,runtime_version=__version__)
            return state

    def _remember_error(self,message,operation='hardware',trace=''):
        if not message:return
        with self.lock:
            message=str(message)[:4000]
            trace=trace[-16000:]
            # IPC encodes non-ASCII characters as escapes. Bound the encoded
            # evidence as well as character count, leaving room for saved state.
            while len(json.dumps(message).encode())>6000:message=message[:len(message)//2]
            while len(json.dumps(trace).encode())>24000:trace=trace[len(trace)//2:]
            if self.last_error and self.last_error['message']==message and (not trace or self.last_error['traceback']==trace):return
            self.last_error=dict(message=message,operation=operation,at=time.time(),traceback=trace)

    def dispatch(self,message):
        if not isinstance(message,dict): raise ValueError('Request must be an object')
        command=message.get('command')
        if command=='status': return self.status()
        if command=='devices':
            with self.lock:
                selected=set(self.store.snapshot()['devices'])
                devices=[dict(d,selected=d['id'] in selected) for d in self.device_cache]
                return {'devices':devices,'error':_bounded_error(self.error or self.store.error)}
        with self.lock:
            if command=='set': self.store.update(message.get('patch'))
            elif command=='preset_save': self.store.save_preset(message.get('name'))
            elif command=='preset_apply': self.store.apply_preset(message.get('id'))
            elif command=='preset_delete': self.store.delete_preset(message.get('id'))
            elif command=='restore': self.force=True
            else: raise ValueError('Unknown daemon command')
            self.revision+=1; self.applying=True; self.wake.set()
            return self.status()

    def _cache(self):
        with self.lock:
            self.connected=self.backend.connected
            self.device_cache=self.backend.devices(self.store.snapshot()['devices'])

    def _ready(self):
        # A listening SDK is not sufficient: discovery must include every target.
        if self.backend.connected:
            self.backend.refresh()
        else:
            self.backend.connect()
        selected=set(self.store.snapshot()["devices"])
        available={device["id"] for device in self.backend.devices([])}
        return self.backend.connected and selected.issubset(available)

    def _recover(self):
        # Keep the barrier across coordinator failures and subsequent loop ticks.
        LOG.info("Resume detected; coordinating RGB recovery")
        self.recovery_pending=True
        self.backend.close()
        with self.lock: self.connected=False; self.applying=True
        try:
            report=self.recovery(readiness=self._ready)
            if isinstance(report,dict) and not report.get('ok',True):
                raise RuntimeError(report.get('error') or 'Hardware recovery failed')
            if not self._ready():
                raise RuntimeError('Selected devices are not ready after resume')
            self.recovery_pending=False
            LOG.info("RGB recovery discovery complete; applying saved settings")
            with self.lock: self.force=True
        except Exception as exc:
            LOG.warning("RGB recovery failed (%s); waiting for device discovery",type(exc).__name__)
            self._next_recovery=time.monotonic()+5
            self._recovery_deadline=time.monotonic()+15
            raise

    def _retry_recovery(self,now):
        if now < self._next_recovery: return False
        self._next_recovery=now+5
        # Retry only SDK discovery. Do not repeatedly restart hardware services.
        try: ready=self._ready()
        except Exception as exc:
            LOG.warning("RGB recovery discovery failed (%s); retaining the bounded wait",type(exc).__name__)
            ready=False
        if not ready and now < self._recovery_deadline: return False
        if ready:
            LOG.info("RGB recovery discovery complete; applying saved settings")
        else:
            LOG.warning("RGB recovery deadline reached; applying available devices and reporting missing targets")
        # A missing target must not freeze healthy targets forever. Backend apply
        # isolates unavailable IDs and keeps reporting them while discovery retries.
        self.recovery_pending=False
        with self.lock: self.force=True; self.error=None
        return True

    def _hardware_loop(self):
        detector=SleepDetector(); origin=time.monotonic(); next_connect=0; next_discovery=0; old_ids=()
        while not self.stopping.is_set():
            now=time.monotonic()
            interval=.1
            try:
                boot=time.clock_gettime(time.CLOCK_BOOTTIME) if hasattr(time,'CLOCK_BOOTTIME') else now
                if detector.check(now,boot): self._recover()
                if self.recovery_pending and not self._retry_recovery(now):
                    self._cache()
                    with self.lock: self.applying=True
                    self.wake.wait(.1); self.wake.clear()
                    continue
                if not self.backend.connected:
                    if now>=next_connect:
                        self.backend.connect(); next_connect=now+5
                        with self.lock: self.force=True
                    self._cache()
                    with self.lock:
                        self.error=self.backend.error or 'OpenRGB SDK unavailable; run doctor or setup'
                        self.applying=False
                else:
                    if now>=next_discovery:
                        self.backend.refresh(); next_discovery=now+15
                    self._cache()
                    with self.lock:
                        ids=tuple(d['id'] for d in self.device_cache)
                        if ids!=old_ids: self.force=True; old_ids=ids
                        state=self.store.snapshot(); revision=self.revision; force=self.force; self.force=False
                    if state['on'] and state['effect']!='static': interval=1/30
                    result=self.backend.apply(state,now-origin,force=force)
                    with self.lock:
                        self.error='; '.join(result.get('errors',{}).values()) or self.backend.error
                        if revision==self.revision: self.applying=False
                    self._cache()
            except Exception as exc:
                with self.lock: self.error=str(exc); self.applying=False
                self._remember_error(self.error,'hardware worker',traceback.format_exc(limit=12))
            self._remember_error(self.error)
            self.wake.wait(interval); self.wake.clear()
        self.backend.close()

    def _claim(self):
        parent=self.socket_path.parent
        parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=parent.stat()
        if info.st_uid != os.getuid() or info.st_mode&0o022:
            raise PermissionError('Zorya runtime directory must be user-owned and not writable by others')
        lock_path=parent/'daemon.lock'
        fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        self._lock_file=os.fdopen(fd,'a')
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_file.close(); self._lock_file=None
            raise RuntimeError('A Zorya daemon is already running')
        if self.socket_path.exists() or self.socket_path.is_symlink():
            info=self.socket_path.lstat()
            if info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode):
                raise PermissionError('Refusing to replace a non-socket runtime path')
            self.socket_path.unlink()

    def serve_forever(self):
        try:
            self._claim()
        except Exception:
            if self._lock_file:
                self._lock_file.close(); self._lock_file=None
            raise
        try:
            self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            self.listener.bind(str(self.socket_path)); os.chmod(self.socket_path,0o600)
            self.listener.listen(16); self.listener.settimeout(.2)
            self.worker=threading.Thread(target=self._hardware_loop,name='zorya-hardware',daemon=True)
            self.worker.start()
            while not self.stopping.is_set():
                try: connection,_=self.listener.accept()
                except socket.timeout: continue
                except OSError:
                    if self.stopping.is_set(): break
                    raise
                with connection:
                    connection.settimeout(2)
                    try:
                        data=b''
                        while b'\n' not in data:
                            chunk=connection.recv(8192)
                            if not chunk: raise ValueError('Incomplete request')
                            data+=chunk
                            if len(data)>MAX_MESSAGE: raise ValueError('Request too large')
                        result=self.dispatch(json.loads(data.split(b'\n',1)[0]))
                    except Exception as exc: result={'error':str(exc),'ok':False}
                    try: connection.sendall(json.dumps(result,allow_nan=False).encode()+b'\n')
                    except OSError: pass
        finally:
            self.stop()
            if self.worker: self.worker.join(timeout=3)
            if self.listener: self.listener.close()
            if self._lock_file:
                if self.socket_path.exists() and stat.S_ISSOCK(self.socket_path.lstat().st_mode): self.socket_path.unlink()
                self._lock_file.close(); self._lock_file=None

    def stop(self):
        self.stopping.set(); self.wake.set()


def main():
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(name)s: %(message)s")
    daemon=ZoryaDaemon()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:daemon.stop())
    daemon.serve_forever()
