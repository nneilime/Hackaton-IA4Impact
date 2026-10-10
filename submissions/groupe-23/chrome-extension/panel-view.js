/* Maquettes Figma 99:14401 (vocal) et 14:224 : rendu du chat. La conversation reste dans panel.js. */
(() => {
  const introduction = 'Bonjour, je suis Maya, votre assistante bancaire IA. Je vous aide à préciser votre besoin et à préparer votre démarche. Donnez-moi un maximum d’informations sur votre projet. Pour un crédit immobilier, indiquez si possible le bien recherché et sa localisation, le prix ou le montant à financer, votre apport, la durée souhaitée, votre situation professionnelle, vos revenus et vos crédits en cours, ainsi que la présence éventuelle d’un co-emprunteur. Vous pouvez répondre avec les informations que vous connaissez et compléter ensuite. Quel est votre projet ?';

  function create() {
    const host = document.createElement('div');
    host.id = 'ia-impact-assistant';
    host.style.cssText = [
      'all:initial!important',
      'position:fixed!important',
      'inset:0 0 0 auto!important',
      'width:min(498px,100vw)!important',
      'pointer-events:none!important',
      'z-index:2147483647!important'
    ].join(';');
    document.documentElement.append(host);
    const root = host.attachShadow({mode: 'closed'});
    const asset = name => chrome.runtime.getURL(`assets/${name}`);

    root.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; }
        [hidden] { display: none !important; }
        button, textarea { font: inherit; }
        button { cursor: pointer; }
        button:disabled { cursor: default; }
        button:focus-visible, textarea:focus-visible, a:focus-visible {
          outline: 2px solid #2fa45b;
          outline-offset: 3px;
        }

        .panel {
          --surface: #f6f4f4;
          --ink: #242424;
          --muted: #686868;
          --border: #e2dfdf;
          pointer-events: auto;
          display: flex;
          flex-direction: column;
          width: 100%;
          height: 100dvh;
          border-top: 4px solid #d20a11;
          font: 12px Arial, sans-serif;
          color: var(--ink);
          background: var(--surface);
          box-shadow: -8px 0 12px rgb(0 0 0 / 7%);
        }
        .header {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-shrink: 0;
          height: 108px;
          padding: 15px 22px;
          border-bottom: 0.8px solid var(--border);
          background: white;
        }
        .identity { display: flex; align-items: center; gap: 11px; }
        .avatar {
          position: relative;
          display: grid;
          place-items: center;
          flex-shrink: 0;
          border-radius: 50%;
          background: #202020;
        }
        .avatar-small { width: 43px; height: 43px; }
        .presence {
          position: absolute;
          top: 32px;
          left: 32px;
          width: 10px;
          height: 10px;
          border: 1.6px solid white;
          border-radius: 50%;
          background: #2fa45b;
        }
        .identity strong { display: block; font-size: 15px; line-height: 22.5px; }
        .subtitle { display: block; margin-top: 3px; font-size: 10px; line-height: 15px; color: #6c6c6c; }
        .availability { display: flex; align-items: center; gap: 6px; font-size: 10px; line-height: 15px; color: #666; }
        .availability::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: #2fa45b; }
        .header-actions { position: absolute; top: 6px; right: 12px; display: flex; gap: 5px; }
        .header-actions button { border: 0; padding: 3px 5px; color: #777; background: transparent; font-size: 14px; }

        .conversation { flex: 1; min-height: 0; overflow: auto; padding: 22px; }
        .welcome { min-height: 100%; display: flex; align-items: center; justify-content: center; }
        .welcome-content { width: 100%; max-width: 320px; text-align: center; }
        .avatar-large { width: 60px; height: 60px; margin: 0 auto 20px; box-shadow: 0 8px 11px rgb(0 0 0 / 14%); }
        .eyebrow { margin: 0; font-size: 10px; font-weight: bold; line-height: 15px; letter-spacing: 1.5px; color: #777; text-transform: uppercase; }
        h2 { margin: 8px 0 10px; font-weight: normal; font-size: 23px; line-height: 34.5px; }
        .intro { max-width: 302px; margin: 0 auto; color: var(--muted); font-size: 12px; line-height: 18.6px; }
        .suggestion { max-width: 302px; margin: 24px auto 0; padding-top: 18px; border-top: 0.8px solid #ddd8d8; }
        .suggestion-label { margin: 0 0 9px; font-size: 9px; line-height: 13.5px; letter-spacing: 1.08px; text-transform: uppercase; color: #898989; }
        .example { width: 100%; min-height: 57.5px; padding: 11.6px 14px; border: 0.8px solid #e2dede; border-radius: 2px; background: white; box-shadow: 0 2px 4px rgb(0 0 0 / 5%); color: #4b4b4b; font-size: 11px; line-height: 15.95px; font-style: italic; }
        .bubble { padding: 14px 16px; margin-bottom: 14px; border: 0.8px solid var(--border); border-radius: 3px; background: white; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
        .message-markdown { white-space: normal; }
        .message-markdown p, .message-markdown ul, .message-markdown ol, .message-markdown h3, .message-markdown pre { margin: 0 0 12px; }
        .message-markdown > :last-child { margin-bottom: 0; }
        .message-markdown ul, .message-markdown ol { padding-left: 24px; }
        .message-markdown li { margin-bottom: 6px; }
        .message-markdown h3 { font-size: 1em; line-height: inherit; }
        .message-markdown code { font-family: monospace; font-size: .9em; background: #f0eeee; border-radius: 3px; padding: 1px 4px; }
        .message-markdown pre { white-space: pre-wrap; padding: 10px; background: #f0eeee; }
        .message-markdown pre code { padding: 0; }
        .message-markdown a { color: inherit; text-decoration: underline; }
        .bubble.user { width: fit-content; max-width: calc(100% - 32px); margin-left: auto; padding: 11px 13px; border: 0; border-radius: 12px 2px 12px 12px; background: #292929; color: white; font-size: 11px; line-height: 17.05px; box-shadow: 0 1px 2px rgb(0 0 0 / 7%); }
        .sources a { display: block; margin-top: 8px; color: #555; font-size: 10px; }
        .primary { margin-top: 10px; border: 0; border-radius: 3px; background: #202020; color: white; padding: 11px 14px; font-size: 12px; }
        .primary:disabled { opacity: 0.5; }
        #status { margin: 0; padding: 0 22px; color: var(--muted); line-height: 18px; font-size: 10px; }
        #status:empty { display: none; }
        #status:not(:empty) { padding-bottom: 10px; }

        .composer { flex-shrink: 0; padding: 14px 20px 15px; border-top: 0.8px solid #dedada; background: white; }
        .input-box { display: flex; align-items: flex-end; gap: 5px; height: 65px; min-height: 65px; padding: 8px; border: 0.8px solid #c9c9c9; border-radius: 3px; }
        textarea { flex: 1; min-width: 0; height: 46px; resize: none; padding: 3px 6px; border: 0; background: white; color: var(--ink); font-size: 11px; line-height: 15.4px; }
        textarea::placeholder { color: #999; }
        .input-actions { display: flex; gap: 5px; align-items: center; }
        .icon-button { display: grid; place-items: center; flex-shrink: 0; width: 34px; height: 34px; padding: 0; border-radius: 50%; }
        .voice { border: 0.8px solid #d5d5d5; background: white; }
        .voice[aria-pressed='true'] { border-color: #2fa45b; background: #e8f4ec; }
        .sound-bars { display: flex; align-items: center; gap: 2px; width: 14px; height: 17px; transform: translate(-.2px, -1.5px); }
        .sound-bars span { flex-shrink: 0; width: 2px; border-radius: 2px; background: #d20a11; }
        .sound-bars span:nth-child(1) { height: 6px; }
        .sound-bars span:nth-child(2), .sound-bars span:nth-child(4) { height: 11px; }
        .sound-bars span:nth-child(3) { height: 17px; }
        .icon-button:disabled { opacity: .5; }
        .send:disabled { opacity: 1; }
        .send { border: 0; background: #202020; }
        .send:disabled { background: #d8d8d8; }
        .disclosure { margin: 7px 0 0; color: #767676; font-size: 10px; line-height: 15px; }
        .disclosure summary { cursor: pointer; }
        .disclosure p { margin: 7px 0 0; }
        #voice-disclosure { margin: 7px 0 0; padding: 0; color: var(--muted); font-size: 10px; line-height: 15px; }
        .panel[data-voice='true'] { --surface: #f7f7f6; --border: #e5e4e1; border-top: 0; }
        .panel[data-voice='true'] > .header,
        .panel[data-voice='true'] > .conversation,
        .panel[data-voice='true'] > .composer { display: none; }
        .vocal-screen { flex: 1; min-height: 0; overflow: auto; font: 14px/1.6 Ubuntu, Arial, sans-serif; }
        .vocal-header { padding: 20px; border-bottom: 1px solid var(--border); }
        .vocal-identity { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .vocal-identity strong { font-size: 40px; line-height: 1; }
        .vocal-badge { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 100px; background: white; font-weight: bold; line-height: 1; }
        .vocal-header p { margin: 14px 0 0; color: #666; }
        .vocal-context { display: flex; align-items: center; gap: 14px; padding: 24px 20px 0; }
        .vocal-project { display: grid; place-items: center; flex-shrink: 0; width: 48px; height: 48px; border: 1px solid var(--border); border-radius: 16px; background: white; }
        .vocal-context strong { font: bold 17px/1.45 Arial, sans-serif; }
        .vocal-context p { margin: 4px 0 0; color: #666; }
        .vocal-presence { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 24px 20px; text-align: center; }
        .vocal-orb-slot { position: relative; width: 100%; height: 261px; overflow: hidden; }
        .vocal-orb, .vocal-halo { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); }
        .vocal-orb { width: 261px; height: 261px; border-radius: 50%; background: radial-gradient(circle closest-side, #fffafa 0%, #ffe0e5 42%, #ff9eaa 53.5%, #ff7d8c 59.25%, #ff5c6e 65%, #f44857 68.5%, #e83340 72%, #dd1f29 75.5%, #d10a12 79%, rgb(215 27 36 / .98137) 80.125%, rgb(221 45 54 / .96275) 81.25%, rgb(232 79 90 / .92549) 83.5%, rgb(244 114 125 / .88824) 85.75%, rgb(255 148 161 / .85098) 88%, rgb(255 229 232 / 0) 100%); animation: kf_99_14420_scale_0 12s linear infinite; }
        .vocal-halo { width: 350px; height: 269px; display: grid; place-items: center; animation: kf_99_14419_scale_0 12s linear infinite; }
        @keyframes kf_99_14420_scale_0 { 0%, 33.333%, 66.667% { animation-timing-function: ease-in-out; scale: 1 1; } 16.667%, 50%, 83.333% { animation-timing-function: ease-in-out; scale: 1.035 1.035; } 100% { scale: 1 1; } }
        @keyframes kf_99_14419_scale_0 { 0%, 33.333%, 66.667% { animation-timing-function: ease-in-out; scale: 1 1; } 16.667%, 50%, 83.333% { animation-timing-function: ease-in-out; scale: 1.07 1.07; } 100% { scale: 1 1; } }
        .vocal-screen[data-state='paused'] .vocal-orb, .vocal-screen[data-state='paused'] .vocal-halo,
        .vocal-screen[data-state='muted'] .vocal-orb, .vocal-screen[data-state='muted'] .vocal-halo { animation-play-state: paused; opacity: .5; }
        .vocal-presence h2 { margin: 0; font-size: 32px; font-weight: bold; line-height: 1.2; }
        .vocal-presence p { margin: 0; color: #666; }
        .vocal-microphone { display: flex; align-items: center; gap: 8px; color: #d20a11; font-weight: bold; }
        .vocal-transcript, .vocal-answer { width: 100%; overflow-wrap: anywhere; white-space: pre-wrap; font-size: 14px; }
        .vocal-presence .vocal-transcript { color: #666; }
        .vocal-presence .vocal-answer { color: var(--ink); }
        .vocal-transcript:empty, .vocal-answer:empty { display: none; }
        .vocal-actions { display: flex; flex-direction: column; gap: 12px; padding: 0 20px 24px; }
        .vocal-actions button { display: flex; align-items: center; justify-content: center; gap: 12px; min-height: 52px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 8px; background: white; color: var(--ink); font-weight: bold; line-height: 1; }
        .vocal-actions #voice-pause { background: #d20a11; border-color: #d20a11; color: white; }
        .vocal-actions p { text-align: center; color: #666; margin: 0; }
        .vocal-footer { border-top: 1px solid var(--border); padding: 20px; color: #666; }
        .vocal-footer > div { display: flex; gap: 10px; align-items: flex-start; }
        .vocal-footer img { flex-shrink: 0; }
        .vocal-footer p { margin: 12px 0 0; text-align: center; }
        .vocal-footer details { margin-top: 12px; font-size: 12px; }
        .vocal-footer summary { cursor: pointer; }
        @media (prefers-reduced-motion: reduce) { .vocal-orb, .vocal-halo { animation: none; } }
        .launcher { position: absolute; right: 22px; bottom: 22px; display: flex; align-items: center; gap: 10px; pointer-events: auto; border: 0; border-radius: 24px; background: #202020; color: white; padding: 13px 18px; box-shadow: 0 6px 24px rgb(0 0 0 / 14%); font: 13px Arial, sans-serif; }
        @media (max-width: 360px) { .header { padding-inline: 16px; } .availability { font-size: 9px; } .conversation { padding: 16px; } h2 { font-size: 21px; } }
      </style>

      <button class="launcher" aria-label="Ouvrir Maya, votre assistante">
        <img src="${asset('chat-spark-small.svg')}" width="21" height="21" alt="">
        Discuter avec Maya
      </button>
      <section class="panel" hidden role="dialog" aria-label="Maya — assistante bancaire">
        <header class="header">
          <div class="identity">
            <div class="avatar avatar-small">
              <img src="${asset('chat-spark-small.svg')}" width="21" height="21" alt="">
              <span class="presence" aria-hidden="true"></span>
            </div>
            <div><strong>Maya</strong><span class="subtitle">Votre assistante bancaire IA</span></div>
          </div>
          <span class="availability">Disponible</span>
          <div class="header-actions">
            <button id="reset" type="button" aria-label="Nouvelle discussion" title="Nouvelle discussion">↻</button>
            <button id="close" type="button" aria-label="Réduire l’assistant" title="Réduire">−</button>
          </div>
        </header>

        <div class="conversation">
          <div id="welcome" class="welcome">
            <div class="welcome-content">
              <div class="avatar avatar-large">
                <img src="${asset('chat-spark-large.svg')}" width="28" height="28" alt="">
              </div>
              <p class="eyebrow">Bienvenue, je suis Maya</p>
              <h2>Parlez-moi de votre projet</h2>
              <p class="intro">${introduction}</p>
              <div class="suggestion">
                <p class="suggestion-label">Par exemple</p>
                <button id="example" class="example" type="button">« Je souhaite comprendre des frais prélevés sur mon compte. »</button>
              </div>
            </div>
          </div>
          <div id="chat" role="log" aria-live="polite" aria-label="Conversation"></div>
        </div>
        <section id="vocal-screen" class="vocal-screen" hidden aria-label="Maya Vocal">
          <header class="vocal-header">
            <div class="vocal-identity"><strong>Maya</strong><span class="vocal-badge"><img src="${asset('vocal-wave.svg')}" width="22" height="22" alt="">100 % vocal</span></div>
            <p id="vocal-subtitle">Votre assistante crédit IA</p>
          </header>
          <div class="vocal-context"><span class="vocal-project"><img src="${asset('vocal-home.svg')}" width="22" height="22" alt=""></span><div><strong id="vocal-project-title">Votre projet immobilier</strong><p id="vocal-project-description">Mon besoin · Parlons de votre financement</p></div></div>
          <div class="vocal-presence">
            <div class="vocal-orb-slot" aria-hidden="true"><div class="vocal-orb" data-node-id="99:14420"></div><div class="vocal-halo" data-node-id="99:14419"><img src="${asset('vocal-halo.svg')}" width="350" height="261" alt=""></div></div>
            <h2 id="vocal-title" aria-live="polite">Maya vous écoute</h2>
            <p id="vocal-description">Parlez-moi de votre projet immobilier. Prenez votre temps, je suis là pour vous.</p>
            <div class="vocal-microphone"><img src="${asset('vocal-microphone.svg')}" width="22" height="22" alt=""><span id="vocal-microphone-state" role="status">Microphone activé</span></div>
            <p id="vocal-transcript" class="vocal-transcript" aria-label="Votre transcription"></p>
            <p id="vocal-answer" class="vocal-answer" aria-label="Réponse de Maya"></p>
          </div>
          <div class="vocal-actions">
            <button id="voice-mute" type="button" aria-pressed="false"><img src="${asset('vocal-mute.svg')}" width="22" height="22" alt=""><span id="voice-mute-label">Couper le micro</span></button>
            <button id="voice-pause" type="button" aria-pressed="false"><img src="${asset('vocal-pause.svg')}" width="22" height="22" alt=""><span id="voice-pause-label">Mettre en pause</span></button>
            <button id="voice-end" type="button"><img src="${asset('vocal-end.svg')}" width="22" height="22" alt="">Terminer la conversation</button>
            <button id="voice-finish" type="button" hidden>J’ai terminé</button>
            <button id="voice-interrupt" type="button" hidden>Interrompre Maya</button>
            <p>En pause, Maya ne vous écoute plus.</p>
          </div>
          <footer class="vocal-footer">
            <div><img src="${asset('vocal-shield.svg')}" width="22" height="22" alt=""><span>Vos transcriptions suivent les échanges du chat.</span></div>
            <p id="vocal-credit-notice">Un crédit vous engage et doit être remboursé.</p>
            <details><summary>Microphone et confidentialité</summary><p>Chrome peut transmettre l’audio à son service de transcription. Les paroles confirmées sont envoyées à n8n après 5 secondes de pause, ou avec « J’ai terminé ». Aucun fichier audio n’est conservé par l’extension. Utilisez des données fictives pour la démonstration.</p></details>
          </footer>
        </section>
        <p id="status" role="status"></p>

        <form id="composer" class="composer">
          <div class="input-box">
            <textarea id="prompt" maxlength="4000" placeholder="Décrivez votre besoin…" aria-label="Votre message" title="Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne" required></textarea>
            <div class="input-actions">
              <button id="voice" class="icon-button voice" type="button" aria-label="Dicter votre message" aria-pressed="false" title="Dicter votre message">
                <img src="${asset('chat-microphone.svg')}" width="16" height="16" alt="">
              </button>
              <button id="voice-mode" class="icon-button voice" type="button" aria-label="Lancer l’assistant vocal" title="Lancer l’assistant vocal" aria-pressed="false" aria-describedby="voice-disclosure" data-node-id="59:206">
                <span class="sound-bars" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
              </button>
              <button id="send" class="icon-button send" type="submit" aria-label="Envoyer le message" title="Envoyer" disabled>
                <img src="${asset('chat-send.svg')}" width="16" height="16" alt="">
              </button>
            </div>
          </div>
          <details class="disclosure">
            <summary>Vos échanges et le microphone</summary>
            <p>À l’envoi, vos messages et les champs reconnus du formulaire sont transmis à l’assistant n8n. Vous validez l’envoi final sur le site.</p>
            <p id="voice-disclosure">En mode vocal, vos paroles sont envoyées après 5 secondes de pause, ou avec « J’ai terminé ». Chrome peut transmettre l’audio à son service de transcription. Maya répond à voix haute, puis le micro se rouvre. Utilisez des données fictives pour la démonstration.</p>
          </details>
        </form>
      </section>
    `;
    return root;
  }
  globalThis.CEPanelView = {create, introduction};
})();
