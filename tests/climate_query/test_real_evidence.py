"""이미 취득한 실원본만 읽는 재현 시험. 네트워크·재다운로드·모델 학습 없음."""

import json
import unittest
from pathlib import Path

from services.climate_query.global_asset import fetch_one_listed_global, sha_file
from services.climate_query.numeric import climate_query, inspect_netcdf

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/cckp_indonesia"


@unittest.skipUnless((EVIDENCE / "global-asset.nc").is_file(), "실원본 evidence가 없는 환경")
class RealEvidenceTests(unittest.TestCase):
    def test_real_classic_cf_and_indonesia_bbox_numeric_reproduction(self):
        receipt = json.loads((EVIDENCE / "raw-receipt.json").read_text())
        self.assertEqual((EVIDENCE / "global-asset.nc").stat().st_size, 4209592)
        self.assertEqual(sha_file(EVIDENCE / "global-asset.nc"), receipt["sha256"])
        metadata = inspect_netcdf(EVIDENCE / "global-asset.nc", receipt["sha256"])
        self.assertEqual(metadata["file_format"], "NETCDF3_CLASSIC")
        self.assertEqual(metadata["calendar_raw"], "gregorian")
        self.assertEqual(metadata["global_attributes"]["wb_period_label"], "1951-1980")
        request = json.loads((EVIDENCE / "query-request.json").read_text())
        result = climate_query(
            request,
            EVIDENCE / "global-asset.nc",
            EVIDENCE / "raw-receipt.json",
            license_evidence_path=EVIDENCE / "license-evidence.json",
            license_evidence_sha256=sha_file(EVIDENCE / "license-evidence.json"),
        )
        self.assertEqual(result["status"], "VERIFIED_REAL")
        self.assertEqual(result["valid_cells"], 12765)
        self.assertAlmostEqual(result["value"], 40.91221481742199, places=10)
        self.assertFalse(result["geography_is_official_country_polygon"])
        self.assertFalse(result["independent_accuracy_validated"])

    def test_existing_verified_raw_is_reused_without_http(self):
        def forbidden(*args):
            raise AssertionError("완료 원본 재사용 중 HTTP 호출")

        result = fetch_one_listed_global(
            ROOT
            / "services/datahub/connectors/cckp/evidence/era5-cdd-historical-listing-20261124.json",
            EVIDENCE,
            execute=True,
            transport=forbidden,
        )
        self.assertEqual(result["status"], "VERIFIED_REAL_REUSED")
        self.assertEqual(result["downloaded_bytes_this_call"], 0)


if __name__ == "__main__":
    unittest.main()
