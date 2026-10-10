// Lecture CSV (UTF-8, séparateur virgule, guillemets doubles) sans dépendance.
// Utilisable dans Node comme dans le navigateur.

export function lireCsv(texte) {
  if (texte.charCodeAt(0) === 0xfeff) texte = texte.slice(1);
  const lignes = [];
  let champ = '', ligne = [], dansGuillemets = false;
  for (let i = 0; i < texte.length; i++) {
    const c = texte[i];
    if (dansGuillemets) {
      if (c === '"') {
        if (texte[i + 1] === '"') { champ += '"'; i++; }
        else dansGuillemets = false;
      } else champ += c;
    } else if (c === '"') dansGuillemets = true;
    else if (c === ',') { ligne.push(champ); champ = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && texte[i + 1] === '\n') i++;
      ligne.push(champ); champ = '';
      if (ligne.length > 1 || ligne[0] !== '') lignes.push(ligne);
      ligne = [];
    } else champ += c;
  }
  if (champ !== '' || ligne.length) { ligne.push(champ); lignes.push(ligne); }
  const [entete, ...corps] = lignes;
  return corps.map((l) => Object.fromEntries(entete.map((k, j) => [k, l[j] ?? ''])));
}

export function ecrireCsv(lignes, colonnes, { sep = ',', entetes = colonnes } = {}) {
  const echapper = (v) => {
    const s = v == null ? '' : String(v);
    return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  return [entetes.map(echapper).join(sep), ...lignes.map((l) => colonnes.map((c) => echapper(l[c])).join(sep))].join('\n') + '\n';
}
