import numpy as np
import pytest

from services.datahub.connectors.klhk.source import KLHK_CODES
from services.lcluc import taxonomy
from services.lcluc.taxonomy import (
    TaxonomyError,
    apply_crosswalk,
    inspect_klhk_annual_metadata,
    load_crosswalk,
    load_taxonomy,
    validate_class_codes,
)


def test_klhk_native_domain_is_pinned_and_cloud_is_qa():
    definition = load_taxonomy()
    assert definition.evidence_status == "VERIFIED_REAL"
    assert definition.approval_status == "BLOCKED"
    assert definition.codes == tuple(sorted(KLHK_CODES))
    assert definition.qa_codes == (2500,)
    assert len(definition.thematic_codes) == 22
    assert definition.nodata == 65535
    cloud = next(entry for entry in definition.classes if entry.code == 2500)
    assert (cloud.label, cloud.role) == ("Awan", "quality_mask")
    assert len(definition.source.raw_metadata_sha256) == 64
    assert load_taxonomy(expected_sha256=definition.sha256) == definition
    assert definition.analysis_groups["natural_forest"] == (2001, 2002, 2004, 2005, 20041, 20051)
    groups = definition.analysis_groups
    groups.clear()
    assert definition.analysis_groups["built_up"] == (2012, 20121, 20122)


def test_legacy_class_order_includes_usable_zero_and_structural_nodata():
    definition = load_taxonomy("legacy-9")
    assert definition.codes == tuple(range(9))
    assert definition.classes[0].label == "water"
    assert definition.classes[5].label == "shrub_and_scrub"
    assert definition.nodata == 255
    np.testing.assert_array_equal(
        validate_class_codes(np.array([0, 1, 255], dtype=np.uint8), definition, nodata=255.0),
        [True, True, False],
    )


def test_unregistered_wrong_hash_and_unapproved_definitions_fail_closed():
    with pytest.raises(TaxonomyError, match="UNREGISTERED"):
        load_taxonomy("../klhk-23")
    with pytest.raises(TaxonomyError, match="SHA256_MISMATCH"):
        load_taxonomy("klhk-23", "0" * 64)
    with pytest.raises(TaxonomyError, match="OPERATIONAL_APPROVAL_REQUIRED"):
        load_taxonomy(require_approved=True)


def test_pinned_definition_file_change_is_rejected(monkeypatch, tmp_path):
    original = taxonomy._DATA_DIR.joinpath("klhk-23.json").read_bytes()
    tmp_path.joinpath("klhk-23.json").write_bytes(original + b"\n")
    monkeypatch.setattr(taxonomy, "_DATA_DIR", tmp_path)
    with pytest.raises(TaxonomyError, match="FILE_TAMPERED"):
        load_taxonomy()


@pytest.mark.parametrize("value", [12, 2001.001, np.inf, np.nan, 65535])
def test_unknown_fractional_nonfinite_or_undeclared_nodata(value):
    with pytest.raises(TaxonomyError, match="CODE_UNREGISTERED"):
        validate_class_codes(np.array([2001, value]), load_taxonomy())


@pytest.mark.parametrize("nodata", [2500, 2001, 50011, True, np.nan, 1.01, 2**31])
def test_nodata_cannot_replace_a_real_class_or_be_malformed(nodata):
    with pytest.raises(TaxonomyError, match="NODATA_INVALID_OR_COLLIDES"):
        validate_class_codes(np.array([2001]), load_taxonomy(), nodata=nodata)


def test_masked_cells_and_explicit_nodata_are_preserved_separately_from_cloud():
    raw = np.ma.array(
        [[2001, 65535], [2500, 123456]],
        mask=[[False, False], [False, True]],
    )
    mask = validate_class_codes(raw, load_taxonomy(), nodata=65535)
    np.testing.assert_array_equal(mask, [[True, False], [True, False]])


def test_provisional_mapping_requires_opt_in_and_retains_explicit_exclusions():
    crosswalk = load_crosswalk()
    assert crosswalk.source.sha256 == load_taxonomy().sha256
    assert crosswalk.target.sha256 == load_taxonomy("legacy-9").sha256
    assert crosswalk.approval_status == "BLOCKED"
    assert len(crosswalk.entries) == 23
    assert 2500 in crosswalk.excluded_codes and 20092 in crosswalk.excluded_codes
    raw = np.array([[2001, 5001], [2500, 65535], [20092, 20093]])
    with pytest.raises(TaxonomyError, match="CROSSWALK_OPERATIONAL_APPROVAL_REQUIRED"):
        load_crosswalk(require_approved=True)
    with pytest.raises(TaxonomyError, match="CROSSWALK_OPERATIONAL_APPROVAL_REQUIRED"):
        apply_crosswalk(raw, crosswalk, source_nodata=65535)
    result = apply_crosswalk(raw, crosswalk, source_nodata=65535, allow_provisional=True)
    assert result.dtype == np.uint8
    np.testing.assert_array_equal(result, [[1, 0], [255, 255], [255, 4]])


def test_crosswalk_validates_source_unknowns_and_target_nodata():
    crosswalk = load_crosswalk()
    with pytest.raises(TaxonomyError, match="CODE_UNREGISTERED"):
        apply_crosswalk(np.array([1970]), crosswalk, allow_provisional=True)
    with pytest.raises(TaxonomyError, match="NODATA_INVALID_OR_COLLIDES"):
        apply_crosswalk(np.array([5001]), crosswalk, target_nodata=0, allow_provisional=True)


def annual_fixture():
    entries = [{"code": item.code, "name": item.label} for item in load_taxonomy().classes]
    return {
        "name": "PL2025",
        "type": "Feature Layer",
        "capabilities": "Map,Query",
        "licenseInfo": "Test fixture text",
        "fields": [{"name": "PL2025_ID", "domain": {"codedValues": entries}}],
    }


def test_matching_annual_native_codes_never_infer_operational_approval():
    fixture = annual_fixture()
    report = inspect_klhk_annual_metadata(fixture, 2025)
    assert report["metadata_contract_valid"]
    assert report["official_label_match"]
    assert report["taxonomy_sha256"] == load_taxonomy().sha256
    assert report["approval_status"] == report["status"] == "BLOCKED"
    assert not report["license_use_approved"]
    assert not report["download_access_verified"]


def test_annual_mismatching_labels_and_renderer_only_stay_blocked():
    fixture = annual_fixture()
    fixture["fields"][0]["domain"]["codedValues"][0]["name"] = "Unrelated meaning"
    report = inspect_klhk_annual_metadata(fixture, 2025)
    assert report["native_23_class_schema_verified"]
    assert not report["metadata_contract_valid"]
    assert "KLHK_ANNUAL_CODE_LABEL_MISMATCH" in report["reasons"]
    fixture["drawingInfo"] = {"renderer": fixture.pop("fields")[0]["domain"]}
    report = inspect_klhk_annual_metadata(fixture, 2025)
    assert not report["official_label_match"]
    assert "NATIVE_23_CLASS_DOMAIN_NOT_VERIFIED" in report["reasons"]
