"""Read-only hardware and dependency diagnosis; importing never probes devices."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

USB_MODELS = {
    ('1cbe', 'a021'): ('HydroShift II LCD-C', 'lianli-aio'),
    ('1cbe', 'a034'): ('HydroShift II LCD-S', 'lianli-aio'),
    ('0416', '8040'): ('L-Wireless TX V1', 'lianli-tx'),
    ('0416', '8041'): ('L-Wireless RX V1', 'lianli-rx'),
    ('1a86', 'e304'): ('L-Wireless TX V2', 'lianli-tx'),
    ('1a86', 'e305'): ('L-Wireless RX V2', 'lianli-rx'),
    ('0cf2', 'a100'): ('UNI FAN SL', 'lianli-wired'),
    ('0cf2', 'a101'): ('UNI FAN AL', 'lianli-wired'),
    ('0cf2', 'a102'): ('UNI FAN SL Infinity', 'lianli-wired'),
    ('0cf2', 'a103'): ('UNI FAN SL V2', 'lianli-wired'),
    ('0cf2', 'a104'): ('UNI FAN AL V2', 'lianli-wired'),
}


def data_dir() -> Path:
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'omarchy-zorya-rgb'


def config_dir() -> Path:
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'omarchy-zorya-rgb'


def parse_usb(text: str) -> list[dict]:
    result = []
    for line in text.splitlines():
        match = re.search(r'ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)', line)
        if match and (key := (match[1].lower(), match[2].lower())) in USB_MODELS:
            model, kind = USB_MODELS[key]
            result.append(dict(vid=key[0], pid=key[1], model=model, kind=kind, description=match[3]))
    return result


def parse_service(text: str) -> dict:
    props = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    value = props.get('ExecStart', '')
    path = re.search(r'path=(.*?)\s*;', value)
    args = re.search(r'argv\[\]=(.*?)\s*;', value)
    try:
        argv = shlex.split(args[1]) if args else []
    except ValueError:
        argv = []
    executable = path[1].strip() if path else (argv[0] if argv else None)
    config = None
    if '--config' in argv and argv.index('--config') + 1 < len(argv):
        config = argv[argv.index('--config') + 1]
    return dict(unit=props.get('Id', ''), active=props.get('ActiveState') == 'active',
                executable=executable, argv=argv, config=config,
                available=bool(executable and os.access(executable, os.X_OK)),
                preserves_cooling='--radiator-fans' in argv or '--rgb-only' not in argv,
                description=props.get('Description', ''))


def _capture(argv, run=subprocess.run) -> str:
    try:
        return run(argv, capture_output=True, text=True, check=True, timeout=8).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def services(run=subprocess.run) -> list[dict]:
    """Inspect actual ExecStart commands, including custom unit names."""
    listing = _capture(['systemctl', '--user', 'list-unit-files', '--type=service', '--no-legend', '--no-pager'], run)
    units = [line.split()[0] for line in listing.splitlines() if line.split()]
    result = []
    for unit in units:
        if not re.fullmatch(r'[A-Za-z0-9_.@-]+\.service', unit):
            continue
        text = _capture(['systemctl', '--user', 'show', unit, '--property=Id,ActiveState,ExecStart,Description'], run)
        info = parse_service(text)
        exe = Path(info['executable'] or '').name.lower()
        if 'lianli' in exe or 'lian-li' in exe or 'openrgb' in exe or unit.startswith('zorya-'):
            result.append(info)
    return result


def doctor(run=subprocess.run) -> dict:
    usb = _capture(['lsusb'], run)
    if not usb:
        lines = []
        for node in Path('/sys/bus/usb/devices').glob('*'):
            try:
                lines.append('ID ' + (node/'idVendor').read_text().strip() + ':' + (node/'idProduct').read_text().strip())
            except OSError:
                pass
        usb = '\n'.join(lines)
    devices = parse_usb(usb)
    deps = [dict(name=n, available=bool(p := shutil.which(n)), path=p)
            for n in ('python3', 'openrgb', 'git', 'cargo', 'rustup', 'make', 'cc', 'pkg-config', 'qmake', 'pkexec', 'systemctl')]
    found_services = services(run)
    openrgb = next((s for s in found_services if 'openrgb' in Path(s['executable'] or '').name.lower() and s['available']), None)
    lianli = next((s for s in found_services if 'lian' in Path(s['executable'] or '').name.lower() and s['available']), None)
    managed_openrgb = data_dir()/'hardware/openrgb/bin/openrgb'
    managed_lianli = data_dir()/'hardware/lianli/bin/lianli-daemon-rgb'
    components = {
        'openrgb': {'available': bool(shutil.which('openrgb') or openrgb or managed_openrgb.exists()), 'service': openrgb},
        'lianli': {'available': bool(lianli or managed_lianli.exists()), 'detected': any(d['kind'].startswith('lianli') for d in devices), 'service': lianli},
        'kingston': {'available': managed_openrgb.exists(), 'requires': 'Supported DDR5 SPD family; detection reads SPD and never writes it'},
    }
    try:
        wireless=wireless_devices()
        wireless_error=None
    except (OSError,ValueError,RuntimeError) as error:
        wireless=[];wireless_error=str(error)
    i2c = list(Path('/dev').glob('i2c-*'))
    return dict(ok=True, devices=devices, wireless_devices=wireless, wireless_error=wireless_error, dependencies=deps, services=found_services, components=components,
                permissions={'i2c_nodes':len(i2c), 'i2c_access':any(os.access(p, os.R_OK|os.W_OK) for p in i2c)},
                error=None)


def _lianli_ipc(method: str, params=None, *, runtime_dir=None, timeout=3):
    """Private newline JSON IPC with UID-owned runtime/socket and peer checks."""
    import json
    import socket
    import stat
    import struct
    uid=os.getuid()
    runtime=Path(runtime_dir) if runtime_dir is not None else Path('/run/user')/str(uid)
    info=runtime.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or stat.S_IMODE(info.st_mode)&0o077:
        raise PermissionError('Lian Li runtime directory must be private and owned by the current UID')
    path=runtime/'lianli-daemon.sock'
    node=path.lstat()
    if not stat.S_ISSOCK(node.st_mode) or node.st_uid!=uid:
        raise PermissionError('Lian Li IPC socket is not owned by the current UID')
    request={'method':method}
    if params is not None:request['params']=params
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        _,peer_uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if peer_uid!=uid:raise PermissionError('Lian Li IPC peer UID mismatch')
        client.sendall(json.dumps(request,separators=(',',':')).encode()+b'\n')
        payload=bytearray()
        while b'\n' not in payload:
            chunk=client.recv(65536)
            if not chunk:raise OSError('Lian Li IPC closed before its response')
            payload.extend(chunk)
            if len(payload)>1048576:raise ValueError('Lian Li IPC response exceeds one MiB')
        response=json.loads(payload.partition(b'\n')[0])
    if not isinstance(response,dict):raise ValueError('Malformed Lian Li IPC response')
    if response.get('status')!='ok':raise RuntimeError(str(response.get('message','Lian Li command failed')))
    return response.get('data')


def wireless_devices(ipc=None):
    ipc=ipc or _lianli_ipc
    result=ipc('ListDevices')
    if not isinstance(result,list):raise ValueError('Lian Li ListDevices is not an array')
    return [dict(device_id=str(d.get('device_id','')), name=str(d.get('name','Wireless device')),
                 is_unbound_wireless=bool(d.get('is_unbound_wireless',False)))
            for d in result if isinstance(d,dict) and str(d.get('device_id','')).startswith(('wireless:','wireless-unbound:'))]
