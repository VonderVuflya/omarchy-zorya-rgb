"""Explicit private-runtime creation independent of mutable Python aliases."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

SYSTEM_PYTHON=Path('/usr/bin/python3')
PYTHON_ENV=('PYTHONHOME','PYTHONPATH','PYTHONEXECUTABLE','__PYVENV_LAUNCHER__')


def clean_env():
    return {key:value for key,value in os.environ.items() if key not in PYTHON_ENV}


def base_python():
    candidates=(SYSTEM_PYTHON,Path(getattr(sys,'_base_executable',sys.executable)))
    for candidate in candidates:
        try:
            resolved=candidate.resolve(strict=True)
            if not resolved.name.startswith('python'):continue
            result=subprocess.run([str(resolved),'-I','-c','import sys,venv; raise SystemExit(sys.version_info < (3,11))'],
                                  env=clean_env(),capture_output=True,timeout=10,check=False)
            if result.returncode==0:return resolved
        except (OSError,subprocess.SubprocessError):pass
    raise RuntimeError('Python 3.11+ with venv is required to prepare the private runtime')


def _backup_path(data,prefix):
    path=Path(tempfile.mkdtemp(prefix=prefix,dir=data))
    path.rmdir()
    return path


def prepare(data,app,run):
    """Rebuild only on explicit setup; preserve the previous venv on failure."""
    data=Path(data);env=data/'venv';backup=None
    creator=base_python()
    if env.is_symlink() or env.exists() and not env.is_dir():
        raise RuntimeError('Refusing to replace an unexpected runtime path')
    if env.exists():
        run(['systemctl','--user','stop','zorya-rgb.service'],90)
        backup=_backup_path(data,'venv.before-runtime-')
        env.rename(backup)
    try:
        run([creator,'-I','-m','venv','--copies',env])
        python=env/'bin/python'
        run([python,'-I','-m','pip','install','--disable-pip-version-check',str(app)+'[hardware]'])
        run([python,'-I','-c','import fcntl,openrgb,zorya_rgb'])
        # Later installer steps may fail; restore the existing daemon now.
        if backup is not None:run(['systemctl','--user','start','zorya-rgb.service'],90)
    except Exception:
        if env.exists():env.rename(_backup_path(data,'venv.failed-runtime-'))
        if backup is not None:
            backup.rename(env)
            try:run(['systemctl','--user','start','zorya-rgb.service'],90)
            except (OSError,subprocess.SubprocessError):pass
        raise
    return python


def launcher(python,app):
    """Retain stdlib diagnostics/setup if the private interpreter cannot start."""
    import shlex
    clean='/usr/bin/env '+ ' '.join('-u '+key for key in PYTHON_ENV)
    code='import sys; sys.path.insert(0, '+repr(str(app))+'); from zorya_rgb.cli import main; raise SystemExit(main())'
    probe=shlex.quote('import sys; raise SystemExit(sys.version_info < (3,11))')
    return ('#!/bin/sh\n'
            'python='+shlex.quote(str(python))+'\n'
            'if ! '+clean+' "$python" -I -c '+probe+' >/dev/null 2>&1; then\n'
            '    python=/usr/bin/python3\n'
            'fi\n'
            'exec '+clean+' "$python" -I -c '+shlex.quote(code)+' "$@"\n')
