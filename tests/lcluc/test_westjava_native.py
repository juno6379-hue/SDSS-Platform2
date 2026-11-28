import json
from threading import Event

import pytest

from services.datahub import westjava_native
from services.lcluc.westjava_native_intake import parse_calibration


def test_supplement_binds_additional_2025_landsat_bytes_to_original_approval_and_plan(tmp_path):
    file = tmp_path / "supplement.json"
    document = {
        "schema_version": "westjava-native-supplement/1",
        "region": "west_java",
        "sensor": "landsat",
        "year": 2025,
        "additional_bytes": 343_105_303,
        "approval_sha256": "a" * 64,
        "head_plan_sha256": "b" * 64,
    }
    file.write_text(json.dumps(document), encoding="utf-8")
    pin = westjava_native.pin(tmp_path, file)
    assert westjava_native.read_supplement(
        tmp_path, file, pin["sha256"], document["approval_sha256"], document["head_plan_sha256"]
    ) == (pin, 343_105_303)
    with pytest.raises(ValueError, match="SUPPLEMENT_SCOPE_MISMATCH"):
        westjava_native.read_supplement(
            tmp_path, file, pin["sha256"], document["approval_sha256"], "c" * 64
        )


def test_cog_ranges_resume_from_persisted_offset(tmp_path, monkeypatch):
    target = tmp_path / "product-metadata.xml"
    target.with_suffix(".xml.part").write_bytes(b"ab")
    calls = []
    body = b"abcdefg"
    monkeypatch.setattr(westjava_native, "RANGE_SIZE", 2)

    class Response:
        status = 206

        def __init__(self, start, end):
            self.content = body[start:end + 1]
            self.headers = {"ETag": '"etag"', "Content-Length": str(len(self.content)),
                            "Content-Range": f"bytes {start}-{end}/{len(body)}"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read1(self, _):
            content, self.content = self.content, b""
            return content

    class Provider:
        def request(self, sensor, uri, *, headers):
            calls.append(headers["Range"])
            assert headers["If-Match"] == '"etag"'
            start, end = map(int, headers["Range"].removeprefix("bytes=").split("-"))
            return Response(start, end)

    assert westjava_native.transfer(Provider(), "sentinel-2", "product-metadata",
                                    {"bytes": len(body), "etag": '"etag"', "uri": "held"}, target, Event())
    assert calls == ["bytes=2-3", "bytes=4-5", "bytes=6-6"]
    assert target.read_bytes() == body


def test_calibration_requires_modern_product_offsets(tmp_path):
    source = tmp_path / "product.xml"
    template = """<L2A><PRODUCT_URI>S2A_MSIL2A_TEST.SAFE</PRODUCT_URI>
    <PROCESSING_BASELINE>{}</PROCESSING_BASELINE>
    <BOA_QUANTIFICATION_VALUE>10000</BOA_QUANTIFICATION_VALUE></L2A>"""
    stac = {"id": "S2A_MSIL2A_TEST"}
    uri = "https://provider.invalid/S2A_MSIL2A_TEST.SAFE/MTD_MSIL2A.xml"
    source.write_text(template.format("02.12"), encoding="utf-8")
    assert parse_calibration(source, stac, uri)["offset"] == [0.0] * 6
    source.write_text(template.format("05.10"), encoding="utf-8")
    with pytest.raises(ValueError, match="POST_BASELINE_OFFSETS"):
        parse_calibration(source, stac, uri)
