"""Download the seven Treasury SLFRF Project & Expenditure releases used by Stall Radar."""
import pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
BASE = "https://home.treasury.gov/system/files/136/"
FILES = {
    "2023-03-31": "April-2023-Reporting-Data-through-March-31-2023.xlsx",
    "2023-12-31": "January-2024-Quarterly-Reporting-Data-through-December-31-2023.xlsx",
    "2024-03-31": "April-2024-Reporting-Data-through-March-31-2024.xlsx",
    "2024-12-31": "January-2025-Reporting-Data-through-December-31-2024.xlsx",
    "2025-03-31": "April-2025-Reporting-Data-through-March-31-2025.xlsx",
    "2025-12-31": "January-2026-Reporting-Data-through-December-31-2025.xlsx",
    "2026-03-31": "April-2026-Reporting-Data-through-March-31-2026.xlsx",
}
for tag, name in FILES.items():
    out = RAW / f"{tag}.xlsx"
    if out.exists() and out.stat().st_size > 1_000_000:
        print("have", out.name); continue
    req = urllib.request.Request(BASE + name, headers={"User-Agent": "Mozilla/5.0 (stall-radar)"})
    with urllib.request.urlopen(req, timeout=300) as r, open(out, "wb") as f:
        f.write(r.read())
    print("got", out.name, out.stat().st_size)
