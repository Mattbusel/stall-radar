"""Export the scored book to small JSON files the web app loads on demand."""
import json, pathlib, re
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "data" / "model"
WEB = ROOT / "web" / "data"
(WEB / "states").mkdir(parents=True, exist_ok=True)

LABEL = {
    "q_vel_ratio": "slow spending last quarter", "vel_ratio": "slow spending over the past year",
    "text_score": "project type historically stalls (description)", "state": "state's track record",
    "ec": "spending category's track record", "ec_group": "spending category group", "log_gap": "large unspent balance",
    "log_obl": "large total budget", "spend_ratio": "low share already spent", "share_of_recipient_gap":
    "big share of this government's open money", "r_spend_ratio": "government's overall spend rate is low",
    "r_vel_ratio": "government spent slowly overall last year", "r_log_gap": "government has a large open balance",
    "r_n_open": "many open projects at this government", "r_n": "many projects at this government",
    "obl_growth": "budget was revised up late", "status": "reported completion status",
    "status_prev": "prior completion status", "status_changed": "status changed since last year",
    "desc_len": "thin or long project description", "capex": "capital project", "cap_type": "capital project type",
    "log_cap_cost": "large capital cost", "rl_std": "revenue-loss standard allowance", "log_alloc": "allocation size",
    "report_fresh_t0": "latest report is stale", "seen_prev": "project is new since last year",
    "tier": "reporting tier", "rtype": "government type",
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def main():
    s = pd.read_parquet(MOD / "scored.parquet")
    summ = json.loads((MOD / "summary.json").read_text())
    s["risk"] = s["at_risk_usd_corrected"]
    s["state"] = s["state"].astype("string").fillna("Unknown")

    projects = []
    for pid, r in s.iterrows():
        drv = [LABEL.get(n, n) for n, _ in json.loads(r["drivers"])]
        projects.append({
            "id": pid, "rid": r["recipient_id"], "st": r["state"], "n": str(r["name"])[:140],
            "d": str(r["desc"])[:600], "ec": str(r["ec_name"]), "status": str(r["status"]),
            "obl": round(float(r["obl"])), "exp": round(float(r["exp"])), "gap": round(float(r["gap"])),
            "p": round(float(r["stall_prob"]), 3), "risk": round(float(r["risk"])), "why": drv,
            "last": str(r["last_period"]) if pd.notna(r["last_period"]) else "",
        })
    P = pd.DataFrame(projects)

    rec = s.groupby("recipient_id").agg(
        name=("recipient", "first"), st=("state", "first"), tier=("tier", "first"), type=("rtype", "first"),
        open=("gap", "size"), gap=("gap", "sum"), risk=("risk", "sum"), pmax=("stall_prob", "max"),
        obl=("r_log_gap", "first"),
    ).reset_index()
    rec["share"] = (rec["risk"] / rec["gap"]).round(3)
    rec = rec.sort_values("risk", ascending=False)
    recipients = [{"rid": r.recipient_id, "name": r.name, "st": r.st, "tier": r.tier, "type": r.type,
                   "open": int(r.open), "gap": round(r.gap), "risk": round(r.risk), "share": float(r.share)}
                  for r in rec.itertuples()]
    (WEB / "recipients.json").write_text(json.dumps(recipients, separators=(",", ":")))

    for st, g in P.groupby("st"):
        g = g.sort_values("risk", ascending=False)
        (WEB / "states" / f"{slug(st)}.json").write_text(json.dumps(g.to_dict("records"), separators=(",", ":")))

    by_state = s.groupby("state").agg(gap=("gap", "sum"), risk=("risk", "sum"), n=("gap", "size")).reset_index()
    by_state = by_state.sort_values("risk", ascending=False)
    s["ecg"] = s["ec_name"].astype("string").str.extract(r"^(\d+)")[0]
    groups = {"1": "Public health", "2": "Negative economic impacts", "3": "Public sector capacity",
              "4": "Premium pay", "5": "Water, sewer and broadband", "6": "Revenue replacement",
              "7": "Administrative", "8": "Natural disasters", "9": "Surface transportation",
              "10": "Title I community development"}
    by_cat = s.groupby("ecg").agg(gap=("gap", "sum"), risk=("risk", "sum"), n=("gap", "size")).reset_index()
    by_cat["label"] = by_cat["ecg"].map(groups).fillna("Other")
    by_cat = by_cat.sort_values("risk", ascending=False)

    nat = summ["national"]
    out = {
        "as_of": "2026-03-31", "deadline": "2026-12-31",
        "national": nat,
        "evaluation": summ["evaluation"], "calibration": summ["calibration"], "slices": summ["slices"],
        "importance": [{"f": LABEL.get(k, k), "v": v} for k, v in summ["importance"].items()][:12],
        "stall_terms": summ["text_terms_production"]["stall"][:20],
        "by_state": [{"st": r.state, "slug": slug(r.state), "gap": round(r.gap), "risk": round(r.risk), "n": int(r.n)}
                     for r in by_state.itertuples()],
        "by_category": [{"label": r.label, "gap": round(r.gap), "risk": round(r.risk), "n": int(r.n)}
                        for r in by_cat.itertuples()],
        "n_train": summ["n_train"], "n_test": summ["n_test"],
        "top_projects": P.sort_values("risk", ascending=False).head(25).to_dict("records"),
    }
    (WEB / "national.json").write_text(json.dumps(out, separators=(",", ":")))
    sizes = sum(f.stat().st_size for f in WEB.rglob("*.json"))
    print(f"recipients {len(recipients):,}, projects {len(P):,}, states {P.st.nunique()}, total {sizes/1e6:.1f} MB")


if __name__ == "__main__":
    main()
