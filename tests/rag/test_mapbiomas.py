import json
from hashlib import sha256

from services.rag.mapbiomas import INDEX, search


def test_mapbiomas_search_links_pdf_page_and_uses_pinned_original(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"fixture")
    index = tmp_path / INDEX
    index.parent.mkdir(parents=True)
    document = {"id": "R03", "title": "Legend Description", "version": "4.1", "language": "en",
                "url": "https://example.org/original.pdf", "raw_path": "original.pdf", "bytes": 7,
                "raw_sha256": sha256(b"fixture").hexdigest(), "priority": "P0",
                "chunks": [{"page": 2, "offset": 0, "text": "Mangrove forest land cover legend"}]}
    index.write_text(json.dumps({"documents": [document], "unavailable": {}}), encoding="utf-8")

    class Store:
        def safe_path(self, location):
            return tmp_path / location

    result = search(Store(), "맹그로브 범례")
    assert result["citations"][0]["url"].endswith("#page=2")
    source.write_bytes(b"changed")
    assert search(Store(), "mangrove")["citations"] == []
