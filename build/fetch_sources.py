"""Download the free source datasets used by make_squares.py into build/sources/."""
import io
import zipfile
from pathlib import Path

import requests

SOURCES = Path(__file__).parent / "sources"

DATASETS = {
    # OSM land polygons (coastline-derived), simplified, EPSG:3857
    "osm_land": "https://osmdata.openstreetmap.de/download/simplified-land-polygons-complete-3857.zip",
    # Natural Earth 10m land boundary lines between countries
    "ne_boundaries": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_land.zip",
    # Natural Earth 10m maritime boundary lines (TH-MM line through the Kra estuary into the Andaman Sea)
    "ne_maritime": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_maritime_indicator.zip",
    # Natural Earth 10m country polygons (Thailand / Myanmar share of each square)
    "ne_countries": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
    # Natural Earth 10m marine area names (Gulf of Thailand, Andaman Sea, ...)
    "ne_marine": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_marine_polys.zip",
}


def main():
    SOURCES.mkdir(exist_ok=True)
    for name, url in DATASETS.items():
        target = SOURCES / name
        if target.exists() and any(target.rglob("*.shp")):
            print(f"[skip] {name} already downloaded")
            continue
        print(f"[get ] {name} <- {url}")
        resp = requests.get(url, timeout=600, headers={"User-Agent": "th-gis-squares/1.0"})
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(target)
        print(f"       {len(resp.content) / 1e6:.1f} MB extracted to {target}")


if __name__ == "__main__":
    main()
