from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOL_ROOT = Path(r"F:\CodeProjects\sbox\tools")
LOOKUP = TOOL_ROOT / 'sbox_lookup.py'
UPDATE = TOOL_ROOT / 'update_sbox_schema.py'


def run(args: list[str]) -> int:
    proc = subprocess.run(args)
    return proc.returncode


def ensure_tools() -> None:
    missing = [str(p) for p in (LOOKUP, UPDATE) if not p.is_file()]
    if missing:
        raise FileNotFoundError('Missing s&box tool(s): ' + ', '.join(missing))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Thin stable entrypoint for the local s&box API tools.')
    sub = parser.add_subparsers(dest='command', required=True)

    p_refresh = sub.add_parser('refresh', help='Refresh local schema')
    p_refresh.add_argument('--force', action='store_true')
    p_refresh.add_argument('--headed', action='store_true')
    p_refresh.add_argument('--timeout-ms', type=int, default=30000)

    sub.add_parser('stats', help='Print schema statistics')

    p_type = sub.add_parser('type', help='Lookup a type')
    p_type.add_argument('query')
    p_type.add_argument('--members', action='store_true')
    p_type.add_argument('--assembly')
    p_type.add_argument('--limit', type=int)

    p_member = sub.add_parser('member', help='Lookup a member')
    p_member.add_argument('query')
    p_member.add_argument('--assembly')
    p_member.add_argument('--limit', type=int)

    p_search = sub.add_parser('search', help='Search schema')
    p_search.add_argument('query')
    p_search.add_argument('--assembly')
    p_search.add_argument('--limit', type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ensure_tools()

    py = sys.executable

    if args.command == 'refresh':
        cmd = [py, str(UPDATE), '--timeout-ms', str(args.timeout_ms)]
        if args.headed:
            cmd.append('--headed')
        cmd.append('update')
        if args.force:
            cmd.append('--force')
        return run(cmd)

    if args.command == 'stats':
        return run([py, str(LOOKUP), 'stats'])

    if args.command == 'type':
        cmd = [py, str(LOOKUP), 'type', args.query]
        if args.members:
            cmd.append('--members')
        if args.assembly:
            cmd.extend(['--assembly', args.assembly])
        if args.limit is not None:
            cmd.extend(['--limit', str(args.limit)])
        return run(cmd)

    if args.command == 'member':
        cmd = [py, str(LOOKUP), 'member', args.query]
        if args.assembly:
            cmd.extend(['--assembly', args.assembly])
        if args.limit is not None:
            cmd.extend(['--limit', str(args.limit)])
        return run(cmd)

    if args.command == 'search':
        cmd = [py, str(LOOKUP), 'search', args.query]
        if args.assembly:
            cmd.extend(['--assembly', args.assembly])
        if args.limit is not None:
            cmd.extend(['--limit', str(args.limit)])
        return run(cmd)

    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
