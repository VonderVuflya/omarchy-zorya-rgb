"""Release-pinned, explicit updates; checking never contacts hardware or services."""
from __future__ import annotations

import ast
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request

from . import __version__, hardware

REPOSITORY = 'https://github.com/VonderVuflya/omarchy-zorya-rgb'
API = 'https://api.github.com/repos/VonderVuflya/omarchy-zorya-rgb/releases/latest'
PLUGIN_ID = 'vondervuflya.zorya-rgb'
CACHE_TTL = 6 * 60 * 60
FAILURE_TTL = 5 * 60
MAX_RESPONSE = 128 * 1024
_VERSION = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')


def _paths():
    data = hardware.data_dir()
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    return data, config/'omarchy/plugins'/PLUGIN_ID, data/'app'


def _version(value):
    if not isinstance(value, str) or len(value) > 64 or not _VERSION.fullmatch(value):
        raise ValueError('Expected a stable X.Y.Z version')
    return tuple(map(int, value.split('.')))


def _read_json(path):
    if path.stat().st_size > MAX_RESPONSE:
        raise ValueError('Metadata exceeds size limit')
    return json.loads(path.read_text())


def _manifest_version(path):
    try:
        manifest = _read_json(path/'manifest.json')
        if manifest.get('id') != PLUGIN_ID:
            return None
        value = manifest['version']; _version(value)
        return value
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _installed():
    _, plugin, app = _paths()
    plugin_version = _manifest_version(plugin)
    runtime_version = _manifest_version(app)
    # Marketplace checkouts can run before the private runtime is installed.
    if runtime_version is None:
        runtime_version = __version__
    versions = [v for v in (plugin_version, runtime_version) if v is not None]
    return dict(installed_version=min(versions, key=_version), runtime_version=runtime_version,
                plugin_version=plugin_version, running_runtime_version=__version__)


def _availability(latest_version, installed):
    versions = [_version(installed[key]) for key in ('runtime_version','plugin_version') if installed.get(key)]
    latest = _version(latest_version)
    ahead = any(version > latest for version in versions)
    return dict(update_available=not ahead and any(version < latest for version in versions),
                version_mismatch=len(set(versions)) > 1,
                hint='Latest release is older than an installed component; reconcile versions through explicit Setup.' if ahead else None)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected redirect from GitHub release API')


def _fetch_release_payload():
    request = urllib.request.Request(API, headers={'Accept':'application/vnd.github+json', 'User-Agent':'ZoryaRGB-release-check'})
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=10) as response:
        payload = response.read(MAX_RESPONSE + 1)
    if len(payload) > MAX_RESPONSE:
        raise ValueError('GitHub release response exceeds size limit')
    return json.loads(payload)


def _fetch_release():
    # A socket timeout restarts for each read and does not bound DNS lookup.
    # Supervise a single-purpose child so the entire operation has a deadline.
    code = ('import json,sys; sys.path.insert(0,sys.argv[1]); '
            'from zorya_rgb.updates import _fetch_release_payload; '
            'print(json.dumps(_fetch_release_payload()))')
    try:
        child = subprocess.run([sys.executable,'-I','-c',code,str(Path(__file__).resolve().parent.parent)],
                               capture_output=True, check=True, timeout=15)
    except subprocess.TimeoutExpired as error:
        raise ValueError('GitHub release check exceeded the 15-second deadline') from error
    except subprocess.CalledProcessError as error:
        raise ValueError('GitHub release request failed') from error
    # JSON escaping can expand the already bounded HTTP payload by up to 6x.
    if len(child.stdout) > MAX_RESPONSE * 6:
        raise ValueError('GitHub release child response exceeds size limit')
    return json.loads(child.stdout)


def _release(payload):
    if not isinstance(payload, dict) or payload.get('draft') is not False or payload.get('prerelease') is not False:
        raise ValueError('GitHub did not return a stable published release')
    tag = payload.get('tag_name')
    if not isinstance(tag, str) or not tag.startswith('v'):
        raise ValueError('Release tag must be vX.Y.Z')
    version = tag[1:]; _version(version)
    url = REPOSITORY+'/releases/tag/'+tag
    if payload.get('html_url') != url:
        raise ValueError('Unexpected release repository or URL')
    return dict(latest_version=version, release_url=url, tag=tag)


def _cache_path():
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'omarchy-zorya-rgb/updates.json'


def check(force=False):
    """Return release information; errors are cached briefly and never alter RGB."""
    base = dict(ok=False, error=None, latest_version=None, release_url=None, tag=None,
                update_available=False, cached=False, hint=None, **_installed())
    base['version_mismatch'] = base['plugin_version'] is not None and base['plugin_version'] != base['runtime_version']
    path = _cache_path()
    now = time.time()
    try:
        cached = _read_json(path)
        age = now - cached['checked_at']
        if not force and 0 <= age < (CACHE_TTL if cached['ok'] else FAILURE_TTL):
            if cached['ok']:
                _release(dict(tag_name=cached['tag'], html_url=cached['release_url'], draft=False, prerelease=False))
            base.update({key:cached.get(key) for key in ('ok','error','latest_version','release_url','tag','checked_at')})
            base['cached'] = True
            if base['ok']:
                base.update(_availability(base['latest_version'], base))
            return base
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    base['checked_at'] = now
    try:
        base.update(_release(_fetch_release()), ok=True)
        base.update(_availability(base['latest_version'], base))
    except (OSError, ValueError, TypeError, TimeoutError) as error:
        base['error'] = 'Could not check GitHub releases: '+str(error)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as handle:
            json.dump(base, handle); temporary = Path(handle.name)
        temporary.replace(path)
    except OSError:
        pass  # An unwritable cache does not turn a successful check into failure.
    return base


def _run(argv, timeout=60):
    return subprocess.run([str(part) for part in argv], check=True, capture_output=True, text=True, timeout=timeout)


def _clone_release(tag, destination):
    _run(['git','-c','core.hooksPath=/dev/null','clone','--depth','1','--single-branch','--branch',tag,'--',REPOSITORY+'.git',destination],timeout=120)
    head = _run(['git','-C',destination,'rev-parse','HEAD']).stdout.strip()
    tagged = _run(['git','-C',destination,'rev-parse','refs/tags/'+tag+'^{commit}']).stdout.strip()
    if head != tagged:
        raise ValueError('Checkout does not match the approved release tag')


def _assert_clean(path):
    if (path/'.git').exists():
        changed = _run(['git','-C',path,'status','--porcelain','--untracked-files=normal']).stdout.strip()
        if changed:
            raise ValueError('Local edits in '+str(path)+'; preserve or commit them before updating')


def _project(path):
    with (path/'pyproject.toml').open('rb') as handle:
        return tomllib.load(handle)['project']


def _validate_source(path, tag, current):
    version = tag[1:]
    if _manifest_version(path) != version:
        raise ValueError('Release manifest identity/version does not match the approved tag')
    for item in path.rglob('*'):
        if item.is_symlink():
            raise ValueError('Release source contains a symlink')
    module = ast.parse((path/'zorya_rgb/__init__.py').read_text())
    values = [ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    project = _project(path)
    if values != [version] or project.get('version') != version or project.get('name') != 'omarchy-zorya-rgb':
        raise ValueError('Release runtime, package and plugin versions differ')
    manifest = _read_json(path/'manifest.json')
    for entry in manifest.get('entryPoints', {}).values():
        if not isinstance(entry, str) or Path(entry).is_absolute() or '..' in Path(entry).parts or not (path/entry).is_file():
            raise ValueError('Invalid release QML entry point')
    if not (path/'BarWidget.qml').is_file() or not (path/'bin/zorya-rgb').is_file():
        raise ValueError('Release lacks required plugin files')
    prior = _project(current)
    for field in ('dependencies', 'optional-dependencies', 'requires-python'):
        if project.get(field) != prior.get(field):
            raise ValueError('Release changes dependencies; run explicit Setup from the release instructions instead')


def _runtime_status(timeout):
    from .daemon import request
    return request({'command':'status'}, timeout=timeout)


def _verify_runtime(version):
    """Wait at most six seconds for the restarted daemon's own version."""
    deadline = time.monotonic() + 6
    for attempt in range(12):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            response = _runtime_status(timeout=min(0.5, remaining))
            if isinstance(response, dict) and response.get('runtime_version') == version:
                return
        except (OSError, ValueError):
            pass
        remaining = deadline - time.monotonic()
        if attempt < 11 and remaining > 0:
            time.sleep(min(0.25, remaining))
    raise ValueError('Restarted Zorya daemon did not report release '+version+' within six seconds')


def apply(tag):
    """Install exactly the confirmed release with source backups and rollback."""
    result = dict(ok=False, error=None, tag=tag)
    stage = None; lock = None; swaps = []
    try:
        if not isinstance(tag, str) or not tag.startswith('v'):
            raise ValueError('Approved tag must be vX.Y.Z')
        _version(tag[1:])
        data, plugin, app = _paths()
        if not plugin.is_dir() or not app.is_dir() or plugin.is_symlink() or app.is_symlink():
            raise ValueError('Complete plugin/runtime installation is required; run Setup first')
        # Serialize against concurrent update clicks without blocking the UI.
        lock = (data/'update.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = check(force=True)
        if not current['ok']:
            raise ValueError(current['error'])
        if tag != current['tag']:
            raise ValueError('Latest release changed; refresh and confirm the new version')
        availability = _availability(tag[1:], _installed())
        if not current['update_available'] or not availability['update_available']:
            raise ValueError(availability['hint'] or 'The approved release is already installed or older')
        _assert_clean(plugin); _assert_clean(app)
        # Each staged directory lives beside its destination for atomic rename.
        stage = Path(tempfile.mkdtemp(prefix='.zorya-update-',dir=data))
        checkout = stage/'source'
        _clone_release(tag, checkout)
        _validate_source(checkout, tag, app)
        _run(['omarchy','plugin','validate',checkout],timeout=30)
        plugin.parent.mkdir(parents=True, exist_ok=True)
        plugin_stage = Path(tempfile.mkdtemp(prefix='.zorya-update-',dir=plugin.parent))
        try:
            shutil.copytree(checkout, plugin_stage/'source')
            for target, prepared in ((plugin,plugin_stage/'source'), (app,checkout)):
                backup = target.parent/('.'+target.name+'.before-update-'+stage.name)
                target.rename(backup)
                swaps.append((target,backup))
                prepared.rename(target)
            _run(['systemctl','--user','restart','zorya-rgb.service'])
            _run(['systemctl','--user','is-active','--quiet','zorya-rgb.service'])
            _verify_runtime(tag[1:])
        finally:
            shutil.rmtree(plugin_stage)
        result.update(ok=True, installed_version=tag[1:], latest_version=tag[1:],
                      backups=[str(backup) for _,backup in swaps], state_preserved=True, reload_required=True)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as error:
        result['error'] = 'Update failed: '+str(error)
        rollback_errors = []
        for target, backup in reversed(swaps):
            try:
                if target.exists():
                    # Retain failed source for inspection; never delete the previous install.
                    target.rename(target.parent/('.'+target.name+'.failed-update-'+stage.name))
                backup.rename(target)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if swaps and not rollback_errors:
            try:
                _run(['systemctl','--user','restart','zorya-rgb.service'])
            except (OSError, subprocess.SubprocessError) as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            result['rollback_error'] = '; '.join(rollback_errors)
    finally:
        if stage is not None:
            shutil.rmtree(stage,ignore_errors=True)
        if lock is not None:
            lock.close()
    return result
