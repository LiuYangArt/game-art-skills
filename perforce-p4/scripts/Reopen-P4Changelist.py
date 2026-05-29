#!/usr/bin/env python3

import argparse
import json
import sys
import tempfile
from pathlib import Path

from p4_common import get_profile_value, load_profile, parse_ztag_records, resolve_p4_command, run_p4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Move files from a source changelist into a target changelist.')
    parser.add_argument('--config-path', default=str(Path(__file__).resolve().parent.parent / 'config' / 'p4-connection.json'))
    parser.add_argument('--target-cl', required=True)
    parser.add_argument('--source-cl', default='default')
    parser.add_argument('--path', action='append', dest='paths')
    parser.add_argument('--all', action='store_true', help='Move every opened file from the source changelist.')
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


def emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=True)
    sys.stdout.write('\n')


def main() -> int:
    args = parse_args()
    if not args.all and not args.paths:
        raise SystemExit('Use --all or at least one --path scope.')

    try:
        profile = load_profile(args.config_path)
        server = get_profile_value(profile, 'server', args.config_path, required=True)
        user = get_profile_value(profile, 'user', args.config_path, required=True)
        password = get_profile_value(profile, 'password', args.config_path)
        executable = resolve_p4_command()

        opened_args = ['-ztag', 'opened', '-c', args.source_cl]
        if args.paths:
            opened_args.extend(args.paths)

        opened_result = run_p4(executable, server, user, password, opened_args)
        if opened_result.returncode != 0:
            raise RuntimeError(f"p4 opened failed ({opened_result.returncode}): {opened_result.stderr.strip() or opened_result.stdout.strip() or 'unknown error'}")

        records = parse_ztag_records(opened_result.stdout)
        client_files: list[str] = []
        seen: set[str] = set()
        for record in records:
            client_file = record.get('clientFile', '').strip()
            if client_file and client_file not in seen:
                client_files.append(client_file)
                seen.add(client_file)

        if not client_files:
            emit({'status': 'ok', 'targetChange': args.target_cl, 'sourceChange': args.source_cl, 'movedCount': 0, 'files': []})
            return 0

        if args.dry_run:
            emit({'status': 'ok', 'targetChange': args.target_cl, 'sourceChange': args.source_cl, 'movedCount': len(client_files), 'files': client_files, 'dryRun': True})
            return 0

        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, newline='\n') as handle:
            for client_file in client_files:
                handle.write(client_file)
                handle.write('\n')
            file_list_path = handle.name

        try:
            reopen_args = ['-x', file_list_path, 'reopen', '-c', args.target_cl]
            reopen_result = run_p4(executable, server, user, password, reopen_args)
            if reopen_result.returncode != 0:
                raise RuntimeError(f"p4 reopen failed ({reopen_result.returncode}): {reopen_result.stderr.strip() or reopen_result.stdout.strip() or 'unknown error'}")
        finally:
            Path(file_list_path).unlink(missing_ok=True)

        emit({'status': 'ok', 'targetChange': args.target_cl, 'sourceChange': args.source_cl, 'movedCount': len(client_files), 'files': client_files, 'stdout': reopen_result.stdout, 'stderr': reopen_result.stderr, 'exitCode': reopen_result.returncode})
        return 0
    except RuntimeError as exc:
        emit({'status': 'error', 'message': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
