"""Bounded transport adapter for the pinned openrgb-python 0.3.6 SDK.

SDK imports stay lazy. This adapter limits untrusted wire data; a loopback SDK
server is still unauthenticated. No installed SDK classes are modified.
"""
from __future__ import annotations

from contextlib import contextmanager
import socket
import struct
import time

PACKET_TIMEOUT=3.0
MAX_PACKET_SIZE=1024*1024
MAX_CONTROLLERS=256
MAX_NOTIFICATIONS=32
MAX_CALLBACK_DEPTH=8
MAX_MODE_COLORS=65535


def validate_mode_colors(mode):
    """Bound advertised palettes before the backend creates their color list."""
    flags=int(mode.flags)
    if not flags & 64 or int(getattr(mode,'color_mode',0))==1 and flags & 32:
        return  # These per-LED palette fields are unused by the backend.
    low=getattr(mode,'colors_min',None); high=getattr(mode,'colors_max',None)
    if low is None and high is None: return
    if (low is None or high is None or not 0<=low<=high<=MAX_MODE_COLORS):
        raise ValueError('Invalid OpenRGB mode palette bounds')


def _validate_controller(data,version,utils):
    """Check SDK allocation lengths before its controller parser allocates them."""
    source=iter(data)
    read=lambda kind:utils.parse_var(kind,source)
    if read('I') != len(data): raise ValueError('Invalid controller data size')
    read('i'); utils.parse_string(source); utils.MetaData.unpack(source,version)
    modes=read('H'); read('i')
    for index in range(modes):
        validate_mode_colors(utils.ModeData.unpack(source,version,index))
    for _ in range(read('H')):
        utils.parse_string(source)
        kind=read('i')
        read('I'); read('I'); read('I'); read('H')
        if kind == utils.ZoneType.MATRIX:
            height=read('I'); width=read('I')
            # A zero-width matrix must not bypass the height allocation bound.
            if height>len(data)//4 or width>len(data)//4 or height*width>len(data)//4:
                raise ValueError('Invalid controller matrix dimensions')
            for _ in range(height*width): read('I')
        if version>=4:
            for _ in range(read('H')):
                segment=utils.SegmentData.unpack(source,version)
                if segment.leds_count>len(data)//4:
                    raise ValueError('Invalid controller segment length')


class _BoundedTransport:
    """Mixin for NetworkClient; its remaining send/request API is unchanged."""

    @contextmanager
    def operation(self):
        """A complete discovery/update shares one budget, including callbacks."""
        previous=getattr(self,'_operation_deadline',None)
        if previous is None: self._operation_deadline=time.monotonic()+PACKET_TIMEOUT
        try:
            yield
            self._remaining()
        except Exception:
            self.stop_connection()
            raise
        finally:
            self._operation_deadline=previous

    def _remaining(self):
        deadline=getattr(self,'_operation_deadline',None)
        if getattr(self,'_read_depth',0)>0:
            deadline=min(deadline,self._read_deadline) if deadline is not None else self._read_deadline
        remaining=PACKET_TIMEOUT if deadline is None else deadline-time.monotonic()
        if remaining<=0: raise TimeoutError('OpenRGB operation deadline exceeded')
        return remaining

    def send_header(self,device_id,packet_type,packet_size,release_lock=True):
        self.check_version(packet_type)
        try:
            if not self.connected: raise self._utils.OpenRGBDisconnected()
            if not self.lock.acquire(timeout=self._remaining()):
                raise TimeoutError('OpenRGB request lock deadline exceeded')
            self.sock.settimeout(self._remaining())
            self.sock.sendall(struct.pack('4sIII',b'ORGB',device_id,packet_type,packet_size))
            packet=self._utils.PacketType
            responses=(packet.REQUEST_CONTROLLER_COUNT,packet.REQUEST_CONTROLLER_DATA,
                       packet.REQUEST_PROTOCOL_VERSION,packet.REQUEST_PROFILE_LIST,
                       packet.REQUEST_PLUGIN_LIST,packet.PLUGIN_SPECIFIC)
            if release_lock and packet_size==0 and packet_type not in responses:
                self._release_lock()
        except Exception:
            self.stop_connection()
            raise

    def send_data(self,data,release_lock=True):
        try:
            if not self.connected: raise self._utils.OpenRGBDisconnected()
            self.sock.settimeout(self._remaining())
            self.sock.sendall(data)
            if release_lock: self._release_lock()
        except Exception:
            self.stop_connection()
            raise

    def start_connection(self):
        if self.sock is not None: return
        self._read_depth=0
        self._notifications=0
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.settimeout(self._remaining())
        try:
            self.sock.connect((self.address,self.port))
            self.send_header(0,self._utils.PacketType.REQUEST_PROTOCOL_VERSION,4)
            self.send_data(struct.pack('I',self._protocol_version),False)
            self.read()
            name=(self.name+'\0').encode('utf-8')
            self.send_header(0,self._utils.PacketType.SET_CLIENT_NAME,len(name))
            self.send_data(name)
        except Exception:
            self.stop_connection()
            raise

    def stop_connection(self):
        sock=self.sock
        self.sock=None
        if sock is not None:
            try: sock.close()
            except OSError: pass
            finally: self._release_lock()
        else: self._release_lock()

    def _release_lock(self):
        try: self.lock.release()
        except RuntimeError: pass

    def _receive(self,size,deadline):
        data=bytearray()
        while len(data)<size:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise TimeoutError('OpenRGB packet deadline exceeded')
            self.sock.settimeout(remaining)
            chunk=self.sock.recv(size-len(data))
            if time.monotonic()>deadline: raise TimeoutError('OpenRGB packet deadline exceeded')
            if not chunk: raise EOFError('OpenRGB server closed an incomplete packet')
            data.extend(chunk)
        return bytes(data)

    def read(self):
        utils=self._utils
        if not self.connected: raise utils.OpenRGBDisconnected()
        if self._read_depth>=MAX_CALLBACK_DEPTH:
            self.stop_connection()
            raise utils.OpenRGBDisconnected('OpenRGB callback nesting limit exceeded')
        if self._read_depth==0: self._notifications=0
        if self._read_depth==0:
            self._read_deadline=time.monotonic()+self._remaining()
        self._read_depth+=1
        deadline=self._read_deadline
        try:
            notifications=[]
            while True:
                header=self._receive(utils.HEADER_SIZE,deadline)
                signature,device,kind,size=struct.unpack('4sIII',header)
                if signature!=b'ORGB': raise ValueError('Invalid OpenRGB packet signature')
                if size>MAX_PACKET_SIZE: raise ValueError('OpenRGB packet exceeds size limit')
                packet=utils.PacketType
                if kind==packet.DEVICE_LIST_UPDATED:
                    if device!=0 or size!=0: raise ValueError('Invalid device-list notification')
                    self._notifications+=1
                    if self._notifications>MAX_NOTIFICATIONS:
                        raise ValueError('OpenRGB notification limit exceeded')
                    notifications.append((device,kind,0))
                    continue
                payload=self._receive(size,deadline)
                if kind in (packet.REQUEST_CONTROLLER_COUNT,packet.REQUEST_PROTOCOL_VERSION):
                    if size!=4: raise ValueError('Invalid OpenRGB scalar packet size')
                    value=struct.unpack('I',payload)[0]
                    if kind==packet.REQUEST_CONTROLLER_COUNT:
                        if value>MAX_CONTROLLERS: raise ValueError('OpenRGB controller count exceeds limit')
                    else:
                        self.max_protocol_version=min(value,4)
                        self._protocol_version=min(self.max_protocol_version,self._protocol_version)
                elif kind==packet.REQUEST_CONTROLLER_DATA:
                    if device>=MAX_CONTROLLERS: raise ValueError('Invalid OpenRGB controller ID')
                    _validate_controller(payload,self._protocol_version,utils)
                    value=utils.ControllerData.unpack(payload,self._protocol_version)
                elif kind in (packet.REQUEST_PROFILE_LIST,packet.REQUEST_PLUGIN_LIST):
                    if size<6 or struct.unpack('I',payload[:4])[0]!=size:
                        raise ValueError('Invalid OpenRGB list packet size')
                    item=utils.Profile if kind==packet.REQUEST_PROFILE_LIST else utils.Plugin
                    value=utils.parse_list(item,iter(payload[4:]),self._protocol_version)
                elif kind==packet.PLUGIN_SPECIFIC:
                    value=iter(payload)
                else: raise ValueError('Unexpected OpenRGB response type')
                break
            # SDK count callbacks synchronously request controller data. Releasing
            # here lets those requests acquire their own lock; never release it
            # again after calling back, when it may belong to another request.
            self.sock.settimeout(self._remaining())
            self._release_lock()
            if kind!=packet.REQUEST_PROTOCOL_VERSION: self.callback(device,kind,value)
            for notification in notifications: self.callback(*notification)
        except Exception as exc:
            self.stop_connection()
            if isinstance(exc,utils.OpenRGBDisconnected): raise
            raise utils.OpenRGBDisconnected('Invalid or incomplete OpenRGB response: '+str(exc)) from exc
        finally:
            self._read_depth-=1


def connect_client(address,port,name='ZoryaRGB',protocol_version=None):
    """Create a client protected from its first negotiation through later reads."""
    from openrgb import OpenRGBClient,utils
    from openrgb.network import NetworkClient

    deadline=time.monotonic()+PACKET_TIMEOUT

    class SafeNetworkClient(_BoundedTransport,NetworkClient):
        _utils=utils

        def __init__(self,*args,**kwargs):
            self._operation_deadline=deadline
            super().__init__(*args,**kwargs)

    class SafeOpenRGBClient(OpenRGBClient):
        def __init__(self):
            # Pinned SDK initializer with the transport injected before any I/O.
            self.device_num=0
            self.devices=[]; self.profiles=[]; self.plugins=[]
            self.comms=SafeNetworkClient(self._callback,address,port,name,protocol_version)
            self.address=address; self.port=port; self.name=name
            try: self.update()
            except Exception:
                self.disconnect()
                raise
            finally: self.comms._operation_deadline=None

        def update(self):
            with self.comms.operation():
                return super().update()

    return SafeOpenRGBClient()
