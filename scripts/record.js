// Records the Stall Radar demo video for real: drives headless Chrome through the live site,
// narrates each scene with Piper (local, free TTS), and assembles an MP4 with ffmpeg.
//   node scripts/record.js [siteUrl]
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "..");
const SITE = process.argv[2] || "https://stall-radar-bice.vercel.app/";
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const VOICE = process.env.PIPER_MODEL || "C:/Users/Matthew/hackathons/tts/en_US-ryan-high.onnx";
const OUT = path.join(ROOT, "demo-out", new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19));
const FR = path.join(OUT, "frames");
fs.mkdirSync(FR, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const SCENES = [
  { k: "hook", say: "On December thirty first, twenty twenty six, any American Rescue Plan money a city, county or state has not spent goes back to the U.S. Treasury. On March thirty first, twenty six billion dollars was still unspent." , cap: 'On Dec 31, 2026, any American Rescue Plan money a city, county or state has not spent goes back to the U.S. Treasury. On Mar 31, $26 billion was still unspent.' },
  { k: "what", say: "Stall Radar follows every one of those projects through seven Treasury data releases, learns which ones stall, and forecasts about twelve billion dollars still unspent at the deadline." , cap: 'Stall Radar follows every one of those projects through seven Treasury data releases, learns which ones stall, and forecasts about $12 billion still unspent at the deadline.' },
  { k: "charts", say: "Half of that risk sits in water, sewer and broadband projects, and it is concentrated in a handful of states." },
  { k: "search", say: "A finance director just types the name of their government." },
  { k: "worklist", say: "They get a closeout worklist: every open project, ranked by the dollars likely to be left behind, with a stall probability and the top reasons the model flagged it, from exact tree SHAP values." , cap: 'They get a closeout worklist: every open project, ranked by the dollars likely to be left behind, with a stall probability and the top reasons the model flagged it, from exact TreeSHAP values.' },
  { k: "csv", say: "One click exports it as a spreadsheet for the Monday staff meeting." },
  { k: "state", say: "State offices get the same view across every city and county they fund." },
  { k: "method", say: "Does it work? The model was trained on one year of outcomes and graded on the next year, which it never saw. It beats last year's pace and the base rate on every ranking metric, with a dollar weighted AUC of zero point seven five." , cap: "Does it work? The model was trained on one year of outcomes and graded on the next year, which it never saw. It beats last year's pace and the base rate on every ranking metric, with a dollar-weighted AUC of 0.75." },
  { k: "drift", say: "We also found where it was wrong. Spending speeds up near a deadline, so the model over predicted unspent money by eighteen percent. We measured that drift and corrected the forecast, and we publish both." , cap: 'We also found where it was wrong. Spending speeds up near a deadline, so the model over-predicted unspent money by 18%. We measured that drift and corrected the forecast, and we publish both.' },
  { k: "outro", say: "Stall Radar. Public data, open code, and nine months left to use it. Search your government at stall radar dash bice dot vercel dot app." , cap: 'Stall Radar. Public data, open code, and nine months left to use it. Search your government at stall-radar-bice.vercel.app' },
];

function voice() {
  const dur = {};
  for (const s of SCENES) {
    const f = path.join(OUT, `${s.k}.wav`);
    const r = spawnSync("python", ["-m", "piper", "-m", VOICE, "-f", f, "--length-scale", "0.97", "--sentence-silence", "0.25"], { input: s.say, encoding: "utf8" });
    if (r.status !== 0) throw new Error("piper: " + r.stderr);
    dur[s.k] = Number(spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], { encoding: "utf8" }).stdout.trim());
  }
  return dur;
}

const CAP_CSS = `#cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);max-width:1180px;background:rgba(11,11,11,.86);color:#fff;
  font:500 21px/1.35 Inter,system-ui,sans-serif;padding:14px 22px;border-radius:12px;z-index:99;text-align:center;pointer-events:none}
  #cursor{position:fixed;width:22px;height:22px;border-radius:50%;background:rgba(227,73,72,.35);border:2px solid #e34948;z-index:100;pointer-events:none;transform:translate(-50%,-50%);transition:left .5s,top .5s}`;

async function main() {
  const dur = voice();
  console.log("narration seconds", Object.values(dur).reduce((a, b) => a + b, 0).toFixed(1));
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new", defaultViewport: { width: 1536, height: 864, deviceScaleFactor: 1.25 }, args: ["--window-size=1920,1080", "--no-first-run", "--lang=en-US", "--force-color-profile=srgb"] });
  const page = await browser.newPage();
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await page.goto(SITE, { waitUntil: "networkidle0" });
  const prep = async () => page.evaluate(css => { if (!document.getElementById("cap")) { const st = document.createElement("style"); st.textContent = css; document.head.append(st);
    const c = document.createElement("div"); c.id = "cap"; document.body.append(c); const k = document.createElement("div"); k.id = "cursor"; k.style.left = "768px"; k.style.top = "432px"; document.body.append(k); } }, CAP_CSS);
  await prep();
  const caption = t => page.evaluate(t => { const c = document.getElementById("cap"); c.textContent = t; c.style.display = t ? "block" : "none"; }, t);
  const pointAt = async sel => { const b = await page.evaluate(s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel); if (b) await page.evaluate(b => { const k = document.getElementById("cursor"); k.style.left = b.x + "px"; k.style.top = b.y + "px"; }, b); await sleep(600); };
  const scroll = async (y, ms = 1200) => { await page.evaluate((y, ms) => new Promise(res => { const s = scrollY, t0 = performance.now(), tgt = y; const step = n => { const p = Math.min(1, (n - t0) / ms); scrollTo(0, s + (tgt - s) * (p < .5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2)); p < 1 ? requestAnimationFrame(step) : res(); }; requestAnimationFrame(step); }), y, ms); };
  const scrollTo_ = async (sel, off = 120) => { const y = await page.evaluate((s, off) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top + scrollY - off : scrollY; }, sel, off); await scroll(y); };
  const go = async hash => { await page.evaluate(h => location.hash = h, hash); await sleep(1200); await prep(); };

  // screencast
  const cdp = await page.createCDPSession();
  const frames = []; let n = 0;
  cdp.on("Page.screencastFrame", async f => { const file = path.join(FR, `${String(n++).padStart(6, "0")}.jpg`); fs.writeFileSync(file, Buffer.from(f.data, "base64")); frames.push({ file, ts: f.metadata.timestamp }); cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {}); });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 88, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  // keep frames flowing even when nothing moves
  await page.evaluate(() => { const d = document.createElement("div"); d.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;z-index:101"; document.body.append(d); let i = 0; setInterval(() => d.style.background = (i++ % 2) ? "rgba(0,0,0,.01)" : "rgba(0,0,0,.02)", 50); });
  await sleep(500);

  const scenes = [];
  const scene = async (k, fn) => { const t = Date.now() / 1000; const sc = SCENES.find(s => s.k === k); await caption(sc.cap || sc.say); const end = t + dur[k] + 0.45; await fn().catch(e => console.log("scene", k, e.message)); while (Date.now() / 1000 < end) await sleep(100); scenes.push({ k, start: t, end: Date.now() / 1000 }); };

  await scene("hook", async () => { await sleep(1500); await pointAt(".stat .v"); });
  await scene("what", async () => { await pointAt(".v.risk"); await sleep(1500); await scrollTo_(".grid.g3", 260); });
  await scene("charts", async () => { await scrollTo_("#cs", 220); await pointAt("#cc"); await sleep(1500); await pointAt("#cs"); });
  await scene("search", async () => { await scroll(0, 900); await pointAt("#q"); await page.click("#q"); await page.type("#q", "state of georgia", { delay: 110 }); await sleep(900); await pointAt("#sugg a"); });
  await scene("worklist", async () => { await page.click("#sugg a"); await sleep(1500); await prep(); await pointAt(".v.risk"); await sleep(2500); await scrollTo_(".tbl", 160); await pointAt(".why span"); await sleep(1500); await page.evaluate(() => document.querySelector("details")?.setAttribute("open", "")); await sleep(1200); await scroll(await page.evaluate(() => scrollY + 500), 2500); });
  await scene("csv", async () => { await scroll(0, 800); await scrollTo_("#dl", 300); await pointAt("#dl"); });
  await scene("state", async () => { await go("#/s/new-jersey"); await pointAt("#cr"); await sleep(1500); await scrollTo_("#cr", 200); await sleep(1500); await scrollTo_(".tbl", 160); });
  await scene("method", async () => { await go("#/method"); await sleep(700); await scrollTo_(".tbl", 200); await pointAt(".best"); await sleep(2500); await scrollTo_("#cal", 240); await pointAt("#cal"); });
  await scene("drift", async () => { await scrollTo_("#cal", 240); await sleep(3500); const y = await page.evaluate(() => { const h = [...document.querySelectorAll("h2")].find(e => e.textContent.startsWith("The drift")); return h.getBoundingClientRect().top + scrollY - 140; }); await scroll(y, 1500); });
  await scene("outro", async () => { await go("#/"); await scroll(0, 600); await pointAt(".v.risk"); });

  await cdp.send("Page.stopScreencast"); await browser.close();

  // assemble video: frames with real timing, audio placed at scene starts
  frames.sort((a, b) => a.ts - b.ts);
  const t0 = scenes[0].start, tEnd = scenes.at(-1).end;
  const use = frames.filter(f => f.ts >= t0 - 0.05 && f.ts <= tEnd);
  const list = [];
  for (let i = 0; i < use.length; i++) { const b = i + 1 < use.length ? use[i + 1].ts : tEnd; list.push(`file '${use[i].file.replace(/\\/g, "/")}'`, `duration ${Math.max(0.001, b - use[i].ts).toFixed(4)}`); }
  list.push(`file '${use.at(-1).file.replace(/\\/g, "/")}'`);
  fs.writeFileSync(path.join(OUT, "frames.txt"), list.join("\n"));
  const args = ["-y", "-f", "concat", "-safe", "0", "-i", path.join(OUT, "frames.txt")];
  scenes.forEach(s => args.push("-i", path.join(OUT, `${s.k}.wav`)));
  const delays = scenes.map((s, i) => `[${i + 1}:a]adelay=${Math.round((s.start - t0) * 1000)}|${Math.round((s.start - t0) * 1000)}[a${i}]`).join(";");
  const mix = scenes.map((_, i) => `[a${i}]`).join("") + `amix=inputs=${scenes.length}:normalize=0,apad[aout]`;
  args.push("-filter_complex", `${delays};${mix};[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[vout]`,
    "-map", "[vout]", "-map", "[aout]", "-t", String((tEnd - t0).toFixed(2)), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", path.join(OUT, "stall-radar-demo.mp4"));
  const r = spawnSync("ffmpeg", args, { encoding: "utf8", maxBuffer: 1 << 26 });
  if (r.status !== 0) throw new Error("ffmpeg: " + r.stderr.slice(-2500));
  console.log("video", path.join(OUT, "stall-radar-demo.mp4"), "seconds", (tEnd - t0).toFixed(1), "frames", use.length);
}
main().catch(e => { console.error(e); process.exit(1); });
