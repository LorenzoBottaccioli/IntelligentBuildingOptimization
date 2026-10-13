"""Download the IWEC file of Turin that the demo session and the tutorials use, and put it where they expect it.

The file is (c) 2001 ASHRAE and is not in git (see NOTICE.md): it is licensed to each user, so each clone fetches its own copy
from the EnergyPlus weather site. Run once after cloning, before building the backend image or `make_tutorials.py`.

    python tests/tutorials/fetch_iwec.py        (needs `requests`; the backend image has it)
"""
import hashlib
import pathlib
import requests

URL = "https://energyplus-weather.s3.amazonaws.com/europe_wmo_region_6/ITA/ITA_Torino.160590_IWEC/ITA_Torino.160590_IWEC.epw"
NAME = "ITA_Torino.160590_IWEC.epw"
ROOT = pathlib.Path(__file__).resolve().parents[2]
PLACES = [
    "tutorials",
    "backend/seed_sessions/bdopt-demo/state/uploads",
    "backend/seed_sessions/bdopt-demo/state/surrogate_notebooks/tutorials",
    "demo_files_2026-09-29/uploads",
]


def main():
    r = requests.get(URL, timeout=120)
    r.raise_for_status()
    data = r.content
    if not data.startswith(b"LOCATION"):
        raise SystemExit("That is not an EPW file: " + URL)
    for place in PLACES:
        folder = ROOT / place
        if folder.is_dir():
            (folder / NAME).write_bytes(data)
            print("written", folder / NAME)
    print("md5", hashlib.md5(data).hexdigest())


if __name__ == "__main__":
    main()
