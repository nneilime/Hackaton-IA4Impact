/* Champs du parcours achat, relevés dans le corpus le 10/10/2026.
   Les clés sont locales : le modèle ne fournit ni sélecteurs ni actions. */
(() => {
  const entryUrl = 'https://www.caisse-epargne.fr/midi-pyrenees/emprunter/demande-credit-immobilier/';
  const tunnelUrl = 'https://www.caisse-epargne.fr/souscrire/pret-immobilier/tunnel/recherche/etat';
  const fields = [];
  function field(key, page, label, kind = 'text', options = [], question) {
    fields.push({key, page, label, kind, options, ...(question ? {question} : {})});
  }
  field('avancement', 'recherche/etat', 'État de la recherche', 'card', ['Je commence à réfléchir', "J’ai repéré un bien", "J’ai fait une offre d’achat"]);
  field('bien', 'mon-projet/achat', "Qu’achetez-vous ?", 'card', ['Un appartement', 'Une maison']);
  field('etatBien', 'mon-projet/etat', "Quel est l’état du bien ?", 'card', ['Ancien', 'Neuf sur plan (VEFA)', 'Neuf construit']);
  field('dpe', 'mon-projet/note-dpe', 'Diagnostic de Performance Energétique (DPE)', 'choice', ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'Je ne sais pas']);
  fields.at(-1).unknownChoice = 'Je ne sais pas';
  field('usage', 'mon-projet/usage', 'Pour quel usage ?', 'choice', ['Résidence principale', 'Résidence secondaire', 'Investissement locatif']);
  field('villeBien', 'mon-projet/emplacement', 'Code postal ou ville', 'location');
  field('prix', 'mon-projet/prix', 'Prix du bien', 'amount');
  field('loyerAttendu', 'mon-projet/investissement-locatif', 'Loyer mensuel attendu de mon investissement', 'amount');
  field('honorairesAgence', 'mon-projet/honoraires-agence', "Honoraires d’agence à votre charge", 'amount');
  fields.at(-1).unknownChoice = 'Je ne sais pas / non concerné';
  field('fraisNotaire', 'mon-projet/frais-notaire', 'Frais de notaire', 'amount');
  fields.at(-1).unknownChoice = 'Je ne sais pas';
  field('travaux', 'mon-projet/travaux', 'Estimation des travaux', 'amount');
  fields.at(-1).zeroChoice = "Je n'ai pas de travaux";
  field('villeResidence', 'mon-projet/residence', 'Code postal ou ville', 'location');
  field('apport', 'mon-projet/apport-personnel', "Montant de l’apport personnel", 'amount');
  field('emprunteurs', 'emprunteurs/nombre', 'Réalisez-vous ce projet seul ou avec un co-emprunteur ?', 'choice', ['Seul', 'À deux']);
  field('logementActuel', 'emprunteurs/statut', 'Dans votre logement actuel vous êtes ?', 'choice', ['Propriétaire', 'Logé(e) à titre gratuit', 'Locataire']);
  const professionalCategories = {
    'Professionnel': ['Agriculteur', 'Artisan, commerçant', "Gérant, Chef d'entreprise", 'Profession libérale'],
    'Salarié du secteur privé': ['Cadre', 'Employé', 'Ouvrier', 'Autre (Profession intermédiaire)'],
    'Salarié du secteur public (fonctionnaire ou non titulaire)': ['Cadre de la fonction publique', 'Employés de la fonction publique', 'Autre (Profession intermédiaire de la fonction publique)'],
    'Salarié des entreprises ou établissements publics sous contrat de droit privé': ['Cadre entreprise ou établissement public', 'Employé entreprise ou établissement public'],
    'Sans activité': ['Sans emploi', 'Retraité', 'Retraité de la fonction publique']
  };
  for (const prefix of ['', 'co']) {
    const key = name => prefix ? 'co' + name[0].toUpperCase() + name.slice(1) : name;
    const suffix = prefix ? '-coemprunteur' : '';
    field(key('civilite'), 'emprunteurs/signaletique' + suffix, 'Civilité', 'choice', ['Madame', 'Monsieur']);
    field(key('prenom'), 'emprunteurs/signaletique' + suffix, prefix ? 'Son prénom' : 'Votre prénom');
    field(key('nom'), 'emprunteurs/signaletique' + suffix, prefix ? 'Son nom' : 'Votre nom');
    field(key('naissance'), 'emprunteurs/date-naissance' + suffix, prefix ? 'Sa date de naissance' : 'Votre date de naissance', 'date');
    field(key('situationFamiliale'), 'emprunteurs/date-naissance' + suffix, 'Votre situation familiale', 'choice', ['Marié(e)', 'Célibataire', 'Séparé ou en instance de séparation', 'Divorcé(e)', 'Pacsé(e)', 'Union libre', 'Veuf/Veuve']);
    field(key('residentFiscal'), 'emprunteurs/date-naissance' + suffix, prefix ? 'Vous confirmez que votre co-emprunteur est résident fiscal Français' : 'Vous êtes résident fiscal Français', 'boolean');
    field(key('categorieProfessionnelle'), 'mon-budget/profession' + suffix, 'Votre catégorie professionnelle', 'choice', Object.keys(professionalCategories));
    field(key('profession'), 'mon-budget/profession' + suffix, 'Votre profession / activité', 'choice', Object.values(professionalCategories).flat());
    field(key('contrat'), 'mon-budget/profession' + suffix, 'Type de contrat / statut', 'choice');
    field(key('debutActivite'), 'mon-budget/profession' + suffix, "Date de début d'activité", 'month');
    field(key('casden'), 'mon-budget/casden' + suffix, 'Êtes-vous sociétaire CASDEN ?', 'card', ['Oui', 'Non']);
    field(key('salaire'), 'mon-budget/salaire' + suffix, 'Salaire mensuel net avant impôt sur le revenu', 'amount');
    field(key('moisSalaire'), 'mon-budget/salaire' + suffix, 'Salaire versé sur :', 'choice', ['12 mois', '13 mois', '14 mois', '15 mois'], prefix ? 'Nombre de mois de versement du salaire du co-emprunteur (12, 13, 14 ou 15 mois)' : 'Nombre de mois de versement de votre salaire (12, 13, 14 ou 15 mois)');
  }
  field('personnesCharge', 'emprunteurs/personne-a-charges', 'Personnes à charge', 'choice', [
    'Aucune personne à charge', '1 personne à charge',
    ...Array.from({length: 6}, (_, index) => (index + 2) + ' personnes à charge'),
    '8 personnes et plus à charge'
  ]);
  field('autresRevenus', 'mon-budget/synthese-revenus', 'Percevez-vous d’autres revenus réguliers comme un loyer, une pension etc. ?', 'card', ['Oui', 'Non'], 'Autres revenus réguliers hors salaire (loyer, pension, etc.) : oui ou non');
  field('autresCharges', 'mon-budget/synthese-charges', 'Avez-vous d’autres charges régulières comme un crédit, une pension etc. ?', 'card', ['Oui', 'Non'], 'Autres charges régulières (crédit en cours, pension versée, etc.) : oui ou non');
  // Ces champs appartiennent à la fenêtre d'ajout, pas à l'écran Oui/Non.
  const chargeFields = [
    {key: 'chargeType', label: 'Type de charge', kind: 'choice', question: 'Type de la charge (libellé du menu du site)'},
    {key: 'chargeMensualite', label: 'Montant des mensualités', kind: 'amount', question: 'Montant mensuel de cette charge en euros'},
    {key: 'chargeDuree', label: 'Durée restante (mois)', kind: 'integer', question: 'Durée restante de cette charge en mois'}
  ].map(definition => ({...definition, page: 'mon-budget/synthese-charges', modal: 'autre-charge', options: []}));
  fields.push(...chargeFields);
  field('email', 'contact/coordonnees', 'E-mail');
  field('telephone', 'contact/coordonnees', 'Téléphone');

  // Ce repère reste disponible même sans modèle et se lit sans voir le formulaire.
  function missingPrompt(keys) {
    const requested = [...new Set(keys)].map(key => fields.find(definition => definition.key === key)).filter(Boolean);
    return requested.map(definition => {
      let label = (definition.question || definition.label).replace(/[\s:?.]+$/, '');
      if (definition.key === 'bien') label = 'Le type de bien à acheter';
      if (definition.key === 'villeBien') label = 'Code postal ou ville du bien à acheter';
      if (definition.key === 'villeResidence') label = 'Code postal ou ville de votre résidence actuelle';
      if (/^co[A-Z]/.test(definition.key)) label = 'Pour votre co-emprunteur : ' + label;
      const options = definition.kind === 'boolean' ? ['Oui', 'Non'] : definition.options;
      let detail = options.length ? ' Choix possibles : ' + options.join(', ') + '.' : '';
      if (definition.kind === 'amount') detail = ' Indiquez le montant en euros.';
      if (definition.kind === 'amount' && definition.unknownChoice) detail += ' Si vous ne le connaissez pas, vous pouvez choisir « ' + definition.unknownChoice + ' ».';
      if (definition.zeroChoice) detail += ' Si vous ne prévoyez pas de travaux, vous pouvez dire « je n’ai pas de travaux ».';
      if (definition.kind === 'date') detail = ' Indiquez le jour, le mois et l’année.';
      if (definition.kind === 'month') detail = ' Indiquez le mois et l’année.';
      return 'Il me manque cette information : ' + label + '.' + detail;
    }).join('\n');
  }

  function entryFor(proposal) {
    const stage = CE.normalize(proposal.champs.avancement);
    if (stage === CE.normalize("J’ai repéré un bien")) return tunnelUrl.replace('recherche/etat', 'mon-projet/achat?recherche=2');
    if (stage === CE.normalize("J’ai fait une offre d’achat")) return tunnelUrl.replace('recherche/etat', 'mon-projet/achat?recherche=3');
    return tunnelUrl;
  }
  function allowed(raw) {
    try {
      const url = new URL(raw);
      return url.protocol === 'https:' && url.hostname === 'www.caisse-epargne.fr' &&
        url.pathname.startsWith('/souscrire/pret-immobilier/tunnel/');
    } catch { return false; }
  }
  function normalizeDpe(value) {
    if (typeof value !== 'string') return value;
    const text = value.trim();
    if (/^(?:inconnu|non connu|je ne sais pas)$/i.test(text)) return 'Je ne sais pas';
    const match = text.match(/^(?:(?:DPE|DPO)\s*[:=]?\s*)?(?:(?:classe|note|étiquette|etiquette)\s*(?:énergétique|energetique)?\s*[:=]?\s*)?([A-G])$/i);
    return match ? match[1].toUpperCase() : value;
  }
  function normalizeDependants(value) {
    if (value == null) return value;
    if (typeof value === 'number' && (!Number.isSafeInteger(value) || value < 0)) return value;
    if (/^\s*-/.test(String(value))) return value;
    const text = CE.normalize(value);
    const words = ['zero', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit'];
    if (['aucun', 'aucune', 'aucune personne a charge', 'pas de personne a charge'].includes(text)) return 'Aucune personne à charge';
    if (/^8\s*\+$/.test(String(value).trim()) || text === '8 et plus' || text === '8 personnes et plus a charge') return '8 personnes et plus à charge';
    const match = text.match(/^(\d+|zero|un|une|deux|trois|quatre|cinq|six|sept|huit)(?: personnes? a charge)?$/);
    if (!match || typeof value === 'boolean') return value;
    const count = match[1] === 'une' ? 1 : words.includes(match[1]) ? words.indexOf(match[1]) : Number(match[1]);
    if (!Number.isSafeInteger(count) || count < 0) return value;
    if (count === 0) return 'Aucune personne à charge';
    if (count === 1) return '1 personne à charge';
    return count < 8 ? count + ' personnes à charge' : '8 personnes et plus à charge';
  }
  function normalizeSalaryMonths(value) {
    if (typeof value === 'number') return Number.isInteger(value) && value >= 12 && value <= 15 ? value + ' mois' : value;
    if (typeof value !== 'string') return value;
    const match = value.trim().match(/^(?:sur\s+)?(12|13|14|15)(?:\s+mois)?$/i);
    return match ? match[1] + ' mois' : value;
  }
  function normalizeValue(definition, value) {
    if (definition.kind === 'amount' && definition.unknownChoice && typeof value === 'string' &&
        ['je ne sais pas', CE.normalize(definition.unknownChoice),
          ...(CE.normalize(definition.unknownChoice).includes('non concerne') ? ['non concerne'] : [])].includes(CE.normalize(value))) return definition.unknownChoice;
    if (definition.key === 'dpe') return normalizeDpe(value);
    if (definition.key === 'personnesCharge') return normalizeDependants(value);
    if (['moisSalaire', 'coMoisSalaire'].includes(definition.key)) return normalizeSalaryMonths(value);
    if (definition.kind === 'boolean' && typeof value === 'string') {
      const text = CE.normalize(value);
      if (['oui', 'true', 'vrai'].includes(text)) return true;
      if (['non', 'false', 'faux'].includes(text)) return false;
    }
    if (definition.options?.includes('Oui') && definition.options.includes('Non') && typeof value === 'boolean') return value ? 'Oui' : 'Non';
    if (['amount', 'integer'].includes(definition.kind) && typeof value === 'string') {
      const text = value.trim().replace(/[\u00a0\u202f]/g, ' ');
      const suffix = definition.kind === 'amount' ? '(?:\\s*(?:€|euros?|EUR))?' : '';
      // Espaces par groupes de trois, décimales explicites : aucune estimation,
      // intervalle, notation scientifique ou expression n'est interprétée.
      const pattern = new RegExp('^(?:\\d+|\\d{1,3}(?: \\d{3})+)' +
        (definition.kind === 'amount' ? '(?:[.,]\\d{1,2})?' : '') + suffix + '$', 'i');
      if (pattern.test(text)) return Number(text.replace(/(?:€|euros?|EUR)$/i, '').trim().replace(/ /g, '').replace(',', '.'));
    }
    return value;
  }
  function validate(proposal) {
    if (!proposal || typeof proposal !== 'object' || Array.isArray(proposal) ||
        !proposal.champs || typeof proposal.champs !== 'object' || Array.isArray(proposal.champs)) {
      throw new Error('La fiche immobilière reçue doit contenir un objet « champs ». Vérifiez la réponse du workflow n8n.');
    }
    if (proposal.resume != null && (typeof proposal.resume !== 'string' || proposal.resume.length > 4000)) {
      throw new Error('Le résumé de la fiche immobilière doit être un texte de 4 000 caractères maximum.');
    }
    // Un intitulé vide ne doit pas empêcher le remplissage des données validées.
    const cleaned = {resume: proposal.resume?.trim() || 'Projet immobilier partiel', champs: {}};
    for (const definition of fields) {
      const raw = proposal.champs[definition.key];
      const value = normalizeValue(definition, raw);
      if (value == null) continue;
      if (definition.unknownChoice && value === definition.unknownChoice) {
        cleaned.champs[definition.key] = value;
        continue;
      }
      if (definition.kind === 'amount') {
        if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 100000000) throw new Error('Montant invalide : ' + definition.label);
      } else if (definition.kind === 'integer') {
        if (!Number.isSafeInteger(value) || value < 0 || value > 1200) throw new Error('Durée invalide : ' + definition.label);
      } else if (definition.kind === 'boolean') {
        if (typeof value !== 'boolean') throw new Error('Situation invalide : ' + definition.label);
      } else {
        if (typeof value !== 'string' || !value.trim() || value.length > 200) throw new Error('Champ invalide : ' + definition.label);
        if (definition.options.length && !definition.options.some(option => CE.normalize(option) === CE.normalize(value))) throw new Error('Choix invalide : ' + definition.label);
        if (definition.kind === 'month' && (!/^(0[1-9]|1[0-2])\/\d{4}$/.test(value) || Number(value.split('/')[1]) === 0)) throw new Error('Date de début d’activité attendue au format MM/AAAA.');
        if (definition.kind === 'date') {
          if (!/^\d{2}\/\d{2}\/\d{4}$/.test(value)) throw new Error('Date attendue au format JJ/MM/AAAA.');
          const [day, month, year] = value.split('/').map(Number);
          const date = new Date(Date.UTC(year, month - 1, day));
          if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new Error('Date invalide.');
        }
        if (definition.key === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) throw new Error('Adresse e-mail invalide.');
      }
      cleaned.champs[definition.key] = definition.options.length ? definition.options.find(option => CE.normalize(option) === CE.normalize(value)) : value;
    }
    for (const prefix of ['', 'co']) {
      const category = cleaned.champs[prefix ? 'coCategorieProfessionnelle' : 'categorieProfessionnelle'];
      const profession = cleaned.champs[prefix ? 'coProfession' : 'profession'];
      if (category && profession && !professionalCategories[category].includes(profession)) throw new Error('La profession ne correspond pas à la catégorie choisie.');
    }
    return cleaned;
  }
  globalThis.CECredit = {entryUrl, tunnelUrl, entryFor, fields, professionalCategories, allowed, validate, normalizeDpe, normalizeDependants, normalizeSalaryMonths, normalizeValue, missingPrompt};
  if (typeof module !== 'undefined') module.exports = globalThis.CECredit;
})();
