#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from p4_common import build_command, resolve_p4_command


NO_WORK_RE = re.compile(r"(no file\(s\)|file\(s\) up-to-date|all revision\(s\) already integrated)", re.IGNORECASE)
CLOBBER_RE = re.compile(r"Can't clobber writable file (.+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Safely run a Perforce child-stream-to-parent-stream copy with required down-merge checks.')
    parser.add_argument('--parent', required=True, help='Parent stream depot path, e.g. //streammain/Art')
    parser.add_argument('--child', required=True, help='Child stream depot path, e.g. //streammain/Env')
    parser.add_argument('--path', required=True, help='Stream-relative path scope, e.g. Content/...')
    parser.add_argument('--parent-client', help='Client mapped to the parent stream. Required for --execute copy unless current client is already parent.')
    parser.add_argument('--child-client', help='Client mapped to the child stream. Defaults to current client/environment.')
    parser.add_argument('--parent-cwd', help='Workspace root/path for the parent client. Defaults to current directory.')
    parser.add_argument('--child-cwd', help='Workspace root/path for the child client. Defaults to current directory.')
    parser.add_argument('--server', help='Optional P4PORT override. Defaults to p4 environment/.p4config.')
    parser.add_argument('--user', help='Optional P4USER override. Defaults to p4 environment/.p4config.')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds for each p4 command.')
    parser.add_argument('--execute', action='store_true', help='Actually open files. Without this flag, only previews are run.')
    parser.add_argument('--submit', action='store_true', help='Submit down-merge and up-copy changelists after successful checks. Implies --execute.')
    parser.add_argument('--clear-stream-debt', action='store_true', help='If scoped down-merge is not enough, merge remaining parent-to-child stream debt across the whole stream.')
    parser.add_argument('--backup-clobber', action='store_true', help='Move unversioned writable files that block branch/sync to .local-backup-<timestamp> and retry once.')
    parser.add_argument('--down-description', default='Merge parent stream changes down before stream up-copy')
    parser.add_argument('--up-description', default='Copy child stream changes up to parent')
    return parser.parse_args()


def emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=True, indent=2)
    sys.stdout.write('\n')


def command_text(cmd: list[str]) -> str:
    return ' '.join(cmd)


class P4Runner:
    def __init__(self, server: str | None, user: str | None, timeout: int):
        self.executable = resolve_p4_command()
        self.server = server
        self.user = user
        self.timeout = timeout
        self.history: list[dict] = []

    def args(self, p4_args: list[str], client: str | None) -> list[str]:
        args: list[str] = []
        if self.server:
            args.extend(['-p', self.server])
        if self.user:
            args.extend(['-u', self.user])
        if client:
            args.extend(['-c', client])
        args.extend(p4_args)
        return args

    def run(self, p4_args: list[str], *, client: str | None = None, cwd: str | None = None, allow_error: bool = False) -> subprocess.CompletedProcess[str]:
        full_args = self.args(p4_args, client)
        cmd = build_command(self.executable, full_args)
        started = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.history.append({
                'command': command_text(cmd),
                'cwd': cwd or os.getcwd(),
                'timeout': True,
                'seconds': self.timeout,
                'stdout': exc.stdout or '',
                'stderr': exc.stderr or '',
            })
            raise RuntimeError(f"p4 command timed out after {self.timeout}s: {command_text(cmd)}") from exc

        self.history.append({
            'command': command_text(cmd),
            'cwd': cwd or os.getcwd(),
            'exitCode': result.returncode,
            'durationSeconds': round(time.time() - started, 3),
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
        })
        if result.returncode != 0 and not allow_error:
            detail = result.stderr.strip() or result.stdout.strip() or 'unknown error'
            raise RuntimeError(f"p4 command failed ({result.returncode}): {command_text(cmd)}: {detail}")
        return result


def parse_info(stdout: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in stdout.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        info[key.strip()] = value.strip()
    return info


def stream_leaf(stream: str) -> str:
    return stream.rstrip('/').split('/')[-1]


def meaningful_lines(stdout: str, stderr: str = '') -> list[str]:
    lines = []
    for raw in (stdout + '\n' + stderr).splitlines():
        line = raw.strip()
        if line:
            lines.append(line)
    return lines


def no_work(result: subprocess.CompletedProcess[str]) -> bool:
    return bool(NO_WORK_RE.search(result.stdout) or NO_WORK_RE.search(result.stderr))


def unresolved_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    lines = meaningful_lines(result.stdout, result.stderr)
    return [line for line in lines if not NO_WORK_RE.search(line)]


def opened_count(result: subprocess.CompletedProcess[str]) -> int:
    return len([line for line in meaningful_lines(result.stdout, result.stderr) if line.startswith('//')])


def file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup_clobber_files(output: str) -> list[dict]:
    backups: list[dict] = []
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for raw_path in CLOBBER_RE.findall(output):
        path = Path(raw_path.strip())
        if not path.exists():
            continue
        backup = path.with_name(path.name + f'.local-backup-{stamp}')
        original_hash = file_hash(path)
        size = path.stat().st_size
        shutil.move(str(path), str(backup))
        backups.append({
            'path': str(path),
            'backup': str(backup),
            'size': size,
            'sha256': original_hash,
        })
    return backups


def check_clean_opened(runner: P4Runner, client: str | None, cwd: str | None, scope: str | None = None) -> int:
    args = ['opened']
    if scope:
        args.append(scope)
    result = runner.run(args, client=client, cwd=cwd, allow_error=True)
    return opened_count(result)


def resolve_safely(runner: P4Runner, client: str | None, cwd: str | None, scope: str | None) -> list[str]:
    args = ['resolve', '-as']
    if scope:
        args.append(scope)
    runner.run(args, client=client, cwd=cwd, allow_error=True)

    check_args = ['resolve', '-n']
    if scope:
        check_args.append(scope)
    check = runner.run(check_args, client=client, cwd=cwd, allow_error=True)
    return unresolved_lines(check)


def submit_if_requested(runner: P4Runner, client: str | None, cwd: str | None, description: str, submit: bool) -> str | None:
    if not submit:
        return None
    result = runner.run(['submit', '-d', description], client=client, cwd=cwd)
    match = re.search(r'Change (\d+) submitted', result.stdout + '\n' + result.stderr)
    return match.group(1) if match else None


def assert_expected_workspace(info: dict[str, str], expected_stream: str, role: str) -> None:
    actual = info.get('Client stream', '')
    if actual != expected_stream:
        raise RuntimeError(f"{role} workspace stream mismatch: expected {expected_stream}, got {actual or '<missing>'}")


def run_down_merge(runner: P4Runner, args: argparse.Namespace, summary: dict) -> None:
    child_cwd = args.child_cwd or os.getcwd()
    child_client = args.child_client
    parent_name = stream_leaf(args.parent)

    preview = runner.run(['merge', '-n', '--from', parent_name, args.path], client=child_client, cwd=child_cwd, allow_error=True)
    summary['downMergePreview'] = meaningful_lines(preview.stdout, preview.stderr)

    if no_work(preview):
        summary['downMerge'] = {'status': 'up-to-date'}
        return
    if not args.execute and not args.submit:
        summary['downMerge'] = {'status': 'preview-only'}
        return

    runner.run(['merge', '--from', parent_name, args.path], client=child_client, cwd=child_cwd)
    unresolved = resolve_safely(runner, child_client, child_cwd, None)
    if unresolved:
        summary['downMerge'] = {'status': 'blocked-unresolved', 'unresolved': unresolved}
        raise RuntimeError('Down-merge has unresolved files; user judgment required.')

    submitted = submit_if_requested(runner, child_client, child_cwd, args.down_description, args.submit)
    summary['downMerge'] = {'status': 'merged', 'submittedChange': submitted}


def clear_stream_debt_if_needed(runner: P4Runner, args: argparse.Namespace, summary: dict) -> None:
    interchanges = runner.run(['interchanges', '-S', args.parent, '-P', args.child], client=args.child_client, cwd=args.child_cwd, allow_error=True)
    lines = meaningful_lines(interchanges.stdout, interchanges.stderr)
    summary['parentToChildInterchangesAfterScopedMerge'] = lines
    if no_work(interchanges) or not lines:
        return
    if not args.clear_stream_debt:
        raise RuntimeError('Parent-to-child stream debt remains. Re-run with --clear-stream-debt or handle listed changes manually.')
    if not args.execute and not args.submit:
        return

    parent_name = stream_leaf(args.parent)
    runner.run(['merge', '--from', parent_name], client=args.child_client, cwd=args.child_cwd or os.getcwd())
    unresolved = resolve_safely(runner, args.child_client, args.child_cwd or os.getcwd(), None)
    if unresolved:
        summary['streamDebtMerge'] = {'status': 'blocked-unresolved', 'unresolved': unresolved}
        raise RuntimeError('Stream-debt merge has unresolved files; user judgment required.')
    submitted = submit_if_requested(runner, args.child_client, args.child_cwd or os.getcwd(), args.down_description, args.submit)
    summary['streamDebtMerge'] = {'status': 'merged', 'submittedChange': submitted}


def run_up_copy(runner: P4Runner, args: argparse.Namespace, summary: dict) -> None:
    parent_cwd = args.parent_cwd or os.getcwd()
    parent_client = args.parent_client
    child_name = stream_leaf(args.child)

    preview = runner.run(['copy', '-n', '--from', child_name, args.path], client=parent_client, cwd=parent_cwd, allow_error=True)
    summary['upCopyPreview'] = meaningful_lines(preview.stdout, preview.stderr)
    if no_work(preview):
        summary['upCopy'] = {'status': 'up-to-date'}
        return
    if not args.execute and not args.submit:
        summary['upCopy'] = {'status': 'preview-only'}
        return

    result = runner.run(['copy', '--from', child_name, args.path], client=parent_client, cwd=parent_cwd, allow_error=True)
    combined = result.stdout + '\n' + result.stderr
    backups: list[dict] = []
    if result.returncode != 0:
        if "Can't clobber writable file" in combined and args.backup_clobber:
            backups = backup_clobber_files(combined)
            if not backups:
                raise RuntimeError('p4 copy hit writable clobber, but no files were backed up.')
            result = runner.run(['copy', '--from', child_name, args.path], client=parent_client, cwd=parent_cwd)
        else:
            raise RuntimeError(combined.strip() or 'p4 copy failed')

    unresolved = resolve_safely(runner, parent_client, parent_cwd, None)
    if unresolved:
        summary['upCopy'] = {'status': 'blocked-unresolved', 'unresolved': unresolved, 'backups': backups}
        raise RuntimeError('Up-copy has unresolved files; user judgment required.')

    submitted = submit_if_requested(runner, parent_client, parent_cwd, args.up_description, args.submit)
    summary['upCopy'] = {'status': 'copied', 'submittedChange': submitted, 'backups': backups}


def main() -> int:
    args = parse_args()
    if args.submit:
        args.execute = True

    runner = P4Runner(args.server, args.user, args.timeout)
    summary: dict = {
        'status': 'ok',
        'mode': 'execute' if args.execute else 'dry-run',
        'submit': args.submit,
        'parent': args.parent,
        'child': args.child,
        'path': args.path,
    }

    try:
        child_info = parse_info(runner.run(['info'], client=args.child_client, cwd=args.child_cwd).stdout)
        summary['childWorkspace'] = {key: child_info.get(key, '') for key in ['User name', 'Client name', 'Client root', 'Client stream', 'Server address']}

        if args.parent_client:
            parent_info = parse_info(runner.run(['info'], client=args.parent_client, cwd=args.parent_cwd).stdout)
            summary['parentWorkspace'] = {key: parent_info.get(key, '') for key in ['User name', 'Client name', 'Client root', 'Client stream', 'Server address']}

        run_down_merge(runner, args, summary)
        clear_stream_debt_if_needed(runner, args, summary)
        run_up_copy(runner, args, summary)

        summary['finalChecks'] = {
            'childOpenedCount': check_clean_opened(runner, args.child_client, args.child_cwd),
            'parentOpenedCount': check_clean_opened(runner, args.parent_client, args.parent_cwd) if args.parent_client else None,
        }
        summary['history'] = runner.history
        emit(summary)
        return 0
    except RuntimeError as exc:
        summary['status'] = 'error'
        summary['message'] = str(exc)
        summary['history'] = runner.history
        emit(summary)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())