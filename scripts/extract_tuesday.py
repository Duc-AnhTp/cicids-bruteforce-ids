"""Extract Tuesday-WorkingHours.pcap_ISCX.csv from GeneratedLabelledFlows.zip."""
from __future__ import annotations

from pathlib import Path
import sys
import zipfile

def extract_tuesday(raw_dir: Path) -> Path:
    zip_path = raw_dir / "GeneratedLabelledFlows.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"Archive not found: {zip_path}")

    target_name = "Tuesday-WorkingHours.pcap_ISCX.csv"
    dest_path = raw_dir / target_name

    print(f"Opening archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        print(f"Archive contains {len(names)} entries.")
        matching = [n for n in names if target_name.lower() in n.lower() or "tuesday" in n.lower()]
        if not matching:
            print("Available files in archive:")
            for n in names:
                print(f"  - {n}")
            raise FileNotFoundError(f"Cannot find Tuesday CSV in {zip_path}")

        member = matching[0]
        print(f"Found match: {member}")
        print(f"Extracting to: {dest_path}...")
        with z.open(member) as source, open(dest_path, "wb") as target:
            # Stream in 8MB chunks
            while chunk := source.read(8 * 1024 * 1024):
                target.write(chunk)

    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"Done! Extracted {dest_path.name} ({size_mb:.2f} MB)")
    return dest_path

if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    raw_dir = repo_root / "data" / "raw"
    try:
        extract_tuesday(raw_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
