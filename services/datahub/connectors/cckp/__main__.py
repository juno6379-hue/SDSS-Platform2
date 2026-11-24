"""CCKP 단일 목록 조회 CLI. --execute 이전에는 네트워크를 호출하지 않는다."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .source import _integer, _key, _write, discover, inventory_from_dict


def main():
    parser = argparse.ArgumentParser(
        description="CCKP 단일 페이지 bounded discovery", allow_abbrev=False
    )
    parser.add_argument("--prefix", default="")
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--max-keys", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    _key(args.prefix, empty=True)
    _integer(args.max_keys, 1, 100, "MAX_KEYS_OUT_OF_RANGE")
    parent = (
        inventory_from_dict(json.loads(args.parent.read_text(encoding="utf-8"))["inventory"])
        if args.parent
        else None
    )
    if args.prefix and (parent is None or args.prefix not in parent.prefixes):
        raise ValueError("PREFIX_NOT_PREVIOUSLY_LISTED")
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "PLANNED",
                    "download_executed": False,
                    "prefix": args.prefix,
                    "max_keys": args.max_keys,
                }
            )
        )
        return
    if args.output.exists():
        raise ValueError("IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    result = discover(args.prefix, parent=parent, max_keys=args.max_keys)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, {"status": "VERIFIED_REAL", "inventory": asdict(result)}, exclusive=True)
    print(
        json.dumps(
            {
                "status": "VERIFIED_REAL",
                "prefixes": result.prefixes,
                "objects": len(result.objects),
                "truncated": result.truncated,
                "response_bytes": len(result.response_xml.encode()),
            }
        )
    )


if __name__ == "__main__":
    main()
