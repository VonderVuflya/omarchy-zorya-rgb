"""Private, bounded, read-only diagnostics and a user-submitted GitHub draft."""
from __future__ import annotations

import getpass
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import socket
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlencode

from . import __version__

ISSUE_BASE = 'https://github.com/VonderVuflya/omarchy-zorya-rgb/issues/new'
UNITS = ('zorya-rgb.service', 'zorya-openrgb.service', 'zorya-lianli.service')


def redact(value):
    """Scrub free-text evidence; structural collectors additionally exclude identities."""
    text = str(value or '')[:32000]
    text = re.sub(r'(?im)(authorization\s*[:=]\s*)(?:\r?\n[ \t]*)?(?:Bearer\s+|Basic\s+)?[^\r\n]+', r'\1[redacted]', text)
    text = re.sub(r'(?i)((?:[\w-]*(?:token|password|passwd|secret|api[_-]?key)|serial(?:[_ -]?(?:number|no))?|s/n)\s*["\x27]?\s*[:=]\s*)(?:["\x27][^"\x27\r\n]*["\x27]|[^\s,;}]+)', r'\1[redacted]', text)
    text = re.sub(r'(?i)\b(serial(?:[ _-]+(?:number|no\.?))?|s/?n)\s*(?:[:=]\s*|\s+)[\"\x27]?[^\s,;}\"\x27]+', r'\1 [redacted]', text)
    # Keep traceback source basenames and line/function context, never source roots.
    text = re.sub(r'(File\s+[\"\x27])(/[^\"\x27\r\n]+)([\"\x27])',
                  lambda match: match[1] + '[path]/' + Path(match[2]).name + match[3], text)
    text = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+)\b', '[redacted]', text)
    text = re.sub(r'https?://[^\s<>]+', '[URL redacted]', text)
    text = re.sub(r'(?:/home/[^/\s]+|/Users/[^/\s]+|/root|~)(?:/[^\s"\x27`<>]*)?', '[user path]', text)
    # Absolute paths may live outside HOME (mounted workspaces, runtime dirs,
    # custom home roots); remove them independently of the machine's layout.
    text = re.sub(r'(?<![\w/:\]])/(?:[^\s\"\x27`<>;,()\[\]]+)', '[path]', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\b', '[identity]', text)
    text = re.sub(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b', '[UUID]', text)
    text = re.sub(r'\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b', '[MAC]', text)
    text = re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', '[IP]', text)
    text = re.sub(r'(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:]+(?:%[\w]+)?', '[IP]', text)
    # Unlabelled high-entropy identifiers have no diagnostic value here.
    text = re.sub(r'\b(?=[A-Za-z0-9_-]{20,}\b)(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]+\b', '[identifier]', text)
    for identity in (getpass.getuser(), socket.gethostname()):
        if identity:
            text = re.sub(r'(?<!\w)' + re.escape(identity) + r'(?!\w)', '[identity]', text, flags=re.I)
    return ''.join(c for c in text if c in '\n\t' or ord(c) >= 32).replace('```', "'''")


def _probe(argv, *, timeout=1.5, limit=8192, details=False):
    """Bound elapsed time and total pipe reads; submission also needs exit evidence."""
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE if details else subprocess.DEVNULL,
                                   stdin=subprocess.DEVNULL,
                                   env={**os.environ, 'LC_ALL': 'C', 'GH_PROMPT_DISABLED': '1'})
    except OSError:
        return ({'started': False, 'exitcode': None, 'timed_out': False,
                 'stdout': '', 'stderr': '', 'truncated': False} if details else 'Unavailable')
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    deadline = time.monotonic() + timeout
    timed_out = truncated = False
    total = 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
            if details:
                selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True; break
                events = selector.select(remaining)
                if not events:
                    timed_out = True; break
                for key, _ in events:
                    part = os.read(key.fileobj.fileno(), min(4096, limit + 1 - total))
                    if not part:
                        selector.unregister(key.fileobj)
                        continue
                    streams[key.data].extend(part[:max(0, limit - total)])
                    total += len(part)
                    if total > limit:
                        truncated = True; break
                if truncated:
                    break
        if not (timed_out or truncated):
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
        process.stdout.close()
        if process.stderr:
            process.stderr.close()
    stdout = streams['stdout'].decode('utf-8', errors='replace').strip()
    stderr = streams['stderr'].decode('utf-8', errors='replace').strip()
    if details:
        return dict(started=True, exitcode=process.returncode, timed_out=timed_out,
                    stdout=stdout, stderr=stderr, truncated=truncated)
    note = '\n[probe timed out]' if timed_out else ('\n[output truncated]' if truncated else '')
    return (stdout or 'Unavailable') + note


def _read(path, limit=2048):
    try:
        with Path(path).open() as source:
            return source.read(limit).strip()
    except (OSError, UnicodeError):
        return 'Unavailable'


def _version(package):
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return 'not installed'


def _report_path():
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'zorya-rgb/support/latest.md'


def _save(body):
    path = _report_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.parent.stat().st_uid != os.getuid():
        raise OSError('Unsafe support directory')
    path.parent.chmod(0o700)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as target:
            name = target.name
            os.chmod(name, 0o600)
            target.write(body)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return str(path)


def _daemon_sections():
    from .daemon import request
    try:
        status = request({'command': 'status'}, timeout=1)
        inventory = request({'command': 'devices'}, timeout=1)
        lines = [f'{key}: {status[key]}' for key in ('connected', 'device_count', 'applying')
                 if isinstance(status.get(key), (bool, int))]
        if status.get('error'):
            lines.append('Daemon error: ' + redact(status['error']))
        last_error = status.get('last_error')
        if isinstance(last_error, dict):
            for key in ('operation', 'message', 'at', 'traceback'):
                value = last_error.get(key)
                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    lines.append('Last failure ' + key + ': ' + redact(value)[:12000])
        devices = []
        for device in inventory.get('devices', [])[:40]:
            if not isinstance(device, dict):
                continue
            name = redact(str(device.get('name', 'Unnamed device'))[:160])
            count = device.get('led_count')
            selected = device.get('selected')
            devices.append(f'- {name}; LEDs: {count if type(count) is int else "unknown"}; selected: {selected if type(selected) is bool else "unknown"}')
        return '\n'.join(lines) or 'Unavailable', '\n'.join(devices) or 'No devices reported'
    except (OSError, ValueError, ConnectionError, TimeoutError, TypeError, AttributeError) as exc:
        return 'Unavailable: ' + redact(exc), 'Unavailable (daemon offline or invalid response)'


def _logs():
    # Journal messages are not safe to publish verbatim. Keep only known failure
    # classifications, with no arguments, paths, device IDs or arbitrary prose.
    raw = _probe(['journalctl', '--user', '-u', 'zorya-rgb.service', '--since=-15min',
                  '-n', '30', '--no-pager', '-o', 'cat'], limit=8192)
    if raw == 'Unavailable':
        return 'Unavailable (journal could not be read)'
    labels = [(r'time[ -]?out|timed out', 'Timeout'), (r'permission denied|access denied', 'Permission denied'),
              (r'connection refused|disconnected|unavailable', 'Connection unavailable'),
              (r'recover|resume', 'Recovery/resume'), (r'error|exception|failed', 'Error/failure')]
    result = [f'- {label}: {sum(bool(re.search(pattern, line, re.I)) for line in raw.splitlines())} recent line(s)'
              for pattern, label in labels if re.search(pattern, raw, re.I)]
    return '\n'.join(result) or 'No recognized recent failure messages (raw logs intentionally omitted).'


def build_report(error='', operation=''):
    """Collect locally; return a preview and prefilled URL, never submit an issue."""
    root = Path(__file__).resolve().parent.parent
    daemon, devices = _daemon_sections()
    services = '\n'.join(f'{unit}: ' + _probe(['systemctl', '--user', 'show', unit,
        '--property=LoadState,ActiveState,SubState,Result', '--no-pager'], limit=512).replace('\n', '; ') for unit in UNITS)
    pci = _probe(['lspci', '-nnk'], limit=8192)
    # lspci's fixed model and driver fields exclude network addresses/host labels.
    pci = '\n'.join(line for line in pci.splitlines() if re.match(r'^(?:[0-9a-fA-F]{2}:|\s*Kernel (?:driver(?: in use)?|modules):)', line)) or 'Unavailable'
    usb = _probe(['lsusb'], limit=4096)
    usb = '\n'.join(match.group(1) for line in usb.splitlines()
                    if (match := re.search(r'\bID ([0-9a-fA-F]{4}:[0-9a-fA-F]{4} .*)', line))) or 'Unavailable'
    i2c = [f'{path.name}: read={os.access(path, os.R_OK)}, write={os.access(path, os.W_OK)}'
           for path in sorted(Path('/dev').glob('i2c-*'))[:32]]
    ui = _read(root / 'manifest.json')
    try:
        ui_version = json.loads(ui).get('version', 'Unavailable')
    except (ValueError, AttributeError):
        ui_version = 'Unavailable'
    omarchy = _read(Path.home() / '.local/share/omarchy/version', 128)
    hardware = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'omarchy-zorya-rgb/hardware'
    managed = [label + ' managed source: ' + _probe(['git', '-C', str(hardware / component / 'source'),
               'rev-parse', '--short=12', 'HEAD'], limit=80)
               for component, label in (('openrgb', 'OpenRGB'), ('lianli', 'Lian Li'))]
    modules = [name + ': ' + _read(Path('/sys/module') / name / 'version', 128)
               for name in ('nvidia', 'amdgpu', 'i915', 'i2c_dev', 'i2c_i801', 'i2c_piix4')
               if (Path('/sys/module') / name).exists()]
    versions = '\n'.join((f'ZoryaRGB: {__version__}; UI: {ui_version}',
        'Git commit: ' + _probe(['git', '-C', str(root), 'rev-parse', '--short=12', 'HEAD'], limit=80),
        f'Python: {platform.python_version()}; openrgb-python SDK: {_version("openrgb-python")}',
        'Omarchy: ' + omarchy,
        'OpenRGB package: ' + _probe(['pacman', '-Q', 'openrgb'], limit=256),
        'Lian Li package: ' + _probe(['pacman', '-Q', 'lianli-daemon'], limit=256),
        *managed, 'Kernel module versions: ' + ('; '.join(modules) or 'Unavailable (built-in modules use kernel version)')))
    operation = redact(operation)[:512] or 'Not specified'
    error = redact(error)[:12000] or 'No error supplied'
    title = 'ZoryaRGB: ' + operation.replace('\n', ' ')[:100]
    sections = [('Problem', f'Operation: {operation}\n\nError / actionable excerpt:\n\n{error}'),
        ('Reproduction', '1. [Describe the steps]\n2. [What triggered the problem?]\n\nExpected: [Describe expected behavior]\n\nActual: [Describe observed behavior]'),
        ('Versions', versions), ('System', f'Linux: {platform.release()}\nArchitecture: {platform.machine()}'),
        ('PCI models and kernel drivers', pci), ('USB VID/PID and models', usb),
        ('I2C device access (no bus reads)', '\n'.join(i2c) or 'No /dev/i2c-* nodes'),
        ('User services', services), ('Daemon', daemon), ('Device inventory (identities omitted)', devices),
        ('Recent user-service log summary', _logs())]
    body = '\n\n'.join('## ' + heading + '\n\n' + redact(content) for heading, content in sections)
    body += '\n\nReview this report before submitting. Raw logs, device identities and configuration are omitted.\n'
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    short = body
    url = ISSUE_BASE + '?' + urlencode({'title': title, 'body': short})
    truncated = len(url.encode()) > 7500
    if truncated:
        notice = '\n\n[Report truncated for the GitHub URL. Copy the full report from ZoryaRGB and paste it here before submitting.]\n'
        low, high = 0, len(body)
        while low < high:
            middle = (low + high + 1) // 2
            candidate = ISSUE_BASE + '?' + urlencode({'title': title, 'body': body[:middle] + notice})
            if len(candidate.encode()) <= 7500:
                low = middle
            else:
                high = middle - 1
        url = ISSUE_BASE + '?' + urlencode({'title': title, 'body': body[:low] + notice})
    result = dict(ok=True, error=None, title=title, body=body, issue_url=url,
                  fingerprint=fingerprint, issue_truncated=truncated, submit_available=bool(shutil.which('gh')))
    try:
        result['path'] = _save(body)
    except OSError:
        result['notice'] = 'Could not save a private local file; the full report is available in the preview.'
    return result


def copy_report():
    """Copy only the last locally generated report, with no shell interpolation."""
    path = _report_path()
    try:
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            raise OSError('Unsafe report file')
        with path.open('rb') as source:
            body = source.read(100001)
        if len(body) > 100000:
            raise OSError('Report too large')
    except OSError:
        return dict(ok=False, error='Generate a support report first.')
    executable = shutil.which('wl-copy') or shutil.which('xclip')
    if not executable:
        return dict(ok=False, error='No clipboard utility available. Copy the report preview manually.')
    argv = [executable] if Path(executable).name == 'wl-copy' else [executable, '-selection', 'clipboard']
    try:
        subprocess.run(argv, input=body, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2, check=True)
        return dict(ok=True, error=None)
    except (OSError, subprocess.SubprocessError):
        return dict(ok=False, error='Clipboard unavailable. Copy the report preview manually.')


def _private_bytes(path, limit=100000):
    """Validate the opened inode, avoiding symlink replacement between check/read."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise OSError('Unsafe private report')
        body = source.read(limit + 1)
        if len(body) > limit:
            raise OSError('Report too large')
        return body


def _receipt(path, data):
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as target:
            name = target.name
            os.chmod(name, 0o600)
            json.dump(data, target)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def submit_report(fingerprint):
    """Explicitly submit exactly the reviewed full report through the user's gh CLI.

    Collection and preview never invoke this function. No authentication probes,
    credential reads or retries happen here; uncertain attempts remain recorded.
    """
    failure = lambda message: dict(ok=False, error=message)
    if not isinstance(fingerprint, str) or not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        return failure('Generate and review a new support report before submitting.')
    path = _report_path()
    lock = None
    try:
        info = path.parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise OSError('Unsafe support directory')
        body = _private_bytes(path)
        if hashlib.sha256(body).hexdigest() != fingerprint:
            return failure('The report changed after preview. Generate and review it again before submitting.')
        lock_descriptor = os.open(path.parent / 'submission.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        lock = os.fdopen(lock_descriptor, 'r+')
        lock_info = os.fstat(lock.fileno())
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid() or stat.S_IMODE(lock_info.st_mode) != 0o600:
            raise OSError('Unsafe submission lock')
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return failure('A support submission is already running. Wait for its result.')
        receipt = path.parent / ('submission-' + fingerprint + '.json')
        url_pattern = r'https://github\.com/VonderVuflya/omarchy-zorya-rgb/issues/[0-9]+'
        if receipt.exists() or receipt.is_symlink():
            previous = json.loads(_private_bytes(receipt, 4096))
            url = previous.get('issue_url')
            if isinstance(url, str) and re.fullmatch(url_pattern, url):
                return dict(ok=True, error=None, issue_url=url, reused=True, already_submitted=True)
            return failure('A previous submission may have reached GitHub. Check GitHub issues before creating another report or using the browser.')
        executable = shutil.which('gh')
        if not executable:
            return failure('GitHub CLI unavailable. Use the browser draft, or install gh and run gh auth login.')
        # Record intent before the network operation so a timeout or crash cannot
        # silently trigger a second issue from another click on the same preview.
        _receipt(receipt, {'status': 'pending'})
        operation = re.search(r'^Operation: (.*)$', body.decode('utf-8'), re.M)
        title = 'ZoryaRGB: ' + (redact(operation[1]).strip()[:100] if operation else 'Support report')
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='reviewed-', suffix='.md') as snapshot:
            os.chmod(snapshot.name, 0o600)
            snapshot.write(body)
            snapshot.flush()
            output = _probe([executable, 'issue', 'create', '--repo', 'https://github.com/VonderVuflya/omarchy-zorya-rgb',
                             '--title', title, '--body-file', snapshot.name], timeout=60, limit=4096, details=True)
        url = output['stdout'].strip()
        if (output['exitcode'] == 0 and not output['timed_out'] and not output['truncated']
                and re.fullmatch(url_pattern, url)):
            _receipt(receipt, {'status': 'created', 'issue_url': url})
            return dict(ok=True, error=None, issue_url=url, reused=False, already_submitted=False)
        auth_rejected = (output['exitcode'] in (1, 4) and not output['timed_out']
                         and not output['truncated'] and not url
                         and re.search(r'gh auth login|not logged (?:in|into)|HTTP 401|requires authentication',
                                       output['stderr'], re.I))
        if not output['started'] or auth_rejected:
            receipt.unlink()
            return failure('GitHub submission failed. Run gh auth login and check access, or use the browser draft.')
        _receipt(receipt, {'status': 'uncertain'})
        return failure('Submission result is uncertain. Check GitHub issues before retrying or using the browser; this preview will not be submitted twice.')
    except (OSError, ValueError, TypeError, AttributeError):
        return failure('Unable to submit the private reviewed report safely. Check GitHub before retrying if submission had started; otherwise generate and review a new report or use the browser draft.')
    finally:
        if lock is not None:
            lock.close()
