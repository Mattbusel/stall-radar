# Stall Radar

**Which ARPA pandemic relief dollars will go unspent by the December 31, 2026 deadline?**

Live demo: **https://stall-radar-bice.vercel.app** · Deck: [StallRadar-DataNova2026.pptx](web/StallRadar-DataNova2026.pptx) · Built for the DataNova 2026 Global Data-thon (Open Innovation, DN-OP-01; track: Operations Research and Decision Intelligence).

The American Rescue Plan Act's State and Local Fiscal Recovery Funds (SLFRF) gave $350B to state, local, territorial and tribal governments. The money had to be obligated by December 31, 2024 and must be **spent by December 31, 2026**; anything left goes back to the U.S. Treasury. On March 31, 2026, **$26.3B** of obligated money was still unspent across **23,295 projects at 4,726 governments**.

Stall Radar follows every project through seven Treasury releases, learns which kinds of projects stall, validates that on a year it never saw, and scores the whole open book. Any government can search its name and get a ranked closeout worklist with the reasons behind each flag, as a CSV.

## Results

Out-of-time validation: fitted on Mar 2024 to Mar 2025 outcomes (37,222 projects), graded on Mar 2025 to Mar 2026 outcomes (37,842 projects). A project "stalls" if it spends less than half of its remaining balance in the next 12 months.

| Model | AUC | AUC, dollar-weighted | Avg precision | Brier | Unspent: predicted vs actual |
|---|---:|---:|---:|---:|---:|
| Base rate | 0.500 | 0.500 | 0.377 | 0.238 | $26.4B vs $26.9B |
| Persistence (last year's pace) | 0.584 | 0.687 | 0.433 | 0.400 | $40.4B vs $26.9B |
| Text only (TF-IDF ridge) | 0.594 | 0.619 | 0.466 | 0.235 | $27.5B vs $26.9B |
| LightGBM, no text | 0.665 | 0.759 | 0.549 | 0.222 | $31.7B vs $26.9B |
| **LightGBM + text (Stall Radar)** | **0.665** | **0.754** | **0.545** | **0.223** | **$31.8B vs $26.9B** |

What we learned:

- The ranking holds out of time; the **level drifts**. Spending speeds up as a deadline nears, so the model over-predicted unspent dollars by 18% on the held-out year. The calibration curve shows it: the slowest-rated projects spent faster than history said.
- We carry that measured drift into the forecast as a correction factor (0.847, bootstrapped over held-out projects): **$12.1B projected unspent at the deadline, 90% band $11.7B to $12.5B**. If the final quarter accelerates harder than 2025 did, the true number will be lower. The ranking is the product; the national total is a planning estimate.
- Text barely moves the tree model (AUC +0.001, dollar-weighted -0.005). We keep it because it powers the per-project explanations, and we report the ablation.
- Half of the projected unspent money is in water, sewer and broadband infrastructure.

## How it works

```
pipeline/00_download.py   seven Treasury SLFRF xlsx releases (Mar 2023 ... Mar 2026)
pipeline/01_ingest.py     xlsx -> parquet; header-row and schema drift handled by content
pipeline/02_features.py   project panels: features at T0, outcome at T1
                            train  T-1=2023-03  T0=2024-03  T1=2025-03
                            test   T-1=2024-03  T0=2025-03  T1=2026-03   (out-of-time)
                            score  T-1=2025-03  T0=2026-03  (deadline Dec 31 2026)
pipeline/03_model.py      TF-IDF ridge (stacked out-of-fold) + LightGBM cross-entropy on spent share,
                          baselines, calibration, slices, TreeSHAP reasons, drift-corrected forecast
pipeline/04_export.py     static JSON for the site (one file per state)
scripts/make_deck.py      the PPTX deck
web/                      the static site (vanilla JS, hand-built SVG charts)
```

Features (all knowable at the snapshot date): prior-year and prior-quarter spending pace, unspent balance, share spent, completion status and its change, late budget revisions, the government's overall pace and open-project count, this project's share of the government's open money, Treasury expenditure category, capital flags and cost, tier, government type, state, and the text score.

Label: share of a project's unspent obligated balance spent over the next 12 months. Projects whose next report was not filed are dropped from training rather than counted as stalls. The 12-month forecast is converted to the 9 months left with a constant-hazard assumption: `share_by_deadline = 1 - (1 - share_12m) ** 0.75`.

## Reproduce

```sh
pip install -r requirements.txt
sh run_all.sh                     # about 2 minutes after the ~250 MB download
python -m http.server 4088 --directory web
```

`npm install && node scripts/shots.js` takes QA screenshots; `node scripts/record.js` records the demo video (headless Chrome + local Piper narration + ffmpeg).

## Responsible use

- Only public, government-level data. No people are scored.
- A flag is a reason to check, never a finding of waste or non-compliance. Some balances are spent but not yet reported.
- Every score ships with its top reasons (exact TreeSHAP contributions mapped to plain language).
- State is a strong feature, so a government is partly judged by its neighbors' record; the reason tags show when that drives a score.
- Annual (Tier 5) reporters are measured less precisely; slice metrics are published on the method page.

## Data

U.S. Department of the Treasury, SLFRF Project and Expenditure public data (home.treasury.gov, State and Local Fiscal Recovery Funds, Public Data). Releases with data through Mar 2023, Dec 2023, Mar 2024, Dec 2024, Mar 2025, Dec 2025 and Mar 2026.

## Team

Matthew Busel (solo): problem framing, data pipeline, modeling and validation, web app, deck and video. Built with Claude Code as a coding assistant.

MIT licensed.
