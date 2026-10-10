/* Libellés issus de la spécification du corpus, relevée le 10/10/2026. */
(() => {
  const motifs = [
  "Moyens de paiement",
  "Fonctionnement du compte courant (dont frais bancaires, services de banque à distance,…)",
  "Crédits",
  "Assurances des biens (auto, habitation, moyens de paiement, mobile...)",
  "Assurances des personnes (famille, santé, dépendance, obsèques...)",
  "Assurances vie",
  "Livrets, plans d'épargne, comptes à terme",
  "Placements financiers (compte titres, PEA, Parts sociales, OPC,…)",
  "Relation Clientèle (avec mon conseiller, mon agence,...)",
  "Engagements et valeurs de la banque",
  "Successions",
  "Coffres forts (en agence ou numérique)"
];
  const normalize = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const validate = draft => {
    if (!draft || !motifs.includes(draft.objet)) throw new Error("Choisissez un motif officiel.");
    if (typeof draft.message !== "string" || !draft.message.trim() || draft.message.length > 1000) throw new Error("Le message doit contenir entre 1 et 1 000 caractères.");
    if (!["Par mail", "Par téléphone"].includes(draft.canal)) throw new Error("Choisissez un canal de réponse.");
    if (typeof draft.particulier !== "boolean") throw new Error("Précisez si vous êtes particulier ou professionnel.");
    for (const key of ["prenom", "nom", "email", "telephone", "civilite"]) {
      if (draft[key] !== undefined && (typeof draft[key] !== "string" || draft[key].length > 200)) throw new Error("Coordonnées invalides : " + key);
    }
    if (draft.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.email)) throw new Error("Vérifiez votre adresse e-mail.");
    if (draft.civilite && !["Madame", "Monsieur"].includes(draft.civilite)) throw new Error("Civilité invalide.");
    return draft;
  };
  const allowed = raw => {
    try {
      const url = new URL(raw);
      return (url.protocol === "https:" && url.hostname === "www.caisse-epargne.fr" && url.pathname.startsWith("/formulaire/contact/") && url.searchParams.get("form") === "reclam") ||
        (url.protocol === "chrome-extension:" && url.pathname === "/demo.html");
    } catch { return false; }
  };
  const siteAllowed = raw => {
    try {
      const url = new URL(raw);
      return url.protocol === 'https:' && url.hostname === 'www.caisse-epargne.fr';
    } catch { return false; }
  };
  const webhook = 'https://clementpardon.app.n8n.cloud/webhook/ia-impact-modele-minimal';
  const api = {motifs, normalize, validate, allowed, siteAllowed, webhook};
  globalThis.CE = api;
  if (typeof module !== "undefined") module.exports = api;
})();
