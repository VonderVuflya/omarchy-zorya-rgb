"""JSON-only UI/command-line interface. Hardware setup is always explicit."""
from __future__ import annotations
import argparse
import json
import sys
from .daemon import request
from .state import StateStore, validate_patch, DEFAULT_STATE, SETTINGS


class Parser(argparse.ArgumentParser):
    def error(self,message): raise ValueError(message)


def parser():
    root=Parser(prog='zorya-rgb',description='ZoryaRGB controller')
    commands=root.add_subparsers(dest='command',required=True)
    for name in ('status','devices','doctor','install','uninstall','daemon','restore','migrate'):
        commands.add_parser(name)
    onboarding=commands.add_parser('onboarding').add_subparsers(dest='action',required=True)
    onboarding.add_parser('plan')
    onboarding.add_parser('run').add_argument('--step',required=True)
    pairing=commands.add_parser('pair'); pairing.add_argument('--device',required=True)
    settings=commands.add_parser('set'); settings.add_argument('--json',required=True,dest='patch')
    presets=commands.add_parser('preset').add_subparsers(dest='action',required=True)
    presets.add_parser('save').add_argument('name')
    presets.add_parser('apply').add_argument('id')
    presets.add_parser('delete').add_argument('id')
    setup=commands.add_parser('setup')
    setup.add_argument('--component',choices=('openrgb','lianli','kingston','all'),default='all')
    setup.add_argument('--dry-run',action='store_true')
    return root


def execute(args,rpc=request,store=None):
    command=args.command
    if command=='onboarding':
        from . import onboarding
        return onboarding.plan() if args.action=='plan' else onboarding.run_step(args.step)
    if command=='pair':
        if not args.device.strip() or len(args.device)>256:
            raise ValueError('device must be a nonempty ID of at most 256 characters')
        from .setup import pair_device
        return pair_device(args.device)
    if command in ('doctor','setup','install','uninstall','migrate'):
        if command=='doctor':
            from .hardware import doctor
            return doctor()
        from . import setup
        if command=='setup': return setup.install(args.component,dry_run=args.dry_run)
        callback={'install':setup.install_plugin,'uninstall':setup.uninstall_plugin,'migrate':setup.migrate}[command]
        report=callback()
        if command=='migrate' and report.get('ok') and report.get('state'):
            try:
                rpc({'command':'set','patch':{k:v for k,v in report['state'].items() if k in SETTINGS}})
                report['applied_to_running_daemon']=True
            except (OSError,ConnectionError,TimeoutError) as error:
                report['applied_to_running_daemon']=False
                report['notice']='State saved; start the daemon to apply it: '+str(error)
        return report
    if command=='daemon':
        from .daemon import main
        main(); return {'ok':True,'error':None}
    if command=='set':
        patch=json.loads(args.patch)
        validate_patch(DEFAULT_STATE,patch)
        return rpc({'command':'set','patch':patch})
    if command=='preset':
        value={'name':args.name} if args.action=='save' else {'id':args.id}
        return rpc({'command':'preset_'+args.action,**value})
    try: return rpc({'command':command})
    except (OSError,ConnectionError,TimeoutError) as exc:
        if command not in ('status','devices'): raise
        error='Zorya daemon unavailable: '+str(exc)
        if command=='devices': return {'devices':[],'error':error}
        store=store or StateStore(); state=store.snapshot()
        return dict(state,connected=False,error=store.error or error,setup={'daemon':False},device_count=0,applying=False)


def main(argv=None,rpc=request,store=None):
    try:
        args=parser().parse_args(argv)
        result=execute(args,rpc=rpc,store=store)
        if not isinstance(result,dict): raise RuntimeError('Operation returned an invalid report')
        code=1 if result.get('ok') is False else 0
    except Exception as exc:
        result={'ok':False,'error':str(exc) or exc.__class__.__name__}; code=1
    print(json.dumps(result,allow_nan=False,ensure_ascii=False))
    return code


if __name__=='__main__': sys.exit(main())
