/* Conversation et commandes locales. Le rendu est défini dans panel-view.js. */
(() => {
  if (!(CE.allowed(location.href) || CE.siteAllowed(location.href))) return;
  if (globalThis.CEPanel) {
    CEPanel.show();
    return;
  }

  const root = CEPanelView.create();
  const panel = root.querySelector('.panel');
  const launcher = root.querySelector('.launcher');
  const chat = root.querySelector('#chat');
  const prompt = root.querySelector('#prompt');
  const status = root.querySelector('#status');
  const composer = root.querySelector('#composer');
  const resetButton = root.querySelector('#reset');
  const closeButton = root.querySelector('#close');
  const welcome = root.querySelector('#welcome');
  const conversation = root.querySelector('.conversation');
  const sendButton = root.querySelector('#send');
  const voiceButton = root.querySelector('#voice');
  const voiceModeButton = root.querySelector('#voice-mode');
  const interruptButton = root.querySelector('#voice-interrupt');
  const finishButton = root.querySelector('#voice-finish');
  const vocalScreen = root.querySelector('#vocal-screen');
  const muteButton = root.querySelector('#voice-mute');
  const pauseButton = root.querySelector('#voice-pause');
  const endVoiceButton = root.querySelector('#voice-end');
  const exampleButton = root.querySelector('#example');

  let messages = [];
  let draft = null;
  let busy = false;
  let recognition = null;
  let listening = false;
  let voiceMode = false;
  let voiceSession = 0;
  let voicePaused = false;
  let voiceMuted = false;
  let pendingSpeech = null;
  let utterance = null;
  let voiceTurn = null;
  let introductionSpoken = false;
  const voiceSilenceMs = 5000;

  function updateVoiceView() {
    panel.setAttribute('data-voice', String(voiceMode));
    vocalScreen.hidden = !voiceMode;
    const state = voicePaused ? 'paused' : utterance ? 'speaking' : busy ? 'waiting' : voiceMuted ? 'muted' : voiceTurn?.finishing ? 'confirming' : 'listening';
    vocalScreen.setAttribute('data-state', state);
    root.querySelector('#vocal-title').textContent = {
      paused: 'Conversation en pause', speaking: 'Maya vous répond', waiting: 'Maya réfléchit',
      muted: 'Microphone coupé', confirming: 'Je termine la transcription', listening: 'Maya vous écoute'
    }[state];
    root.querySelector('#vocal-microphone-state').textContent = listening ? 'Microphone activé' : 'Microphone désactivé';
    const credit = CECredit.allowed(location.href) || draft?.parcours === 'credit_immobilier';
    root.querySelector('#vocal-subtitle').textContent = credit ? 'Votre assistante crédit IA' : 'Votre assistante bancaire IA';
    root.querySelector('#vocal-project-title').textContent = credit ? 'Votre projet immobilier' : 'Votre besoin bancaire';
    root.querySelector('#vocal-project-description').textContent = credit ? 'Mon besoin · Parlons de votre financement' : 'Mon besoin · Parlons de votre demande';
    root.querySelector('#vocal-description').textContent = state === 'listening' ?
      (credit ? 'Parlez-moi de votre projet immobilier. Prenez votre temps, je suis là pour vous.' : 'Parlez-moi de votre besoin. Prenez votre temps, je suis là pour vous.') :
      {confirming: 'Vos derniers mots sont en cours de confirmation.', paused: 'Reprenez la conversation quand vous êtes prêt.', muted: 'Réactivez le micro pour continuer à parler.', waiting: 'Votre réponse est en cours de préparation.', speaking: 'Vous pouvez interrompre Maya pour reprendre la parole.'}[state];
    root.querySelector('#vocal-credit-notice').hidden = !credit;
    muteButton.setAttribute('aria-pressed', String(voiceMuted));
    pauseButton.setAttribute('aria-pressed', String(voicePaused));
    root.querySelector('#voice-mute-label').textContent = voiceMuted ? 'Activer le micro' : 'Couper le micro';
    root.querySelector('#voice-pause-label').textContent = voicePaused ? 'Reprendre la conversation' : 'Mettre en pause';
    muteButton.disabled = disconnected || voicePaused;
    pauseButton.disabled = disconnected;
    endVoiceButton.disabled = false;
    finishButton.hidden = !voiceMode || voicePaused || voiceMuted || !listening;
    interruptButton.hidden = !utterance || voicePaused;
  }

  function suspendListening() {
    clearTurnTimers();
    if (voiceTurn) {
      // Conserver uniquement les mots confirmés, sans envoyer au moment de la pause.
      prompt.value = voiceTurn.text;
      voiceTurn.interim = false;
      voiceTurn.speaking = false;
      voiceTurn.finishing = false;
    }
    stopDictation();
  }

  function toggleVoicePause() {
    if (!voiceMode) return;
    voicePaused = !voicePaused;
    if (voicePaused) {
      suspendListening();
      if (utterance) {
        pendingSpeech = {text: utterance.text, resumeListening: utterance.resumeListening};
        utterance = null;
        globalThis.speechSynthesis.cancel();
      }
    } else if (pendingSpeech !== null) {
      const pending = pendingSpeech;
      pendingSpeech = null;
      speakVoice(pending.text, voiceSession, {resumeListening: pending.resumeListening});
    } else listenVoice();
    updateVoiceView();
  }

  function toggleVoiceMute() {
    if (!voiceMode || voicePaused) return;
    voiceMuted = !voiceMuted;
    if (voiceMuted) suspendListening();
    else listenVoice();
    updateVoiceView();
  }

  function clearTurnTimers() {
    if (!voiceTurn) return;
    clearTimeout(voiceTurn.silenceTimer);
    clearTimeout(voiceTurn.restartTimer);
    clearTimeout(voiceTurn.confirmationTimer);
    voiceTurn.silenceTimer = null;
    voiceTurn.restartTimer = null;
    voiceTurn.confirmationTimer = null;
  }

  function sendVoiceTurn(turn) {
    if (voiceTurn !== turn || !voiceMode || turn.session !== voiceSession) return;
    if (turn.interim || !turn.text.trim()) {
      stopVoice('Aucune parole confirmée. Vous pouvez relire la transcription avant de l’envoyer.');
      return;
    }
    clearTurnTimers();
    voiceTurn = null;
    stopDictation();
    finishButton.hidden = true;
    prompt.value = turn.text;
    void sendMessage({preventDefault() {}}, turn.session);
  }

  function finishVoiceTurn() {
    const turn = voiceTurn;
    if (!turn || turn.finishing || !prompt.value.trim()) return;
    clearTurnTimers();
    turn.finishing = true;
    finishButton.disabled = true;
    updateVoiceView();
    turn.confirmationTimer = setTimeout(() => {
      if (voiceTurn === turn && turn.finishing) stopVoice('Chrome ne termine pas la transcription. Votre texte est conservé : relisez-le et envoyez-le depuis le chat.');
    }, 5000);
    if (recognition) {
      // stop() laisse au navigateur le temps de confirmer les derniers mots.
      try { recognition.stop(); }
      catch { stopVoice('Impossible de terminer la transcription. Relisez votre message.'); }
    } else sendVoiceTurn(turn);
  }

  function waitForVoicePause(turn, resultActivity = false) {
    clearTimeout(turn.silenceTimer);
    turn.silenceTimer = null;
    if (turn.finishing || (turn.speaking && !resultActivity)) return;
    turn.silenceTimer = setTimeout(() => {
      if (voiceTurn === turn) finishVoiceTurn();
    }, voiceSilenceMs);
  }
  let disconnected = false;
  const reconnectMessage = 'L’extension a été rechargée ou mise à jour. Rechargez cette page pour reconnecter Maya, puis renvoyez votre message.';

  function stopVoice(message = '') {
    clearTurnTimers();
    voiceTurn = null;
    voiceMode = false;
    voicePaused = false;
    voiceMuted = false;
    pendingSpeech = null;
    voiceSession++;
    const speaking = utterance;
    utterance = null;
    if (speaking) globalThis.speechSynthesis?.cancel();
    stopDictation();
    voiceModeButton.setAttribute('aria-pressed', 'false');
    voiceModeButton.setAttribute('aria-label', 'Lancer l’assistant vocal');
    voiceModeButton.setAttribute('title', 'Lancer l’assistant vocal');
    interruptButton.hidden = true;
    finishButton.hidden = true;
    prompt.disabled = false;
    updateSendButton();
    updateVoiceView();
    status.textContent = disconnected ? reconnectMessage : message;
  }

  function listenVoice() {
    if (!voiceMode || voicePaused || voiceMuted || busy || recognition || utterance) return;
    const session = voiceSession;
    const turn = voiceTurn ||= {session, text: '', interim: false, speaking: false, finishing: false};
    if (turn.finishing) return;
    const prefix = turn.text;
    const SpeechRecognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
    const current = new SpeechRecognition();
    const active = () => recognition === current && voiceTurn === turn && session === voiceSession;
    recognition = current;
    listening = true;
    finishButton.hidden = false;
    finishButton.disabled = !prompt.value.trim();
    voiceButton.setAttribute('aria-pressed', 'true');
    updateSendButton();
    current.lang = 'fr-FR';
    current.continuous = true;
    current.interimResults = true;
    current.onstart = () => {
      if (active()) updateVoiceView();
      if (active()) status.textContent = 'Je vous écoute… Prenez votre temps. Envoi automatique après 5 secondes de pause, ou cliquez sur « J’ai terminé ».';
    };
    current.onspeechstart = () => {
      if (!active() || turn.finishing) return;
      turn.speaking = true;
      clearTimeout(turn.silenceTimer);
      turn.silenceTimer = null;
    };
    current.onspeechend = () => {
      if (!active()) return;
      turn.speaking = false;
      if (prompt.value.trim()) waitForVoicePause(turn);
    };
    current.onresult = event => {
      if (!active()) return;
      const results = Array.from(event.results);
      const confirmed = results.filter(result => result.isFinal).map(result => result[0].transcript).join(' ');
      turn.text = [prefix, confirmed].filter(Boolean).join(' ').slice(0, 4000);
      turn.interim = results.some(result => !result.isFinal);
      // Chrome peut confirmer une phrase sans émettre speechend en mode continu.
      // Une confirmation sans mots provisoires constitue aussi une fin de phrase.
      if (!turn.interim && confirmed.trim()) turn.speaking = false;
      prompt.value = [prefix, results.map(result => result[0].transcript).join(' ')].filter(Boolean).join(' ').slice(0, 4000);
      finishButton.disabled = turn.finishing || !prompt.value.trim();
      root.querySelector('#vocal-transcript').textContent = prompt.value;
      // Les résultats provisoires prouvent aussi une activité récente. Leur absence
      // pendant la pause doit déclencher stop(), qui demande les derniers mots confirmés.
      if (prompt.value.trim()) waitForVoicePause(turn, true);
    };
    current.onerror = event => {
      if (!active()) return;
      // Une absence de nouveaux mots après une phrase ne doit pas couper le tour.
      if (event.error === 'no-speech' && turn.text.trim() && !turn.interim) return;
      stopVoice(event.error === 'no-speech' ?
        'Aucune parole détectée. Relancez la discussion vocale quand vous êtes prêt.' :
        'Micro indisponible ou accès refusé. Vous pouvez écrire ou relancer le mode vocal.');
    };
    current.onend = () => {
      if (!active()) return;
      recognition = null;
      turn.speaking = false;
      if (turn.finishing) { sendVoiceTurn(turn); return; }
      if (turn.interim || !turn.text.trim()) {
        stopVoice('Aucune parole confirmée. Vous pouvez relire la transcription avant de l’envoyer.');
        return;
      }
      // Chrome peut fermer le service malgré continuous=true : conserver le texte
      // et rouvrir l'écoute, sans confondre cette fermeture avec la fin du tour.
      if (!turn.silenceTimer) waitForVoicePause(turn);
      turn.restartTimer = setTimeout(() => {
        if (voiceTurn === turn && voiceMode && session === voiceSession) listenVoice();
      }, 150);
    };
    try { current.start(); }
    catch { stopVoice('Impossible de démarrer le micro. Vous pouvez écrire votre message.'); }
  }

  function speakVoice(text, session, {resumeListening = true} = {}) {
    if (!voiceMode || session !== voiceSession) return;
    if (voicePaused) { pendingSpeech = {text, resumeListening}; updateVoiceView(); return; }
    // Les liens restent consultables à l'écran ; leur URL n'est pas lue à voix haute.
    const spoken = String(text).replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/https?:\/\/\S+/g, '').replace(/[*#`_>]/g, '').trim();
    if (!spoken) { listenVoice(); return; }
    const current = new SpeechSynthesisUtterance(spoken);
    current.resumeListening = resumeListening;
    current.lang = 'fr-FR';
    current.voice = globalThis.speechSynthesis.getVoices().find(voice => voice.lang.startsWith('fr')) || null;
    utterance = current;
    interruptButton.hidden = false;
    updateVoiceView();
    status.textContent = 'Maya vous répond…';
    current.onend = () => {
      if (utterance !== current || session !== voiceSession) return;
      utterance = null;
      interruptButton.hidden = true;
      if (resumeListening) listenVoice();
      else stopVoice('La discussion vocale est arrêtée après cette erreur. Vous pouvez la relancer pour réessayer.');
      updateVoiceView();
    };
    current.onerror = () => {
      if (utterance === current) stopVoice('Lecture audio indisponible. La réponse reste affichée.');
    };
    try { globalThis.speechSynthesis.speak(current); }
    catch { stopVoice('Lecture audio indisponible. La réponse reste affichée.'); }
  }

  function toggleVoiceMode() {
    if (voiceMode) { stopVoice('Discussion vocale arrêtée.'); return; }
    if (busy) return;
    if (!(globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition) ||
        !globalThis.speechSynthesis || !globalThis.SpeechSynthesisUtterance) {
      status.textContent = 'Discussion vocale indisponible dans ce navigateur. Vous pouvez écrire ou utiliser la dictée.';
      return;
    }
    if (prompt.value.trim()) {
      status.textContent = 'Envoyez ou effacez votre message avant de démarrer la discussion vocale.';
      return;
    }
    stopDictation();
    voiceMode = true;
    voiceSession++;
    voiceModeButton.setAttribute('aria-pressed', 'true');
    voiceModeButton.setAttribute('aria-label', 'Quitter le mode vocal');
    voiceModeButton.setAttribute('title', 'Quitter le mode vocal');
    prompt.disabled = true;
    root.querySelector('#vocal-transcript').textContent = '';
    root.querySelector('#vocal-answer').textContent = '';
    updateVoiceView();
    endVoiceButton.focus();
    const session = voiceSession;
    // Restaurer l'historique avant de distinguer un nouveau chat d'une reprise.
    void ready.then(() => {
      if (!voiceMode || session !== voiceSession || disconnected) return;
      const description = CECredit.allowed(location.href) ? CECreditAdapter.screenDescription?.() : null;
      if (description) {
        addMessage('assistant', description);
        root.querySelector('#vocal-answer').textContent = description;
        speakVoice(description, session);
      } else if (!introductionSpoken && !draft && !messages.some(message => message.role === 'user')) {
        introductionSpoken = true;
        root.querySelector('#vocal-answer').textContent = CEPanelView.introduction;
        speakVoice(CEPanelView.introduction, session);
      } else listenVoice();
      updateVoiceView();
    });
  }

  async function relay(action, extra = {}) {
    if (disconnected) throw new Error(reconnectMessage);
    try {
      const response = await chrome.runtime.sendMessage({type: 'ce-draft', action, ...extra});
      if (!response?.ok) throw new Error(response?.error || 'Rechargez la page pour retrouver l’assistant.');
      return response;
    } catch (error) {
      // Après un rechargement dans Chrome, le panneau encore présent dans
      // l'onglet appartient à l'ancien contexte et ne peut plus joindre le worker.
      if (/extension context invalidated/i.test(error?.message || '')) {
        disconnected = true;
        stopVoice(reconnectMessage);
        setBusy(false);
        throw new Error(reconnectMessage);
      }
      throw error;
    }
  }

  function show(question) {
    panel.hidden = false;
    launcher.hidden = true;
    if (typeof question === 'string') prompt.value = question.slice(0, 4000);
    updateSendButton();
    prompt.focus();
  }

  function hide() {
    stopVoice();
    panel.hidden = true;
    launcher.hidden = false;
  }

  function setBusy(value) {
    busy = value;
    root.querySelectorAll('button').forEach(button => { button.disabled = value || disconnected; });
    closeButton.disabled = false;
    voiceModeButton.disabled = disconnected || (value && !voiceMode);
    updateVoiceView();
    updateSendButton();
  }

  function updateSendButton() {
    sendButton.disabled = disconnected || busy || listening || voiceMode || !prompt.value.trim();
  }

  function stopDictation() {
    const current = recognition;
    recognition = null;
    listening = false;
    current?.abort();
    voiceButton.setAttribute('aria-pressed', 'false');
    updateSendButton();
  }

  function toggleDictation() {
    if (voiceMode) return;
    if (busy) return;
    if (listening) {
      recognition.stop();
      return;
    }
    const SpeechRecognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      status.textContent = 'La dictée n’est pas disponible dans ce navigateur. Vous pouvez écrire votre message.';
      prompt.focus();
      return;
    }

    const current = new SpeechRecognition();
    recognition = current;
    const previousText = prompt.value.trim();
    current.lang = 'fr-FR';
    current.interimResults = true;
    current.onstart = () => {
      listening = true;
      voiceButton.setAttribute('aria-pressed', 'true');
      status.textContent = 'Je vous écoute…';
      updateSendButton();
    };
    current.onresult = event => {
      if (recognition !== current) return;
      const transcript = Array.from(event.results).map(result => result[0].transcript).join(' ');
      prompt.value = [previousText, transcript].filter(Boolean).join(' ').slice(0, 4000);
    };
    current.onerror = () => {
      status.textContent = 'La dictée est indisponible ou refusée. Vous pouvez écrire votre message.';
    };
    current.onend = () => {
      if (recognition !== current) return;
      recognition = null;
      listening = false;
      voiceButton.setAttribute('aria-pressed', 'false');
      if (status.textContent === 'Je vous écoute…') status.textContent = 'Relisez votre message avant de l’envoyer.';
      updateSendButton();
    };
    try {
      current.start();
    } catch {
      stopDictation();
      status.textContent = 'Impossible de démarrer la dictée. Vous pouvez écrire votre message.';
    }
  }

  function appendSources(item, sources) {
    const links = document.createElement('div');
    links.className = 'sources';
    for (const source of sources) {
      try {
        const url = new URL(source.url);
        if (url.protocol !== 'https:') continue;
        const link = document.createElement('a');
        link.href = url.href;
        link.textContent = source.titre || url.hostname;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        links.append(link);
      } catch {
        // Une source invalide ne doit pas interrompre la conversation.
      }
    }
    item.append(links);
  }

  function appendDraft(item, proposal) {
    const preview = document.createElement('p');
    if (proposal.parcours === 'credit_immobilier') {
      const values = CECredit.fields.filter(field => proposal.champs[field.key] != null)
        .map(field => field.label + ' : ' + String(proposal.champs[field.key]));
      preview.textContent = proposal.resume + '\n\n' + values.join('\n');
    }
    const situation = proposal.particulier ? 'Particulier' : 'Professionnel';
    if (proposal.parcours !== 'credit_immobilier') preview.textContent = `${proposal.objet}\n\n${proposal.message}\n\nRéponse : ${proposal.canal} · ${situation}`;
    const identity = [proposal.civilite, proposal.prenom, proposal.nom].filter(Boolean).join(' ');
    const contact = [identity, proposal.email, proposal.telephone].filter(Boolean).join(' · ');
    if (contact) preview.textContent += '\n\nCoordonnées à vérifier : ' + contact;
    item.append(preview);

    if (proposal.parcours === 'credit_immobilier') return;

    const button = document.createElement('button');
    button.className = 'primary';
    button.textContent = 'Remplir et continuer';
    button.onclick = () => applyDraft(proposal);
    item.append(button);
  }

  function addMessage(role, text, sources = [], proposal = null) {
    welcome.hidden = true;
    const item = document.createElement('div');
    item.className = 'bubble' + (role === 'user' ? ' user' : '');
    const body = document.createElement('div');
    if (role === 'assistant') CEMarkdown.render(body, text);
    else body.textContent = text;
    item.append(body);
    appendSources(item, sources);
    if (proposal) appendDraft(item, proposal);
    chat.append(item);
    conversation.scrollTop = conversation.scrollHeight;
    return item;
  }

  function offerFormLink(proposal) {
    const item = addMessage('assistant', 'Ouvrez le formulaire pour utiliser ce brouillon.');
    const link = document.createElement('a');
    link.textContent = ' Ouvrir le formulaire';
    link.href = proposal?.parcours === 'credit_immobilier' ? CECredit.entryFor(proposal) :
      'https://www.caisse-epargne.fr/formulaire/contact/auth-generic?form=reclam&bank=13135';
    item.append(link);
  }

  async function applyDraft(proposal = draft, spokenSession = null, options = {}) {
    if (busy || !proposal) return null;
    const continueVoice = spokenSession !== null && voiceMode && spokenSession === voiceSession;
    if (continueVoice) suspendListening();
    else stopVoice();
    setBusy(true);
    status.textContent = 'Je remplis le formulaire…';
    const mortgage = proposal.parcours === 'credit_immobilier';
    let navigating = false;
    let finalMessage = null;
    try {
      await relay('save', {draft: proposal, ...(mortgage ? {autoFill: true} : {})});
      draft = proposal;
      if (!(mortgage ? CECredit.allowed(location.href) : CE.allowed(location.href))) {
        if (mortgage) {
          const destination = CECredit.entryFor(proposal);
          if (!CECredit.allowed(destination)) throw new Error('Destination du parcours immobilier invalide.');
          location.assign(destination);
          navigating = true;
          return;
        }
        offerFormLink(proposal);
        return;
      }
      const result = await (mortgage ? CECreditAdapter.complete(proposal, options) : CEAdapter.complete(proposal));
      let message = result.message;
      if (mortgage && result.reason === 'missing_fields') {
        const orientation = CECredit.missingPrompt(result.missing);
        message = orientation;
        await relay('save', {draft: proposal, autoFill: false});
        status.textContent = 'Maya prépare la prochaine question…';
        try {
          const response = await relay('explain', {missing: result.missing});
          if (typeof response.message === 'string' && response.message.trim()) {
            // Le modèle enrichit l'échange ; le catalogue garantit le repère vocal.
            message = response.message.trim() === orientation ? orientation : orientation + '\n\n' + response.message.trim();
          }
        } catch {} // Garder une indication locale si le modèle est indisponible.
      }
      if (mortgage) {
        finalMessage = message;
        if (messages.at(-1)?.role === 'assistant') messages.pop();
        messages.push({role: 'assistant', content: message});
      }
      addMessage('assistant', message);
    } catch (error) {
      finalMessage = error.message;
      addMessage('assistant', error.message);
    } finally {
      if (mortgage && !navigating && !disconnected) {
        try { await relay('save', {draft: proposal, autoFill: false, ...(finalMessage ? {message: finalMessage} : {})}); } catch {}
      }
      setBusy(false);
      status.textContent = disconnected ? reconnectMessage : '';
    }
    return finalMessage;
  }

  async function restoreDraft() {
    try {
      const result = await relay('load');
      draft = result.draft || null;
      messages = result.messages || [];
      const pending = draft?.parcours === 'credit_immobilier' && result.autoFill === true;
      for (const [index, message] of messages.entries()) {
        if (pending && index === messages.length - 1 && message.role === 'assistant') continue;
        addMessage(message.role, message.content);
      }
      if (draft && draft.parcours !== 'credit_immobilier') addMessage('assistant', 'Votre brouillon est disponible.', [], draft);
      if (draft?.parcours === 'credit_immobilier' && result.autoFill === true && CECredit.allowed(location.href)) {
        await applyDraft(draft);
      }
    } catch (error) {
      status.textContent = error.message;
    }
  }
  const ready = restoreDraft();

  function isContinueCommand(text) {
    const normalized = CE.normalize(text);
    if (normalized.length > 200 || /[?？]/.test(text)) return false;
    // Une phrase complète d’accord est une commande ; une négation, question
    // ou demande de modification ne correspond pas à cette grammaire bornée.
    return /^(?:(?:oui|ok|d accord|c est tres bien|c est bien|tres bien|parfait|merci|alors) )*(?:(?:tu peux|vous pouvez|on peut|je veux|je souhaite|je voudrais|on) )?(?:suivant|continue|continuer|continuons|passe a l etape suivante|passer a l etape suivante|passons a l etape suivante)(?: (?:s il te plait|s il vous plait|merci))*$/.test(normalized);
  }

  function isLocalCommand(text) {
    return isContinueCommand(text) || /^(remplis|remplir|remplis le formulaire|remplir le formulaire)[.! ]*$/i.test(text);
  }

  async function sendMessage(event, spokenSession = null) {
    event.preventDefault();
    if (disconnected || busy || listening || !prompt.value.trim()) return;
    await ready;
    if (spokenSession !== null && (!voiceMode || spokenSession !== voiceSession)) return;
    if (disconnected || busy || listening || !prompt.value.trim()) return;
    const text = prompt.value.trim();
    prompt.value = '';
    addMessage('user', text);
    if (spokenSession !== null) root.querySelector('#vocal-answer').textContent = '';

    // Les commandes de navigation restent locales, sans nouvel appel au modèle.
    const localDraft = draft || (CECredit.allowed(location.href) && CECreditAdapter.screenDescription?.() ?
      {parcours: 'credit_immobilier', resume: 'Projet à compléter', champs: {}} : null);
    if (isLocalCommand(text) && localDraft) {
      if (spokenSession !== null && localDraft.parcours !== 'credit_immobilier') {
        addMessage('assistant', 'Relisez la fiche puis cliquez sur « Remplir et continuer » pour valider le préremplissage.');
        speakVoice('Relisez la fiche puis cliquez sur Remplir et continuer pour valider le préremplissage.', spokenSession);
        return;
      }
      const answer = await applyDraft(localDraft, spokenSession, {continueSummary: isContinueCommand(text)});
      if (answer && spokenSession !== null) {
        root.querySelector('#vocal-answer').textContent = answer;
        speakVoice(answer, spokenSession);
      }
      return;
    }

    setBusy(true);
    status.textContent = 'L’assistant prépare sa réponse…';
    const nextMessages = [...messages, {role: 'user', content: text}].slice(-20);
    let spokenAnswer = null;
    let failedAnswer = false;
    let automaticDraft = null;
    try {
      const siteFields = CECredit.allowed(location.href) ? CECreditAdapter.read?.() : CEAdapter.read?.();
      const response = await relay('chat', {messages: nextMessages, ...(siteFields ? {siteFields} : {})});
      messages = [...nextMessages, {role: 'assistant', content: response.message}].slice(-20);
      const proposal = response.fiche_credit_immobilier || response.fiche_reclamation;
      if (proposal) {
        draft = proposal;
        await relay('save', {draft});
        if (proposal.parcours === 'credit_immobilier') automaticDraft = proposal;
      }
      if (!automaticDraft) addMessage('assistant', response.message, response.sources, proposal);
      spokenAnswer = response.message;
      if (spokenSession !== null) root.querySelector('#vocal-answer').textContent = response.message;
    } catch (error) {
      addMessage('assistant', error.message);
      if (disconnected) prompt.value = text; // Garder le message pour le copier avant de recharger.
      if (spokenSession !== null && spokenSession === voiceSession && !disconnected) {
        spokenAnswer = error.message;
        failedAnswer = true;
        root.querySelector('#vocal-answer').textContent = spokenAnswer;
      }
    } finally {
      setBusy(false);
      if (disconnected) status.textContent = reconnectMessage;
      else if (spokenSession === null) status.textContent = '';
    }
    if (automaticDraft && !disconnected) {
      spokenAnswer = await applyDraft(automaticDraft, spokenSession);
      if (spokenAnswer && spokenSession !== null) root.querySelector('#vocal-answer').textContent = spokenAnswer;
    }
    if (spokenAnswer !== null && spokenSession !== null) speakVoice(spokenAnswer, spokenSession, {resumeListening: !failedAnswer});
  }

  async function resetConversation() {
    if (busy) return;
    await ready;
    stopVoice();
    prompt.value = '';
    try {
      await relay('clear');
      messages = [];
      introductionSpoken = false;
      draft = null;
      chat.replaceChildren();
      welcome.hidden = false;
      status.textContent = '';
    } catch (error) {
      status.textContent = error.message;
    }
  }

  globalThis.CEPanel = {show};
  launcher.onclick = () => show();
  closeButton.onclick = hide;
  resetButton.onclick = resetConversation;
  voiceButton.onclick = toggleDictation;
  voiceModeButton.onclick = toggleVoiceMode;
  muteButton.onclick = toggleVoiceMute;
  pauseButton.onclick = toggleVoicePause;
  endVoiceButton.onclick = () => { stopVoice('Conversation vocale terminée. Retrouvez vos échanges dans le chat.'); prompt.focus(); };
  finishButton.onclick = finishVoiceTurn;
  interruptButton.onclick = () => {
    if (!voiceMode || !utterance) return;
    utterance = null;
    globalThis.speechSynthesis.cancel();
    interruptButton.hidden = true;
    listenVoice();
    updateVoiceView();
  };
  exampleButton.onclick = () => show('Je souhaite comprendre des frais prélevés sur mon compte.');
  prompt.addEventListener('input', updateSendButton);
  prompt.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    if (event.repeat || disconnected || busy || listening || !prompt.value.trim()) return;
    composer.requestSubmit(sendButton);
  });
  composer.onsubmit = sendMessage;
  updateSendButton();
  updateVoiceView();
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      hide();
      launcher.focus();
    }
  });
  globalThis.addEventListener?.('pagehide', () => stopVoice(), {once: true});
})();
