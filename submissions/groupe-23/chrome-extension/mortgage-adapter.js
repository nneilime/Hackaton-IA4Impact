/* Parcours immobilier : uniquement les champs et étapes définis localement. */
(() => {
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const {label, visible, setNative, fillChoice, readControl} = CEAdapter.form;
  const pageKey = () => new URL(location.href).pathname.split('/tunnel/')[1]?.replace(/\/$/, '');
  const fieldNames = element => label(element);
  let chargeAdded = false; // Éviter un second ajout lors d'une reprise locale.

  function openDialogs() {
    return Array.from(document.querySelectorAll('dialog[open]'))
      .filter(dialog => dialog.tagName === 'DIALOG' && dialog.open && visible(dialog));
  }

  function chargeDialog() {
    const dialogs = openDialogs();
    if (dialogs.length !== 1) return null;
    const matches = dialogs.filter(dialog => CE.normalize(dialog.querySelector('h1')?.textContent) === 'autre charge');
    return matches.length === 1 ? matches[0] : null;
  }

  function cardLabel(button) {
    return button.querySelector?.('.bpce-card-label .label')?.textContent || button.textContent;
  }

  function radioCards(group) {
    return Array.from(group.querySelectorAll('button[aria-pressed]'));
  }

  function nextButtons() {
    return Array.from(document.querySelectorAll('button')).filter(button => visible(button) &&
      ['continuer', 'suivant'].includes(CE.normalize(button.querySelector?.('.neo-button-content')?.textContent || button.textContent)));
  }

  function unconfirmedZero(definition, value) {
    return Boolean((definition.unknownChoice || definition.zeroChoice) && value === 0 &&
      Array.from(document.querySelectorAll('button')).some(button =>
        CE.normalize(button.querySelector?.('.neo-button-content')?.textContent || button.textContent) === 'continuer' &&
        (button.disabled || button.getAttribute?.('aria-disabled') === 'true') &&
        (!button.getClientRects || button.getClientRects().length > 0)));
  }

  function financingSummary() {
    if (!CECredit.allowed(location.href) || /^(?:contact|propositions?)\//.test(pageKey())) return null;
    const headings = Array.from(document.querySelectorAll('h1, h2, h3, .subHeader-title--main'));
    if (!headings.some(node => visible(node) && CE.normalize(node.textContent) === 'besoin de financement')) return null;
    const labels = ['Prix de vente du bien', "Honoraires d’agence", 'Frais de notaire (estimation)',
      'Coût total du projet', 'Votre apport personnel', 'Besoin de financement'];
    const nodes = Array.from(document.querySelectorAll('td, th, dt, span, p, div, strong'));
    const rows = [];
    for (const label of labels) {
      const candidates = nodes.filter(node => visible(node) && CE.normalize(node.textContent) === CE.normalize(label) &&
        !Array.from(node.children || []).some(child => CE.normalize(child.textContent) === CE.normalize(label)));
      const values = new Set();
      for (const node of candidates) {
        let row = node.parentElement;
        for (let depth = 0; depth < 3 && row; depth++, row = row.parentElement) {
          const text = row.textContent.trim();
          if (!CE.normalize(text).startsWith(CE.normalize(label))) break;
          const rest = text.slice(node.textContent.trim().length).trim();
          const matches = rest.match(/(?:-?\s*\d[\d\s\u00a0\u202f]*(?:[,.]\d{2})?\s*€|non renseigné)/gi) || [];
          if (matches.length === 1) { values.add(matches[0].trim()); break; }
          if (matches.length > 1) break;
        }
      }
      if (values.size !== 1) return null;
      rows.push(label + ' : ' + [...values][0].replace('€', 'euros').replace(/^-\s*/, 'moins ') + '.');
    }
    return 'Voici le besoin de financement affiché par le site. ' + rows.join(' ');
  }

  function notaryEstimation() {
    if (!CECredit.allowed(location.href) || pageKey() !== 'mon-projet/estimation-frais-notaire') return null;
    const nodes = Array.from(document.querySelectorAll('h1, h2, h3, p, span, div'));
    // Lire les deux textes visibles du site, sans calculer ni coder un taux.
    const textOf = node => node.textContent?.trim().replace(/\s+/g, ' ') || '';
    const paragraphs = pattern => {
      const matching = nodes.filter(node => visible(node) && textOf(node).length <= 1000 && pattern.test(textOf(node)));
      // Les conteneurs englobants reprennent aussi les paragraphes ; choisir les
      // descendants les plus précis pour éviter une description en double.
      return [...new Set(matching.filter(node => !matching.some(other => other !== node && node.contains?.(other))).map(textOf))];
    };
    const estimates = paragraphs(/^nous estimerons .*frais de notaire.*prix de vente.*\.$/i);
    const caveats = paragraphs(/^le montant exact des frais .*notaire\.$/i);
    if (estimates.length !== 1 || caveats.length !== 1) return null;
    return 'Le site indique : ' + estimates[0].replace(/\s*%/g, ' pour cent') + ' ' + caveats[0];
  }

  function screenDescription() {
    const text = notaryEstimation();
    return text ? text + ' Vous pouvez dire « continuer » pour passer à l’étape suivante.' : null;
  }

  async function fillRadioCards(group, value, definition) {
    const cards = radioCards(group).filter(visible);
    const matching = cards.filter(card => CE.normalize(cardLabel(card)) === CE.normalize(value));
    if (matching.length !== 1) return 'Choix non reconnu ou ambigu : ' + definition.label;
    const selected = cards.filter(card => card.getAttribute('aria-pressed') === 'true');
    const alreadySelected = selected.length === 1 && selected[0] === matching[0];
    if (alreadySelected && nextButtons().length) return null;
    if (selected.length && !alreadySelected) return 'Un autre usage est déjà sélectionné. Vérifiez votre choix sur le site';

    const previous = location.href;
    matching[0].click();
    for (let attempt = 0; attempt < 40; attempt++) {
      await pause(75);
      // Angular peut confirmer le choix ou passer directement à l'étape suivante.
      if (location.href !== previous) return CECredit.allowed(location.href) ? null : 'La destination après sélection est inattendue';
      if (matching[0].getAttribute('aria-pressed') === 'true') return null;
    }
    return 'La sélection n’a pas été confirmée : ' + definition.label;
  }

  function matchingControls(definition, root = document) {
    const candidates = Array.from(root.querySelectorAll('input, textarea, select, [role="combobox"], [role="radiogroup"], fieldset[neoradiogroup]'));
    return candidates.filter(element => {
      if (!visible(element) || ['password', 'file', 'submit', 'hidden'].includes(element.type)) return false;
      if (definition.kind === 'boolean') return element.type === 'checkbox' && fieldNames(element).includes(CE.normalize(definition.label));
      if (element.type === 'checkbox' || element.type === 'radio') return false;
      const names = fieldNames(element);
      if (names.includes(CE.normalize(definition.label))) return true;
      // Les légendes Neo peuvent être vides : identifier le groupe par tous ses choix.
      if (definition.options.length && element.getAttribute('role') === 'radiogroup') {
        const options = Array.from(element.querySelectorAll('input[type="radio"], [role="radio"]'));
        const cards = radioCards(element).filter(visible);
        return definition.options.every(value =>
          options.some(option => fieldNames(option).includes(CE.normalize(value))) ||
          cards.some(card => CE.normalize(cardLabel(card)) === CE.normalize(value)));
      }
      return false;
    });
  }

  function locationParts(text) {
    const codes = String(text).match(/\b\d{5}\b/g) || [];
    const city = CE.normalize(String(text).replace(/\b\d{5}\b/g, ' '));
    return {codes, city};
  }

  function locationMatches(text, requested) {
    const candidate = locationParts(text);
    const query = locationParts(requested);
    return (query.codes.length || query.city) &&
      query.codes.every(code => candidate.codes.includes(code)) &&
      (!query.city || candidate.city === query.city);
  }

  function locationIsValid(control) {
    return Boolean(control.value.trim()) && control.getAttribute('aria-invalid') === 'false' &&
      control.getAttribute('aria-expanded') !== 'true';
  }

  async function fillLocation(control, value, definition) {
    // Un texte déjà saisi peut encore être invalide : seule une commune choisie
    // dans la liste est acceptée par Angular.
    if (locationIsValid(control)) {
      return locationMatches(control.value, value) ? null : 'Une autre commune est déjà sélectionnée : ' + definition.label;
    }
    if (control.readOnly) return 'Champ en lecture seule : ' + definition.label;
    if (control.maxLength >= 0 && value.length > control.maxLength) return 'Valeur trop longue : ' + definition.label;
    const listIds = (control.getAttribute('aria-controls') || '').split(/\s+/).filter(Boolean);
    if (!listIds.length) return 'Liste des communes non reconnue : ' + definition.label;

    control.focus?.();
    const searchText = locationParts(value).codes[0] || value;
    setNative(control, searchText, {blur: false});
    // Les options proviennent uniquement du popover associé à ce champ.
    for (let attempt = 0; attempt < 40; attempt++) {
      await pause(100);
      const options = listIds.flatMap(id => {
        const list = document.getElementById(id);
        return list && visible(list) ? Array.from(list.querySelectorAll('[role="option"]')) : [];
      }).filter(option => visible(option) && option.getAttribute('aria-disabled') !== 'true' &&
        locationMatches(option.textContent, value));
      if (options.length > 1) return 'Plusieurs communes correspondent. Précisez la ville et son code postal sur le site';
      if (options.length !== 1) continue;

      const chosen = options[0];
      const previous = location.href;
      chosen.click();
      for (let confirmation = 0; confirmation < 30; confirmation++) {
        await pause(100);
        if (location.href !== previous) return CECredit.allowed(location.href) ? null : 'Destination inattendue après choix de la commune';
        if (locationIsValid(control) && locationMatches(chosen.textContent, control.value)) return null;
      }
      return 'La commune n’a pas été validée par le site : ' + definition.label;
    }
    return 'Aucune commune correspondante n’est proposée. Vérifiez la ville et le code postal sur le site';
  }

  async function fillField(definition, value, root = document) {
    if (definition.kind === 'card') {
      const cards = Array.from(document.querySelectorAll('button, [role="button"], [role="radio"]'))
        .filter(element => visible(element) && CE.normalize(element.textContent) === CE.normalize(value));
      if (cards.length !== 1) return 'Choix non reconnu : ' + definition.label;
      cards[0].click();
      return null;
    }
    let controls = matchingControls(definition, root);
    // Certains écrans de montant n'ont pas de label, mais un seul champ de saisie.
    if (!controls.length && definition.kind === 'amount' && root === document) {
      controls = Array.from(root.querySelectorAll('input'))
        .filter(element => visible(element) && ['text', 'number', 'tel'].includes(element.type));
    }
    if (controls.length !== 1) return 'Champ non reconnu ou ambigu : ' + definition.label;
    const control = controls[0];
    if (definition.kind === 'choice') {
      if (control.getAttribute('role') === 'radiogroup' && radioCards(control).length) {
        return fillRadioCards(control, value, definition);
      }
      const status = await fillChoice(control, value, false);
      return ['rempli', 'conservé'].includes(status) ? null : definition.label + ' : ' + status;
    }
    if (definition.kind === 'boolean') {
      if (control.checked !== value) control.click();
      await pause(50);
      return control.checked === value ? null : 'Vérifiez : ' + definition.label;
    }
    if (definition.kind === 'location') return fillLocation(control, String(value), definition);
    const defaultZero = control.value && ['amount', 'integer'].includes(definition.kind) &&
      unconfirmedZero(definition, Number(String(control.value).replace(/[\s€]/g, '').replace(',', '.')));
    if (control.value && !defaultZero) return null;
    if (control.readOnly) return 'Champ en lecture seule : ' + definition.label;
    let text = String(value);
    if (definition.kind === 'month' && control.type === 'month') text = value.split('/').reverse().join('-');
    if (definition.kind === 'date' && control.type === 'date') {
      text = value.split('/').reverse().join('-');
    }
    if (control.maxLength >= 0 && text.length > control.maxLength) return 'Valeur trop longue : ' + definition.label;
    setNative(control, text);
    return null;
  }

  async function waitForPage(previous, attempts = 40) {
    for (let attempt = 0; attempt < attempts; attempt++) {
      await pause(75);
      if (location.href !== previous) return CECredit.allowed(location.href);
      if (chargeDialog()) return true; // Oui peut ouvrir une fenêtre sans changer l'URL.
    }
    return false;
  }

  async function skipUnknownChoice(previous, definition, choice = definition.unknownChoice) {
    const expected = CE.normalize(choice);
    const subject = definition.key === 'dpe' ? 'DPE' : definition.label;
    for (let attempt = 0; attempt < 40; attempt++) {
      if (location.href !== previous || pageKey() !== definition.page) {
        return 'L’étape « ' + subject + ' » a changé. Vérifiez le site avant de reprendre.';
      }
      // Neo peut rendre cette action sous forme de lien plutôt que de button.
      const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], input[type="button"]'))
        .filter(element => {
          if (!visible(element)) return false;
          // Le loader Neo peut ajouter du texte au bouton pendant sa transition.
          // Lire son contenu dédié plutôt que le texte du composant entier.
          const content = element.querySelector?.('.neo-button-content')?.textContent;
          const names = [element.getAttribute?.('aria-label'), element.value, content || element.textContent];
          if (!names.some(name => CE.normalize(name) === expected)) return false;
          const href = element.getAttribute?.('href');
          return !href || CECredit.allowed(new URL(href, location.href).href);
        }).filter((element, _, all) => !all.some(other => other !== element && element.contains?.(other)));
      if (candidates.length > 1) return 'Plusieurs choix « ' + definition.unknownChoice + ' » sont affichés. Vérifiez « ' + subject + ' » sur le site.';
      if (candidates.length === 1) {
        candidates[0].click();
        // Un seul clic : le site peut attendre sa réponse réseau avant de naviguer.
        return await waitForPage(previous, 134) ? null : 'Le bouton ' + subject + ' « ' + definition.unknownChoice + ' » a été activé, mais le site n’a pas changé d’étape. Vous pouvez réessayer ou poursuivre sur le site.';
      }
      await pause(75);
    }
    return 'Le choix « ' + choice + ' » pour « ' + subject + ' » n’est pas disponible. Vérifiez le site.';
  }

  async function fillChargeDialog(dialog, proposal) {
    const fields = CECredit.fields.filter(field => field.modal === 'autre-charge');
    for (const field of fields) {
      // La durée est conditionnelle : l'attendre après le choix du type.
      if (field.key === 'chargeDuree') {
        for (let attempt = 0; attempt < 20 && !matchingControls(field, dialog).length; attempt++) await pause(75);
        if (!matchingControls(field, dialog).length) continue;
      }
      const value = read().champs[field.key] ?? proposal.champs[field.key];
      if (value == null) return 'Pour ajouter cette charge, précisez : ' + field.question + '. Vous pouvez aussi compléter la fenêtre sur le site.';
      const error = await fillField(field, value, dialog);
      if (error) return error + '. Vérifiez la fenêtre sur le site.';
    }
    // Ce bouton ajoute seulement la charge dans la fenêtre reconnue.
    // Ne jamais cliquer sur un autre bouton Valider de la page bancaire.
    let buttons = [];
    for (let attempt = 0; attempt < 20; attempt++) {
      buttons = Array.from(dialog.querySelectorAll('button[type="submit"]'))
        .filter(button => visible(button) && CE.normalize(button.textContent) === 'valider');
      if (buttons.length === 1) break;
      await pause(75);
    }
    if (buttons.length !== 1) return 'Les champs de la charge ne sont pas encore validés par le site. Vérifiez la fenêtre avant de poursuivre.';
    buttons[0].click();
    for (let attempt = 0; attempt < 40; attempt++) {
      await pause(75);
      if (!CECredit.allowed(location.href)) return 'La destination après ajout de la charge est inattendue. Vérifiez le site.';
      if (!chargeDialog()) {
        chargeAdded = true;
        return 'La fenêtre de la charge a été validée. Vérifiez son ajout dans la liste ; les charges supplémentaires restent à saisir sur le site, puis poursuivez le formulaire.';
      }
    }
    return 'La validation de la charge n’a pas été confirmée. Vérifiez les erreurs dans la fenêtre sur le site.';
  }

  async function complete(proposal, {continueSummary = false} = {}) {
    proposal = CECredit.validate(proposal);
    continueSummary = continueSummary && Boolean(financingSummary() || notaryEstimation());
    let advanced = 0;
    const stop = message => ({advanced, message});
    for (let step = 0; step < 60; step++) {
      if (!CECredit.allowed(location.href)) return stop('Ouvrez le parcours de crédit immobilier pour remplir votre projet.');
      const dialog = chargeDialog();
      if (dialog) return stop(await fillChargeDialog(dialog, proposal));
      if (openDialogs().length) return stop('Cette fenêtre nécessite une vérification sur le site. Complétez-la avant de reprendre.');
      const page = pageKey();
      const estimate = notaryEstimation();
      if (estimate) {
        if (!continueSummary) return stop(screenDescription());
        const buttons = nextButtons();
        if (buttons.length !== 1) return stop(estimate + ' Le bouton Continuer n’est pas disponible ou est ambigu.');
        const previous = location.href;
        buttons[0].click();
        continueSummary = false;
        if (!await waitForPage(previous, 134)) return stop(estimate + ' Le site n’a pas confirmé le passage à l’étape suivante.');
        advanced++;
        continue;
      }
      const summary = financingSummary();
      if (summary) {
        if (!continueSummary) return stop(summary + ' Vous pouvez dire « continuer » pour passer à l’étape suivante, ou demander une modification.');
        const buttons = Array.from(document.querySelectorAll('button')).filter(button => visible(button) &&
          CE.normalize(button.querySelector?.('.neo-button-content')?.textContent || button.textContent) === 'valider et passer a l etape suivante');
        if (buttons.length !== 1) return stop(summary + ' Le bouton de passage à l’étape suivante n’est pas disponible ou est ambigu.');
        const previous = location.href;
        buttons[0].click();
        continueSummary = false;
        if (!await waitForPage(previous, 134)) return stop(summary + ' Le site n’a pas confirmé le passage à l’étape suivante.');
        advanced++;
        continue;
      }
      if (page === 'mon-budget/synthese-charges' && chargeAdded) return stop('Une charge a déjà été préparée. Vérifiez la liste et poursuivez cet écran sur le site pour éviter un doublon.');
      const fields = CECredit.fields.filter(field => field.page === page && !field.modal);
      if (!fields.length) return stop('Cette étape nécessite une vérification sur le site. Complétez-la puis dites « continuer ».');
      const previous = location.href;
      const zero = fields.find(field => field.zeroChoice &&
        (typeof readControl === 'function' ? read().champs[field.key] ?? proposal.champs[field.key] : proposal.champs[field.key]) === 0);
      if (zero) {
        const error = await skipUnknownChoice(previous, zero, zero.zeroChoice);
        if (error) return stop(error);
        advanced++;
        continue;
      }
      const unknown = fields.find(field => field.unknownChoice && proposal.champs[field.key] === field.unknownChoice);
      if (unknown) {
        const error = await skipUnknownChoice(previous, unknown);
        if (error) return stop(error);
        advanced++;
        continue;
      }
      const missing = [];
      for (const field of fields) {
        // Les listes et le champ de début d'activité apparaissent après le choix
        // précédent. Les attendre, puis ignorer ceux que le site ne demande pas.
        const conditionalProfessionalField = page.startsWith('mon-budget/profession') &&
          !['categorieProfessionnelle', 'coCategorieProfessionnelle'].includes(field.key);
        if (conditionalProfessionalField) {
          for (let attempt = 0; attempt < 20 && !matchingControls(field).length; attempt++) await pause(75);
          if (!matchingControls(field).length) continue;
        }
        const siteValues = typeof readControl === 'function' ? read().champs : {};
        const value = siteValues[field.key] ?? proposal.champs[field.key];
        if (value == null) {
          missing.push(field);
          continue;
        }
        const error = await fillField(field, value);
        if (error) return stop(error + '. Vérifiez sur le site puis dites « continuer ».');
      }
      if (missing.length) return {
        ...stop(CECredit.missingPrompt(missing.map(field => field.key))),
        reason: 'missing_fields', missing: missing.map(field => field.key)
      };
      // La validation des coordonnées peut créer une demande : arrêt avant ce clic.
      if (page.startsWith('contact/')) return stop('Les coordonnées sont préparées. Vérifiez le récapitulatif et poursuivez vous-même la demande sur le site.');
      if (location.href === previous && !fields.some(field => field.kind === 'card')) {
        let buttons = [];
        // La sélection et la navigation peuvent être deux transitions Angular
        // distinctes. Attendre le changement de page OU un bouton devenu actif.
        for (let attempt = 0; attempt < 100; attempt++) {
          await pause(100);
          if (location.href !== previous) break;
          buttons = nextButtons();
          if (buttons.length) break;
        }
        if (location.href !== previous) {
          if (!CECredit.allowed(location.href)) return stop('La destination après sélection est inattendue. Vérifiez le site.');
          advanced++;
          continue;
        }
        if (buttons.length !== 1) {
          const usage = fields.find(field => field.key === 'usage');
          if (usage) return stop('Le choix d’usage « ' + proposal.champs.usage + ' » est sélectionné, mais le site n’a pas avancé et aucun bouton Continuer unique n’est actif.');
          return stop(currentStepDescription() + ' Je ne trouve pas de bouton Continuer actif et unique pour cette étape. Le passage à l’étape suivante n’est pas confirmé.');
        }
        buttons[0].click();
      }
      if (location.href === previous && !await waitForPage(previous)) return stop('Le passage à l’étape suivante n’a pas été confirmé. Vérifiez le site puis dites « continuer ».');
      advanced++;
    }
    return stop('Vérifiez l’étape affichée avant de poursuivre.');
  }
  function currentStepDescription() {
    const fields = CECredit.fields.filter(field => field.page === pageKey() && !field.modal);
    if (!fields.length) return 'Le formulaire est arrêté sur une étape que je ne reconnais pas.';
    const values = typeof readControl === 'function' ? read().champs : {};
    return 'Le formulaire affiche actuellement : ' + fields.map(field => {
      const value = values[field.key];
      const label = field.question || field.label;
      if (value == null) return label;
      if (field.kind === 'amount' && typeof value === 'number') return label + ' : ' + value.toLocaleString('fr-FR') + ' euros';
      return label;
    }).join('; ') + '.';
  }
  function read() {
    if (!CECredit.allowed(location.href)) return undefined;
    const champs = {};
    const dialog = chargeDialog();
    if (!dialog && openDialogs().length) return {parcours: 'credit_immobilier', champs};
    const fields = CECredit.fields.filter(field => dialog ? field.modal === 'autre-charge' : field.page === pageKey() && !field.modal);
    if (dialog) champs.autresCharges = 'Oui';
    for (const field of fields) {
      let controls = matchingControls(field, dialog || document);
      if (field.kind === 'card') {
        controls = Array.from(document.querySelectorAll('button[aria-pressed="true"], [role="radio"][aria-checked="true"]'))
          .filter(element => visible(element) && field.options.some(option => CE.normalize(cardLabel(element)) === CE.normalize(option)));
      }
      if (controls.length !== 1) continue;
      const control = controls[0];
      if (field.kind === 'location' && !locationIsValid(control)) continue;
      let value = field.kind === 'card' ? cardLabel(control).trim() : readControl(control, field.options);
      if (value === undefined || value === '') continue;
      if (field.kind === 'month' && /^\d{4}-\d{2}$/.test(value)) value = value.split('-').reverse().join('/');
      if (field.kind === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(value)) value = value.split('-').reverse().join('/');
      if (['amount', 'integer'].includes(field.kind)) {
        const text = String(value).replace(/[\s€]/g, '');
        if (!/^\d+(?:[,.]\d{1,2})?$/.test(text)) continue;
        value = Number(text.replace(',', '.'));
        // Neo affiche parfois 0 avant toute réponse, avec Continuer désactivé.
        if (unconfirmedZero(field, value)) continue;
      }
      try {Object.assign(champs, CECredit.validate({resume: 'Valeurs du formulaire', champs: {[field.key]: value}}).champs);}
      catch { /* Ne pas transmettre un champ invalide ou encore incomplet. */ }
    }
    return {parcours: 'credit_immobilier', champs};
  }
  globalThis.CECreditAdapter = {complete, read, financingSummary, screenDescription};
})();
