"""작은 공식 문서·KLHK metadata의 실제 취득. --execute 없으면 계획만 출력한다."""

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path

from services.datahub.connectors.klhk.source import (
    DICTIONARY,
    Blocked,
    BoundedTransport,
    ImmutableStore,
    discover,
    now,
)

from .pipeline import preserve_graph, preserve_stage, stage_document


def acquire(output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("새 빈 output 경로 필요")
    output.mkdir(parents=True, exist_ok=True)
    store = ImmutableStore(output / "raw")
    transport = BoundedTransport()
    events = []

    def fetch(url, source_id, version=None, format="json"):
        try:
            raw, headers = transport.fetch(url)
            receipt = store.preserve(
                url,
                raw,
                headers,
                version=version or "content-sha256:" + sha256(raw).hexdigest(),
                source_id=source_id,
                evidence_status="VERIFIED_REAL",
            )
            staged = stage_document(
                receipt, authority=source_id, raw_root=store.directory, format=format
            )
            stage_path = preserve_stage(staged, output / "staged")
            graph_path = preserve_graph(staged, output / "graphs")
            events.append(
                dict(
                    source_id=source_id,
                    status="VERIFIED_REAL",
                    receipt=receipt,
                    stage_path=stage_path,
                    graph_path=graph_path,
                    chunk_count=len(staged.spans),
                    rag_publication="BLOCKED_LICENSE_VALIDITY_ACCESS_REVIEW_REQUIRED",
                )
            )
            return raw
        except (Blocked, ValueError, UnicodeError) as error:
            events.append(dict(source_id=source_id, status="BLOCKED", url=url, reason=str(error)))
            return None

    base = "https://api.github.com/repos/worldbank/climateknowledgeportal"
    fetch(base, "worldbank-cckp-repository-metadata")
    commit_raw = fetch(base + "/commits?per_page=1", "worldbank-cckp-commit")
    if commit_raw:
        try:
            commit = json.loads(commit_raw)[0]["sha"]
            if not re.fullmatch("[a-f0-9]{40}", commit):
                raise ValueError("COMMIT_SHA_INVALID")
            listing_raw = fetch(
                base + "/contents?ref=" + commit, "worldbank-cckp-file-list", version=commit
            )
            if listing_raw:
                listing = json.loads(listing_raw)
                names = {row["name"] for row in listing if row.get("type") == "file"}
                for name in ("README.md", "LICENSE", "LICENSE.md", "LICENSE.txt"):
                    if name in names:
                        fetch(
                            "https://raw.githubusercontent.com/worldbank/climateknowledgeportal/"
                            + commit
                            + "/"
                            + name,
                            "worldbank-cckp-" + name,
                            version=commit,
                            format="markdown",
                        )
        except (ValueError, KeyError, IndexError, TypeError) as error:
            events.append(
                dict(
                    source_id="worldbank-cckp-document-discovery",
                    status="BLOCKED",
                    reason=str(error),
                )
            )
    fetch(DICTIONARY, "klhk-official-landcover-dictionary", format="html")
    klhk = []
    for year in (2021, 2024, 2025):
        result = discover(year, transport, store)
        if result.get("receipt"):
            staged = stage_document(
                result["receipt"],
                authority=f"klhk-landcover-{year}",
                raw_root=store.directory,
                format="json",
            )
            result["document_ingestion"] = dict(
                stage_path=preserve_stage(staged, output / "staged"),
                graph_path=preserve_graph(staged, output / "graphs"),
                chunk_count=len(staged.spans),
                publication="BLOCKED_PENDING_CURATED_METADATA",
            )
        klhk.append(result)
    summary = dict(
        recorded_at=now(),
        state="VERIFIED_REAL_ACQUISITION_WITH_BLOCKED_PUBLICATION"
        if any(item["status"] == "VERIFIED_REAL" for item in events)
        else "BLOCKED",
        documents=events,
        klhk_discovery=klhk,
        request_count=transport.requests,
        body_bytes=transport.bytes,
        limits=dict(
            max_requests=transport.max_requests,
            max_bytes=transport.max_bytes,
            per_document=transport.per_document,
            timeout=transport.timeout,
        ),
        embedding_quality_verified=False,
        institution_authority_certified=False,
        quantitative_rag_answers=0,
        limitations=[
            "metadata 접근성과 다운로드 권한·23클래스·연도·라이선스·기관 인증은 별도",
            "실제 취득 문서는 검토 전 staging에만 보존하며 운영 RAG 검색에 게시하지 않음",
        ],
    )
    with (output / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "PLANNED",
                    "network_requests": 0,
                    "max_requests": 12,
                    "max_bytes": 2097152,
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return
    result = acquire(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requests": result["request_count"],
                "body_bytes": result["body_bytes"],
                "documents": [
                    {
                        k: v
                        for k, v in item.items()
                        if k in ("source_id", "status", "reason", "chunk_count")
                    }
                    for item in result["documents"]
                ],
                "klhk": [
                    {"year": r["year"], "status": r["status"], "reasons": r["reasons"]}
                    for r in result["klhk_discovery"]
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
