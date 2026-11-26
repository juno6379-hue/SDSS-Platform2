"""Registry and spatially matched Landsat / Sentinel-2 classification trials."""

SOURCE_DIR = "data/curated/explorer/banten-province/landsat-explore"
SENSOR_MODELS = {
    "landsat": {"rf": "rf-report.json", "tiny-unet": "tiny-unet-report.json", "deeplabv3plus": "deeplabv3plus-report.json"},
    "sentinel-2": {method: f"sentinel2-benchmark/{method}-report.json" for method in ("rf", "tiny-unet", "deeplabv3plus")},
}
CANDIDATES = {f"banten-{sensor}-{method}-2020": path
              for sensor, models in SENSOR_MODELS.items() for method, path in models.items()}
