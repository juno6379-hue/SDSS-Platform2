"""기존 BIG snapshot의 hash를 검증해 새 저장소에 불변 복사한다."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

PROVINCES = ("banten", "west_java", "east_java", "gorontalo", "south_sulawesi", "southeast_sulawesi")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_pin(path: Path, expected: str, allowed_root: Path) -> Path:
    resolved = Path(path).resolve()
    resolved.relative_to(Path(allowed_root).resolve())
    if not resolved.is_file() or sha256(resolved) != expected:
        raise ValueError("SOURCE_PIN_MISMATCH:" + str(resolved))
    return resolved


def write_json_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def pin_big_snapshot(path: Path, expected_sha: str, reference_root: Path, output: Path) -> dict:
    """기관 승인·발행 버전을 추정하지 않고 획득 snapshot 버전으로 고정한다."""
    path = read_pin(path, expected_sha, reference_root)
    doc = json.loads(path.read_text(encoding="utf-8"))
    authority = doc["authority"]
    uri = authority["source_url"]
    parsed = urlsplit(uri)
    if parsed.scheme != "https" or parsed.netloc != "geoservices.big.go.id" or authority["layer_id"] != 12:
        raise ValueError("OFFICIAL_BIG_SOURCE_REQUIRED")
    if {f["properties"]["province_id"] for f in doc["features"]} != set(PROVINCES) or len(doc["features"]) != 6:
        raise ValueError("EXACT_SIX_PROVINCES_REQUIRED")
    if not doc.get("retrieved_at"):
        raise ValueError("SOURCE_ACQUISITION_TIME_REQUIRED")
    output = Path(output).resolve()
    if output.is_relative_to(Path(reference_root).resolve()) or Path(reference_root).resolve().is_relative_to(output):
        raise ValueError("OUTPUT_MUST_NOT_WRITE_REFERENCE_ROOT")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("IMMUTABLE_SNAPSHOT_OUTPUT_NOT_EMPTY")
    records = [(path, "boundary.geojson", expected_sha)]
    metadata = read_pin(path.parent / authority["metadata_path"], authority["metadata_sha256"], reference_root)
    records.append((metadata, "big-layer-metadata.json", authority["metadata_sha256"]))
    rows = doc["derivation"]["query_evidence"]
    if {r["province_id"] for r in rows} != set(PROVINCES):
        raise ValueError("SIX_ORIGINAL_RESPONSES_REQUIRED")
    for row in rows:
        source = read_pin(path.parent / row["response_path"], row["response_sha256"], reference_root)
        records.append((source, row["province_id"] + ".geojson", row["response_sha256"]))
    receipts = []
    for source, filename, checksum in records:
        target = output / filename
        with source.open("rb") as original, target.open("xb") as copied:
            for block in iter(lambda: original.read(1024 * 1024), b""):
                copied.write(block)
        if sha256(target) != checksum:
            raise ValueError("COPY_SHA_MISMATCH")
        receipts.append({"path": str(target), "sha256": checksum, "bytes": target.stat().st_size})
    result = {"status": "VERIFIED_REAL_SNAPSHOT_AUTHORITY_APPROVAL_PENDING", "source_uri": uri,
              "source_id": "BIG:BATAS_WILAYAH:12", "snapshot_version": "sha256:" + expected_sha,
              "publisher_version": None, "publisher_effective_date": None,
              "acquired_at": doc["retrieved_at"], "imported_at": datetime.now(timezone.utc).isoformat(),
              "approved_for_project_statistics": False, "boundary": receipts[0], "files": receipts,
              "provinces": list(PROVINCES), "remote_requests": 0}
    write_json_new(output / "receipt.json", result)
    return result
