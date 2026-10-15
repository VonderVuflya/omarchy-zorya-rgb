#!/usr/bin/env python3
"""Pinned hardware setup. Only main() performs installation or service changes."""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from zorya_rgb import hardware

PINS={
 'lianli':('https://github.com/sgtaziz/lian-li-linux.git','d262007c9bfbe87ae7c9d390d68ec74e5deb4d0a'),
 'openrgb':('https://github.com/CalcProgrammer1/OpenRGB.git','6fbcf62d7694e7b92fd0a5884b40b92984fbd1b0'),
 'ffmpeg':('https://git.ffmpeg.org/ffmpeg.git','894da5ca7d742e4429ffb2af534fcda0103ef593'),
 'evdi':('https://github.com/DisplayLink/evdi.git','750044ce73cf2eec9178889c4f851f0ff01368b3'),
}
PACKAGES={
 'arch':['base-devel','git','rustup','clang','llvm','pkgconf','libusb','hidapi','libdrm','systemd','qt5-base','mbedtls3','cmake','python'],
 'debian':['build-essential','git','clang','llvm','pkg-config','libusb-1.0-0-dev','libudev-dev','libdrm-dev','qtbase5-dev','libhidapi-dev','libmbedtls-dev','cmake','python3-venv','python3-pip'],
 'fedora':['gcc','gcc-c++','make','git','rustup','clang','llvm','pkgconf-pkg-config','libusb1-devel','hidapi-devel','libdrm-devel','systemd-devel','qt5-qtbase-devel','mbedtls-devel','cmake','python3'],
}

def execute(argv,*,cwd=None,env=None,timeout=3600):
    print(json.dumps({'action':[str(a) for a in argv]}),flush=True)
    return subprocess.run([str(a) for a in argv],cwd=cwd,env=env,check=True,timeout=timeout)


def capture(argv):
    return subprocess.check_output(argv,text=True,timeout=15).strip()


def checkout(name,target):
    url,commit=PINS[name]
    if not (target/'.git').is_dir():
        target.mkdir(parents=True,exist_ok=True)
        execute(['git','init',target]);execute(['git','-C',target,'remote','add','origin',url])
        execute(['git','-C',target,'fetch','--depth=1','origin',commit])
        execute(['git','-C',target,'checkout','--detach',commit])
        execute(['git','-C',target,'submodule','update','--init','--recursive'])
    actual=capture(['git','-C',str(target),'rev-parse','HEAD'])
    if actual!=commit:raise RuntimeError(f'{name} source pin mismatch: {actual}')
    return target


def apply_patch(source,name):
    patch=ROOT/'patches'/name
    if subprocess.run(['git','-C',str(source),'apply','--reverse','--check',str(patch)],capture_output=True).returncode==0:
        return
    execute(['git','-C',source,'apply','--check',patch])
    execute(['git','-C',source,'apply',patch])


def dependencies(component):
    required=['git','make','cc','pkg-config']
    if component=='lianli':required.extend(['cargo','rustup','clang'])
    else:required.append('qmake')
    libraries=['libusb-1.0','libdrm'] if component=='lianli' else ['libusb-1.0','hidapi-hidraw','Qt5Widgets']
    missing=[tool for tool in required if not shutil.which(tool)]
    if component=='openrgb' and not mbedtls3_ready():missing.append('mbedtls3 development headers/libraries')
    if shutil.which('pkg-config'):
        missing.extend(lib for lib in libraries if subprocess.run(['pkg-config','--exists',lib]).returncode)
    if not missing:
        if component=='lianli':ensure_rust()
        return
    if not shutil.which('pkexec'):raise RuntimeError('Missing dependencies '+', '.join(missing)+'. Install polkit/pkexec and development packages first.')
    if shutil.which('pacman'):argv=['pkexec','pacman','-S','--needed','--noconfirm',*PACKAGES['arch']]
    elif shutil.which('apt-get'):
        if component=='lianli' and not shutil.which('rustup'):
            raise RuntimeError('Lian Li source build requires rustup with stable Rust. Automatic Rust installation is currently supported on Arch; install rustup on this distribution first, then retry.')
        argv=['pkexec','apt-get','install','-y',*PACKAGES['debian']]
    elif shutil.which('dnf'):argv=['pkexec','dnf','install','-y',*PACKAGES['fedora']]
    else:raise RuntimeError('Missing dependencies: '+', '.join(missing)+'; no supported package manager found')
    execute(argv,timeout=1800)
    missing=[tool for tool in required if not shutil.which(tool)]
    if component=='openrgb' and not mbedtls3_ready():missing.append('mbedtls3 development headers/libraries')
    if missing:raise RuntimeError('Still missing '+', '.join(missing)+'. Install the listed development dependencies before retrying.')
    if component=='lianli':ensure_rust()


def mbedtls3_ready():
    for prefix in (Path('/usr/include/mbedtls3'),Path('/usr/include')):
        for name in ('build_info.h','version.h'):
            path=prefix/'mbedtls'/name
            if path.exists() and re.search(r'MBEDTLS_VERSION_MAJOR\s+3\b',path.read_text()):
                libs=[Path('/usr/lib/mbedtls3/libmbedtls.so'),Path('/usr/lib/libmbedtls.so')]
                libs.extend(Path('/usr/lib').glob('*/libmbedtls.so'))
                return any(p.exists() for p in libs)
    return False


def ensure_rust():
    if subprocess.run(['rustup','run','stable','rustc','--version'],capture_output=True).returncode:
        execute(['rustup','toolchain','install','stable','--profile','minimal'],timeout=1800)


def build_lianli(root):
    dependencies('lianli')
    source=checkout('lianli',root/'source')
    # The supplement changes compatibility-patched lines. Detect it first,
    # otherwise reverse-checking the older patch on a second build can fail.
    supplement=ROOT/'patches/lianli-onboard-replay.patch'
    if subprocess.run(['git','-C',str(source),'apply','--reverse','--check',str(supplement)],capture_output=True).returncode:
        apply_patch(source,'lianli-rgb-compat.patch')
        apply_patch(source,'lianli-onboard-replay.patch')
    deps=root/'deps';deps.mkdir(parents=True,exist_ok=True)
    # Pin FFmpeg8 locally. Do not replace the system FFmpeg or load EVDI DKMS.
    if not (deps/'lib/libavcodec.so').exists():
        ffmpeg=checkout('ffmpeg',root/'ffmpeg')
        execute([ffmpeg/'configure','--prefix='+str(deps),'--enable-shared','--disable-static','--disable-programs','--disable-doc','--disable-x86asm','--disable-everything','--disable-autodetect','--enable-avcodec','--enable-avformat','--enable-swscale','--enable-swresample'],cwd=ffmpeg)
        execute(['make','-j'+str(min(os.cpu_count() or 2,8))],cwd=ffmpeg)
        execute(['make','install'],cwd=ffmpeg)
    if not (deps/'lib/libevdi.so').exists():
        evdi=checkout('evdi',root/'evdi')
        execute(['make','-C',evdi/'library'])
        execute(['make','-C',evdi/'library','install','PREFIX='+str(deps)])
    env=dict(os.environ)
    for key,extra in [('LIBRARY_PATH',deps/'lib'),('LD_LIBRARY_PATH',deps/'lib'),('PKG_CONFIG_PATH',deps/'lib/pkgconfig')]:
        env[key]=str(extra)+(os.pathsep+env[key] if env.get(key) else '')
    env['CARGO_TARGET_DIR']=str(root/'target')
    execute(['cargo','+stable','test','--locked','-p','lianli-daemon'],cwd=source,env=env)
    execute(['cargo','+stable','build','--locked','-p','lianli-daemon'],cwd=source,env=env)
    out=root/'bin';out.mkdir(exist_ok=True)
    shutil.copy2(root/'target/debug/lianli-daemon',out/'lianli-daemon.new')
    if shutil.which('strip'):execute(['strip',out/'lianli-daemon.new'])
    (out/'lianli-daemon.new').replace(out/'lianli-daemon')
    wrapper=out/'lianli-daemon-rgb'
    wrapper.write_text('#!/bin/sh\nset -eu\nZORYA_LIANLI_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\nexport LD_LIBRARY_PATH="$ZORYA_LIANLI_ROOT/deps/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\nexec "$ZORYA_LIANLI_ROOT/bin/lianli-daemon" --rgb-only "$@"\n')
    wrapper.chmod(0o755)
    return wrapper


def build_openrgb(root):
    dependencies('openrgb')
    source=checkout('openrgb',root/'source');apply_patch(source,'kingston-rc3-spd.patch')
    build=root/'build';build.mkdir(parents=True,exist_ok=True)
    argv=['qmake',source/'OpenRGB.pro','-after','CONFIG-=lrelease','CONFIG-=embed_translations']
    if Path('/usr/include/mbedtls3').is_dir():argv+=['INCLUDEPATH+=/usr/include/mbedtls3','LIBS+=-L/usr/lib/mbedtls3']
    execute(argv,cwd=build)
    execute(['make','-j'+str(min(os.cpu_count() or 2,8))],cwd=build)
    out=root/'bin';out.mkdir(exist_ok=True)
    shutil.copy2(build/'openrgb',out/'openrgb.new');(out/'openrgb.new').replace(out/'openrgb')
    return out/'openrgb'


def unit_quote(value):
    if '\n' in str(value) or '\r' in str(value):raise ValueError('Newline in systemd argument')
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'


def write_unit(units,name,argv):
    units.mkdir(parents=True,exist_ok=True)
    path=units/name
    text='[Unit]\nDescription=Zorya '+name+'\nAfter=graphical-session-pre.target\n\n[Service]\nType=simple\nExecStart='+ ' '.join(unit_quote(a) for a in argv)+'\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=default.target\n'
    path.write_text(text)


def privileged_rules(component,root):
    """Explicit setup is the only caller of these exact privileged operations."""
    source=ROOT/'systemd/60-zorya-lianli.rules'
    if component=='openrgb':
        script=root/'source/scripts/build-udev-rules.sh'
        if not script.exists():raise RuntimeError('Pinned OpenRGB udev generator missing')
        # Upstream script takes source-root as its first argument.
        execute(['bash',script,str(root/'source'),PINS['openrgb'][1]],cwd=root/'build')
        generated=root/'build/60-openrgb.rules'
        source=root/'zorya-openrgb.rules'
        if generated.exists():
            source.write_text('# Generated from pinned OpenRGB; active-user USB ACLs only.\n'+'\n'.join(line for line in generated.read_text().splitlines() if not line.startswith('#') and 'TAG+=' in line and 'RUN+=' not in line and ('usb' in line or 'hidraw' in line))+'\n')
        if not source.exists():raise RuntimeError('OpenRGB did not generate its USB ACL rules')
    dest='/etc/udev/rules.d/60-zorya-'+component+'.rules'
    execute(['pkexec','/usr/bin/install','-m','644',source,dest],timeout=120)
    execute(['pkexec','udevadm','control','--reload-rules'],timeout=120)
    execute(['pkexec','udevadm','trigger','--subsystem-match=usb','--action=change'],timeout=120)
    if component=='openrgb':
        execute(['pkexec','/usr/bin/install','-m','644',ROOT/'systemd/zorya-i2c.conf','/etc/modules-load.d/zorya-openrgb.conf'],timeout=120)
        execute(['pkexec','modprobe','i2c-dev'],timeout=120)
        execute(['pkexec','/usr/bin/install','-m','644',ROOT/'systemd/61-zorya-i2c.rules','/etc/udev/rules.d/61-zorya-i2c.rules'],timeout=120)
        execute(['pkexec','udevadm','control','--reload-rules'],timeout=120)
        execute(['pkexec','udevadm','trigger','--subsystem-match=i2c-dev','--action=change'],timeout=120)


def setup(component,data,adopt_only=False):
    if sys.platform!='linux':raise RuntimeError('Hardware setup requires Linux with systemd user services')
    report=hardware.doctor()
    chosen=['openrgb','lianli'] if component=='all' else ['openrgb' if component=='kingston' else component]
    if component=='all' and not report['components']['lianli']['detected']:chosen.remove('lianli')
    cfg=hardware.config_dir();cfg.mkdir(parents=True,exist_ok=True)
    units=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'systemd/user'
    data.mkdir(parents=True,exist_ok=True)
    metadata_path=data/'installation.json'
    metadata=json.loads(metadata_path.read_text()) if metadata_path.exists() else {'hardware_units':[],'adopted':[]}
    if not isinstance(metadata,dict):raise RuntimeError('Invalid installation metadata')
    metadata.setdefault('hardware_units',[])
    metadata.setdefault('adopted',[])
    metadata.setdefault('endpoints',{})
    for name in chosen:
        buildroot=data/'hardware'/name
        candidates=[s for s in report['services'] if s['available'] and not s['unit'].startswith('zorya-') and name in Path(s['executable']).name.lower()]
        candidate=next((s for s in candidates if s['active']),next(iter(candidates),None))
        if adopt_only and not candidate:continue
        if name=='lianli' and candidate:
            argv=list(candidate['argv'])
            # Adopt the full existing command/config, retaining explicitly configured cooling.
            if not argv or not candidate.get('config'):raise RuntimeError('Existing Lian Li command has no explicit config; cannot safely adopt its cooling policy')
            adopted_config=cfg/'lianli-adopted.json'
            settings=json.loads(Path(candidate['config']).read_text())
            settings.setdefault('rgb',{}).update(openrgb_server=True,openrgb_port=6743)
            adopted_config.write_text(json.dumps(settings,indent=2))
            argv[argv.index('--config')+1]=str(adopted_config)
            if not adopt_only:
                # Explicit setup upgrades the bridge as well as adopting its
                # cooling policy. Runtime installation still only adopts tools.
                executable=build_lianli(buildroot)
                argv=[str(executable),*[arg for arg in argv[1:] if arg!='--rgb-only']]
                privileged_rules(name,buildroot)
        elif name=='lianli':
            executable=build_lianli(buildroot)
            config=cfg/'lianli-rgb.json'
            if not config.exists():config.write_text(json.dumps({'lcds':[],'fans':{'speeds':[]},'fan_curves':[],'aio':{},'rgb':{'enabled':True,'openrgb_server':True,'openrgb_port':6743,'devices':[]}},indent=2))
            argv=[str(executable),'--config',str(config)]
            privileged_rules(name,buildroot)
        else:
            executable=build_openrgb(buildroot) if not adopt_only and (component in ('kingston','all') or not candidate and not shutil.which('openrgb')) else Path(candidate['executable'] if candidate else shutil.which('openrgb'))
            config=cfg/'openrgb';config.mkdir(exist_ok=True)
            argv=[str(executable),'--server','--server-host','127.0.0.1','--server-port','6742','--config',str(config)]
            if not adopt_only and (buildroot/'source').exists():privileged_rules(name,buildroot)
        unit='zorya-'+name+'.service'
        write_unit(units,unit,argv)
        if unit not in metadata['hardware_units']:metadata['hardware_units'].append(unit)
        metadata.setdefault('endpoints',{})[unit]=6743 if name=='lianli' else 6742
        for old in candidates:
            old['enabled']=subprocess.run(['systemctl','--user','is-enabled',old['unit']],capture_output=True).returncode==0
            if old['active'] or old['enabled']:
                if not any(s['unit']==old['unit'] for s in metadata['adopted']):metadata['adopted'].append(old)
                metadata_path.write_text(json.dumps(metadata,indent=2));metadata_path.chmod(0o600)
                execute(['systemctl','--user','disable','--now',old['unit']],timeout=90)
    # Previous watchers/helpers must not restore a different plugin's state.
    legacy='omarchy-rgb-resume.service'
    legacy_active=subprocess.run(['systemctl','--user','is-active','--quiet',legacy]).returncode==0
    legacy_enabled=subprocess.run(['systemctl','--user','is-enabled',legacy],capture_output=True).returncode==0
    if metadata['adopted'] and (legacy_active or legacy_enabled):
        if not any(s['unit']==legacy for s in metadata['adopted']):metadata['adopted'].append({'unit':legacy,'active':legacy_active,'enabled':legacy_enabled})
        metadata_path.write_text(json.dumps(metadata,indent=2));metadata_path.chmod(0o600)
        execute(['systemctl','--user','disable','--now',legacy])
    metadata_path.write_text(json.dumps(metadata,indent=2));metadata_path.chmod(0o600)
    execute(['systemctl','--user','daemon-reload'])
    if metadata['hardware_units']:execute(['systemctl','--user','enable','--now',*metadata['hardware_units']],timeout=90)
    print(json.dumps({'ok':True,'hardware_units':metadata['hardware_units'],'cooling':'preserved when adopted; fresh installation RGB-only'}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component',choices=['openrgb','lianli','kingston','all'],default='all')
    parser.add_argument('--data-home',type=Path,default=hardware.data_dir())
    parser.add_argument('--adopt-only',action='store_true',help='Use only installed tools; never build or install packages')
    args=parser.parse_args()
    try:setup(args.component,args.data_home.resolve(),args.adopt_only)
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        print(json.dumps({'ok':False,'error':str(error)}),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
