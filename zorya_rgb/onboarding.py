"""Read-only setup diagnosis and individually authorized setup steps.

Only run_step installs anything. Discovery uses the bounded SDK transport and
never changes selection, modes, pairing, cooling, or colors.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

from . import hardware, setup
from .daemon import request
from .state import StateStore

STEPS = ('runtime', 'openrgb', 'lianli', 'verify')


def _runtime_ready():
    python = hardware.data_dir()/'venv/bin/python'
    if not python.is_file():
        return False
    try:
        result = subprocess.run([str(python), '-c', 'import openrgb; import zorya_rgb'],
                                capture_output=True, text=True, timeout=10, check=False)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _probe_local(port):
    from .openrgb_backend import OpenRGBBackend
    from .sdk_transport import connect_client
    client = None
    try:
        client = connect_client(address='127.0.0.1', port=port,
                                name='Zorya setup diagnosis', protocol_version=1 if port == 6743 else None)
        backend = OpenRGBBackend(endpoints=[('127.0.0.1', port)])
        backend.clients = [(('127.0.0.1', port), client)]
        backend._discover()
        devices = backend.devices(StateStore().snapshot()['devices'])
        return dict(ok=bool(devices), devices=devices,
                    error=None if devices else f'SDK on port {port} has no devices yet')
    except Exception as error:
        return dict(ok=False, devices=[], error=str(error))
    finally:
        if client is not None:
            try: client.disconnect()
            except Exception: pass


def _probe(port):
    if importlib.util.find_spec('openrgb') is not None:
        return _probe_local(port)
    # A checkout may run under stdlib Python while an existing private SDK is
    # installed. Keep all source imports pointed at this checkout for diagnosis.
    python = hardware.data_dir()/'venv/bin/python'
    if not python.is_file():
        return dict(ok=False, devices=[], error='Private OpenRGB SDK runtime is not installed')
    source = ('import sys,json;sys.path.insert(0,' + repr(str(setup.ROOT)) + ');'
              'from zorya_rgb.onboarding import _probe_local;print(json.dumps(_probe_local(' + str(port) + ')))')
    try:
        result = subprocess.run([str(python), '-c', source], capture_output=True,
                                text=True, timeout=10, check=True)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return dict(ok=False, devices=[], error=str(error))


def _full_mode(service):
    if not service.get('available'):
        return False
    executable = Path(service.get('executable') or '')
    if 'lianli' not in executable.name.lower() and 'lian-li' not in executable.name.lower():
        return False
    if '--rgb-only' in service.get('argv', []):
        return False
    # Match the existing installer's recognition of explicit RGB-only wrappers.
    if executable.name.endswith('-rgb'):
        try:
            with executable.open(encoding='utf-8') as stream:
                text = stream.read(8192)
            if re.search(r'(?m)^\s*exec[^\n]*\s--rgb-only(?:\s|$)', text):
                return False
        except (OSError, UnicodeError):
            pass
    return True


def plan():
    diagnostics = hardware.doctor()
    runtime = _runtime_ready()
    try:
        daemon = bool(request({'command': 'status'}).get('setup', {}).get('daemon'))
    except (OSError, ValueError, ConnectionError, TimeoutError):
        daemon = False
    openrgb = _probe(6742)
    detected = bool(diagnostics.get('components', {}).get('lianli', {}).get('detected'))
    lianli = _probe(6743) if detected else dict(ok=False, devices=[], error=None)
    blocked = detected and not lianli['ok'] and any(_full_mode(s) for s in diagnostics.get('services', []))
    cooling_error = ('Existing full-mode Lian Li service controls cooling/LCDs and cannot be replaced safely. '
                     'Keep it running and configure a compatible local RGB SDK explicitly before retrying setup.')
    openrgb_optional = detected and lianli['ok'] and not openrgb['ok']
    ready = runtime and daemon and (openrgb['ok'] or openrgb_optional) and (not detected or lianli['ok'])
    def step(identity, label, description, status, required=True):
        return dict(id=identity, label=label, description=description, status=status, required=required)
    steps = [
        step('runtime', 'Zorya runtime', 'Install the private Python SDK and user daemon; leave hardware services unchanged.',
             'ready' if runtime and daemon else 'needed'),
        step('openrgb', 'OpenRGB', 'The Lian Li bridge already provides devices; OpenRGB is optional in advanced setup.' if openrgb_optional else
             'Reuse a reachable SDK, or install OpenRGB, required build packages, device permissions and its user service.',
             'skipped' if openrgb_optional else 'ready' if openrgb['ok'] else 'needed', not openrgb_optional),
        step('lianli', 'Lian Li RGB bridge', cooling_error if blocked else
             'Reuse a reachable bridge, or install an RGB-only bridge, build packages, USB permissions and its user service; keep cooling unchanged.',
             'skipped' if not detected else 'ready' if lianli['ok'] else 'blocked' if blocked else 'needed', detected),
        step('verify', 'Verify devices', 'Read device inventories through bounded local SDK connections. Select devices in the panel afterward.',
             'ready' if ready else 'needed'),
    ]
    devices = {d['id']: d for probe in (openrgb, lianli) for d in probe['devices']}
    return dict(ok=True, steps=steps, summary='Ready; choose devices in the panel.' if ready else
                'Review the steps, then start setup. Package installation may request administrator authentication.',
                ready=ready, error=cooling_error if blocked else None, diagnostics=diagnostics,
                devices=list(devices.values()), verification_errors=[p['error'] for p in
                    ((lianli,) if openrgb_optional else (openrgb, lianli)) if p.get('error')])


def run_step(step):
    if step not in STEPS:
        return dict(ok=False, error='Unknown onboarding step: ' + str(step))
    report = plan()
    item = next(s for s in report['steps'] if s['id'] == step)
    if item['status'] == 'blocked':
        return dict(ok=False, error=item['description'], hint='Preserve the existing cooling service and configure its RGB SDK explicitly.')
    if step == 'verify':
        if not report['ready']:
            errors = report['verification_errors'] or ['Private runtime or user daemon is not ready']
            return dict(ok=False, error='; '.join(errors), hint='Complete the required setup steps, then retry verification.', devices=report['devices'])
        return dict(ok=True, error=None, devices=report['devices'])
    if item['status'] in ('ready', 'skipped'):
        return dict(ok=True, error=None, skipped=True)
    if step != 'runtime':
        return setup.install(step)
    try:
        subprocess.run([sys.executable, str(setup.ROOT/'scripts/install-plugin.py'), '--runtime-only'],
                                capture_output=True, text=True, check=True, timeout=600)
        return dict(ok=True, error=None)
    except (OSError, subprocess.SubprocessError) as error:
        return dict(ok=False, error=str(getattr(error, 'stderr', None) or error)[-8000:],
                    hint='Retry the runtime step after resolving the installation error.')
