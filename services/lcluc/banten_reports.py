"""Publish deterministic reports from the verified province-wide Esri audit."""

import csv
import json
from hashlib import sha256
from html import escape
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from services.lcluc.banten_esri_audit import REPORT
from services.lcluc.province_esri import SNAPSHOT_SHA256, digest
from services.lcluc.taxonomy import load_taxonomy

REPORTS = REPORT.parent / "reports"


def comparison(root, start, end, source=None):
    if not 2020 <= start < end <= 2025:
        raise ValueError("BANTEN_YEAR_PAIR_INVALID")
    if source is None:
        audit = root / REPORT
        if not audit.is_file():
            return None
        source = json.loads(audit.read_bytes())
    if source["region"] != "banten" or source["boundary_sha256"] != SNAPSHOT_SHA256:
        raise ValueError("BANTEN_AUDIT_BOUNDARY_MISMATCH")
    result = next(
        (row for row in source["pairs"] if (row["from_year"], row["to_year"]) == (start, end)),
        None,
    )
    if result is None:
        return None
    pins = [row for row in source["annual"] if row["year"] in (start, end)]
    taxonomy = load_taxonomy("esri-io-v003")
    labels = {item.code: item.label for item in taxonomy.classes}
    classes = [{"code": code, "name": labels[code]} for code in source["classes"]]
    from services.lcluc.banten_spatial_change import spatial_path

    spatial_document = root / spatial_path(start, end)
    spatial = None
    if spatial_document.is_file():
        spatial = json.loads(spatial_document.read_bytes())
        if spatial["source_sha256"] != [row["source_pin"]["sha256"] for row in pins]:
            raise ValueError("BANTEN_SPATIAL_SOURCE_MISMATCH")
        spatial = {key: value for key, value in spatial.items() if key != "preview"}
        spatial["preview"] = f"/api/lcluc/banten-province-change-preview/{start}/{end}"
    timeline = root / REPORT
    area_source = json.loads(timeline.read_bytes()) if timeline.is_file() else source
    if area_source["boundary_sha256"] != SNAPSHOT_SHA256:
        raise ValueError("BANTEN_TIMELINE_BOUNDARY_MISMATCH")
    return {
        "schema_version": "sdss-banten-province-report/1",
        "boundary_sha256": SNAPSHOT_SHA256,
        "boundary_approval": source["boundary_approval"],
        "region": "banten",
        "scope": "province_boundary",
        "source": source["source"],
        "grid_crs": source["grid_crs"],
        "grid_resolution_m": source["grid_resolution_m"],
        "boundary_area_ha": source["aoi_pixel_center_area_ha"],
        "independent_accuracy_measured": False,
        "classes": classes,
        "annual_area": [
            {
                "year": row["year"],
                "areas_ha": {
                    str(code): row["area_ha_by_source_code"][str(code)] for code in source["classes"]
                },
                "thematic_valid_pct": row["thematic_valid_pct"],
            }
            for row in area_source["annual"]
        ],
        "spatial": spatial,
        "annual": [
            {
                "year": row["year"],
                "thematic_valid_pct": row["thematic_valid_pct"],
                "native_class_or_cloud_pct": row["native_class_or_cloud_pct"],
                "source_uri": row["source_pin"]["uri"],
                "source_sha256": row["source_pin"]["sha256"],
            }
            for row in pins
        ],
        **result,
    }, [row["source_pin"] for row in pins]


def publish(root, result, pins):
    for pin in pins:
        path = (root / pin["path"]).resolve(strict=True)
        path.relative_to(root.resolve())
        if path.stat().st_size != pin["bytes"] or digest(path) != pin["sha256"]:
            raise ValueError("BANTEN_SOURCE_INTEGRITY_MISMATCH")
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    key = sha256(payload).hexdigest()
    directory = root / REPORTS
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{key}.json"
    with NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as temp:
        part = Path(temp.name)
        temp.write(payload)
    try:
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return key


def load_report(root, key):
    path = root / REPORTS / f"{key}.json"
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != key:
        raise ValueError("BANTEN_REPORT_INTEGRITY_MISMATCH")
    return payload


def matrix_csv(report):
    file = StringIO()
    writer = csv.writer(file)
    names = [item["name"] for item in report["classes"]]
    writer.writerow(["T1 → T2 (ha)", *names])
    writer.writerows(
        [name, *row] for name, row in zip(names, report["transition_matrix_ha"], strict=True)
    )
    return file.getvalue()


def report_html(report):
    names = [escape(item["name"]) for item in report["classes"]]
    heading = "".join(f"<th>{name}</th>" for name in names)
    rows = "".join(
        f"<tr><th>{name}</th>" + "".join(f"<td>{cell:,.2f}</td>" for cell in row) + "</tr>"
        for name, row in zip(names, report["transition_matrix_ha"], strict=True)
    )
    sources = "".join(
        f"<li>{item['year']} · <a href='{escape(item['source_uri'], quote=True)}'>Esri 원본</a>"
        f" · SHA-256 <code>{escape(item['source_sha256'])}</code></li>"
        for item in report["annual"]
    )
    yearly = "".join(
        f"<tr><th>{item['year']}</th>"
        + "".join(
            f"<td>{item['areas_ha'][str(entry['code'])]:,.2f}</td>" for entry in report["classes"]
        )
        + "</tr>"
        for item in report.get("annual_area", [])
    )
    hotspots = report.get("spatial") or {}
    rank = "".join(
        f"<li>{row['rank']}위 · 변화 {row['changed_area_ha']:,.2f}ha ({row['rate_pct']:.2f}%)</li>"
        for row in hotspots.get("hotspots", [])
    )
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<title>반텐주 전체 토지피복 변화 보고서</title>
<style>body{{font-family:system-ui;margin:2rem auto;max-width:74rem;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #cbd5e1;padding:.4rem;text-align:right}}
th{{background:#eef4fb}}code{{overflow-wrap:anywhere}}</style>
<h1>반텐주 전체 토지피복 변화 보고서</h1>
<p>{report["from_year"]}–{report["to_year"]}년 · {escape(report["source"])} · 10m 등적 격자</p>
<ul><li>경계 안 {report["boundary_area_ha"]:,.2f}ha</li>
<li>공통 유효 {report["common_valid_area_ha"]:,.2f}ha</li>
<li>변화 {report["changed_area_ha"]:,.2f}ha</li></ul>
<p>두 연도의 유효 토지피복이 함께 있는 픽셀로 계산했습니다. 독립 정확도는 미측정이며 사업통계 경계 승인은 대기 중입니다.</p>
<h2>토지피복 전이 면적 (ha)</h2><table><thead><tr><th>T1 → T2</th>{heading}</tr></thead>
<tbody>{rows}</tbody></table>
<h2>연도별 유효 토지피복 면적 (ha)</h2><table><thead><tr><th>관측 연도</th>{heading}</tr></thead>
<tbody>{yearly}</tbody></table>
<h2>1km 격자 변화 집중지역</h2><ol>{rank}</ol><h2>출처</h2><ul>{sources}</ul>
<p>One Map 경계 SHA-256 <code>{report["boundary_sha256"]}</code></p></html>"""
