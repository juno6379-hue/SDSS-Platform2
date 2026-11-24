"""명시 plan/download와 로컬 NetCDF inspection/query를 분리하는 소형 CLI."""

import argparse
import json
from pathlib import Path

from .global_asset import _write_new, fetch_one_listed_global
from .models import tool_contract
from .numeric import climate_query, inspect_netcdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("contract")
    get = sub.add_parser("download")
    get.add_argument("--listing", required=True, type=Path)
    get.add_argument("--output", required=True, type=Path)
    get.add_argument("--execute", action="store_true")
    get.add_argument("--reviewed-range-retry", action="store_true")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--raw", required=True, type=Path)
    inspect.add_argument("--sha256", required=True)
    inspect.add_argument("--output", required=True, type=Path)
    query = sub.add_parser("query")
    for field in ("raw", "receipt", "request", "license-evidence", "output"):
        query.add_argument("--" + field, required=True, type=Path)
    query.add_argument("--license-evidence-sha256", required=True)
    args = parser.parse_args()
    if args.operation == "contract":
        result = tool_contract()
    elif args.operation == "download":
        result = fetch_one_listed_global(
            args.listing,
            args.output,
            execute=args.execute,
            reviewed_range_retry=args.reviewed_range_retry,
        )
    elif args.operation == "inspect":
        result = inspect_netcdf(args.raw, args.sha256)
        _write_new(args.output, result)
    else:
        result = climate_query(
            json.loads(args.request.read_text(encoding="utf-8")),
            args.raw,
            args.receipt,
            license_evidence_path=args.license_evidence,
            license_evidence_sha256=args.license_evidence_sha256,
        )
        _write_new(args.output, result)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
