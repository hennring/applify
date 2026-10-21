"""Build the offline geo data (D11) from GeoNames: python -m applify.build_geonames

Downloads the German place and postal code dumps and writes two compact TSV files to
resources/. GeoNames data is licensed under CC BY 4.0 (https://www.geonames.org).
"""

import csv
import io
import zipfile
from pathlib import Path

import httpx

RESOURCES = Path(__file__).resolve().parent.parent / "resources"
PLACES_URL = "https://download.geonames.org/export/dump/DE.zip"
POSTAL_URL = "https://download.geonames.org/export/zip/DE.zip"


def _rows(url: str) -> list[list[str]]:
    data = httpx.get(url, timeout=120, follow_redirects=True).raise_for_status().content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = archive.read("DE.txt").decode("utf-8")
    return list(csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE))


def main() -> None:
    postal: dict[str, tuple[str, str, str]] = {}
    for row in _rows(POSTAL_URL):
        code, place, lat, lon = row[1], row[2], row[9], row[10]
        postal.setdefault(code, (place, lat, lon))
    official_names = {place for place, _, _ in postal.values()}

    places: dict[tuple[str, str], tuple[str, str, int]] = {}
    # Populated places (feature class P) with a population or an administrative role;
    # tens of thousands of unnamed hamlets are left out.
    for row in _rows(PLACES_URL):
        name, alternates, lat, lon = row[1], row[3], row[4], row[5]
        feature_class, feature_code, population = row[6], row[7], int(row[14] or 0)
        if feature_class != "P" or not (population or feature_code.startswith(("PPLA", "PPLC"))):
            continue
        # Some cities carry their English name ("Munich"); the German one is an alternate
        # name that also appears as an official place name in the postal data.
        german = {a for a in alternates.split(",") if a in official_names} if population else set()
        for variant in {name} | german:
            key = (variant, f"{float(lat):.2f},{float(lon):.2f}")
            places[key] = (lat, lon, max(population, places.get(key, ("", "", 0))[2]))

    with (RESOURCES / "geonames_places.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("# GeoNames (CC BY 4.0, geonames.org): name, lat, lon, population\n")
        for (name, _), (lat, lon, population) in sorted(places.items()):
            f.write(f"{name}\t{lat}\t{lon}\t{population}\n")
    with (RESOURCES / "geonames_postal.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("# GeoNames (CC BY 4.0, geonames.org): postal code, place, lat, lon\n")
        for code, (place, lat, lon) in sorted(postal.items()):
            f.write(f"{code}\t{place}\t{lat}\t{lon}\n")
    print(f"{len(places)} places, {len(postal)} postal codes")


if __name__ == "__main__":
    main()
