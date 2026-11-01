// Screenshots of every view (used for QA and the deck): node scripts/shots.js [baseUrl]
import fs from "node:fs";
import puppeteer from "puppeteer-core";
const BASE = process.argv[2] || "http://127.0.0.1:4088/";
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
fs.mkdirSync("docs/shots", { recursive: true });
const b = await puppeteer.launch({ executablePath: CHROME, headless: "new", args: ["--no-first-run"] });
const p = await b.newPage();
const errs = []; p.on("pageerror", e => errs.push(e.message)); p.on("console", m => m.type() === "error" && errs.push(m.text()));
const views = [["home", "#/", 1440], ["recipient", "#/r/RCP-036010", 1440], ["state", "#/s/new-jersey", 1440], ["method", "#/method", 1440], ["data", "#/data", 1440], ["mobile", "#/", 390], ["recipient-mobile", "#/r/RCP-036010", 390]];
for (const [name, h, w] of views) {
  await p.setViewport({ width: w, height: 900, deviceScaleFactor: 1 });
  await p.goto(BASE + h, { waitUntil: "networkidle0" });
  await new Promise(r => setTimeout(r, 600));
  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  await p.screenshot({ path: `docs/shots/${name}.png`, fullPage: true });
  console.log(name, "scrollWidth", sw, "viewport", w);
}
for (const dark of [true]) {
  await p.setViewport({ width: 1440, height: 900 });
  await p.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
  await p.goto(BASE + "#/method", { waitUntil: "networkidle0" }); await new Promise(r => setTimeout(r, 500));
  await p.screenshot({ path: "docs/shots/method-dark.png", fullPage: false });
}
console.log("errors:", errs);
await b.close();
