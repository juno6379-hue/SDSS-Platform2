import json
import tempfile
import unittest
from pathlib import Path

from services.datahub.institution_sources import build_inventory, pin_file, public_summary


class InstitutionTests(unittest.TestCase):
    def test_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            x = build_inventory(d)
            self.assertTrue(all(r["verification"] == "BLOCKED" for r in x["records"]))
            self.assertEqual(x["ledger_writes"], 0)

    def test_hash_drift(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "raw").write_bytes(b"raw")
            with self.assertRaises(ValueError):
                pin_file(Path(d), "raw", "0" * 64)

    def test_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                pin_file(Path(d), "../outside")

    def test_public_redaction(self):
        x = {
            "schema_version": "x",
            "records": [
                {
                    "source_id": "private",
                    "verification": "VERIFIED_REAL",
                    "publication_gate": "APPROVED",
                    "secret": "text",
                    "evidence_pins": [{"path": "private.db"}],
                }
            ],
        }
        result = public_summary(x)
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("private.db", json.dumps(result))
        self.assertEqual(result["sources"][0]["publication_gate"], "BLOCKED")

    def test_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "evidence/rtrw-20261125")
            p.mkdir(parents=True)
            (p / "source-candidates.json").write_text("[]")
            self.assertEqual(build_inventory(d)["records"][0]["verification"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
