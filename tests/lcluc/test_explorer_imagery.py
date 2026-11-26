import json
from hashlib import sha256

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.lcluc_cases import pinned_bytes
from services.api.lcluc_explorer import INDEX, mount_explorer_imagery


def test_imagery_inventory_and_asset_integrity(tmp_path):
    class Store:
        def safe_path(self, relative):
            return tmp_path / relative

    app = FastAPI()
    mount_explorer_imagery(app, Store(), pinned_bytes)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 49000)) as client:
        assert client.get("/api/lcluc/imagery").json() == {"series": []}
        index = tmp_path / INDEX
        index.parent.mkdir(parents=True)
        asset = index.parent / "held.png"
        content = b"pinned bytes for transport contract"
        asset.write_bytes(content)
        pin = {
            "path": asset.relative_to(tmp_path).as_posix(),
            "bytes": len(content),
            "sha256": sha256(content).hexdigest(),
        }
        observation = {"scene": "test-observation", "preview": pin, "preview_type": "image/png", "bundle": pin}
        index.write_text(json.dumps({"series": [{
            "id": "sentinel-2", "region": "banten", "title": "Sentinel-2", "attribution": "test", "scope": "test",
            "earlier": {**observation, "observed_on": "2020-06-28"},
            "later": {**observation, "observed_on": "2025-08-26"},
        }]}))
        output = client.get("/api/lcluc/imagery").json()["series"][0]["earlier"]
        assert output["observed_on"] == "2020-06-28"
        assert pin["path"] not in json.dumps(output)
        assert client.get(output["preview"]).content == content
        assert client.get(output["bundle"]).headers["Content-Disposition"].endswith('sentinel-2-2020-06-28.zip"')
        asset.write_bytes(b"tampered")
        assert client.get(output["preview"]).status_code == 409
        assert client.get("/api/lcluc/imagery/landsat/earlier/bundle").status_code == 404
