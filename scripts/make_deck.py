"""Build the DataNova 2026 presentation (PPTX) from the pipeline outputs and site screenshots."""
import json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAT = json.loads((ROOT / "web" / "data" / "national.json").read_text())
FIG = ROOT / "docs" / "deck"
FIG.mkdir(parents=True, exist_ok=True)
SHOTS = ROOT / "docs" / "shots"
OUT = ROOT / "web" / "StallRadar-DataNova2026.pptx"

INK, INK2, MUTED = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x52, 0x51, 0x4E), RGBColor(0x7A, 0x78, 0x73)
BLUE, RED, BG, CARD, LINE = RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xE3, 0x49, 0x48), RGBColor(0xF6, 0xF5, 0xF2), RGBColor(0xFC, 0xFC, 0xFB), RGBColor(0xDE, 0xDC, 0xD5)
B = lambda v: f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.0f}M"
n = NAT["national"]; ev = NAT["evaluation"]; best = ev[-1]

# ---------- figures ----------
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#dedcd5", "axes.labelcolor": "#52514e",
                     "xtick.color": "#7a7873", "ytick.color": "#52514e", "axes.spines.top": False, "axes.spines.right": False})


def hbar(rows, label, value, path, fmt=B, w=6.2, h=4.2):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    labs = [label(r) for r in rows][::-1]; vals = [value(r) for r in rows][::-1]
    ax.barh(labs, vals, color="#2a78d6", height=0.62)
    for i, v in enumerate(vals):
        ax.text(v, i, " " + fmt(v), va="center", fontsize=9.5, color="#0b0b0b")
    ax.set_xticks([]); ax.spines["bottom"].set_visible(False); ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(vals) * 1.18)
    fig.tight_layout(); fig.savefig(path, transparent=True); plt.close(fig)


hbar(NAT["by_state"][:12], lambda r: r["st"], lambda r: r["risk"], FIG / "states.png")
hbar([c for c in NAT["by_category"] if c["risk"] > 2e7], lambda r: r["label"], lambda r: r["risk"], FIG / "cats.png", w=6.2, h=3.4)
hbar(NAT["importance"][:8], lambda r: r["f"], lambda r: r["v"], FIG / "imp.png", fmt=lambda v: f"{v*100:.1f}%", w=6.2, h=3.4)

fig, ax = plt.subplots(figsize=(5, 4.2), dpi=200)
cal = NAT["calibration"]
ax.plot([0, 1], [0, 1], ls="--", color="#7a7873", lw=1)
ax.plot([c["pred"] for c in cal], [c["actual"] for c in cal], color="#2a78d6", lw=2, marker="o", ms=6, mec="white", mew=1.5)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.grid(color="#efeee9")
ax.set_xlabel("Predicted share of open balance spent (12 mo)"); ax.set_ylabel("Actual share spent")
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
fig.tight_layout(); fig.savefig(FIG / "calib.png", transparent=True); plt.close(fig)

# ---------- deck ----------
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide(title=None, kicker=None):
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill; bg.solid(); bg.fore_color.rgb = BG
    if kicker:
        text(s, kicker.upper(), 0.6, 0.45, 12, 0.3, 11, MUTED, bold=True)
    if title:
        text(s, title, 0.6, 0.72, 12.1, 1.0, 30, INK, bold=True)
    text(s, "Stall Radar  |  DataNova 2026 Global Data-thon  |  Open Innovation (DN-OP-01)", 0.6, 7.0, 9, 0.3, 9, MUTED)
    return s


def text(s, t, x, y, w, h, size=16, color=INK2, bold=False, align=PP_ALIGN.LEFT):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    lines = t if isinstance(t, list) else [t]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run(); r.text = line; r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
        p.alignment = align; p.space_after = Pt(6)
    return tb


def bullets(s, items, x, y, w, h, size=16):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        head, _, rest = it.partition(": ")
        if rest:
            r = p.add_run(); r.text = head + ": "; r.font.bold = True; r.font.size = Pt(size); r.font.color.rgb = INK
            r = p.add_run(); r.text = rest; r.font.size = Pt(size); r.font.color.rgb = INK2
        else:
            r = p.add_run(); r.text = it; r.font.size = Pt(size); r.font.color.rgb = INK2
        p.space_after = Pt(10)


def card(s, x, y, w, h, big, label, sub=None, color=INK):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = 0.06; sh.fill.solid(); sh.fill.fore_color.rgb = CARD; sh.line.color.rgb = LINE
    text(s, big, x + 0.25, y + 0.2, w - 0.5, 0.8, 34, color, bold=True)
    text(s, label, x + 0.25, y + 1.0, w - 0.5, 0.6, 14, INK2)
    if sub:
        text(s, sub, x + 0.25, y + h - 0.55, w - 0.5, 0.4, 11, MUTED)


def pic(s, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return s.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


# 1 title
s = slide()
text(s, "STALL RADAR", 0.6, 1.2, 12, 0.5, 14, RED, bold=True)
text(s, f"{B(n['at_risk_usd'])} of pandemic relief is on track to go unspent. We found which projects.", 0.6, 1.7, 11.5, 2.0, 36, INK, bold=True)
text(s, "An out-of-time validated model that scores every open ARPA project before the Dec 31, 2026 spending deadline, and a free closeout worklist for every government.", 0.6, 3.75, 11, 1.0, 18, INK2)
text(s, ["Live demo: stall-radar-bice.vercel.app", "Code (MIT): github.com/Mattbusel/stall-radar", "Matthew Busel  |  Track: Operations Research and Decision Intelligence  |  Problem: DN-OP-01 Open Innovation"], 0.6, 5.2, 12, 1.4, 14, MUTED)

# 2 problem
s = slide("A hard deadline, $26 billion still open, and no way to see what is stuck", "Problem statement")
card(s, 0.6, 1.9, 3.9, 2.0, B(n["open_gap_usd"]), "obligated but not spent on Mar 31, 2026", f"{n['open_projects']:,} projects, {n['recipients_with_open_projects']:,} governments")
card(s, 4.7, 1.9, 3.9, 2.0, "Dec 31, 2026", "last day to spend ARPA SLFRF money", "unspent funds return to Treasury", RED)
card(s, 8.8, 1.9, 3.9, 2.0, "9 months", "left at the latest data point", "the reports lag the spending by a quarter")
bullets(s, [
    "Who has the problem: city and county finance directors, state ARPA offices, auditors and the Treasury itself.",
    "Why it matters: money left unspent is lost to the communities it was granted to (water systems, broadband, housing, health).",
    "Why it is hard: thousands of projects per state, each at a different stage; the public reports are 190,000-row spreadsheets released quarterly.",
    "What they need: a ranked list of the projects most likely to miss, with a reason, early enough to act (reallocate, accelerate, or close out).",
], 0.6, 4.25, 12.1, 2.6, 15)

# 3 data
s = slide("Data: seven Treasury releases, followed project by project", "Data and methodology")
bullets(s, [
    "Source: U.S. Treasury SLFRF Project and Expenditure public data, releases with data through Mar 2023, Dec 2023, Mar 2024, Dec 2024, Mar 2025, Dec 2025, Mar 2026.",
    "Scale: about 900,000 project-snapshot rows; ~190,000 projects at ~31,000 governments in the latest release.",
    "Linking: Treasury project IDs are stable, so every project is tracked across snapshots (99.99% overlap between consecutive March releases).",
    "Unit of prediction: a project with more than $1,000 obligated but unspent at a snapshot.",
    "Label: share of that unspent balance actually spent over the next 12 months. Projects with no fresh follow-up report are excluded, not counted as stalls.",
    "Privacy: all inputs are public, government-level records. No personal data.",
], 0.6, 1.9, 7.2, 5, 13)
pic(s, FIG / "cats.png", 7.9, 2.0, w=5.0)
text(s, "Projected unspent at deadline by Treasury category", 7.9, 5.6, 5, 0.4, 11, MUTED)

# 4 method
s = slide("Method: pace, position, context and text, in one gradient-boosted model", "Solution and methodology")
steps = [("1  Ingest", "7 xlsx releases to parquet; header and schema drift handled"),
         ("2  Panels", "features at T0, outcome at T1: train 2024>2025, test 2025>2026, score 2026"),
         ("3  Text model", "TF-IDF (1-2 grams) ridge on name + description, stacked out-of-fold"),
         ("4  LightGBM", "cross-entropy on spent share, dollar-weighted; 29 features"),
         ("5  Explain", "exact TreeSHAP per project, mapped to plain-language reasons"),
         ("6  Forecast", "12-month share to 9 months via constant hazard; drift correction from holdout")]
for i, (h, b) in enumerate(steps):
    x = 0.6 + (i % 3) * 4.15; y = 1.95 + (i // 3) * 1.65
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(3.95), Inches(1.45))
    sh.adjustments[0] = 0.08; sh.fill.solid(); sh.fill.fore_color.rgb = CARD; sh.line.color.rgb = LINE
    text(s, h, x + 0.2, y + 0.15, 3.6, 0.4, 16, BLUE, bold=True)
    text(s, b, x + 0.2, y + 0.6, 3.6, 0.8, 13, INK2)
bullets(s, [
    "Features: prior-year and prior-quarter spending pace, unspent balance, share spent, status and its change, late budget revisions, the government's overall pace, open-project count, category, capital flags, tier, type, state, text score.",
    "Stack: Python, pandas, pyarrow, LightGBM, scikit-learn; static web app (vanilla JS, hand-built SVG charts) on Vercel.",
], 0.6, 5.35, 12.1, 1.6, 14)

# 5 validation
s = slide("Validation: graded on a year the model never saw", "Results and validation")
rows = [["Model", "AUC", "AUC ($-weighted)", "Avg precision", "Brier"]] + [[e["model"], f"{e['auc_stall']:.3f}", f"{e['auc_stall_dollar_weighted']:.3f}", f"{e['ap_stall']:.3f}", f"{e['brier_stall']:.3f}"] for e in ev]
tbl = s.shapes.add_table(len(rows), 5, Inches(0.6), Inches(1.95), Inches(7.3), Inches(0.42 * len(rows))).table
for i, r in enumerate(rows):
    for j, v in enumerate(r):
        c = tbl.cell(i, j); c.text = v
        c.fill.solid(); c.fill.fore_color.rgb = RGBColor(0xEF, 0xEE, 0xE9) if i == 0 else CARD
        for p in c.text_frame.paragraphs:
            for run in p.runs:
                run.font.size = Pt(12); run.font.color.rgb = INK; run.font.bold = (i == 0 or i == len(rows) - 1)
            if j: p.alignment = PP_ALIGN.RIGHT
tbl.columns[0].width = Inches(3.1)
for j in range(1, 5): tbl.columns[j].width = Inches(1.05)
bullets(s, [
    f"Fit on {NAT['n_train']:,} projects (2024 to 2025 outcomes); graded on {NAT['n_test']:,} projects (2025 to 2026), after the obligation deadline.",
    "Beats last-year-pace persistence and the base rate on every ranking metric.",
    "Text adds little on top of the tree model; we report the ablation and keep it for explanations.",
], 0.6, 4.75, 7.3, 2.2, 13)
pic(s, FIG / "calib.png", 8.3, 1.85, w=4.5)
text(s, "Calibration by decile on the held-out year", 8.3, 5.7, 4.5, 0.4, 11, MUTED)

# 6 drift
s = slide("What we learned: the ranking held, the level drifted", "Data and analytical rigor")
card(s, 0.6, 1.9, 3.9, 2.0, B(best["predicted_unspent_B"] * 1e9), "model's predicted unspent on holdout")
card(s, 4.7, 1.9, 3.9, 2.0, B(best["actual_unspent_B"] * 1e9), "actual unspent, Mar 2026")
card(s, 8.8, 1.9, 3.9, 2.0, f"x{n['drift_correction']:.3f}", "measured drift factor", "bootstrap, 500 resamples", BLUE)
bullets(s, [
    "Spending accelerates as a deadline nears. The slowest-rated projects spent faster than history predicted (see calibration).",
    f"We carry the measured drift into the forecast: {B(n['at_risk_usd'])} projected unspent at Dec 31, 2026, 90% band {B(n['at_risk_90ci_usd'][0])} to {B(n['at_risk_90ci_usd'][1])}.",
    "If the last quarter accelerates harder than 2025 did, the true figure will be lower. The ranking is the product; the national total is a planning estimate.",
    "Slice checks: AUC holds from 0.63 (annual reporters) to 0.72 (administrative spending); weakest where data is sparsest.",
], 0.6, 4.25, 12.1, 2.6, 15)

# 7 findings
s = slide("Findings: where the stuck money is", "Impact")
pic(s, FIG / "states.png", 0.4, 1.7, w=6.3)
tp = NAT["top_projects"][:6]
text(s, "Largest rescue targets", 7.0, 1.8, 5.8, 0.4, 16, INK, bold=True)
bullets(s, [f"{p['n'][:52]}: {B(p['risk'])} projected unspent of {B(p['gap'])} open (stall risk {p['p']:.0%})" for p in tp], 7.0, 2.3, 5.9, 4.4, 12)

# 8 demo
s = slide("Working demo: a closeout worklist for every government", "Demonstration")
from PIL import Image
for i, (nm, cap) in enumerate([("home", "Overview: national forecast, search, top targets"), ("recipient", "Government view: ranked worklist with reasons, CSV export")]):
    im = Image.open(SHOTS / f"{nm}.png"); crop = im.crop((0, 0, im.width, int(im.width * 0.62))); p = FIG / f"{nm}_crop.png"; crop.save(p)
    pic(s, p, 0.6 + i * 6.25, 1.9, w=6.0)
    text(s, cap, 0.6 + i * 6.25, 5.75, 6, 0.4, 12, MUTED)
text(s, "stall-radar-bice.vercel.app  |  search any of 4,726 governments  |  23,295 scored projects  |  method page with every metric", 0.6, 6.25, 12, 0.4, 14, BLUE, bold=True)

# 9 impact & feasibility
s = slide("Impact and feasibility", "Impact and feasibility")
bullets(s, [
    "Who uses it: finance directors get a worklist in one search; state ARPA offices see every subrecipient; auditors and Treasury get a risk-ranked sample.",
    "What it changes: staff time goes to the few projects that hold most of the at-risk money. In the holdout, the top 10% of projects by predicted stuck dollars held 81% of the stuck dollars.",
    "Cost to run: zero. Public data, a laptop-sized pipeline (under 2 minutes end to end after download), a static site.",
    "Scales and repeats: re-run when Treasury posts the next release; the same panel design works for any grant program with a spending deadline (IIJA, CHIPS, E-Rate, BEAD).",
    "Next: monthly state-portal data for faster pace signals, and survival models that use the deadline explicitly.",
], 0.6, 1.9, 12.1, 4.8, 17)

# 10 responsible AI
s = slide("Responsible use", "Responsible AI")
bullets(s, [
    "A flag is a reason to check, never a finding of waste or non-compliance. Some balances are spent but not yet reported.",
    "Every prediction ships with its top reasons (exact TreeSHAP), so a person can disagree with it.",
    "State is a strong feature: a government is partly judged by its neighbors' track record. The reason tags make that visible when it drives a score.",
    "Annual (Tier 5) reporters are measured less precisely; their slice AUC is shown, not averaged away.",
    "Only public, government-level data. No people are scored. Open code and data so anyone can audit the model.",
], 0.6, 1.9, 12.1, 4.8, 17)

# 11 team
s = slide("Team and links", "Team contributions")
bullets(s, [
    "Matthew Busel (solo): problem framing, data pipeline, feature design, modeling and validation, web app, deck and video.",
    "Tools used while building: Claude Code as a coding assistant.",
    "Demo: stall-radar-bice.vercel.app",
    "Code and full reproduction steps (MIT): github.com/Mattbusel/stall-radar",
    "Data: U.S. Department of the Treasury, SLFRF Project and Expenditure public data.",
], 0.6, 1.9, 12.1, 4.6, 18)

prs.save(OUT)
print("wrote", OUT, OUT.stat().st_size)
