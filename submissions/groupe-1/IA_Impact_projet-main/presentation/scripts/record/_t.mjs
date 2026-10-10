import { chromium } from "playwright-core";
const out = process.argv[2];
const b = await chromium.launch({ channel: "chrome", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 960, height: 540 } });
p.on("pageerror", (e) => console.log("ERR", e.message));
await p.goto("http://localhost:4321/");
for (const t of [1200, 1500, 1500, 1500]) { await p.waitForTimeout(t); await p.screenshot({ path: `${out}/i-${Date.now()}.jpg`, quality: 60, type: "jpeg" }); }
await p.keyboard.press("ArrowRight"); await p.waitForTimeout(700); await p.screenshot({ path: `${out}/j1.jpg`, quality: 60, type: "jpeg" });
await p.waitForTimeout(1500); await p.screenshot({ path: `${out}/j2.jpg`, quality: 60, type: "jpeg" });
await b.close();
