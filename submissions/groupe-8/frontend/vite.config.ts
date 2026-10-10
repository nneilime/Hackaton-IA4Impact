import { mkdirSync, writeFileSync } from 'node:fs';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

/** Dev only: POST a PNG data URL to /__shot?name=x to save it under SHOT_DIR (default .shots/). */
function devShot(): Plugin {
  return {
    name: 'dev-shot',
    apply: 'serve',
    configureServer(server) {
      const dir = process.env.SHOT_DIR ?? '.shots';
      mkdirSync(dir, { recursive: true });
      server.middlewares.use('/__shot', (req, res) => {
        const name = new URL(req.url ?? '', 'http://x').searchParams.get('name')?.replace(/[^\w-]/g, '') || 'shot';
        let body = '';
        req.on('data', (c) => (body += c));
        req.on('end', () => {
          writeFileSync(`${dir}/${name}.png`, Buffer.from(body.replace(/^data:image\/png;base64,/, ''), 'base64'));
          res.end('ok');
        });
      });
      // Dev only, for headless screenshots (firefox --headless --screenshot captures on the page's load event):
      // /__frame?ms=12000&tab=Équipes&scroll=.roster&q=%3Fmode%3Dreplay shows the app in an iframe, clicks a side-panel
      // tab 2.5 s before the end (then scrolls `scroll` into view), and keeps the load event pending for `ms` through a
      // held script (/__hold).
      server.middlewares.use('/__hold', (req, res) => {
        const ms = Number(new URL(req.url ?? '', 'http://x').searchParams.get('ms') ?? 8000);
        setTimeout(() => {
          res.setHeader('Content-Type', 'application/javascript');
          res.end('// held');
        }, ms);
      });
      server.middlewares.use('/__frame', (req, res) => {
        const q = new URL(req.url ?? '', 'http://x').searchParams;
        const ms = Number(q.get('ms') ?? 8000);
        const tab = JSON.stringify(q.get('tab') ?? '');
        const scroll = JSON.stringify(q.get('scroll') ?? '');
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.end(
          `<!doctype html><html><body style="margin:0"><iframe id="f" src="/${q.get('q') ?? ''}" style="border:0;width:100vw;height:100vh"></iframe>` +
            `<script>setTimeout(() => { const d = document.getElementById('f').contentDocument; const b = [...d.querySelectorAll('[role=tab]')].find((x) => x.textContent.trim().startsWith(${tab})); if (b && ${tab}) b.click(); setTimeout(() => { if (${scroll}) d.querySelector(${scroll})?.scrollIntoView(); }, 800); }, ${Math.max(0, ms - 2500)});</script>` +
            `<script src="/__hold?ms=${ms}"></script></body></html>`,
        );
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), devShot()],
  server: { port: 5173, open: false },
});
