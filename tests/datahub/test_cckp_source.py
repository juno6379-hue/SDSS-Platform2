"""모든 국가 prefix·수치·원본은 합성 fixture이며 실 CCKP 국가 schema가 아니다."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from xml.sax.saxutils import escape

import pytest

from services.datahub.connectors.cckp.source import (
    CckpError,
    S3Transport,
    confirm_country_scope,
    digest,
    discover,
    download,
    head_object,
    plan_download,
)


def xml(prefix="", prefixes=(), objects=(), truncated=False):
    parts = [
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">',
        "<Name>wbg-cckp</Name>",
        f"<Prefix>{escape(prefix)}</Prefix>",
        f"<IsTruncated>{str(truncated).lower()}</IsTruncated>",
    ]
    parts += [f"<CommonPrefixes><Prefix>{escape(p)}</Prefix></CommonPrefixes>" for p in prefixes]
    for key, size in objects:
        parts.append(
            f"<Contents><Key>{escape(key)}</Key><Size>{size}</Size>"
            '<ETag>"test"</ETag><LastModified>2026-01-01T00:00:00Z</LastModified></Contents>'
        )
    return "".join(parts).encode() + b"</ListBucketResult>"


def listed(raw, prefix="", parent=None, max_keys=10):
    return discover(
        prefix, parent=parent, max_keys=max_keys, transport=lambda *args: (200, {}, raw)
    )


def fixture_plan(max_bytes=8, objects=None):
    # 국가별 디렉터리가 실제 서비스에 존재한다는 뜻이 아닌 프로토콜 시험이다.
    root = listed(xml(prefixes=["country/IDN/"]))
    scope = confirm_country_scope(root, "IDN", "country/IDN/")
    objects = objects or [("country/IDN/tas/product_2020-2021.nc", 4)]
    leaf = listed(xml("country/IDN/", objects=objects), "country/IDN/", root)
    return plan_download(
        leaf,
        scope,
        country_id="IDN",
        variable="tas",
        start_year=2020,
        end_year=2021,
        max_files=2,
        max_bytes=max_bytes,
        license="SYNTHETIC_TEST_LICENSE",
        trace_id="test-trace",
    )


def test_discovery_preserves_raw_sha_and_does_not_auto_page():
    raw = xml(prefixes=["data/"], truncated=True)
    transport = Mock(return_value=(200, {}, raw))
    result = discover(max_keys=1, transport=transport)
    assert result.truncated and result.response_sha256 == digest(raw)
    assert result.response_xml.encode() == raw
    transport.assert_called_once()


def test_guessed_indonesia_prefix_never_calls_network():
    transport = Mock()
    with pytest.raises(CckpError, match="PREFIX_NOT_PREVIOUSLY_LISTED"):
        discover("IND/", transport=transport)
    transport.assert_not_called()
    with pytest.raises(CckpError, match="COUNTRY_IDENTIFIER_NOT_LISTED"):
        confirm_country_scope(listed(xml(prefixes=["data/"])), "IND", "IND/")


@pytest.mark.parametrize("key", ["../IND/", "/IND/", "x?token=y", "x\\y", "x/../y"])
def test_unsafe_keys_rejected(key):
    with pytest.raises(CckpError):
        discover(key, transport=Mock())


def test_xml_entity_and_scope_drift_rejected():
    with pytest.raises(CckpError, match="XML_ENTITY"):
        listed(b'<!DOCTYPE x [<!ENTITY x "a">]><x/>')
    with pytest.raises(CckpError, match="LIST_SCOPE_MISMATCH"):
        listed(xml().replace(b"wbg-cckp", b"other"))


def test_result_limit_and_duplicate_rejected():
    with pytest.raises(CckpError, match="LIMIT_OR_DUPLICATE"):
        listed(xml(prefixes=["a/", "b/"]), max_keys=1)
    with pytest.raises(CckpError, match="SCOPE_INVALID"):
        listed(xml(objects=[("same", 1), ("same", 1)]))


def test_plan_only_has_no_network_or_files(tmp_path):
    transport = Mock()
    result = download(fixture_plan(), tmp_path / "raw", transport=transport)
    assert result["status"] == "PLANNED" and not (tmp_path / "raw").exists()
    transport.assert_not_called()


def test_global_bucket_scope_and_drift_cannot_be_country_plan():
    plan = fixture_plan()
    with pytest.raises(CckpError, match="COUNTRY_SCOPE"):
        plan_download(
            listed(xml()),
            plan.country_scope,
            country_id="IDN",
            variable="tas",
            start_year=2020,
            end_year=2021,
            max_files=2,
            max_bytes=8,
            license="TEST",
            trace_id="trace",
        )
    bad = replace(plan.inventory, objects=())
    with pytest.raises(CckpError, match="INVENTORY_CONTENT_DRIFT"):
        download(replace(plan, inventory=bad), Path("unused"))


def test_file_byte_and_year_limits():
    with pytest.raises(CckpError, match="PLAN_FILE_OR_BYTE"):
        fixture_plan(max_bytes=3)
    plan = fixture_plan()
    with pytest.raises(CckpError, match="NO_VERIFIED_SCOPED_OBJECTS"):
        download(replace(plan, end_year=2020), Path("unused"))
    with pytest.raises(CckpError, match="FILE_LIMIT_INVALID"):
        download(replace(plan, max_files=21), Path("unused"))
    with pytest.raises(CckpError, match="PLAN_FILE_OR_BYTE"):
        fixture_plan(
            max_bytes=16, objects=[(f"country/IDN/tas/p{i}_2020-2021.nc", 4) for i in range(3)]
        )


def test_immutable_receipt_dedupe_and_raw_drift(tmp_path):
    plan = fixture_plan()
    transport = Mock(
        return_value=(206, {"etag": '"test"', "content-range": "bytes 0-3/4"}, b"abcd")
    )
    first = download(plan, tmp_path, execute=True, transport=transport)
    receipt = first["receipts"][0]
    assert receipt["sha256"] == digest(b"abcd") and not receipt["etag_is_sha256"]
    assert receipt["unit"] is None and receipt["next_gate"] == "CLIM_METADATA_MISSING"
    path = next(tmp_path.glob("*.receipt.json"))
    original = path.read_bytes()
    assert download(plan, tmp_path, execute=True, transport=transport)["receipts"][0] == receipt
    assert path.read_bytes() == original and transport.call_count == 1
    next(tmp_path.glob("*.nc")).write_bytes(b"evil")
    with pytest.raises(CckpError, match="DRIFT"):
        download(plan, tmp_path, execute=True, transport=transport)


def test_resume_requires_verified_partial_and_range(tmp_path):
    plan = fixture_plan()
    name = digest(plan.objects[0].key.encode())
    (tmp_path / (name + ".part")).write_bytes(b"ab")
    (tmp_path / "transfer-state.json").write_text(
        json.dumps(
            {
                "plan_id": plan.plan_id,
                "charged_upper_bound_bytes": 2,
                "partial": {name: {"size": 2, "sha256": digest(b"ab")}},
            }
        ),
        encoding="utf-8",
    )
    transport = Mock(return_value=(206, {"etag": '"test"', "content-range": "bytes 2-3/4"}, b"cd"))
    result = download(plan, tmp_path, execute=True, transport=transport)
    assert transport.call_args.args[2]["Range"] == "bytes=2-3"
    assert result["charged_upper_bound_bytes"] == 4
    assert next(tmp_path.glob("*.nc")).read_bytes() == b"abcd"


def test_failed_unknown_transfer_keeps_reservation_and_stops_repeated_budget(tmp_path):
    plan = fixture_plan(max_bytes=4)
    transport = Mock(side_effect=TimeoutError("fixture timeout"))
    with pytest.raises(TimeoutError):
        download(plan, tmp_path, execute=True, transport=transport)
    with pytest.raises(CckpError, match="PERSISTENT_TRANSFER_BUDGET"):
        download(plan, tmp_path, execute=True, transport=transport)
    assert transport.call_count == 1
    assert not list(tmp_path.glob("*.receipt.json"))


def test_429_persists_circuit_and_does_not_retry(tmp_path):
    plan = fixture_plan()
    transport = Mock(return_value=(429, {"retry-after": "3600"}, b""))
    with pytest.raises(CckpError, match="HTTP_429"):
        download(plan, tmp_path, execute=True, transport=transport)
    with pytest.raises(CckpError, match="PERSISTED_RATE_LIMIT"):
        download(plan, tmp_path, execute=True, transport=transport)
    assert transport.call_count == 1


def test_head_only_listed_object_and_drift():
    plan = fixture_plan()
    transport = Mock(return_value=(200, {"etag": '"test"', "content-length": "4"}, b""))
    result = head_object(plan.inventory, plan.objects[0].key, transport=transport)
    assert result["downloaded_body_bytes"] == 0 and transport.call_args.args[0] == "HEAD"
    with pytest.raises(CckpError, match="HEAD_KEY_NOT_LISTED"):
        head_object(plan.inventory, "guessed/IND/file.nc", transport=transport)


def test_transport_host_and_oversized_limits_fail_before_network():
    with pytest.raises(CckpError, match="SOURCE_HOST_NOT_ALLOWED"):
        S3Transport()("GET", "https://attacker.invalid/x", {}, 10)
    with pytest.raises(CckpError, match="RESPONSE_LIMIT"):
        S3Transport()("GET", "https://wbg-cckp.s3.amazonaws.com/x", {}, 100_000_000)


@pytest.mark.parametrize(
    "headers,body",
    [
        ({"etag": '"other"', "content-range": "bytes 0-3/4"}, b"abcd"),
        ({"etag": '"test"', "content-range": "bytes 1-4/4"}, b"abcd"),
        ({"etag": '"test"', "content-range": "bytes 0-3/4"}, b"abcde"),
    ],
)
def test_bad_transfer_never_emits_receipt(tmp_path, headers, body):
    with pytest.raises(CckpError):
        download(
            fixture_plan(),
            tmp_path,
            execute=True,
            transport=Mock(return_value=(206, headers, body)),
        )
    assert not list(tmp_path.glob("*.receipt.json"))


def test_active_lock_stops_network(tmp_path):
    (tmp_path / ".execution.lock").write_text("other", encoding="utf-8")
    transport = Mock()
    with pytest.raises(FileExistsError):
        download(fixture_plan(), tmp_path, execute=True, transport=transport)
    assert (tmp_path / ".execution.lock").read_text(encoding="utf-8") == "other"
    transport.assert_not_called()


def test_invalid_saved_budget_cannot_refund_usage(tmp_path):
    plan = fixture_plan()
    (tmp_path / "transfer-state.json").write_text(
        json.dumps({"plan_id": plan.plan_id, "charged_upper_bound_bytes": -100, "partial": {}}),
        encoding="utf-8",
    )
    transport = Mock()
    with pytest.raises(CckpError, match="PERSISTED_BUDGET_INVALID"):
        download(plan, tmp_path, execute=True, transport=transport)
    transport.assert_not_called()


def test_receipt_edit_is_detected_before_any_redownload(tmp_path):
    plan = fixture_plan()
    transport = Mock(
        return_value=(206, {"etag": '"test"', "content-range": "bytes 0-3/4"}, b"abcd")
    )
    download(plan, tmp_path, execute=True, transport=transport)
    receipt = next(tmp_path.glob("*.receipt.json"))
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(CckpError, match="IMMUTABLE_RECEIPT_PIN_MISMATCH"):
        download(plan, tmp_path, execute=True, transport=transport)
    assert transport.call_count == 1
