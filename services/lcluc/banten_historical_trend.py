"""Import official MapBiomas Indonesia Collection 4.1 province statistics."""

import argparse
from datetime import date
from hashlib import file_digest
from math import isfinite
from pathlib import Path

from services.lcluc.province_esri import write_json

SOURCE = "https://landy.mapbiomas.id/en/statistics"
WORKBOOK_URL = (
    "https://landy.mapbiomas.id/storage/files/statistics_lulc_indonesia_col4-1%20%281%29%20%281%29.xlsx"
)
WORKBOOK_SHA256 = "f6951577d1abb29c44b198a8772965313d739a65e6c98fdb1202b97fb3e80837"
OUTPUT = Path("data/curated/explorer/banten-province/mapbiomas-4.1-trend.json")
YEARS = list(range(1990, 2025))


def import_trend(workbook, acquired_on):
    from openpyxl import load_workbook

    with workbook.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    if digest != WORKBOOK_SHA256:
        raise ValueError("MapBiomas Collection 4.1 workbook hash changed")
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        legend = {row[4]: (row[2], row[5]) for row in book["LEGEND"].values if type(row[4]) is int}
        rows = book["COVERAGE"].values
        header = next(rows)
        year_indices = [header.index(f"y{year}") for year in YEARS]
        territory = [header.index(f"territory_level_{level}") for level in (1, 2, 3)]
        code_index = header.index("class")
        by_code = {}
        for row in rows:
            if tuple(row[index] for index in territory) != ("Indonesia", "Jawa", "Banten"):
                continue
            code = row[code_index]
            values = [row[index] for index in year_indices]
            if code in by_code or any(type(value) not in (int, float) or not isfinite(value) or value < 0
                                      for value in values):
                raise ValueError(f"invalid MapBiomas Banten row for class {code}")
            name, color = legend[code]
            by_code[code] = {"code": code, "name": name, "color": color, "areas_ha": values}
        if len(by_code) != 11:
            raise ValueError("expected 11 published MapBiomas Banten classes")
    finally:
        book.close()
    return {
        "scope": "publisher_province_statistics",
        "region": "banten",
        "source": "MapBiomas Indonesia Collection 4.1",
        "source_url": SOURCE,
        "workbook_url": WORKBOOK_URL,
        "sha256": digest,
        "acquired_on": acquired_on.isoformat(),
        "license": "CC-BY-SA (publisher terms)",
        "source_sheet": "COVERAGE",
        "area_unit": "ha",
        "years": YEARS,
        "classes": [by_code[code] for code in sorted(by_code)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--acquired-on", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    write_json(OUTPUT, import_trend(args.workbook, args.acquired_on))


if __name__ == "__main__":
    main()
