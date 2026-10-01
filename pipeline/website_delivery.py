"""Artifact Git handoff and CI receipts. Publishing credentials never live on VM."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .agent_shadow import read, write
from .website_release import check_reader, sha


def validate_receipt(root):
    receipt = read(root/'approval.json')
    if receipt['operation'] not in ('publish','rollback','resume'): raise ValueError('Unknown operation')
    if datetime.now(timezone.utc) > datetime.fromisoformat(receipt['expires_at']): raise ValueError('Release approval expired')
    if receipt.get('target') != 'kidsnews.21mins.com' or receipt.get('ack_same_day_slots') is not True:
        raise ValueError('Target/slot acknowledgement missing')
    check_reader((root/'reader.zip').read_bytes(),read(root/'latest-manifest.json'))
    if receipt['zip_sha256'] != sha((root/'reader.zip').read_bytes()): raise ValueError('Approval hash mismatch')
    if receipt.get('records_sha256') != sha((root/'records.json').read_bytes()): raise ValueError('Approval records hash mismatch')
    if receipt['operation'] != 'publish' and not str(receipt.get('backup_run_id','')).isdigit():
        raise ValueError('Resume/rollback requires original CI run backup')
    return receipt


def handoff(artifact, branch, operation='publish', backup_run_id=None, push=False):
    if not re.fullmatch(r'codex/website-release-[a-z0-9-]+',branch): raise ValueError('Use a new website-release branch')
    files = ('reader.zip','latest-manifest.json','records.json')
    check_reader((artifact/'reader.zip').read_bytes(),read(artifact/'latest-manifest.json'))
    receipt = {'operation':operation,'backup_run_id':backup_run_id,'target':'kidsnews.21mins.com',
        'ack_same_day_slots':True,'zip_sha256':sha((artifact/'reader.zip').read_bytes()),
        'records_sha256':sha((artifact/'records.json').read_bytes()),
        'expires_at':(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat()}
    repo = Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
    if not (repo/'.github/workflows/publish-reader.yml').exists(): raise ValueError('Bot snapshot with publishing workflow required')
    remote = subprocess.check_output(['git','remote','get-url','origin'],text=True).strip()
    if not remote.endswith(('daijiong1977/grokbot-kidsnews.git','daijiong1977/grokbot-kidsnews')):
        raise ValueError('Artifact pushes only allowed in grokbot-kidsnews')
    if subprocess.check_output(['git','ls-remote','--heads','origin',branch],text=True).strip():
        raise ValueError('Release branch already exists; choose a new name')
    scratch = Path(tempfile.mkdtemp(prefix='kidsnews-release-')) / 'checkout'
    subprocess.run(['git','worktree','add','--detach',str(scratch),'HEAD'],check=True,stdout=subprocess.DEVNULL)
    target = scratch/'releases/current'; target.mkdir(parents=True)
    for name in files: shutil.copyfile(artifact/name,target/name)
    write(target/'approval.json',receipt); validate_receipt(target)
    subprocess.run(['git','add','--','releases/current'],cwd=scratch,check=True)
    staged = subprocess.check_output(['git','diff','--cached','--name-only'],cwd=scratch,text=True).splitlines()
    if set(staged) != {'releases/current/'+name for name in (*files,'approval.json')}:
        raise ValueError('Unexpected staged files; inspect '+str(scratch))
    subprocess.run(['git','-c','user.name=Kids News artifact bot','-c','user.email=noreply@6ray.com','commit','-m','website-only '+operation],cwd=scratch,check=True,stdout=subprocess.DEVNULL)
    if push:
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+branch],cwd=scratch,check=True)
    return {'branch':branch,'worktree':str(scratch),'pushed':push,'zip_sha256':receipt['zip_sha256']}


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    h=sub.add_parser('handoff'); h.add_argument('--artifact-dir',type=Path,required=True); h.add_argument('--branch',required=True)
    h.add_argument('--operation',choices=('publish','rollback','resume'),default='publish'); h.add_argument('--backup-run-id'); h.add_argument('--push',action='store_true')
    c=sub.add_parser('receipt'); c.add_argument('--release-dir',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.cmd=='handoff': result=handoff(args.artifact_dir,args.branch,args.operation,args.backup_run_id,args.push)
        else:
            result=validate_receipt(args.release_dir)
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:
                f.write('operation='+result['operation']+'\nbackup_run_id='+str(result.get('backup_run_id') or '')+'\n')
        print(json.dumps({'ok':True,**result})); return 0
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})); return 1


if __name__=='__main__': raise SystemExit(main())
