/* Mémoire de collecte : champs autorisés, réponses déclarées et report sur le site.
   Les extraits servent à rattacher chaque mise à jour à un message utilisateur. */
(() => {
  const complaintFields = {
    faits: 'Les faits et le problème rencontré', periode: 'La date ou période, si connue',
    montant: 'Le montant, si pertinent', demarches: 'Les démarches déjà effectuées',
    resultat: 'Le résultat souhaité', objet: 'Le motif de réclamation',
    canal: 'Le canal de réponse : mail ou téléphone', particulier: 'Votre situation : particulier ou professionnel',
    civilite: 'Votre civilité', prenom: 'Votre prénom', nom: 'Votre nom',
    email: 'Votre e-mail', telephone: 'Votre téléphone'
  };
  const fields = [
    ...Object.entries(complaintFields).map(([key, label]) => ({
      key: 'reclamation.' + key, label, type: key === 'particulier' ? 'boolean' : 'string'
    })),
    ...CECredit.fields.map(field => ({key: 'credit_immobilier.' + field.key, label: field.question || field.label,
      type: ['amount', 'integer'].includes(field.kind) ? 'number' : field.kind === 'boolean' ? 'boolean' : 'string'}))
  ];
  const byKey = new Map(fields.map(field => [field.key, field]));
  const empty = () => ({parcours: null, informations: []});
  function clean(state) {
    if (state == null) return empty();
    if (JSON.stringify(state).length > 30000 || !state || Array.isArray(state) || !Array.isArray(state.informations) || state.informations.length > fields.length ||
        ![null, 'reclamation', 'credit_immobilier'].includes(state.parcours)) throw new Error('Mémoire de collecte invalide.');
    const seen = new Set();
    const informations = state.informations.map(entry => {
      const field = byKey.get(entry?.champ);
      if (!field || seen.has(entry.champ) || !['renseigne', 'sur_le_site'].includes(entry.statut) ||
          typeof entry.source !== 'string' || !entry.source.trim() || entry.source.length > 2000) throw new Error('Information mémorisée invalide.');
      seen.add(entry.champ);
      const key = entry.champ.split('.')[1];
      const definition = entry.champ.startsWith('credit_immobilier.') ? CECredit.fields.find(item => item.key === key) :
        {key, kind: field.type === 'boolean' ? 'boolean' : 'text', options: []};
      let value = entry.statut === 'renseigne' ? CECredit.normalizeValue(definition, entry.valeur) : entry.valeur;
      const dedicatedUnknown = definition.unknownChoice && value === definition.unknownChoice;
      if (entry.statut === 'sur_le_site' ? value !== null :
          (!dedicatedUnknown && typeof value !== field.type) || (field.type === 'string' && (!value.trim() || value.length > 2000)) ||
          (!dedicatedUnknown && field.type === 'number' && (!Number.isFinite(value) || value < 0 || value > 100000000))) throw new Error('Valeur mémorisée invalide pour « ' + field.label + ' ». Précisez cette information dans votre prochain message.');
      if (entry.statut === 'renseigne') {
        if (entry.champ.startsWith('credit_immobilier.')) value = CECredit.validate({resume: 'Collecte', champs: {[key]: value}}).champs[key];
        const choices = {objet: CE.motifs, canal: ['Par mail', 'Par téléphone'], civilite: ['Madame', 'Monsieur']};
        if (entry.champ.startsWith('reclamation.') && choices[key] && !choices[key].includes(value)) throw new Error('Choix mémorisé invalide.');
        if (key === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) throw new Error('E-mail mémorisé invalide.');
      }
      return {champ: entry.champ, valeur: value, statut: entry.statut, source: entry.source};
    });
    return {parcours: state.parcours, informations};
  }
  function merge(previous, update, latestUserText, userTexts = [latestUserText]) {
    const current = clean(previous);
    if (update == null) return current; // Compatibilité avec le workflow précédent.
    const patch = clean(update);
    const entries = new Map(current.informations.map(entry => [entry.champ, entry]));
    for (const entry of patch.informations) {
      // Une absence ne supprime rien. Une correction exige un nouvel extrait déclaré.
      const texts = entries.has(entry.champ) ? [latestUserText] : userTexts;
      if (texts.some(text => text.includes(entry.source))) entries.set(entry.champ, entry);
    }
    return {parcours: patch.parcours ?? current.parcours, informations: [...entries.values()]};
  }
  function values(state, parcours) {
    return Object.fromEntries(clean(state).informations
      .filter(entry => entry.statut === 'renseigne' && entry.champ.startsWith(parcours + '.'))
      .map(entry => [entry.champ.split('.')[1], entry.valeur]));
  }
  function forDraft(state, parcours, proposed) {
    const result = {...proposed};
    for (const entry of clean(state).informations) {
      if (!entry.champ.startsWith(parcours + '.')) continue;
      const key = entry.champ.split('.')[1];
      if (entry.statut === 'sur_le_site') delete result[key];
      else result[key] = entry.valeur;
    }
    return result;
  }
  function questions(state, requested) {
    const known = new Set(clean(state).informations.map(entry => entry.champ));
    return [...new Set(requested)].filter(key => byKey.has(key) &&
      key.startsWith(state.parcours + '.') && !known.has(key));
  }
  globalThis.CECollection = {fields, empty, clean, merge, questions, values, forDraft, label: key => byKey.get(key)?.label};
})();
if (typeof module !== 'undefined') module.exports = globalThis.CECollection;
