/* Reconnaissance, remplissage et navigation du formulaire de réclamation. */
(() => {
  const {normalize} = CE;
  const fields = [
    {key: 'objet', aliases: ['motif de reclamation', 'quel est l objet de votre reclamation'], kind: 'choice'},
    {key: 'message', aliases: ['exprimez votre reclamation en quelques lignes'], kind: 'text'},
    {key: 'canal', aliases: ['comment souhaitez vous etre recontacte'], kind: 'choice'},
    {key: 'particulier', aliases: ['a quel titre nous contactez vous'], kind: 'choice'},
    {key: 'civilite', aliases: ['civilite', 'civilite madame monsieur'], kind: 'choice'},
    {key: 'prenom', aliases: ['prenom'], kind: 'text'},
    {key: 'nom', aliases: ['nom'], kind: 'text'},
    {key: 'email', aliases: ['e mail', 'email', 'adresse e mail'], kind: 'text'},
    {key: 'telephone', aliases: ['telephone', 'numero de telephone'], kind: 'text'}
  ];
  function label(el) {
    const ids = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
    // Un bouton combobox ne possède pas la propriété native « labels ».
    const associatedLabels = el.id ? Array.from(document.querySelectorAll('label[for]'))
      .filter(node => node.getAttribute('for') === el.id) : [];
    return [el.getAttribute('aria-label'), ...ids.map(id => document.getElementById(id)?.textContent),
      ...Array.from(el.labels || []).map(l => l.textContent),
      ...associatedLabels.map(node => node.textContent),
      el.closest('mat-form-field')?.querySelector('mat-label')?.textContent,
      el.closest('fieldset')?.querySelector('legend')?.textContent,
      ...(el.getAttribute('role') === 'radiogroup' ? [el.closest('section, fieldset, [role="group"]')?.querySelector('h1, h2, h3, legend')?.textContent] : []),
      ...(isRadioGroup(el) ? [el.closest('app-reclam')?.querySelector('.subHeader-title--main')?.textContent] : []),
      el.getAttribute('placeholder')].filter(Boolean).map(normalize);
  }
  const visible = el => !el.disabled && el.getAttribute('aria-disabled') !== 'true' && el.getClientRects().length > 0;
  function controls(field) {
    const selector = [
      'input', 'textarea', 'select', 'fieldset', 'mat-radio-group', 'mat-select',
      'ng-select', '[role="combobox"]', '[role="radiogroup"]', '[aria-haspopup="listbox"]'
    ].join(', ');
    const excludedTypes = ['checkbox', 'radio', 'password', 'hidden', 'file', 'submit', 'button'];
    const matches = Array.from(document.querySelectorAll(selector)).filter(element => {
      const choiceButton = element.tagName === 'BUTTON' &&
        (element.getAttribute('role') === 'combobox' || element.getAttribute('aria-haspopup') === 'listbox');
      if (!visible(element) || (excludedTypes.includes(element.type) && !choiceButton)) return false;
      if (field.kind === 'text' && !['INPUT', 'TEXTAREA'].includes(element.tagName)) return false;
      return label(element).some(text => {
        const cleanedLabel = text.replace(/ (obligatoire|facultatif)$/, '');
        return field.aliases.includes(cleanedLabel);
      });
    });
    // Un composant peut exposer à la fois son conteneur et un contrôle enfant.
    return matches.filter(element => !matches.some(parent => parent !== element && parent.contains?.(element)));
  }

  function isRadioGroup(element) {
    return element.getAttribute('role') === 'radiogroup' || element.tagName === 'MAT-RADIO-GROUP' ||
      (element.tagName === 'FIELDSET' && Boolean(element.querySelector('input[type="radio"], [role="radio"]')));
  }

  function selectedValue(element) {
    if (isRadioGroup(element)) {
      return element.querySelector('input:checked, [aria-checked="true"]') ? 'selected' : '';
    }
    const selectedText = element.querySelector?.('.neo-select-simple-field-display, .mat-mdc-select-value-text, .mat-select-value-text, [data-selected-value]')?.textContent;
    return normalize(selectedText || element.value || element.getAttribute('aria-valuetext') || '');
  }

  function readControl(element, options = []) {
    if (element.getAttribute('aria-invalid') === 'true' || element.checkValidity?.() === false) return undefined;
    if (element.getAttribute('role') === 'radiogroup' || isRadioGroup(element)) {
      const selected = Array.from(element.querySelectorAll('input:checked, [aria-checked="true"], button[aria-pressed="true"]'));
      if (selected.length !== 1) return undefined;
      const texts = [...label(selected[0]), normalize(selected[0].querySelector?.('.bpce-card-label .label')?.textContent || selected[0].textContent)];
      return options.length ? options.find(option => texts.includes(normalize(option))) : texts.find(Boolean);
    }
    if (element.type === 'checkbox') return element.checked;
    if (element.tagName === 'SELECT') return element.selectedOptions?.[0]?.textContent?.trim();
    if (element.getAttribute('role') === 'combobox' && element.tagName !== 'INPUT') {
      const text = element.querySelector?.('.neo-select-simple-field-display, .mat-mdc-select-value-text, .mat-select-value-text')?.textContent?.trim();
      return isChoicePlaceholder(text) ? undefined : text;
    }
    return element.value?.trim();
  }

  function read() {
    if (!CE.allowed(location.href)) return undefined;
    const champs = {};
    for (const field of fields) {
      const elements = controls(field);
      if (elements.length !== 1) continue;
      const choices = field.key === 'particulier' ? ['Particuliers', 'Professionnels / Entreprises'] :
        field.key === 'canal' ? ['Par mail', 'Par téléphone'] : field.key === 'civilite' ? ['Madame', 'Monsieur'] : CE.motifs;
      const value = readControl(elements[0], choices);
      if (value === undefined || value === '') continue;
      const key = field.key === 'message' ? 'faits' : field.key;
      champs[key] = field.key === 'particulier' ? value === 'Particuliers' : value;
    }
    return {parcours: 'reclamation', champs};
  }

  function isChoicePlaceholder(text) {
    const value = normalize(text).replace(/ (obligatoire|facultatif)$/, '');
    return !value || /choisir|selectionner|choisissez/.test(value) ||
      fields.some(field => field.kind === 'choice' && field.aliases.includes(value));
  }

  function valueFor(field, draft) {
    return field.key === 'particulier' ? (draft.particulier ? 'Particuliers' : 'Professionnels / Entreprises') : draft[field.key];
  }
  function setNative(el, value, {blur = true} = {}) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    if (blur) el.dispatchEvent(new Event('blur', {bubbles: true}));
  }
  function radioClickTarget(radio) {
    if (radio.disabled || radio.getAttribute('aria-disabled') === 'true') return null;
    if (visible(radio)) return radio;
    // Neo peut masquer l'input natif ; son label visible reste cliquable.
    const labels = Array.from(radio.labels || []);
    return labels.find(element => visible(element)) || null;
  }
  async function fillChoice(el, value, overwrite) {
    if (el.tagName === 'SELECT') {
      const currentOption = el.selectedOptions[0];
      if (!overwrite && el.value && currentOption && !isChoicePlaceholder(currentOption.textContent)) return 'conservé';
      const options = Array.from(el.options).filter(o => !o.disabled && normalize(o.textContent) === normalize(value));
      if (options.length !== 1) return 'option introuvable ou ambiguë';
      setNative(el, options[0].value);
      return 'rempli';
    }
    if (isRadioGroup(el)) {
      if (!overwrite && el.querySelector('input:checked, [aria-checked="true"]')) return 'conservé';
      const radios = Array.from(el.querySelectorAll('input[type="radio"], [role="radio"]')).filter(r => radioClickTarget(r) &&
        [...label(r), normalize(r.textContent)].includes(normalize(value)));
      if (radios.length !== 1) return 'option introuvable ou ambiguë';
      radioClickTarget(radios[0]).click();
      for (let attempt = 0; attempt < 10; attempt++) {
        await pause(50);
        if (radios[0].checked || radios[0].getAttribute('aria-checked') === 'true') return 'rempli';
      }
      return 'sélection non confirmée';
    }
    // Ne pas confondre le libellé / texte d'aide avec une sélection.
    const selection = () => selectedValue(el);
    if (!overwrite && !isChoicePlaceholder(selection())) return 'conservé';
    el.click();
    const optionScope = () => {
      const ids = (el.getAttribute('aria-controls') || el.getAttribute('aria-owns') || '').split(/\s+/).filter(Boolean);
      const owned = ids.map(id => document.getElementById(id)).filter(Boolean);
      if (owned.length) return owned.flatMap(node => Array.from(node.querySelectorAll('[role="option"], mat-option')));
      const panels = Array.from(document.querySelectorAll('[role="listbox"], .mat-mdc-select-panel, .mat-select-panel')).filter(visible);
      if (panels.length === 1) return Array.from(panels[0].querySelectorAll('[role="option"], mat-option'));
      if (panels.length > 1) return [];
      return Array.from(document.querySelectorAll('[role="option"]'));
    };
    const matches = () => optionScope().filter(o => visible(o) && o.getAttribute('aria-disabled') !== 'true' && normalize(o.textContent) === normalize(value));
    let options;
    for (let attempt = 0; attempt < 20; attempt++) {
      options = matches(); if (options.length) break;
      await pause(75);
    }
    if (options.length !== 1) {
      el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', bubbles: true}));
      return 'option introuvable ou ambiguë';
    }
    options[0].click();
    for (let attempt = 0; attempt < 10; attempt++) {
      if (selection() === normalize(value) || options[0].getAttribute('aria-selected') === 'true') return 'rempli';
      await pause(50);
    }
    return 'sélection non confirmée';
  }
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

  function isAnonymousEntryPage() {
    const url = new URL(location.href);
    if (typeof CECredit !== 'undefined' && CECredit.allowed(location.href)) return true;
    return url.protocol === 'https:' && url.hostname === 'www.caisse-epargne.fr' &&
      url.pathname.replace(/\/$/, '') === '/formulaire/contact/auth-generic' && url.searchParams.get('form') === 'reclam';
  }

  function chooseAnonymousEntry() {
    if (!isAnonymousEntryPage()) return false;

    const mortgage = typeof CECredit !== 'undefined' && CECredit.allowed(location.href);
    const question = normalize(mortgage ? 'Êtes-vous déjà client ?' : 'Souhaitez-vous vous connecter afin de faciliter la saisie de votre demande ?');
    // Le site peut afficher ce titre dans un div, sans rôle heading.
    const candidates = Array.from(document.querySelectorAll('h1, h2, h3, [role="heading"], div, p'))
      .filter(element => visible(element) && normalize(element.textContent) === question);
    // Garder le bloc le plus précis si plusieurs conteneurs reprennent le titre.
    const headings = candidates.filter(element => !candidates.some(child =>
      child !== element && element.contains?.(child)));
    if (headings.length !== 1) return false;

    // Limiter le clic au bloc de cette question, avec les deux choix attendus.
    let container = headings[0].parentElement;
    for (let depth = 0; container && depth < 12; depth++, container = container.parentElement) {
      const buttons = Array.from(container.querySelectorAll('button, [role="button"], input[type="button"]')).filter(visible);
      const choices = value => buttons.filter(button => normalize(button.textContent || button.value) === value);
      const no = choices(mortgage ? 'non je reste visiteur' : 'non');
      if (no.length === 1 && choices(mortgage ? 'oui je m identifie' : 'oui').length === 1) {
        no[0].click();
        return true;
      }
    }
    return false;
  }

  function startAnonymousEntry() {
    if (!isAnonymousEntryPage() ||
        typeof MutationObserver !== 'function' || globalThis.CEAnonymousEntryStarted) return;
    globalThis.CEAnonymousEntryStarted = true;
    let chosen = false;
    let timeout;
    const stop = () => { observer.disconnect(); clearTimeout(timeout); };
    const observer = new MutationObserver(() => {
      if (chosen) return;
      chosen = chooseAnonymousEntry();
      if (chosen) stop();
    });
    observer.observe(document.body, {childList: true, subtree: true, attributes: true});
    // Le formulaire Angular peut arriver après le chargement du script.
    timeout = setTimeout(stop, 120000);
    globalThis.addEventListener?.('pagehide', stop, {once: true});
    chosen = chooseAnonymousEntry();
    if (chosen) stop();
  }

  async function run(action, draft, overwrite = false) {
    if (!CE.allowed(location.href)) throw new Error('Ouvrez le formulaire de réclamation officiel ou la démonstration.');
    if (!['fill', 'inspect'].includes(action)) throw new Error('Action inconnue.');
    if (action === 'fill') CE.validate(draft);
    const report = [];
    for (const field of fields) {
      const nodes = controls(field);
      if (!nodes.length) continue;
      let status = nodes.length === 1 ? 'détecté' : 'plusieurs champs : remplissage manuel';
      if (action === 'fill' && nodes.length === 1) {
        const el = nodes[0], value = valueFor(field, draft);
        if (value === undefined || value === '') {
          const existing = selectedValue(el);
          status = existing && (field.kind !== 'choice' || !isChoicePlaceholder(existing)) ? 'conservé' : 'non renseigné';
        }
        else if (field.kind === 'choice') status = await fillChoice(el, value, overwrite);
        else if (!overwrite && el.value) status = 'conservé';
        else if (el.readOnly) status = 'lecture seule';
        else if (el.maxLength >= 0 && value.length > el.maxLength) status = 'trop long : remplissage manuel';
        else { setNative(el, value); status = 'rempli'; }
      }
      report.push({field: field.key, status});
    }
    return report;
  }
  function stepSignature() {
    return fields.flatMap(field => controls(field).map(el => field.key + ':' + (el.id || '') + ':' + label(el).join('|'))).join(';');
  }
  function hasInvalidFields(form) {
    const elements = form.querySelectorAll('input, textarea, select, [aria-invalid="true"]');
    return Array.from(elements).some(element => {
      if (!visible(element)) return false;
      if (element.getAttribute('aria-invalid') === 'true') return true;
      return element.required && typeof element.checkValidity === 'function' && !element.checkValidity();
    });
  }

  function findNextButtons(form) {
    const nextLabels = ['suivant', 'suivante', 'etape suivante', 'continuer'];
    const buttons = form.querySelectorAll('button, input[type="button"]');
    return Array.from(buttons).filter(button => {
      if (!visible(button)) return false;
      const label = normalize(button.textContent || button.value || button.getAttribute('aria-label'));
      const accessibleLabel = button.getAttribute('aria-label') || '';
      return nextLabels.includes(label) && !/envoyer|soumettre|confirmer|valider|terminer/i.test(accessibleLabel);
    });
  }

  async function waitForNextStep(previousSignature) {
    for (let attempt = 0; attempt < 30; attempt++) {
      await pause(75);
      if (!CE.allowed(location.href)) return false;
      const signature = stepSignature();
      if (signature && signature !== previousSignature) return true;
    }
    return false;
  }

  async function complete(draft) {
    CE.validate(draft);
    let advanced = 0;
    const stop = message => ({advanced, message});

    for (let step = 0; step < 8; step++) {
      const report = await run('fill', draft);
      if (!report.length) {
        return stop('Choisissez le parcours sur le site, puis dites « continuer » pour reprendre le remplissage.');
      }

      const blockedFields = report.filter(item => !['rempli', 'conservé'].includes(item.status));
      if (blockedFields.length) {
        const names = blockedFields.map(item => item.field).join(', ');
        return stop('Complétez ou vérifiez sur le site : ' + names + '. Dites ensuite « continuer ».');
      }

      const firstControl = fields.flatMap(field => controls(field))[0];
      const form = firstControl?.closest('form') || firstControl?.closest('[role="form"]') ||
        firstControl?.closest('app-reclam') || firstControl?.closest('main') || firstControl?.closest('app-root');
      if (!form) {
        return stop('Les champs reconnus sont remplis. Passez cette étape sur le site, puis dites « continuer ».');
      }
      if (hasInvalidFields(form)) {
        return stop('Il reste des informations obligatoires à compléter sur le site. Dites ensuite « continuer ».');
      }

      // Cliquer uniquement sur une transition explicite. L'envoi final reste manuel.
      const buttons = findNextButtons(form);
      if (buttons.length !== 1) {
        return stop('Le formulaire est préparé jusqu’à cette étape. Vérifiez les informations et complétez vous-même le consentement, le CAPTCHA et l’envoi final.');
      }

      const signature = stepSignature();
      buttons[0].click();
      if (!await waitForNextStep(signature)) {
        return stop('L’étape suivante n’a pas été confirmée. Vérifiez les champs ou messages du site, puis dites « continuer ».');
      }
      advanced++;
    }
    return stop('Vérifiez l’étape affichée sur le site. Dites « continuer » pour reprendre.');
  }

  globalThis.CEAdapter = {run, complete, read, form: {label, visible, setNative, fillChoice, readControl}};
  startAnonymousEntry();
})();
