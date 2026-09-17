from pathlib import Path
import hashlib
import numpy as np
import pandas as pd


def resolve_data_path() -> Path:
    candidates = [
        Path("data/raw/Tuesday-WorkingHours.pcap_ISCX.csv"),
        Path("data/raw/cicids2017/GeneratedLabelledFlows/Tuesday-WorkingHours.pcap_ISCX.csv"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


DATA_PATH = resolve_data_path()

REQUIRED_COLS = ["Label", "Timestamp", "Flow Duration"]


def sha256_file(path: Path, chunk_size=1024 * 1024):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)

    return h.hexdigest()


def main():
    print("=" * 80)
    print("AUDIT CICIDS2017 - TUESDAY - GENERATED LABELLED FLOWS")
    print("=" * 80)

    # ------------------------------------------------------------------
    # 1. FILE / PROVENANCE
    # ------------------------------------------------------------------
    print("\n[1] FILE")

    if not DATA_PATH.exists():
        print("FAIL: Không tìm thấy file:")
        print(DATA_PATH)
        return

    print("Path:", DATA_PATH)
    print("Size (bytes):", DATA_PATH.stat().st_size)
    print("SHA256:", sha256_file(DATA_PATH))

    # ------------------------------------------------------------------
    # 2. LOAD DATA
    # ------------------------------------------------------------------
    print("\n[2] LOAD DATA")

    df = pd.read_csv(DATA_PATH)

    # canonical column names
    df.columns = df.columns.astype(str).str.strip()

    print("Số dòng:", len(df))
    print("Số cột:", len(df.columns))

    # ------------------------------------------------------------------
    # 3. REQUIRED SCHEMA
    # ------------------------------------------------------------------
    print("\n[3] REQUIRED SCHEMA")

    missing_required = []

    for col in REQUIRED_COLS:
        if col in df.columns:
            print(f"{col}: OK")
        else:
            print(f"{col}: MISSING")
            missing_required.append(col)

    if missing_required:
        print("\nAUDIT FAILED")
        print("Thiếu:", missing_required)
        return

    # ------------------------------------------------------------------
    # 4. SUSPICIOUS / DUPLICATED COLUMN NAMES
    # ------------------------------------------------------------------
    print("\n[4] COLUMN AUDIT")

    unnamed = [c for c in df.columns if c.lower().startswith("unnamed")]
    dot_columns = [c for c in df.columns if ".1" in c or ".2" in c]

    print("Unnamed columns:", unnamed if unnamed else "None")
    print("Columns dạng .1/.2:", dot_columns if dot_columns else "None")

    # ------------------------------------------------------------------
    # 5. LABEL DISTRIBUTION
    # ------------------------------------------------------------------
    print("\n[5] LABEL DISTRIBUTION")

    df["Label"] = df["Label"].astype(str).str.strip()

    print(df["Label"].value_counts(dropna=False))

    # ------------------------------------------------------------------
    # 6. TIMESTAMP RAW AUDIT
    # ------------------------------------------------------------------
    print("\n[6] TIMESTAMP RAW")

    print("\nFirst 10:")
    print(
        df[["Timestamp", "Flow Duration", "Label"]]
        .head(10)
        .to_string(index=False)
    )

    print("\nLast 10:")
    print(
        df[["Timestamp", "Flow Duration", "Label"]]
        .tail(10)
        .to_string(index=False)
    )

    print("\nTimestamp missing:", df["Timestamp"].isna().sum())

    # Timestamp examples by label
    print("\nTimestamp samples by Label:")

    for label, group in df.groupby("Label"):
        print(f"\n--- {label} ---")
        print(group["Timestamp"].head(5).to_string(index=False))

    # ------------------------------------------------------------------
    # 7. FLOW DURATION
    # ------------------------------------------------------------------
    print("\n[7] FLOW DURATION")

    duration = pd.to_numeric(df["Flow Duration"], errors="coerce")

    print("Missing / non-numeric:", duration.isna().sum())
    print("Min:", duration.min())
    print("Max:", duration.max())
    print("Median:", duration.median())
    print("Negative:", (duration < 0).sum())

    # ------------------------------------------------------------------
    # 8. NaN / INFINITY
    # ------------------------------------------------------------------
    print("\n[8] NaN / INFINITY")

    numeric = df.select_dtypes(include=[np.number])

    nan_total = int(df.isna().sum().sum())
    inf_total = int(np.isinf(numeric.to_numpy()).sum())

    print("Total NaN:", nan_total)
    print("Total Infinity:", inf_total)

    # ------------------------------------------------------------------
    # 9. DUPLICATES
    # ------------------------------------------------------------------
    print("\n[9] DUPLICATES")

    duplicate_count = int(df.duplicated().sum())

    print("Raw duplicate rows:", duplicate_count)

    # ------------------------------------------------------------------
    # 10. RESULT
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SCHEMA AUDIT: PASS")
    print(
        "Chưa được split cho tới khi Timestamp format "
        "và đơn vị Flow Duration được xác minh."
    )
    print("=" * 80)


if __name__ == "__main__":
    main()