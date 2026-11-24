"""전송 실패·명시 재개·429는 fake transport/임시 폴더로만 검증한다."""

import hashlib
import json
import re
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from urllib.error import HTTPError

from services.climate_query.global_asset import fetch_one_listed_global, sha_file
from services.datahub.connectors.cckp.source import CckpError, Inventory, ObjectRecord


class GlobalTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.body = b"explicit-synthetic-transfer-fixture" * 10000
        self.etag = '"explicit-fixture-etag"'
        prefix = "data/era5-x0.25/synthetic/"
        key = prefix + "explicit-fixture.nc"
        xml = (
            f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>wbg-cckp</Name>'
            f"<Prefix>{prefix}</Prefix><Contents><Key>{key}</Key><Size>{len(self.body)}</Size>"
            f"<ETag>{self.etag}</ETag><LastModified>2026-01-01T00:00:00Z</LastModified></Contents></ListBucketResult>"
        )
        inventory = Inventory(
            "wbg-cckp",
            prefix,
            (),
            (ObjectRecord(key, len(self.body), self.etag, "2026-01-01T00:00:00Z"),),
            hashlib.sha256(xml.encode()).hexdigest(),
            "https://wbg-cckp.s3.amazonaws.com",
            "2026-01-01T00:00:00Z",
            False,
            None,
            xml,
        )
        self.listing = self.root / "listing.json"
        self.listing.write_text(json.dumps({"inventory": asdict(inventory)}))
        self.output = self.root / "raw"
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def transport(self, method, url, headers, limit):
        self.calls.append((method, headers))
        self.assertEqual(headers["If-Match"], self.etag)
        if method == "HEAD":
            return 200, {"etag": self.etag, "content-length": str(len(self.body))}, b""
        if "Range" not in headers:
            raise TimeoutError("explicit fixture initial timeout")
        lo, hi = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
        self.assertLessEqual(hi - lo + 1, 256 * 1024)
        return (
            206,
            {"etag": self.etag, "content-range": f"bytes {lo}-{hi}/{len(self.body)}"},
            self.body[lo : hi + 1],
        )

    def test_same_reservation_explicit_retry_persists_chunk_hash_and_reuses(self):
        with self.assertRaises(TimeoutError):
            fetch_one_listed_global(
                self.listing, self.output, execute=True, transport=self.transport
            )
        initial = (self.output / "transfer-state.json").read_bytes()
        result = fetch_one_listed_global(
            self.listing,
            self.output,
            execute=True,
            transport=self.transport,
            reviewed_range_retry=True,
        )
        self.assertEqual((self.output / "first-transfer-state.json").read_bytes(), initial)
        state = json.loads((self.output / "transfer-state.json").read_text())
        self.assertEqual(state["reserved_bytes"], len(self.body))
        self.assertEqual(state["conservative_total_bytes"], len(self.body) * 2)
        self.assertEqual(state["partial_sha256"], sha_file(self.output / "global-asset.nc"))
        for progress in self.output.glob("range-progress-*.json"):
            receipt = json.loads(progress.read_text())
            self.assertEqual(
                receipt["partial_sha256"],
                hashlib.sha256(self.body[: receipt["partial_bytes"]]).hexdigest(),
            )
        calls = len(self.calls)
        again = fetch_one_listed_global(
            self.listing, self.output, execute=True, transport=self.transport
        )
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(again["downloaded_bytes_this_call"], 0)
        self.assertEqual(result["receipt"]["sha256"], again["receipt"]["sha256"])

    def test_429_stops_and_does_not_automatically_retry(self):
        with self.assertRaises(TimeoutError):
            fetch_one_listed_global(
                self.listing, self.output, execute=True, transport=self.transport
            )

        def rate_limited(method, url, headers, limit):
            if method == "HEAD":
                return self.transport(method, url, headers, limit)
            raise HTTPError(url, 429, "explicit synthetic rate limit", {"Retry-After": "60"}, None)

        with self.assertRaises(HTTPError):
            fetch_one_listed_global(
                self.listing,
                self.output,
                execute=True,
                transport=rate_limited,
                reviewed_range_retry=True,
            )
        state = json.loads((self.output / "transfer-state.json").read_text())
        self.assertTrue(state["rate_limited"])
        self.assertEqual(state["retry_after"], "60")
        self.assertFalse((self.output / "download.lock").exists())
        with self.assertRaises(CckpError):
            fetch_one_listed_global(
                self.listing,
                self.output,
                execute=True,
                transport=self.transport,
                reviewed_range_retry=True,
            )

    def test_plan_only_never_calls_network_or_creates_directory(self):
        result = fetch_one_listed_global(
            self.listing, self.output, transport=lambda *args: self.fail("plan HTTP")
        )
        self.assertEqual(result["status"], "PLANNED")
        self.assertFalse(self.output.exists())

    def test_first_attempt_429_also_prevents_reviewed_retry(self):
        def rate_limited(*args):
            raise HTTPError(args[1], 429, "synthetic-only", {"Retry-After": "120"}, None)

        with self.assertRaises(HTTPError):
            fetch_one_listed_global(self.listing, self.output, execute=True, transport=rate_limited)
        with self.assertRaises(CckpError):
            fetch_one_listed_global(
                self.listing,
                self.output,
                execute=True,
                transport=self.transport,
                reviewed_range_retry=True,
            )


if __name__ == "__main__":
    unittest.main()
