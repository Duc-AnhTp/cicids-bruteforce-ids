from pathlib import Path
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

if not DATA_PATH.is_file():
    print(f"FAIL: Không tìm thấy file dữ liệu raw Tuesday tại các đường dẫn mặc định:")
    print(f"  - data/raw/Tuesday-WorkingHours.pcap_ISCX.csv")
    print(f"  - data/raw/cicids2017/GeneratedLabelledFlows/Tuesday-WorkingHours.pcap_ISCX.csv")
    print("Vui lòng tải file và đặt vào một trong các thư mục trên.")
    exit(1)

df = pd.read_csv(DATA_PATH)
df.columns = df.columns.astype(str).str.strip()
df["Label"] = df["Label"].astype(str).str.strip()

print("=" * 80)
print("INSPECT TUESDAY DATA QUALITY")
print("=" * 80)

# 1. Timestamp
print("\n[1] TIMESTAMP")

print("Mẫu raw:")
print(df["Timestamp"].head(10).to_string(index=False))

# Chưa mặc định format sai.
# Với CICIDS2017 Tuesday, trước mắt thử format ngày/tháng/năm.
ts = pd.to_datetime(
    df["Timestamp"].astype(str).str.strip(),
    format="%d/%m/%Y %H:%M",
    errors="coerce"
)

print("\nParse failed:", ts.isna().sum())

if ts.notna().any():
    print("Min timestamp:", ts.min())
    print("Max timestamp:", ts.max())

    print("\nTimestamp min/max theo Label:")
    tmp = pd.DataFrame({
        "TimestampParsed": ts,
        "Label": df["Label"]
    })

    print(
        tmp.groupby("Label")["TimestampParsed"]
        .agg(["min", "max", "count"])
    )

# 2. Flow Duration âm
print("\n[2] NEGATIVE FLOW DURATION")

duration = pd.to_numeric(df["Flow Duration"], errors="coerce")
negative = df.loc[
    duration < 0,
    ["Flow ID", "Source IP", "Destination IP",
     "Timestamp", "Flow Duration", "Label"]
]

print("Số dòng âm:", len(negative))

if len(negative):
    print(negative.to_string(index=False))

# 3. NaN
print("\n[3] NaN BY COLUMN")

nan_by_col = df.isna().sum()
nan_by_col = nan_by_col[nan_by_col > 0].sort_values(ascending=False)

print(nan_by_col if len(nan_by_col) else "None")

# 4. Infinity
print("\n[4] INFINITY BY COLUMN")

numeric = df.select_dtypes(include=[np.number])

inf_by_col = pd.Series(
    {
        col: int(np.isinf(numeric[col]).sum())
        for col in numeric.columns
    }
)

inf_by_col = inf_by_col[inf_by_col > 0].sort_values(ascending=False)

print(inf_by_col if len(inf_by_col) else "None")

# 5. Duplicate
print("\n[5] RAW DUPLICATES")

dup_mask = df.duplicated(keep=False)
duplicates = df.loc[dup_mask]

print("Số dòng tham gia duplicate:", len(duplicates))
print("Số duplicate dư thừa:", df.duplicated().sum())

if len(duplicates):
    cols = [
        c for c in
        ["Flow ID", "Source IP", "Source Port",
         "Destination IP", "Destination Port",
         "Protocol", "Timestamp", "Flow Duration", "Label"]
        if c in duplicates.columns
    ]

    print(duplicates[cols].to_string(index=True))

# 6. Cột .1
print("\n[6] .1 COLUMNS")

dot_cols = [c for c in df.columns if c.endswith(".1")]
print(dot_cols)

for c in dot_cols:
    original = c[:-2]

    if original in df.columns:
        equal_count = (df[c] == df[original]).sum()
        comparable = df[[c, original]].dropna()

        print(
            f"{c} vs {original}: "
            f"equal={equal_count}/{len(df)}, "
            f"comparable={len(comparable)}"
        )