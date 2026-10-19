#!/usr/bin/env python3
"""Install Zorya explicitly into XDG directories; keep all saved RGB state."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from zorya_rgb import hardware, runtime


def run(argv,timeout=600):
    subprocess.run([str(a) for a in argv],check=True,timeout=timeout,env=runtime.clean_env())


def quote(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'


def install(data, *, runtime_only=False):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    identity=manifest.get('id','vondervuflya.zorya-rgb')
    if not identity or any(x in identity for x in ('/','\\','..')):raise ValueError('Unsafe manifest ID')
    config=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    plugin=config/'omarchy/plugins'/identity
    data.mkdir(parents=True,exist_ok=True)
    # A stable source location survives deletion or movement of the checkout.
    app=data/'app';app.mkdir(exist_ok=True)
    ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache','.venv','node_modules','build','dist')
    for name in ('zorya_rgb','bin','scripts','patches','systemd'):
        if ROOT!=app and (ROOT/name).exists():shutil.copytree(ROOT/name,app/name,dirs_exist_ok=True,ignore=ignore)
    for name in ('pyproject.toml','LICENSE','manifest.json'):
        if ROOT!=app and (ROOT/name).exists():shutil.copy2(ROOT/name,app/name)
    env=data/'venv'
    python=runtime.prepare(data,app,run)
    for file in ROOT.iterdir():
        if ROOT!=app and file.suffix in ('.qml','.js'):shutil.copy2(file,app/file.name)
    if ROOT!=app and (ROOT/'qml').is_dir():shutil.copytree(ROOT/'qml',app/'qml',dirs_exist_ok=True)
    if not runtime_only:
        plugin.mkdir(parents=True,exist_ok=True)
        for file in ROOT.iterdir():
            if file.suffix in ('.qml','.js') or file.name=='manifest.json':shutil.copy2(file,plugin/file.name)
        if (ROOT/'qml').is_dir():shutil.copytree(ROOT/'qml',plugin/'qml',dirs_exist_ok=True)
    # CLI dispatcher avoids relying on the invoking desktop shell's PATH.
    launcher=data/'bin/zorya-rgb';launcher.parent.mkdir(exist_ok=True)
    launcher.write_text(runtime.launcher(python,app));launcher.chmod(0o755)
    if not runtime_only:
        plugin_bin=plugin/'bin';plugin_bin.mkdir(exist_ok=True)
        wrapper=plugin_bin/'zorya-rgb'
        if wrapper.is_symlink():wrapper.unlink()
        wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(launcher))+' "$@"\n')
        wrapper.chmod(0o755)
    bindir=Path.home()/'.local/bin';bindir.mkdir(parents=True,exist_ok=True)
    link=bindir/'zorya-rgb'
    if link.exists() and not link.is_symlink():raise RuntimeError('Refusing to overwrite an existing non-symlink zorya-rgb launcher')
    link.unlink(missing_ok=True);link.symlink_to(launcher)
    units=config/'systemd/user';units.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'systemd/zorya-rgb.service.in').read_text().replace('@ZORYA_LAUNCHER@',quote(launcher))
    (units/'zorya-rgb.service').write_text(text)
    path=data/'installation.json'
    metadata=json.loads(path.read_text()) if path.exists() else {}
    metadata.update(app=str(app),venv=str(env))
    if not runtime_only:metadata.update(plugin=str(plugin),plugin_id=identity)
    path.write_text(json.dumps(metadata,indent=2));path.chmod(0o600)
    if not runtime_only:
        run([python,app/'scripts/build-hardware.py','--component','all','--adopt-only','--data-home',data],180)
    run(['systemctl','--user','daemon-reload'])
    run(['systemctl','--user','enable','--now','zorya-rgb.service'],90)
    if runtime_only:
        print(json.dumps({'ok':True,'error':None,'runtime_only':True,'hardware_setup':'unchanged'}))
        return
    if not shutil.which('omarchy'):raise RuntimeError('Omarchy CLI is required to register the native bar widget')
    shell_config=config/'omarchy/shell.json'
    if shell_config.is_file():
        import tempfile
        backups=data/'backups';backups.mkdir(exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='shell-before-zorya-',suffix='.json',dir=backups)
        os.close(fd);shutil.copy2(shell_config,name)
    run(['omarchy','plugin','validate',plugin],30)
    run(['omarchy-shell','shell','rescanPlugins'],30)
    run(['omarchy','plugin','enable',identity,'--section','right'],30)
    print(json.dumps({'ok':True,'plugin':str(plugin),'state_preserved':True,'hardware_setup':'separate explicit action'}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-home',type=Path,default=hardware.data_dir())
    parser.add_argument('--runtime-only',action='store_true',help='Install private SDK and user daemon without hardware adoption or plugin registration')
    args=parser.parse_args()
    try:install(args.data_home.resolve(),runtime_only=args.runtime_only)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(json.dumps({'ok':False,'error':str(error)}),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
