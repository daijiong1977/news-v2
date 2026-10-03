"""Three-part fixed-five website run. No article DB/archive/email writes.

Python runs continuous preparation, yields native Grok tasks, then builds the
official reader and optionally hands artifacts to the existing publishing CI.
Exit 2 always resumes this SAME command/directory after the Agent answers.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .agent_shadow import read, write, run_lock


def invoke(module, *args):
    result = subprocess.run([sys.executable, '-m', module, *map(str, args)],
                            capture_output=True, text=True,
                            env={**os.environ, 'KIDSNEWS_DEFER_LOG_SHIP': '1'})
    lines = result.stdout.strip().splitlines()
    try:
        value = json.loads(lines[-1])
    except (IndexError, ValueError):
        raise ValueError(f'{module}: no JSON result (exit {result.returncode}); inspect stage logs')
    return result.returncode, value


def artifacts(root, publish=False, branch=None):
    """Idempotent local build; preserve ambiguous Git pushes for inspection."""
    with run_lock(root):
        done = read(root / 'done.json')
        if done.get('counts') != {'news': 3, 'science': 3, 'fun': 3}:
            raise ValueError('Exactly three per section required; do not publish a short group')
        if read(root / 'input.json').get('test_profile') != 'source-first-deepseek':
            raise ValueError('Use the frozen fixed-five profile')
        from .publication_bundle import build, unpack
        from .publication_bundle import sha
        from .website_release import check_reader
        internal = root / 'publication.zip'
        if not internal.exists():
            build(root, internal)
        private_files, private_manifest = unpack(internal.read_bytes())
        output = root / 'reader-artifact'
        internal_sha = sha(internal.read_bytes())
        if not output.exists():
            staging = Path(tempfile.mkdtemp(prefix='reader-build-', dir=root)) / 'artifact'
            code, value = invoke('pipeline.website_release', 'build', '--zip', internal,
                                 '--output-dir', staging)
            if code:
                raise ValueError('Official reader build failed: ' + str(value.get('error')))
            check_reader((staging / 'reader.zip').read_bytes(), read(staging / 'latest-manifest.json'))
            write(staging / 'reader-build.json', {'publication_sha256': internal_sha})
            os.replace(staging, output)
        if read(output / 'reader-build.json') != {'publication_sha256': internal_sha}:
            raise ValueError('Reader was built from a different internal publication ZIP')
        reader = (output / 'reader.zip').read_bytes()
        manifest = read(output / 'latest-manifest.json')
        public_files = check_reader(reader, manifest)
        if not (output / 'records.json').exists():
            raise ValueError('Missing publication records')
        if read(output / 'records.json') != json.loads(private_files['publication-records.json']):
            raise ValueError('Reader publication records differ from internal ZIP')
        from .website_release import CONTENT_DIRS
        expected = {n: b for n, b in private_files.items() if n.split('/')[0] in CONTENT_DIRS}
        actual = {n: b for n, b in public_files.items() if n.split('/')[0] in CONTENT_DIRS}
        if expected != actual or manifest.get('story_count') != 9:
            raise ValueError('Reader content differs from the nine ready articles')
        result = {'ok': True, 'counts': done['counts'], 'publication_zip': str(internal),
                  'reader_zip': str(output / 'reader.zip'), 'zip_sha256': sha(reader),
                  'published': False, 'status': 'checked_local_zip'}
        if not publish:
            return result
        receipt = root / 'website-handoff.json'
        if receipt.exists():
            previous = read(receipt)
            if previous.get('status') == 'pushed' and previous.get('branch') == branch:
                return {**result, 'delivery': previous, 'status': 'ci_verification_pending'}
            raise ValueError('Handoff already attempted; inspect the remote/CI before resume, never push twice blindly')
        from .website_delivery import handoff
        write(receipt, {'status': 'attempting', 'branch': branch, 'zip_sha256': sha(reader),
                        'at': datetime.now(timezone.utc).isoformat()})
        value = handoff(output, branch, push=True)
        write(receipt, {**value, 'status': 'pushed'})
        # A Git push is NOT proof the website deployed. Existing CI verifies it.
        return {**result, 'delivery': read(receipt), 'status': 'ci_verification_pending'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--date')
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--providers-config', type=Path)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--ack-same-day-replacement', action='store_true')
    parser.add_argument('--branch')
    parser.add_argument('--confirm-stale', action='store_true')
    parser.add_argument('--stage', choices=('prepare', 'finalize'),
                        help='True three-stage mode: prepare -> Grok file work -> finalize')
    args = parser.parse_args()
    root = args.run_dir.resolve()
    started = time.monotonic()
    try:
        from .agent_shadow import verify_answer_hashes
        verify_answer_hashes(root)
        if args.stage == 'prepare' and args.publish:
            raise ValueError('prepare cannot publish; use finalize explicitly')
        if args.publish and (not args.ack_same_day_replacement or not args.branch):
            raise ValueError('Website publication requires --ack-same-day-replacement and a new --branch')
        if not (root / 'input.json').exists() and (not args.date or not args.registry):
            raise ValueError('Fresh run requires --date and history-overlaid --registry')
        if args.stage == 'finalize':
            from .kidsnews_groups import import_groups, check_group_stale
            from .agent_shadow import advance
            with run_lock(root):
                if not (root / 'groups/manifest.json').exists():
                    raise ValueError('Run --stage prepare first; finalize never calls models')
                check_group_stale(root, args.confirm_stale, args.registry)
                import_groups(root)
                advance(root, stepwise=False)
            print(json.dumps(artifacts(root, args.publish, args.branch), ensure_ascii=False)); return 0
        if not (root / 'drafts-for-grok.json').exists():
            command = ['preflight', '--run-dir', root, '--editor-mode', 'autonomous',
                       '--test-profile', 'source-first-deepseek']
            if args.date:
                command += ['--date', args.date]
            if args.registry:
                command += ['--registry', args.registry]
            if args.providers_config:
                command += ['--providers-config', args.providers_config]
            if args.confirm_stale:
                command += ['--confirm-stale']
            code, value = invoke('pipeline.agent_shadow', *command)
            if code:
                if code == 2:
                    value['rerun'] = 'Resume the same pipeline.kidsnews_bot command after answering this request'
                print(json.dumps(value, ensure_ascii=False)); return code
        if args.stage == 'prepare':
            from .kidsnews_groups import prepare_groups
            from .agent_shadow import check_stale
            with run_lock(root):
                if not (root / 'groups/manifest.json').exists():
                    check_stale(root, args.confirm_stale, args.registry)
                value = prepare_groups(root)
            print(json.dumps({'ok': True, 'stage': 'grok', **value}, ensure_ascii=False)); return 0
        if (root / 'groups/manifest.json').exists():
            raise ValueError('Three-stage directory: use --stage finalize, not the interleaved runner')
        # Drain cheap Python boundaries in one invocation; stop only for an
        # actual native answer or a real failure. No model work in a busy loop.
        for _ in range(200):
            if (root / 'done.json').exists():
                result = artifacts(root, args.publish, args.branch)
                print(json.dumps(result, ensure_ascii=False)); return 0
            command = ['step', '--run-dir', root]
            if args.confirm_stale:
                command += ['--confirm-stale']
                if args.registry:
                    command += ['--registry', args.registry]
            code, value = invoke('pipeline.agent_shadow', *command)
            if code not in (0, 3):
                if code == 2:
                    value['rerun'] = 'Resume the same pipeline.kidsnews_bot command after answering this request'
                print(json.dumps(value, ensure_ascii=False)); return code
        raise ValueError('Python boundary limit reached; preserve state and inspect')
    except Exception as exc:
        from .kidsnews_groups import GroupNeeded
        if isinstance(exc, GroupNeeded):
            print(json.dumps({'ok': False, 'stage': 'targeted_group_fix', 'read': exc.path,
                              'errors': [str(exc)], 'next': 'Correct only the indicated file, then repeat --stage finalize'}, ensure_ascii=False))
            return 2
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}, ensure_ascii=False))
        return 1
    finally:
        if root.exists():
            try:
                with (root / 'steps.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(),
                        'cmd': 'kidsnews_bot', 'stage': args.stage or 'legacy_interleaved',
                        'command_seconds': round(time.monotonic() - started, 3)}) + '\n')
            except OSError:
                print('Could not append command timing; preserve run directory', file=sys.stderr)
        # Ship once per meaningful handoff/completion rather than after every
        # cheap subprocess boundary, including the website delivery receipt.
        from .agent_shadow_logs import ship
        if root.exists():
            ship(root)


if __name__ == '__main__':
    raise SystemExit(main())
