#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from p4_common import get_profile_value, load_profile, parse_ztag_records, resolve_p4_command, run_p4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Check whether a scoped merge changelist is ready to submit.')
    parser.add_argument('--config-path', default=str(Path(__file__).resolve().parent.parent / 'config' / 'p4-connection.json'))
    parser.add_argument('--target-cl', required=True)
    parser.add_argument('--path', action='append', dest='paths')
    parser.add_argument('--all', action='store_true', help='Check the full workspace scope instead of a specific path list.')
    return parser.parse_args()


def emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=True)
    sys.stdout.write('\n')


def summarize_resolve_output(stdout: str) -> list[str]:
    lines: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith('no file(s) to resolve'):
            continue
        if lower.startswith('file(s) already resolved'):
            continue
        if line.startswith('//'):
            lines.append(line)
    return lines


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

        default_args = ['-ztag', 'opened', '-c', 'default']
        target_args = ['-ztag', 'opened', '-c', args.target_cl]
        resolve_args = ['resolve', '-n', '-c', args.target_cl]
        if args.paths:
            default_args.extend(args.paths)
            target_args.extend(args.paths)
            resolve_args.extend(args.paths)

        default_result = run_p4(executable, server, user, password, default_args)
        if default_result.returncode != 0:
            raise RuntimeError(f"p4 opened -c default failed ({default_result.returncode}): {default_result.stderr.strip() or default_result.stdout.strip() or 'unknown error'}")

        target_result = run_p4(executable, server, user, password, target_args)
        if target_result.returncode != 0:
            raise RuntimeError(f"p4 opened -c {args.target_cl} failed ({target_result.returncode}): {target_result.stderr.strip() or target_result.stdout.strip() or 'unknown error'}")

        resolve_result = run_p4(executable, server, user, password, resolve_args)
        if resolve_result.returncode != 0:
            raise RuntimeError(f"p4 resolve -n failed ({resolve_result.returncode}): {resolve_result.stderr.strip() or resolve_result.stdout.strip() or 'unknown error'}")

        default_records = parse_ztag_records(default_result.stdout)
        target_records = parse_ztag_records(target_result.stdout)
        unresolved = summarize_resolve_output(resolve_result.stdout)

        ready = bool(target_records) and not default_records and not unresolved
        emit({
            'status': 'ok',
            'targetChange': args.target_cl,
            'defaultOpenCount': len(default_records),
            'targetOpenCount': len(target_records),
            'unresolvedCount': len(unresolved),
            'readyToSubmit': ready,
            'defaultFiles': [record.get('clientFile', '') for record in default_records if record.get('clientFile')],
            'targetFiles': [record.get('clientFile', '') for record in target_records if record.get('clientFile')],
            'unresolved': unresolved,
        })
        return 0 if ready else 1
    except RuntimeError as exc:
        emit({'status': 'error', 'message': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
