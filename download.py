"""Download OPSSAT-AD from Zenodo (both versions) and verify the md5 of every file."""
import hashlib
import sys
import urllib.request

from opssat import FEATURE_TABLES, RAW_SERIES, UPSTREAM_LICENSE

URL = "https://zenodo.org/api/records/{record}/files/{name}/content"
# (Zenodo record, file, destination, md5 published by Zenodo)
FILES = [
    # Current version, DOI 10.5281/zenodo.15108715 (uploaded 2025-03-30).
    ("15108715", "dataset.csv", FEATURE_TABLES["current"], "5246fdc5e4630a4cecbf7fb6bc8b795e"),
    ("15108715", "segments.csv", RAW_SERIES, "72f109630abb933a386106897a631188"),
    ("15108715", "LICENSE", UPSTREAM_LICENSE, "ea8befa9af2b37b7a54b5a16fc3712b0"),
    # First version, DOI 10.5281/zenodo.12588359 (2024-07-09): only the feature table.
    ("12588359", "dataset.csv", FEATURE_TABLES["paper"], "c12fb83863afa4463dec07303a20bb14"),
]


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    for record, name, destination, expected in FILES:
        label = f"{destination.parent.name}/{name}"
        if destination.exists() and md5(destination) == expected:
            print(f"present     {label}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL.format(record=record, name=name), destination)
        obtained = md5(destination)
        if obtained != expected:
            destination.unlink()
            sys.exit(f"md5 mismatch for {label}: expected {expected}, got {obtained}")
        print(f"downloaded  {label}  ({destination.stat().st_size} bytes, md5 ok)")


if __name__ == "__main__":
    main()
