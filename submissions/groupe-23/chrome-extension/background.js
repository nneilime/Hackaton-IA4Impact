/* Le service worker gère le réseau et le stockage privé de l'extension. */
importScripts('shared.js', 'mortgage-contract.js', 'collection.js');

function isAllowedSender(sender) {
  if (sender.id !== chrome.runtime.id || !sender.url) return false;
  if (sender.url.startsWith('chrome-extension:')) {
    return sender.url === chrome.runtime.getURL('demo.html');
  }
  return CE.allowed(sender.url) || CE.siteAllowed(sender.url);
}

function cleanDraft(draft) {
  if (!draft || typeof draft !== 'object' || Array.isArray(draft)) {
    throw new Error('Brouillon invalide.');
  }

  if (draft.parcours === 'credit_immobilier') return {...CECredit.validate(draft), parcours: 'credit_immobilier'};

  const cleaned = {};
  const allowedFields = ['objet', 'message', 'canal', 'particulier', 'civilite', 'prenom', 'nom', 'email', 'telephone'];
  for (const field of allowedFields) {
    const value = draft[field];
    if (value === undefined) continue;

    if (field === 'particulier') {
      if (typeof value !== 'boolean') throw new Error('Situation invalide.');
    } else {
      const maximumLength = field === 'message' ? 1000 : 200;
      if (typeof value !== 'string' || value.length > maximumLength) {
        throw new Error('Champ invalide.');
      }
    }
    cleaned[field] = value;
  }
  return cleaned;
}

chrome.runtime.onMessage.addListener((request, sender, respond) => {
  if (!isAllowedSender(sender) || request.type !== 'ce-draft') return;

  // Un onglet possède sa propre discussion, indépendante des autres demandes.
  const sessionKey = 'maya:' + (sender.tab?.id ?? 'demo');
  const loadSession = async () => (await chrome.storage.session.get(sessionKey))[sessionKey] || {};
  const saveSession = async patch => chrome.storage.session.set({[sessionKey]: {...await loadSession(), ...patch}});
  const operations = {
    connection: async () => ({configured: true}),
    chat: async () => {
      const session = await loadSession();
      const site = collectSiteFields(request.siteFields, sender.url, session);
      const contexte = mortgageContext(sender.url);
      const unknownField = CECredit.fields.find(field => field.page === contexte?.etape && field.unknownChoice);
      const choice = CE.normalize(request.messages?.at(-1)?.content).match(/^(?:(?:je prefere|je veux|je souhaite) )?(?:(?:choisir|selectionner) )?(je ne sais pas|non concerne|je ne sais pas non concerne)$/)?.[1];
      const explicitUnknownChoice = Boolean(unknownField && choice) &&
        ['je ne sais pas', CE.normalize(unknownField.unknownChoice), ...(CE.normalize(unknownField.unknownChoice).includes('non concerne') ? ['non concerne'] : [])].includes(choice);
      const result = await chatRequest(request.messages, site.collecte, contexte,
        {mergeCollection: true, unknownField, explicitUnknownChoice});
      await saveSession({siteValues: site.siteValues});
      await saveSession({collecte: result.collecte ?? site.collecte,
        messages: [...request.messages.map(({role, content}) => ({role, content})),
          {role: 'assistant', content: result.message}].slice(-20)});
      return result;
    },
    load: loadSession,
    explain: async () => {
      if (!CECredit.allowed(sender.url) || !Array.isArray(request.missing) || !request.missing.length) throw new Error('Étape invalide.');
      const page = new URL(sender.url).pathname.split('/tunnel/')[1]?.replace(/\/$/, '');
      const champs = [...new Set(request.missing)].map(key => {
        const field = CECredit.fields.find(field => field.key === key && field.page === page && !field.modal);
        if (!field) throw new Error('Champ invalide.');
        return {cle: 'credit_immobilier.' + field.key, question: field.question || field.label, choix: field.options, ...(field.unknownChoice ? {choix_inconnu: field.unknownChoice} : {})};
      });
      const session = await loadSession();
      const history = [...(session.messages || [])];
      if (history.at(-1)?.role === 'assistant') history.pop();
      const result = await chatRequest([...history.slice(-19), {role: 'user', content: 'Le formulaire attend les informations indiquées dans contexte_interface. Poursuis notre échange à cette étape.'}], session.collecte,
        {type: 'missing_fields', etape: page, champs});
      const messages = [...(session.messages || [])];
      if (messages.at(-1)?.role === 'assistant') messages.pop();
      messages.push({role: 'assistant', content: result.message});
      // La reformulation ne modifie ni la collecte, ni le brouillon, ni la navigation.
      await saveSession({messages: messages.slice(-20)});
      return {message: result.message};
    },
    clear: async () => {
      await chrome.storage.session.remove(sessionKey);
      return {};
    },
    save: async () => {
      const draft = cleanDraft(request.draft);
      const patch = {draft, autoFill: draft.parcours === 'credit_immobilier' && request.autoFill === true};
      if (draft.parcours === 'credit_immobilier' && typeof request.message === 'string' && request.message.trim() && request.message.length <= 8000) {
        const session = await loadSession();
        const messages = [...(session.messages || [])];
        if (messages.at(-1)?.role === 'assistant') messages.pop();
        patch.messages = [...messages, {role: 'assistant', content: request.message}].slice(-20);
      }
      await saveSession(patch);
      return {};
    }
  };
  if (!Object.hasOwn(operations, request.action)) return;

  Promise.resolve()
    .then(operations[request.action])
    .then(result => respond({ok: true, ...result}))
    .catch(error => respond({
      ok: false,
      error: request.action === 'chat' ? error.message : 'Le brouillon de session est indisponible.'
    }));
  return true; // Garder le canal Chrome ouvert pendant le traitement asynchrone.
});

function mortgageContext(url) {
  if (!CECredit.allowed(url)) return undefined;
  const etape = new URL(url).pathname.split('/tunnel/')[1]?.replace(/\/$/, '');
  if (!etape) return undefined;
  return {type: 'formulaire', etape, champs: CECredit.fields.filter(field => field.page === etape && !field.modal)
    .map(field => ({cle: 'credit_immobilier.' + field.key, question: field.question || field.label, choix: field.options, ...(field.unknownChoice ? {choix_inconnu: field.unknownChoice} : {})}))};
}

function collectSiteFields(received, url, session) {
  const collecte = CECollection.clean(session.collecte);
  const siteValues = {...session.siteValues};
  if (!received || !received.champs || Array.isArray(received.champs)) return {collecte: session.collecte, siteValues};
  let allowed;
  if (received.parcours === 'credit_immobilier' && CECredit.allowed(url)) {
    const page = new URL(url).pathname.split('/tunnel/')[1]?.replace(/\/$/, '');
    allowed = CECredit.fields.filter(field => field.page === page).map(field => field.key);
  } else if (received.parcours === 'reclamation' && CE.allowed(url)) {
    allowed = ['faits', 'objet', 'canal', 'particulier', 'civilite', 'prenom', 'nom', 'email', 'telephone'];
  } else return {collecte: session.collecte, siteValues};
  const entries = new Map(collecte.informations.map(entry => [entry.champ, entry]));
  for (const key of allowed) {
    if (!Object.hasOwn(received.champs, key)) continue;
    const champ = received.parcours + '.' + key;
    // Une préférence explicite de saisie privée sur le site est respectée.
    if (entries.get(champ)?.statut === 'sur_le_site') continue;
    const valeur = received.champs[key];
    if (siteValues[champ] === valeur) continue;
    try {
      const entry = CECollection.clean({parcours: received.parcours, informations: [
        {champ, valeur, statut: 'renseigne', source: 'Champ saisi sur le formulaire : ' + key}
      ]}).informations[0];
      entries.set(champ, entry);
      siteValues[champ] = entry.valeur;
    } catch { /* Ignorer un champ invalide, sans bloquer la conversation. */ }
  }
  return {collecte: CECollection.clean({parcours: received.parcours, informations: [...entries.values()]}), siteValues};
}

function validateConversation(messages) {
  const validMessage = message => message &&
    ['user', 'assistant'].includes(message.role) &&
    typeof message.content === 'string' &&
    message.content.trim() && message.content.length <= 8000;

  if (!Array.isArray(messages) || messages.length < 1 || messages.length > 20 ||
      !messages.every(validMessage) || messages.at(-1).role !== 'user' ||
      messages.reduce((length, message) => length + message.content.length, 0) > 60000) {
    throw new Error('Conversation invalide.');
  }
}

function parseChatResponse(data) {
  if (!data || typeof data.message !== 'string' || !data.message.trim() || data.message.length > 8000) {
    throw new Error('Réponse n8n invalide : message attendu.');
  }

  if (data.fiche_credit_immobilier != null && data.fiche_reclamation != null) throw new Error('Réponse n8n ambiguë.');
  const fiche_credit_immobilier = data.fiche_credit_immobilier == null ? undefined :
    {...CECredit.validate(data.fiche_credit_immobilier), parcours: 'credit_immobilier'};
  let fiche_reclamation;
  if (data.fiche_reclamation != null) {
    const received = data.fiche_reclamation;
    const optionalFields = ['civilite', 'prenom', 'nom', 'email', 'telephone'];
    const proposal = {objet: received.objet, message: received.message, canal: received.canal, particulier: received.particulier};
    for (const field of optionalFields) {
      if (received[field] != null && received[field] !== '') proposal[field] = received[field];
    }
    fiche_reclamation = CE.validate(proposal);
  }

  const sources = Array.isArray(data.sources)
    ? data.sources.slice(0, 10)
      .filter(source => source && typeof source.url === 'string' && source.url.length < 2000 &&
        (source.titre === undefined || typeof source.titre === 'string'))
      .map(source => ({url: source.url, titre: source.titre?.slice(0, 200)}))
    : [];
  return {message: data.message, sources, fiche_reclamation, fiche_credit_immobilier,
    ...(data.collecte == null ? {} : {collecte: CECollection.clean(data.collecte)})};
}

async function requestChatData(messages, collecte, contexteInterface) {
  validateConversation(messages);
  let response;
  try {
    response = await fetch(CE.webhook, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        version: 1,
        ...(contexteInterface ? {contexte_interface: contexteInterface} : {}),
        ...(collecte == null ? {} : {collecte: CECollection.clean(collecte)}),
        messages: messages.map(({role, content}) => ({role, content}))
      }),
      credentials: 'omit',
      redirect: 'error',
      signal: AbortSignal.timeout(30000)
    });
  } catch {
    throw new Error('n8n est inaccessible ou ne répond pas sous 30 secondes. Réessayez depuis le panneau.');
  }
  const text = await response.text();
  if (text.length > 100000) throw new Error('Réponse n8n trop volumineuse.');
  if (!text.trim()) throw new Error('Le webhook n8n a renvoyé une réponse vide. Vérifiez le nœud Répondre à l’extension.');
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error('Le webhook n8n a renvoyé du texte ou du HTML au lieu de JSON. Vérifiez le workflow publié et son nœud de réponse.');
  }
  if (!response.ok) {
    const errors = {
      model_error: 'L’appel au modèle a échoué. Consultez l’exécution n8n.',
      model_incomplete: 'La réponse du modèle est inachevée. Consultez l’exécution n8n.',
      model_empty: 'Le modèle a renvoyé une réponse vide ou un refus.',
      model_format: 'Le modèle a renvoyé un format JSON inattendu.'
    };
    const code = data?.error?.code;
    throw new Error(Object.hasOwn(errors, code) ? errors[code] : 'Le webhook n8n a renvoyé une erreur HTTP. Consultez l’exécution n8n.');
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Le webhook n8n doit renvoyer un objet JSON, sans enveloppe texte ni tableau.');
  }
  return data;
}

// La correction est une seconde génération au même webhook, sans rejouer une
// mutation ni recopier la réponse fournisseur refusée dans le contexte.
function validationFeedback(data, {unknownField, explicitUnknownChoice = false} = {}, messages = [], collecte) {
  const issues = new Map();
  const describe = field => {
    const key = field.key.replace(/^credit_immobilier\./, '');
    const mortgage = field.key.startsWith('credit_immobilier.') ? CECredit.fields.find(item => item.key === key) : null;
    return {champ: field.key, question: field.label, type: field.type,
      ...(mortgage?.options.length ? {choix: mortgage.options} : {}),
      ...(mortgage?.unknownChoice ? {choix_inconnu: mortgage.unknownChoice} : {}),
      ...(mortgage?.kind === 'date' ? {format: 'JJ/MM/AAAA'} : {}),
      ...(mortgage?.kind === 'month' ? {format: 'MM/AAAA'} : {}),
      ...(field.type === 'number' ? {minimum: 0, maximum: mortgage?.kind === 'integer' ? 1200 : 100000000} : {})};
  };
  if (Array.isArray(data.collecte?.informations)) {
    const seen = new Set();
    for (const entry of data.collecte.informations.slice(0, CECollection.fields.length)) {
      const field = CECollection.fields.find(item => item.key === entry?.champ);
      if (!field) continue;
      try {
        if (seen.has(field.key)) throw new Error('Duplicate');
        seen.add(field.key);
        CECollection.clean({parcours: data.collecte.parcours, informations: [entry]});
      } catch { issues.set(field.key, describe(field)); }
    }
  }
  const fiche = data.fiche_credit_immobilier;
  if (fiche?.champs && typeof fiche.champs === 'object' && !Array.isArray(fiche.champs)) {
    for (const field of CECredit.fields) {
      if (fiche.champs[field.key] == null) continue;
      try { CECredit.validate({resume: 'Validation', champs: {[field.key]: fiche.champs[field.key]}}); }
      catch {
        const memoryField = CECollection.fields.find(item => item.key === 'credit_immobilier.' + field.key);
        issues.set(memoryField.key, describe(memoryField));
      }
    }
  }
  for (const key of missingDraftMemory(data, messages, collecte)) {
    const field = CECollection.fields.find(item => item.key === 'credit_immobilier.' + key);
    issues.set(field.key, {...describe(field), motif: 'Information de la fiche absente de la mémoire : ajoute une entrée de collecte avec un extrait exact de la déclaration utilisateur, même pour une étape future. Si elle n’a pas été déclarée, laisse le champ null.'});
  }
  if (explicitUnknownChoice && unknownField) {
    const field = CECollection.fields.find(item => item.key === 'credit_immobilier.' + unknownField.key);
    issues.set(field.key, {...describe(field), valeur_attendue: unknownField.unknownChoice,
      motif: 'Choix explicite du bouton de l’étape : une fiche exécutable est attendue, pas seulement un message de confirmation.'});
  }
  return {code: 'invalid_structured_response', champs: [...issues.values()]};
}

function missingDraftMemory(data, messages, collecte) {
  // Les anciens workflows sans collecte restent compatibles. Ne jamais fabriquer
  // une source à partir de la fiche : le modèle doit citer la déclaration exacte.
  if (data.collecte == null || !data.fiche_credit_immobilier?.champs) return [];
  try {
    const merged = CECollection.merge(collecte, data.collecte, messages.at(-1)?.content || '',
      messages.filter(message => message.role === 'user').map(message => message.content));
    const known = new Set(merged.informations.map(entry => entry.champ));
    const draft = CECredit.validate(data.fiche_credit_immobilier);
    return Object.keys(draft.champs).filter(key => !known.has('credit_immobilier.' + key));
  } catch { return []; } // Les autres erreurs sont traitées par la validation existante.
}

function validateModelData(data, messages, collecte, {mergeCollection = false, unknownField, explicitUnknownChoice = false} = {}) {
  const result = parseChatResponse(data);
  if (!mergeCollection) return result;
  if (missingDraftMemory(data, messages, collecte).length) {
    throw new Error('Les informations de la fiche doivent être mémorisées avec leur source.');
  }
  result.collecte = CECollection.merge(collecte, result.collecte, messages.at(-1).content,
    messages.filter(message => message.role === 'user').map(message => message.content));
  if (result.fiche_credit_immobilier) {
    const fiche = result.fiche_credit_immobilier;
    result.fiche_credit_immobilier = {...CECredit.validate({...fiche,
      champs: CECollection.forDraft(result.collecte, 'credit_immobilier', fiche.champs)}), parcours: 'credit_immobilier'};
  }
  if (unknownField) {
    const entry = result.collecte.informations.find(item => item.champ === 'credit_immobilier.' + unknownField.key);
    const declaredUnknown = entry?.statut === 'renseigne' && entry.valeur === unknownField.unknownChoice &&
      messages.at(-1).content.includes(entry.source);
    // Une collecte validée peut contenir le choix sans fiche. Reconstituer alors
    // l'action depuis cette mémoire, jamais depuis la prose du modèle.
    if (!result.fiche_credit_immobilier && !result.fiche_reclamation &&
        result.collecte.parcours === 'credit_immobilier' && declaredUnknown) {
      result.fiche_credit_immobilier = {...CECredit.validate({resume: 'Projet immobilier',
        champs: CECollection.forDraft(result.collecte, 'credit_immobilier', {})}), parcours: 'credit_immobilier'};
    }
    // Un acquiescement sans choix structuré ne doit pas être affiché comme un succès.
    if (explicitUnknownChoice && result.fiche_credit_immobilier?.champs[unknownField.key] !== unknownField.unknownChoice) {
      throw new Error('Le choix déclaré n’a pas été transmis au formulaire.');
    }
  }
  return result;
}

function retainValidInformation(data, messages, previous, contexteInterface, options) {
  if (!options.mergeCollection || data?.collecte?.parcours !== 'credit_immobilier' ||
      !Array.isArray(data.collecte.informations) || data.collecte.informations.length > CECollection.fields.length ||
      data.fiche_reclamation != null) return null;
  const before = CECollection.clean(previous);
  let state = before;
  const groups = new Map();
  for (const entry of data.collecte.informations) {
    if (!groups.has(entry?.champ)) groups.set(entry?.champ, []);
    groups.get(entry?.champ).push(entry);
  }
  // Une erreur sur un champ ne doit pas effacer les autres déclarations. Chaque
  // entrée conserve les mêmes contrôles de type, de liste blanche et de source.
  for (const entries of groups.values()) {
    if (entries.length !== 1) continue;
    try {
      const candidate = CECollection.clean(CECollection.merge(state,
        {parcours: 'credit_immobilier', informations: entries}, messages.at(-1).content,
        messages.filter(message => message.role === 'user').map(message => message.content)));
      CECredit.validate({champs: CECollection.forDraft(candidate, 'credit_immobilier', {})});
      state = candidate;
    } catch { /* Garder la mémoire validée, pas la valeur rejetée. */ }
  }
  const oldEntries = new Map(before.informations.map(entry => [entry.champ, entry]));
  const changed = state.informations.some(entry => JSON.stringify(entry) !== JSON.stringify(oldEntries.get(entry.champ)));
  if (!changed) return null;
  const diagnostic = validationFeedback(data, options, messages, state);
  const keys = CECollection.questions(state, diagnostic.champs.map(field => field.champ));
  const current = (contexteInterface?.champs || []).map(field => field.cle);
  const requested = [...new Set([...CECollection.questions(state, current), ...keys])].slice(0, 2);
  const clarification = requested.length ? CECredit.missingPrompt(requested.map(key => key.split('.')[1])) :
    'Une partie de votre réponse reste à préciser. Pouvez-vous me la reformuler ?';
  // Cette réponse conserve la collecte mais ne déclenche aucun remplissage.
  return {message: 'J’ai conservé les informations de votre message que j’ai pu vérifier. ' + clarification,
    collecte: state, sources: [], questions: requested};
}

async function chatRequest(messages, collecte, contexteInterface, options = {}) {
  const data = await requestChatData(messages, collecte, contexteInterface);
  try { return validateModelData(data, messages, collecte, options); }
  catch {
    const correction = {...contexteInterface, correction_validation: validationFeedback(data, options, messages, collecte)};
    // Un seul essai de correction. Erreurs HTTP, réseau et JSON restent hors de
    // cette boucle et ne provoquent jamais de nouvel appel automatique.
    const repaired = await requestChatData(messages, collecte, correction);
    try { return validateModelData(repaired, messages, collecte, options); }
    catch {
      const partial = retainValidInformation(repaired, messages, collecte, contexteInterface, options);
      if (partial) return partial;
      throw new Error('Maya n’a pas pu interpréter une information après correction. Reformulez votre dernière réponse ; vos informations précédentes sont conservées.');
    }
  }
}

// Éviter de garder les informations d'un onglet fermé pendant la session Chrome.
chrome.tabs?.onRemoved?.addListener(tabId => {
  chrome.storage.session.remove('maya:' + tabId);
});
