import json, sys
src, manifeste, sortie = sys.argv[1:4]
s = open(src).read()
m = json.load(open(manifeste))
d = s.index('export const EXTRAITS = ['); f = s.index('];', d) + 2
extraits = ',\n'.join("  { fichier: '%s', min: %d, max: %d, bbox: [%s] }" % (x['fichier'].replace('.pmtiles', '.txt'), x['min'], x['max'], ', '.join(str(v) for v in x['bbox'])) for x in m)
s = s[:d] + """// Copie en ligne : chaque fichier publié fait moins de 15 Mo, le fond est donc découpé par zoom et par zone.
export const EXTRAITS = [
""" + extraits + """
];

// L'hébergeur ne sert pas de fichiers binaires bruts : chaque morceau est publié en base64 (texte).
// Lecture par plages quand l'hébergeur les accepte (3 octets = 4 caractères) ; sinon le morceau est lu en entier, une fois.
const decoder64 = (texte) => { const b = atob(texte.trim()); const o = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; };
class SourceSouple {
  constructor(url) { this.url = url; this.entier = null; this.plages = false; }
  getKey() { return this.url; }
  async getBytes(offset, length, signal) {
    const decouper = (o, debut) => ({ data: o.slice(debut, debut + length).buffer });
    if (this.entier) return decouper(await this.entier, offset);
    const bloc = Math.floor(offset / 3), a = bloc * 4, b = Math.ceil((offset + length) / 3) * 4 - 1;
    const r = await fetch(this.url, { headers: { Range: `bytes=${a}-${b}` }, signal: this.plages ? signal : undefined });
    if (r.status === 206) { this.plages = true; return decouper(decoder64(await r.text()), offset - bloc * 3); }
    if (!r.ok) throw new Error(`fond indisponible (${r.status})`);
    this.entier = r.text().then(decoder64);
    this.entier.catch(() => (this.entier = null));
    return decouper(await this.entier, offset);
  }
}
const lonDe = (x, n) => (x / n) * 360 - 180;
const latDe = (y, n) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI;
const bornesTuile = (z, x, y) => { const n = 2 ** z; return [lonDe(x, n), latDe(y + 1, n), lonDe(x + 1, n), latDe(y, n)]; };
const croise = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];""" + s[f:]
ancien = """  const archives = EXTRAITS.map((x) => ({ ...x, pm: new PMTiles(BASE + x.fichier) }));
  maplibregl.addProtocol('assise-fond', async (params, abandon) => {
    const [z, x, y] = params.url.split('/').slice(-3).map(Number);
    const archive = archives.find((a) => z >= a.min && z <= a.max);
    const tuile = archive && (await archive.pm.getZxy(z, x, y, abandon.signal));
    // Hors de l'extrait : une erreur fait retomber MapLibre sur la tuile parente, au lieu d'un trou.
    if (!tuile || !tuile.data) throw new Error('hors extrait');
    return { data: new Uint8Array(tuile.data) };
  });"""
nouveau = """  const archives = EXTRAITS.map((x) => ({ ...x, pm: new PMTiles(new SourceSouple(BASE + x.fichier)) }));
  maplibregl.addProtocol('assise-fond', async (params, abandon) => {
    const [z, x, y] = params.url.split('/').slice(-3).map(Number);
    const t = bornesTuile(z, x, y);
    for (const a of archives) {
      if (z < a.min || z > a.max || !croise(t, a.bbox)) continue;
      const tuile = await a.pm.getZxy(z, x, y, abandon.signal);
      if (tuile && tuile.data) return { data: new Uint8Array(tuile.data) };
    }
    // Hors de l'extrait : une erreur fait retomber MapLibre sur la tuile parente, au lieu d'un trou.
    throw new Error('hors extrait');
  });
  maplibregl.addProtocol('assise-glyphes', async (params) => {
    const [pile, plage] = params.url.replace('assise-glyphes://', '').split('/').map(decodeURIComponent);
    const r = await fetch(BASE + `vendor/glyphes/${pile}/${plage}.txt`);
    if (!r.ok) throw new Error('glyphes indisponibles');
    return { data: decoder64(await r.text()).buffer };
  });"""
assert ancien in s
s = s.replace(ancien, nouveau)
open(sortie, 'w').write(s)
