"""Refresh medicinal-plant data on request, then build the Data exports."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent / "scripts"


def run_script(name: str, *arguments: str) -> None:
    command = [sys.executable, str(SCRIPTS / name), *arguments]
    print(f"\nRunning: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT.parent, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract-web",
        action="store_true",
        help="refresh website links and detail pages using the existing names.csv",
    )
    parser.add_argument(
        "--refresh-identity-names",
        action="store_true",
        help="scrape identity.csv and regenerate names.csv before website extraction",
    )
    parser.add_argument(
        "--extract-shlokas",
        action="store_true",
        help="capture shloka-page images and refresh the existing OCR text",
    )
    args = parser.parse_args()

    if args.refresh_identity_names and not args.extract_web:
        parser.error("--refresh-identity-names requires --extract-web")

    if args.refresh_identity_names:
        run_script("extract_identity.py", "--overwrite")
        run_script("extract_names.py", "--overwrite")

    if args.extract_web:
        run_script("extract_links.py", "--overwrite", "--allow-fewer")
        run_script("extract_plant_details.py", "--overwrite", "--allow-fewer")
        run_script("normalize_plants.py", "--overwrite", "--allow-fewer")

    if args.extract_shlokas:
        run_script("capture_shloka_images.py", "--overwrite")
        run_script("process_shloka_ocr.py", "--overwrite")

    run_script("validate_plants.py")
    subprocess.run(
        [sys.executable, str(ROOT / "run_data_pipeline.py"), "--force"],
        cwd=ROOT.parent,
        check=True,
    )


if __name__ == "__main__":
    main()
