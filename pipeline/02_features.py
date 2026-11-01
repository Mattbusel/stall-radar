"""Build project-level panels: features at T0, outcome at T1.

A panel row is a project that, at snapshot T0, had obligated money it had not yet
spent (gap > $1,000). Features come from T0 and from the prior snapshot T-1
(spending velocity). The outcome is how much of the T0 gap was spent by T1.

Panels:
  train : T-1=2023-03, T0=2024-03, T1=2025-03
  test  : T-1=2024-03, T0=2025-03, T1=2026-03   (out-of-time holdout)
  score : T-1=2025-03, T0=2026-03, T1=unknown (deadline Dec 31 2026)
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PQ = ROOT / "data" / "parquet"
OUT = ROOT / "data" / "panels"
OUT.mkdir(parents=True, exist_ok=True)

OBL, EXP = "Total Cumulative Obligations", "Total Cumulative Expenditures"
MIN_GAP = 1000.0


def load(tag):
    p = pd.read_parquet(PQ / f"projects_{tag}.parquet")
    p = p.rename(columns={"Current Period P&E Reporting Status": "Status"})
    p["obl"] = pd.to_numeric(p[OBL], errors="coerce").fillna(0.0)
    p["exp"] = pd.to_numeric(p[EXP], errors="coerce").fillna(0.0)
    p["cap_cost"] = pd.to_numeric(
        p.get("Total Expected Cost of Capital Expenditures (Select Expenditure Categories Only)"),
        errors="coerce")
    r = pd.read_parquet(PQ / f"recipients_{tag}.parquet")
    r["alloc"] = pd.to_numeric(r["Allocation"], errors="coerce")
    r["rl_std"] = r["Claiming Revenue Loss Standard Allowance? (Yes/No)"].astype("string").str.lower().eq("yes").fillna(False)
    p = p.merge(r[["Recipient-ID", "alloc", "rl_std"]], on="Recipient-ID", how="left")
    return p.set_index("Project ID")


def fresh(period, t1_tag):
    """True when a project's last submitted report covers the period ending at t1."""
    year = t1_tag[:4]
    s = period.astype("string").fillna("")
    return (s.str.contains(f"Q1 {year}") | s.str.contains(f"Annual {year}")).fillna(False)


def build(prev_tag, t0_tag, t1_tag=None, q_tag=None):
    t0 = load(t0_tag)
    prev = load(prev_tag)
    df = pd.DataFrame(index=t0.index)
    df["recipient_id"] = t0["Recipient-ID"]
    df["recipient"] = t0["Recipient Name"]
    df["state"] = t0["State/Territory"]
    df["tier"] = t0["Reporting Tier"].astype("string").str.extract(r"Tier (\d)")[0]
    df["rtype"] = t0["Recipient Type"]
    df["status"] = t0["Completion Status"]
    df["ec_group"] = t0["Expenditure Category Group"].astype("string").str.extract(r"^(\d+)")[0]
    df["ec"] = t0["Expenditure Category"].astype("string").str.extract(r"^([\d.]+)")[0]
    df["ec_name"] = t0["Expenditure Category"]
    df["name"] = t0["Project Name"]
    df["desc"] = t0["Project Description"].astype("string").fillna("")
    df["obl"] = t0["obl"]
    df["exp"] = t0["exp"]
    df["gap"] = (t0["obl"] - t0["exp"]).clip(lower=0)
    df["spend_ratio"] = np.where(t0["obl"] > 0, t0["exp"] / t0["obl"].where(t0["obl"] > 0), 0.0)
    df["log_gap"] = np.log10(df["gap"] + 1)
    df["log_obl"] = np.log10(df["obl"].clip(lower=0) + 1)
    df["capex"] = t0["Does the Project have Capital Expenditures? (Yes/No) (Select Expenditure Categories Only)"].astype("string").str.lower().eq("yes").fillna(False).astype(int)
    df["cap_type"] = t0["Type of Capital Expenditures (Select Expenditure Categories Only)"].astype("string")
    df["log_cap_cost"] = np.log10(t0["cap_cost"].fillna(0).clip(lower=0) + 1)
    df["desc_len"] = df["desc"].str.len()
    df["rl_std"] = t0["rl_std"].fillna(False).astype(int)
    df["log_alloc"] = np.log10(t0["alloc"].fillna(0).clip(lower=0) + 1)
    df["last_period"] = t0.get("Reporting Period Last Submitted")
    df["report_fresh_t0"] = fresh(t0["Reporting Period Last Submitted"], t0_tag).astype(int) if "Reporting Period Last Submitted" in t0 else 1

    # velocity from the prior snapshot
    pv = prev.reindex(df.index)
    df["seen_prev"] = pv["obl"].notna().astype(int)
    df["exp_prev"] = pv["exp"].fillna(0.0)
    df["obl_prev"] = pv["obl"].fillna(0.0)
    df["spent_last_yr"] = (df["exp"] - df["exp_prev"]).clip(lower=0)
    df["vel_ratio"] = np.where(df["gap"] > 0, df["spent_last_yr"] / df["gap"].where(df["gap"] > 0), 0.0)
    df["vel_ratio"] = df["vel_ratio"].clip(0, 20)
    df["obl_growth"] = np.where(df["obl_prev"] > 0, df["obl"] / df["obl_prev"].where(df["obl_prev"] > 0), 0.0).clip(0, 20)
    df["status_prev"] = pv["Completion Status"].astype("string").fillna("NEW")
    df["status_changed"] = (df["status_prev"] != df["status"].astype("string")).fillna(True).astype(int)

    # last-quarter pace for quarterly (Tier 1/2) reporters; annual reporters have no Dec snapshot
    if q_tag:
        q = load(q_tag).reindex(df.index)
        qe = q["exp"].astype("float64").to_numpy(na_value=np.nan)
        qo = q["obl"].astype("float64").to_numpy(na_value=np.nan)
        lq = np.clip(df["exp"].to_numpy(dtype=float) - qe, 0, None)
        gap_q = np.clip(qo - qe, 0, None)
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(gap_q > 0, lq / gap_q, np.nan)
        v[~df["tier"].isin(["1", "2"]).fillna(False).to_numpy()] = np.nan
        df["q_vel_ratio"] = v
        df["q_vel_ratio"] = df["q_vel_ratio"].clip(0, 20)
    else:
        df["q_vel_ratio"] = np.nan

    # recipient context at T0
    g = t0.groupby("Recipient-ID")
    rc = pd.DataFrame({
        "r_obl": g["obl"].sum(), "r_exp": g["exp"].sum(), "r_n": g.size(),
    })
    rc["r_gap"] = (rc["r_obl"] - rc["r_exp"]).clip(lower=0)
    rc["r_spend_ratio"] = np.where(rc["r_obl"] > 0, rc["r_exp"] / rc["r_obl"].where(rc["r_obl"] > 0), 0.0)
    pg = prev.groupby("Recipient-ID")["exp"].sum()
    rc["r_spent_last_yr"] = (rc["r_exp"] - pg.reindex(rc.index).fillna(0)).clip(lower=0)
    rc["r_vel_ratio"] = np.where(rc["r_gap"] > 0, rc["r_spent_last_yr"] / rc["r_gap"].where(rc["r_gap"] > 0), 0.0).clip(0, 20)
    rc["r_n_open"] = (t0["obl"] - t0["exp"] > MIN_GAP).groupby(t0["Recipient-ID"]).sum()
    df = df.join(rc[["r_n", "r_n_open", "r_spend_ratio", "r_vel_ratio"]], on="recipient_id")
    df["r_log_gap"] = np.log10(df.join(rc["r_gap"], on="recipient_id")["r_gap"] + 1)
    df["share_of_recipient_gap"] = df["gap"] / (10 ** df["r_log_gap"])

    df = df[df["gap"] > MIN_GAP].copy()

    if t1_tag:
        t1 = load(t1_tag).reindex(df.index)
        df["in_t1"] = t1["obl"].notna().astype(int)
        df["fresh_t1"] = fresh(t1["Reporting Period Last Submitted"].fillna(""), t1_tag).astype(int)
        df["exp_t1"] = t1["exp"]
        df["obl_t1"] = t1["obl"]
        df["status_t1"] = t1["Completion Status"]
        spent = (df["exp_t1"].fillna(df["exp"]) - df["exp"]).clip(lower=0)
        df["closure"] = (spent / df["gap"]).clip(0, 1)
        # a project cancelled or de-obligated at T1 releases its money; it is not "stuck"
        released = df["obl_t1"].notna() & (df["obl_t1"] <= df["exp_t1"].fillna(0) + MIN_GAP)
        df["released"] = released.astype(int)
        df["remaining_t1"] = (df["obl_t1"].fillna(df["obl"]) - df["exp_t1"].fillna(df["exp"])).clip(lower=0)
    return df


if __name__ == "__main__":
    for name, tags in {
        "train": ("2023-03-31", "2024-03-31", "2025-03-31", "2023-12-31"),
        "test": ("2024-03-31", "2025-03-31", "2026-03-31", "2024-12-31"),
        "score": ("2025-03-31", "2026-03-31", None, "2025-12-31"),
    }.items():
        d = build(*tags)
        d.to_parquet(OUT / f"{name}.parquet")
        msg = f"{name}: {len(d):,} open projects, gap ${d['gap'].sum()/1e9:.2f}B"
        if "closure" in d:
            lab = d[(d.in_t1 == 1) & (d.fresh_t1 == 1)]
            msg += (f"; labelled(fresh T1) {len(lab):,}; mean closure {lab.closure.mean():.3f};"
                    f" share closing <50%: {(lab.closure < .5).mean():.3f}")
        print(msg)
