"""Private effective website history. Never changes Supabase story tables."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from .agent_shadow import read, write

BRANCH='website-effective-history'


def load_remote():
    result=subprocess.run(['git','ls-remote','--heads','origin',BRANCH],check=True,capture_output=True,text=True)
    if not result.stdout.strip(): return {}, None
    commit=result.stdout.split()[0]
    subprocess.run(['git','fetch','origin',commit],check=True,stdout=subprocess.DEVNULL)
    raw=subprocess.check_output(['git','show',commit+':effective-publications.json'],text=True)
    value=json.loads(raw)
    if not isinstance(value,dict): raise ValueError('Invalid remote history ledger')
    return value,commit


def record(root):
    state=read(root/'release.json')
    if state.get('public_verified') is not True: raise ValueError('Public verification required for ledger')
    ledger,parent=load_remote()
    if state['mode']=='rollback':
        target=read(root/'ledger-before.json')
        if ledger==target: return
        if ledger != read(root/'ledger-after.json'): raise ValueError('Ledger changed since publication; inspect rollback')
    else:
        target={**ledger,read(root/'latest-manifest.json')['version']:read(root/'records.json')}
        write(root/'ledger-after.json',target)
    if target==ledger: return
    scratch=Path(tempfile.mkdtemp(prefix='kidsnews-ledger-'))/'checkout'
    subprocess.run(['git','worktree','add','--detach',str(scratch),parent or 'HEAD'],check=True,stdout=subprocess.DEVNULL)
    write(scratch/'effective-publications.json',target)
    subprocess.run(['git','add','effective-publications.json'],cwd=scratch,check=True)
    subprocess.run(['git','-c','user.name=Kids News publication bot','-c','user.email=noreply@6ray.com','commit','-m','Record verified website '+state['mode']],cwd=scratch,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=scratch,check=True)


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('snapshot'); s.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('record'); r.add_argument('--release-dir',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.cmd=='snapshot': write(args.output,load_remote()[0])
        else: record(args.release_dir)
        print(json.dumps({'ok':True,'cmd':args.cmd})); return 0
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})); return 1


if __name__=='__main__': raise SystemExit(main())
