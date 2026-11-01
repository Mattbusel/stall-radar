"""Ingest Treasury SLFRF Project & Expenditure workbooks into parquet.

Each workbook has a Recipients sheet and a Projects sheet. Header row position and
sheet names drift between releases, so we locate them by content.
"""
import sys, pathlib, re
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "parquet"
OUT.mkdir(parents=True, exist_ok=True)

def find_header(df, must):
    for i in range(min(15, len(df))):
        row = [str(x) for x in df.iloc[i].tolist()]
        if any(c.strip() in must for c in row):
            return i
    raise ValueError(f"header with {must!r} not found")

def load_sheet(path, kind):
    xl = pd.ExcelFile(path, engine="calamine")
    names = [s for s in xl.sheet_names if s.lower().startswith(kind)]
    if not names:
        raise ValueError(f"{path.name}: no {kind} sheet in {xl.sheet_names}")
    raw = pd.read_excel(xl, sheet_name=names[0], header=None, dtype=object)
    h = find_header(raw, {"Recipient-ID", "Recipient ID", "Project ID"})
    df = raw.iloc[h + 1:].copy()
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in raw.iloc[h].tolist()]
    df = df.loc[:, [c for c in df.columns if c and c != "nan" and c != "None"]]
    return df.dropna(how="all")

for f in sorted(RAW.glob("*.xlsx")):
    tag = f.stem
    for kind in ("recipients", "projects"):
        df = load_sheet(f, kind)
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].astype("string")
        df.to_parquet(OUT / f"{kind}_{tag}.parquet", index=False)
        print(tag, kind, df.shape)
        print("   ", list(df.columns)[:32])
