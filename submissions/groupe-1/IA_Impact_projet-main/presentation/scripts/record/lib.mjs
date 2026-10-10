// Enregistreur de démos du vrai site, pour le diapo.
// - Chrome installé (playwright-core, channel "chrome"), headless, 1440 × 810 rendu en 2× (2880 × 1620) :
//   le diapo zoome jusqu'à ×2,5 dans la vidéo, il faut de la définition en réserve pour que ça reste net.
// - Une souris dessinée dans la page suit les vrais événements souris ; un clic laisse une onde rouge.
// - Les images viennent du screencast CDP (JPEG haute qualité, horodatées), recollées en mp4 30 i/s par ffmpeg.
// - `cam(zoom, x, y)` note un plan de caméra à l'instant présent ; le diapo zoome la vidéo en suivant ces plans.
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const VW = 1440, VH = 810;
const OUT = path.resolve(import.meta.dirname, "../../public/assets/videos");
const SITE = process.env.SITE ?? "http://localhost:5173/";

const CURSOR = `(() => {
  const css = document.createElement("style");
  css.textContent = \`
    #rec-cursor { position: fixed; left: 0; top: 0; width: 34px; height: 34px; z-index: 2147483647; pointer-events: none;
      transform: translate(-200px, -200px); filter: drop-shadow(0 3px 6px rgba(0,0,0,.35)); transform-origin: 5px 3px; transition: scale .12s; }
    #rec-cursor.down { scale: .82; }
    .rec-ripple { position: fixed; z-index: 2147483646; pointer-events: none; width: 20px; height: 20px; margin: -10px 0 0 -10px;
      border-radius: 50%; border: 4px solid #c90c0f; animation: rec-ripple .6s ease-out forwards; }
    @keyframes rec-ripple { to { transform: scale(4); opacity: 0; } }
    * { scrollbar-width: none; }\`;
  const c = document.createElement("div");
  c.id = "rec-cursor";
  c.innerHTML = '<svg viewBox="0 0 24 24" width="34" height="34"><path d="M4 2l15 11.5-6.6.9 3.9 7.4-3 1.5-3.9-7.5L4 20z" fill="#0f2149" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const mount = () => { document.documentElement.append(css, c); };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", mount); else mount();
  addEventListener("mousemove", (e) => (c.style.transform = \`translate(\${e.clientX - 5}px, \${e.clientY - 3}px)\`), true);
  addEventListener("mousedown", (e) => {
    c.classList.add("down");
    const r = document.createElement("div"); r.className = "rec-ripple";
    r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
    document.documentElement.append(r); setTimeout(() => r.remove(), 700);
  }, true);
  addEventListener("mouseup", () => c.classList.remove("down"), true);
})();`;

export async function record(name, script) {
  const dir = fs.mkdtempSync(path.join(process.env.TMPDIR ?? "/tmp", `rec-${name}-`));
  const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--use-angle=metal", "--enable-gpu", "--hide-scrollbars"] });
  const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 2, locale: "fr-FR" });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  await page.goto(SITE);
  await page.waitForTimeout(3500); // carte et tuiles chargées avant de filmer

  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  cdp.on("Page.screencastFrame", async (f) => {
    const file = path.join(dir, `${String(frames.length).padStart(5, "0")}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ file, t: f.metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: 2880, maxHeight: 1620, everyNthFrame: 1 });
  await page.mouse.move(VW * 0.62, VH * 0.55);
  while (!frames.length) await page.waitForTimeout(20);
  const t0 = frames[0].t;
  const cams = [];
  let mouse = { x: VW * 0.62, y: VH * 0.55 };

  const api = {
    page,
    wait: (ms) => page.waitForTimeout(ms),
    now: () => Date.now() / 1000 - t0,
    // Plan de caméra : zoom (1 = plein cadre) centré sur (x, y) en pixels CSS de la page
    cam(zoom, x = VW / 2, y = VH / 2, ease = 1.1) { cams.push({ t: +api.now().toFixed(2), z: zoom, x: +(x / VW).toFixed(4), y: +(y / VH).toFixed(4), e: ease }); },
    async center(locator) {
      const b = await locator.boundingBox();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height };
    },
    // Déplacement naturel : courbe légèrement arquée, accélère puis freine
    async move(x, y, ms = 750) {
      const from = { ...mouse }, steps = Math.max(12, Math.round(ms / 16));
      const bend = (Math.random() < 0.5 ? -1 : 1) * Math.min(80, Math.hypot(x - from.x, y - from.y) * 0.12);
      const nx = -(y - from.y), ny = x - from.x, nl = Math.hypot(nx, ny) || 1;
      for (let i = 1; i <= steps; i++) {
        const p = i / steps, e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2, arc = Math.sin(Math.PI * e) * bend;
        await page.mouse.move(from.x + (x - from.x) * e + (nx / nl) * arc, from.y + (y - from.y) * e + (ny / nl) * arc);
        await page.waitForTimeout(ms / steps);
      }
      mouse = { x, y };
    },
    async moveTo(locator, ms) { const c = await api.center(locator); await api.move(c.x, c.y, ms); return c; },
    async click(locator, { ms = 750, hold = 110 } = {}) {
      const c = await api.moveTo(locator, ms);
      await page.waitForTimeout(140);
      await page.mouse.down(); await page.waitForTimeout(hold); await page.mouse.up();
      return c;
    },
    async type(text, delay = 85) { for (const ch of text) { await page.keyboard.type(ch); await page.waitForTimeout(delay + Math.random() * 50); } },
    async drag(dx, dy, ms = 1600) {
      const from = { ...mouse };
      await page.mouse.down();
      const steps = Math.round(ms / 16);
      for (let i = 1; i <= steps; i++) {
        const p = i / steps, e = (1 - Math.cos(Math.PI * p)) / 2;
        await page.mouse.move(from.x + dx * e, from.y + dy * e);
        await page.waitForTimeout(16);
      }
      await page.mouse.up();
      mouse = { x: from.x + dx, y: from.y + dy };
    },
  };

  api.cam(1);
  await script(api);
  await page.waitForTimeout(600);
  await cdp.send("Page.stopScreencast");
  const end = Date.now() / 1000;
  await browser.close();

  // Images horodatées -> mp4 à cadence fixe
  const list = frames.map((f, i) => `file '${f.file}'\nduration ${((frames[i + 1]?.t ?? end) - f.t).toFixed(4)}`).join("\n") + `\nfile '${frames.at(-1).file}'\n`;
  fs.writeFileSync(path.join(dir, "list.txt"), list);
  fs.mkdirSync(OUT, { recursive: true });
  const mp4 = path.join(OUT, `${name}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(dir, "list.txt"),
    "-vf", "scale=2560:1440:flags=lanczos,fps=30", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]);
  fs.rmSync(dir, { recursive: true, force: true });
  const duration = +(end - t0).toFixed(2);
  fs.writeFileSync(path.join(OUT, `${name}.json`), JSON.stringify({ file: `assets/videos/${name}.mp4`, duration, cams }, null, 1));
  collect();
  console.log(`${name}: ${frames.length} images, ${duration} s, ${cams.length} plans -> ${mp4}`);
}

// src/data/videos.json : toutes les démos enregistrées, lues par les slides vidéo du diapo
export function collect() {
  const all = {};
  for (const f of fs.readdirSync(OUT).filter((f) => f.endsWith(".json")).sort()) all[f.replace(".json", "")] = JSON.parse(fs.readFileSync(path.join(OUT, f), "utf8"));
  fs.writeFileSync(path.resolve(OUT, "../../../src/data/videos.json"), JSON.stringify(all));
}
