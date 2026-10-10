// Dev only (never in the build): full-page captures for visual review.
// window.__page('name') renders the DOM with html-to-image, composites the WebGL map,
// and POSTs the PNG to the dev server (/__shot, see vite.config.ts; needs SHOT_DIR).
type MapLike = {
  redraw(): void;
  getCanvas(): HTMLCanvasElement;
  getContainer(): HTMLElement;
  _controls: { _deck?: { redraw(r: string): void; canvas: HTMLCanvasElement } }[];
};

async function b64(url: string) {
  const a = new Uint8Array(await (await fetch(url)).arrayBuffer());
  let s = '';
  for (let i = 0; i < a.length; i += 0x8000) s += String.fromCharCode(...a.subarray(i, i + 0x8000));
  return btoa(s);
}

let fontCSS: string | null = null;
async function fonts() {
  fontCSS ??= [
    `@font-face{font-family:'Outfit Variable';font-weight:100 900;src:url(data:font/woff2;base64,${await b64('/node_modules/@fontsource-variable/outfit/files/outfit-latin-wght-normal.woff2')}) format('woff2-variations');}`,
    `@font-face{font-family:'Public Sans Variable';font-weight:100 900;src:url(data:font/woff2;base64,${await b64('/node_modules/@fontsource-variable/public-sans/files/public-sans-latin-wght-normal.woff2')}) format('woff2-variations');}`,
  ].join('\n');
  return fontCSS;
}

/** SVG paint from CSS classes is lost in the clone: copy it into attributes first,
 *  and give back a function that removes them (React does not manage these). */
function inlineSvgPaint() {
  const added: [Element, string][] = [];
  for (const el of document.querySelectorAll<SVGElement>('svg *')) {
    const cs = getComputedStyle(el);
    for (const p of ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-linejoin', 'paint-order', 'opacity', 'fill-opacity', 'font-size', 'font-weight', 'font-family', 'text-anchor']) {
      if (el.hasAttribute(p)) continue;
      el.setAttribute(p, cs.getPropertyValue(p));
      added.push([el, p]);
    }
  }
  return () => added.forEach(([el, p]) => el.removeAttribute(p));
}

async function page(name: string) {
  const { toCanvas } = await import(/* @vite-ignore */ '/node_modules/html-to-image/es/index.js' as string);
  const restore = inlineSvgPaint();
  const opts = { pixelRatio: 1, fontEmbedCSS: await fonts(), filter: (n: HTMLElement) => n.tagName !== 'CANVAS' };
  const m = (window as unknown as { __map: MapLike }).__map;
  const deck = m._controls.find((c) => c._deck)!._deck!;
  m.redraw();
  const base = m.getCanvas().toDataURL();
  deck.redraw('shot');
  const deckUrl = deck.canvas.toDataURL();
  const out: HTMLCanvasElement = await toCanvas(document.body, { ...opts, width: innerWidth, height: innerHeight });
  const g = out.getContext('2d')!;
  const wrap = m.getContainer().parentElement!;
  const r = wrap.getBoundingClientRect();
  const mr = m.getContainer().getBoundingClientRect();
  const load = (u: string) => new Promise<HTMLImageElement>((res) => {
    const i = new Image();
    i.onload = () => res(i);
    i.src = u;
  });
  g.drawImage(await load(base), mr.left, mr.top, mr.width, mr.height);
  g.drawImage(await load(deckUrl), mr.left, mr.top, mr.width, mr.height);
  const over: HTMLCanvasElement = await toCanvas(wrap, { ...opts, backgroundColor: 'transparent', style: { background: 'transparent', border: '0' } });
  g.drawImage(over, r.left, r.top);
  restore();
  await fetch(`/__shot?name=${encodeURIComponent(name)}`, { method: 'POST', body: out.toDataURL('image/png') });
  return [out.width, out.height];
}

/** One element only (header, band…) at a given pixel ratio. */
async function element(selector: string, name: string, pixelRatio = 1) {
  const { toPng } = await import(/* @vite-ignore */ '/node_modules/html-to-image/es/index.js' as string);
  const restore = inlineSvgPaint();
  const el = document.querySelector(selector) as HTMLElement;
  const png: string = await toPng(el, { pixelRatio, fontEmbedCSS: await fonts(), backgroundColor: getComputedStyle(document.body).backgroundColor });
  restore();
  await fetch(`/__shot?name=${encodeURIComponent(name)}`, { method: 'POST', body: png });
  return [el.offsetWidth, el.offsetHeight];
}

Object.assign(window, { __page: page, __element: element });
export {};
