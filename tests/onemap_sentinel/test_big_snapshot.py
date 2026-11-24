"""합성 공식 응답 fixture로 출처·버전·원본 불변 계약을 검증한다."""
import json

import pytest

from services.datahub.connectors.onemap.boundary import PROVINCES, pin_big_snapshot, sha256


def bundle(root):
    root.mkdir()
    metadata = root / 'metadata.json'
    metadata.write_text('{"currentVersion": 11.1}', encoding='utf-8')
    rows, features = [], []
    for i, name in enumerate(PROVINCES):
        geometry = {'type':'Polygon','coordinates':[[[i,0],[i+0.5,0],[i+0.5,0.5],[i,0.5],[i,0]]]}
        feature = {'type':'Feature','properties':{'province_id':name},'geometry':geometry}
        raw = root / (name + '.geojson')
        raw.write_text(json.dumps({'type':'FeatureCollection','features':[feature]}))
        rows.append({'province_id':name,'response_path':raw.name,'response_sha256':sha256(raw)})
        features.append(feature)
    result = root / 'boundary.geojson'
    result.write_text(json.dumps({'type':'FeatureCollection','features':features,
        'retrieved_at':'2026-01-01T00:00:00+00:00',
        'authority':{'source_url':'https://geoservices.big.go.id/rbi/rest/services/BATASWILAYAH/BATAS_WILAYAH/MapServer/12',
                     'layer_id':12,'metadata_path':metadata.name,'metadata_sha256':sha256(metadata)},
        'derivation':{'query_evidence':rows}}))
    return result


def test_originals_and_software_version_never_become_legal_dataset_approval(tmp_path):
    original = bundle(tmp_path/'reference')
    before = sha256(original)
    output = tmp_path/'new-repo'
    receipt = pin_big_snapshot(original, before, original.parent, output)
    assert len(receipt['files']) == 8 and receipt['publisher_version'] is None
    assert receipt['snapshot_version'] == 'sha256:' + before
    assert receipt['acquired_at'] == '2026-01-01T00:00:00+00:00'
    assert not receipt['approved_for_project_statistics']
    assert sha256(original) == before
    assert sha256(output/'boundary.geojson') == before
    with pytest.raises(ValueError, match='OUTPUT_NOT_EMPTY'):
        pin_big_snapshot(original, before, original.parent, output)


def test_raw_response_drift_aborts_snapshot(tmp_path):
    original = bundle(tmp_path/'reference')
    checksum = sha256(original)
    (original.parent / 'banten.geojson').write_text('changed')
    with pytest.raises(ValueError, match='SOURCE_PIN'):
        pin_big_snapshot(original, checksum, original.parent, tmp_path/'out')


def test_low_level_snapshot_cannot_write_into_reference_root(tmp_path):
    original = bundle(tmp_path/'reference')
    with pytest.raises(ValueError,match='MUST_NOT_WRITE_REFERENCE'):
        pin_big_snapshot(original,sha256(original),original.parent,original.parent/'new-copy')
    assert not (original.parent/'new-copy').exists()
