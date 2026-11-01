"""Train the stall model, validate out-of-time, score every open project.

Target: closure = share of a project's unspent obligated balance that is actually
spent over the next 12 months. We fit a LightGBM model with a cross-entropy
objective on that fraction (so it predicts an expected share in [0, 1]), stack in a
text model over the project name and description, and compare against two
baselines. Validation is strictly out-of-time: the model is fitted on 2024->2025
outcomes and judged on 2025->2026 outcomes it never saw.
"""
import json, pathlib
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, mean_absolute_error

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAN = ROOT / "data" / "panels"
OUT = ROOT / "data" / "model"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 7

NUM = ["log_gap", "log_obl", "spend_ratio", "capex", "log_cap_cost", "desc_len", "rl_std", "log_alloc",
       "report_fresh_t0", "seen_prev", "vel_ratio", "q_vel_ratio", "obl_growth", "status_changed", "r_n", "r_n_open",
       "r_spend_ratio", "r_vel_ratio", "r_log_gap", "share_of_recipient_gap"]
CAT = ["tier", "rtype", "status", "ec_group", "ec", "cap_type", "status_prev", "state"]


def numpyify(d):
    """pandas 3 reads parquet floats as nullable arrays; LightGBM wants plain float64."""
    for c in d.columns:
        if pd.api.types.is_numeric_dtype(d[c]) and not pd.api.types.is_bool_dtype(d[c]):
            d[c] = d[c].astype("float64")
    return d


def load(name):
    return numpyify(pd.read_parquet(PAN / f"{name}.parquet"))


def labelled(d):
    return d[(d.in_t1 == 1) & (d.fresh_t1 == 1)].copy()


def text_of(d):
    return (d["name"].astype("string").fillna("") + " . " + d["desc"].astype("string").fillna("")).str.lower()


def text_model(train, others):
    """Ridge on TF-IDF of name+description. Out-of-fold predictions for train rows."""
    vec = TfidfVectorizer(min_df=5, max_features=60000, ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    Xt = vec.fit_transform(text_of(train))
    y = train["closure"].values
    oof = np.zeros(len(train))
    for tr, va in KFold(5, shuffle=True, random_state=SEED).split(Xt):
        m = Ridge(alpha=3.0).fit(Xt[tr], y[tr])
        oof[va] = m.predict(Xt[va])
    full = Ridge(alpha=3.0).fit(Xt, y)
    preds = [full.predict(vec.transform(text_of(o))) for o in others]
    terms = np.array(vec.get_feature_names_out())
    order = np.argsort(full.coef_)
    words = {"stall": terms[order[:25]].tolist(), "spend": terms[order[-25:]][::-1].tolist()}
    return oof, preds, words


def prep(d, cats=None):
    X = d[NUM].astype(float).copy()
    for c in CAT:
        X[c] = d[c].astype("string").fillna("NA")
    if cats is None:
        cats = {c: pd.CategoricalDtype(sorted(X[c].unique())) for c in CAT}
    for c in CAT:
        X[c] = X[c].astype(cats[c])
    X["text_score"] = d["text_score"].values
    return X, cats


def fit_gbm(X, y, w=None):
    params = dict(objective="cross_entropy", learning_rate=0.03, num_leaves=63, min_data_in_leaf=60,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                  cat_smooth=20, verbose=-1, seed=SEED)
    return lgb.train(params, lgb.Dataset(X, y, weight=w, categorical_feature=CAT), num_boost_round=900)


def metrics(d, pred, name):
    stall = (d["closure"] < 0.5).astype(int).values
    risk = 1 - pred
    act_rem = (d["gap"] * (1 - d["closure"])).sum()
    pred_rem = (d["gap"] * (1 - pred)).sum()
    # dollar capture: share of truly stuck dollars found in the top 10% of projects by predicted stuck $
    stuck_d = d["gap"] * (1 - d["closure"])
    rank = np.argsort(-(d["gap"].values * risk))
    k = int(0.1 * len(d))
    capture = stuck_d.values[rank[:k]].sum() / stuck_d.sum()
    return {
        "model": name,
        "auc_stall": round(roc_auc_score(stall, risk), 4),
        "auc_stall_dollar_weighted": round(roc_auc_score(stall, risk, sample_weight=d["gap"].values), 4),
        "ap_stall": round(average_precision_score(stall, risk), 4),
        "brier_stall": round(brier_score_loss(stall, np.clip(risk, 0, 1)), 4),
        "mae_closure": round(mean_absolute_error(d["closure"], pred), 4),
        "actual_unspent_B": round(act_rem / 1e9, 3),
        "predicted_unspent_B": round(pred_rem / 1e9, 3),
        "dollar_error_pct": round(100 * (pred_rem - act_rem) / act_rem, 2),
        "top10pct_capture_of_stuck_dollars": round(float(capture), 4),
    }


def main():
    train = labelled(load("train"))
    test = labelled(load("test"))
    score = load("score")
    print(f"train {len(train):,}  test {len(test):,}  score {len(score):,}")

    # ---- out-of-time evaluation: fit on train only
    oof, (t_test, t_score), words = text_model(train, [test, score])
    train["text_score"], test["text_score"] = oof, t_test
    Xtr, cats = prep(train)
    Xte, _ = prep(test, cats)
    w = np.log10(train["gap"].values + 10)  # mild dollar weighting
    gbm = fit_gbm(Xtr, train["closure"].values, w)
    p_gbm = np.clip(gbm.predict(Xte), 0, 1)

    # baselines
    p_persist = np.clip(test["vel_ratio"].values, 0, 1)            # last year's pace repeats
    p_mean = np.full(len(test), train["closure"].mean())           # base rate
    p_text = np.clip(t_test, 0, 1)                                 # text alone
    Xtr_nt = Xtr.drop(columns=["text_score"]); Xte_nt = Xte.drop(columns=["text_score"])
    p_notext = np.clip(fit_gbm(Xtr_nt, train["closure"].values, w).predict(Xte_nt), 0, 1)

    rows = [metrics(test, p, n) for p, n in [
        (p_mean, "base rate"), (p_persist, "persistence (last-year pace)"), (p_text, "text only (TF-IDF ridge)"),
        (p_notext, "GBM, no text"), (p_gbm, "GBM + text (Stall Radar)")]]
    ev = pd.DataFrame(rows)
    print(ev.to_string(index=False))

    # calibration on test (deciles of predicted closure)
    test["pred"] = p_gbm
    test["dec"] = pd.qcut(test["pred"], 10, labels=False, duplicates="drop")
    calib = test.groupby("dec").agg(pred=("pred", "mean"), actual=("closure", "mean"), n=("pred", "size")).reset_index()

    # slices
    sl = []
    for col in ["tier", "rtype", "ec_group"]:
        for k, g in test.groupby(col):
            if len(g) < 300 or g["closure"].lt(.5).nunique() < 2:
                continue
            sl.append({"slice": f"{col}={k}", "n": len(g),
                       "auc": round(roc_auc_score((g.closure < .5).astype(int), 1 - g.pred), 3),
                       "actual_closure": round(g.closure.mean(), 3), "pred_closure": round(g.pred.mean(), 3)})
    slices = pd.DataFrame(sl)

    imp = pd.Series(gbm.feature_importance("gain"), index=Xtr.columns).sort_values(ascending=False)
    imp = (imp / imp.sum()).round(4)

    # ---- production model: refit on train + test, score the open book as of Mar 31 2026
    both = pd.concat([train, test.drop(columns=["pred", "dec"])])
    oof2, (t_score2,), words2 = text_model(both, [score])
    both["text_score"] = oof2
    score["text_score"] = t_score2
    Xb, cats2 = prep(both)
    Xs, _ = prep(score, cats2)
    gbm2 = fit_gbm(Xb, both["closure"].values, np.log10(both["gap"].values + 10))
    c12 = np.clip(gbm2.predict(Xs), 0, 1)
    # horizon: 12-month model, 9 months left (Mar 31 -> Dec 31 2026). Constant-hazard conversion.
    c9 = 1 - (1 - c12) ** 0.75
    score["closure_12m"] = c12
    score["closure_by_deadline"] = c9
    score["at_risk_usd"] = score["gap"] * (1 - c9)
    score["stall_prob"] = 1 - c9

    # bootstrap interval on the national at-risk total, using test-set residual structure
    rng = np.random.default_rng(SEED)
    ratio = (test["gap"] * (1 - test["closure"])).values
    pratio = (test["gap"] * (1 - test["pred"])).values
    boots = []
    for _ in range(500):
        i = rng.integers(0, len(test), len(test))
        boots.append(ratio[i].sum() / pratio[i].sum())
    lo, mid, hi = np.percentile(boots, [5, 50, 95])
    raw_total = score["at_risk_usd"].sum()
    # The 2025->2026 holdout showed the model over-predicts unspent dollars as the deadline nears
    # (spending accelerates). We carry that measured drift into the forecast as a correction factor.
    score["at_risk_usd_corrected"] = score["at_risk_usd"] * mid
    total = raw_total * mid

    # per-project explanations: LightGBM's exact TreeSHAP contributions (log-odds space)
    contrib = gbm2.predict(Xs, pred_contrib=True)
    names = list(Xs.columns)
    top = []
    for row in contrib[:, :-1]:
        idx = np.argsort(row)[:3]  # most negative = pushes toward stalling
        top.append([[names[i], round(float(row[i]), 3)] for i in idx if row[i] < 0])
    score["drivers"] = [json.dumps(t) for t in top]
    gbm2.save_model(str(OUT / "stall_radar_lgbm.txt"))
    score.to_parquet(OUT / "scored.parquet")
    summary = {
        "evaluation": rows,
        "calibration": calib.round(4).to_dict("records"),
        "slices": slices.to_dict("records"),
        "importance": imp.head(20).to_dict(),
        "text_terms_train_only": words,
        "text_terms_production": words2,
        "national": {
            "open_projects": int(len(score)), "open_gap_usd": float(score["gap"].sum()),
            "at_risk_usd_model": float(raw_total), "drift_correction": float(mid),
            "at_risk_usd": float(total), "at_risk_90ci_usd": [float(raw_total * lo), float(raw_total * hi)],
            "recipients_with_open_projects": int(score["recipient_id"].nunique()),
        },
        "n_train": int(len(train)), "n_test": int(len(test)),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print("\nimportance:\n", imp.head(12).to_string())
    print("\ncalibration:\n", calib.round(3).to_string(index=False))
    print("\nslices:\n", slices.to_string(index=False))
    print(f"\nNational: open gap ${score.gap.sum()/1e9:.2f}B, projected unspent at deadline ${total/1e9:.2f}B "
          f"(raw ${raw_total/1e9:.2f}B, drift x{mid:.3f}, 90% band ${raw_total*lo/1e9:.2f}B-${raw_total*hi/1e9:.2f}B)")
    print("stall words:", words2["stall"][:15])
    print("spend words:", words2["spend"][:15])


if __name__ == "__main__":
    main()
