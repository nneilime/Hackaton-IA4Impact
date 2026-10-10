/* Carte Figma 12:59, intégrée au contenu public sans modifier ses formulaires. */
(() => {
  function isHomePage() {
    if (!CE.siteAllowed(location.href)) return false;
    const path = new URL(location.href).pathname.replace(/\/$/, '') || '/';
    return ['/', '/midi-pyrenees'].includes(path);
  }
  if (!isHomePage() || globalThis.CESearch) return;
  const host = document.createElement('div');
  host.id = 'ia-impact-search';
  const baseStyle = 'all:initial!important;display:block!important;position:relative!important;z-index:10!important;width:min(802px,calc(100% - 32px))!important;';
  const root = host.attachShadow({mode: 'closed'});
  root.innerHTML = `
    <style>
      :host{all:initial}*{box-sizing:border-box}
      .card{background:#fff;color:#242424;font-family:Barlow,"Arial Narrow",Arial,sans-serif;padding:29px 34px 24px;box-shadow:0 18px 27.5px #1c1c1c24}
      .heading{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
      .eyebrow{margin:0;color:#d20a11;font-size:13px;font-weight:700;line-height:19.5px;letter-spacing:1.04px;text-transform:uppercase}
      h2{margin:4px 0 0;font-size:27px;font-weight:400;line-height:29.7px;letter-spacing:-.6px}
      .badge{flex:none;background:#f6ebeb;color:#d20a11;border-radius:99px;padding:6px 11px;font-size:12px;font-weight:600;line-height:18px}
      form{display:flex;align-items:center;min-height:62px;margin-top:20px;border:.8px solid #aaa8a5;background:#fff}
      .search-icon{margin-left:17px;flex:none;display:block}
      input{font:400 17px Barlow,"Arial Narrow",Arial,sans-serif;color:#242424;flex:1;min-width:0;width:100%;height:60px;border:0;background:transparent;padding:0 8px}
      input::placeholder{color:#898784;opacity:1}
      button{font-family:inherit;cursor:pointer}
      .voice{display:flex;align-items:center;justify-content:center;gap:9px;flex:none;min-width:78px;height:46px;padding:0 13px;margin-right:8px;border:.8px solid #d4d2cf;border-radius:99px;background:#f6f5f3}
      .bars{display:flex;align-items:center;gap:2px;height:22px}.bars i{display:block;width:2px;height:11px;border-radius:2px;background:#d20a11}.bars i:first-child{height:6px}.bars i:nth-child(3){height:17px}
      .voice[aria-pressed=true]{background:#f6ebeb;border-color:#d20a11}
      .submit{display:flex;align-items:center;justify-content:center;gap:18px;align-self:stretch;min-width:161px;padding:0 20px;background:#d20a11;color:white;border:0;font-size:16px;font-weight:700;line-height:24px}
      .arrow{font-size:20px;line-height:30px}.hint{margin:14px 0 0;font-size:13px;line-height:19.5px;color:#6b6865}
      :focus-visible{outline:3px solid #565452;outline-offset:3px}input:focus-visible{outline-offset:-3px}
      @media(max-width:720px){.heading{align-items:flex-start;flex-direction:column;gap:12px}.card{padding:24px}h2{font-size:24px;line-height:28px}.badge{align-self:flex-start}}
      @media(max-width:480px){form{flex-wrap:wrap}.submit{width:100%;min-height:48px}.search-icon{margin-left:10px}.voice{min-width:60px;padding:0 8px;margin-right:6px;gap:5px}input{font-size:16px}.card{padding:20px 16px}}
    </style>
    <section class="card" aria-labelledby="search-title">
      <div class="heading"><div><p class="eyebrow">Comment pouvons-nous vous aider ?</p><h2 id="search-title">Trouvez une réponse en quelques mots</h2></div><span class="badge">Recherche intelligente</span></div>
      <form role="search">
        <img class="search-icon" src="${chrome.runtime.getURL('assets/search.svg')}" alt="" width="21" height="21">
        <input type="search" aria-label="Votre question à l’assistant" placeholder="Ex. Comment ouvrir un compte pour mon enfant ?" maxlength="4000" required>
        <button class="voice" type="button" aria-label="Dicter votre question" aria-pressed="false"><img src="${chrome.runtime.getURL('assets/microphone.svg')}" alt="" width="21" height="21"><span class="bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span></button>
        <button class="submit" type="submit">Rechercher <span class="arrow" aria-hidden="true">→</span></button>
      </form>
      <p class="hint" role="status" aria-live="polite">Vous pouvez aussi essayer la recherche vocale.</p>
    </section>`;
  const input = root.querySelector('input'), voice = root.querySelector('.voice'), hint = root.querySelector('.hint');
  let recognition = null;
  root.querySelector('form').onsubmit = event => {
    event.preventDefault();
    if (!input.value.trim()) { input.focus(); return; }
    recognition?.stop();
    if (!globalThis.CEPanel) { hint.textContent = 'Rechargez la page pour ouvrir l’assistant.'; return; }
    CEPanel.show(input.value.trim());
    hint.textContent = 'Votre question est prête dans l’assistant. Relisez-la avant de l’envoyer.';
  };
  voice.onclick = () => {
    if (recognition) { recognition.stop(); return; }
    const Recognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
    if (!Recognition) { hint.textContent = 'La recherche vocale n’est pas disponible dans ce navigateur. Saisissez votre question.'; input.focus(); return; }
    const current = new Recognition(); recognition = current;
    current.lang = 'fr-FR'; current.interimResults = false; current.maxAlternatives = 1;
    current.onstart = () => { voice.setAttribute('aria-pressed', 'true'); voice.setAttribute('aria-label', 'Arrêter la dictée'); hint.textContent = 'Écoute en cours. La dictée peut être traitée par le service vocal du navigateur. Cliquez à nouveau pour arrêter.'; };
    current.onresult = event => { input.value = Array.from(event.results, result => result[0].transcript).join(' ').slice(0, 4000); hint.textContent = 'Relisez la dictée, puis cliquez sur Rechercher.'; input.focus(); };
    current.onerror = () => { hint.textContent = 'Dictée indisponible ou microphone refusé. Vous pouvez saisir votre question.'; };
    current.onend = () => {
      recognition = null; voice.setAttribute('aria-pressed', 'false'); voice.setAttribute('aria-label', 'Dicter votre question');
      if (hint.textContent.startsWith('Écoute en cours.')) hint.textContent = 'Dictée terminée. Vous pouvez saisir votre question ou réessayer.';
    };
    try { current.start(); } catch { current.onend(); hint.textContent = 'Impossible de démarrer la dictée. Vous pouvez saisir votre question.'; }
  };
  function findHero(container) {
    const visible = node => {
      const rect = node.getBoundingClientRect();
      return rect.width >= Math.min(innerWidth * .6, 600) && rect.height >= 180;
    };
    // Le corpus du site identifie les sections .hero-banner. Les autres
    // variantes couvrent les carrousels des pages d'accueil régionales.
    const named = container.querySelectorAll('.hero-banner, .hero, [data-component="hero"], section[class*="hero"], section[class*="slider"], section[class*="carousel"], .swiper, .slick-slider');
    const hero = Array.from(named).find(visible);
    if (hero) return hero.closest('section') || hero;
    // Repli sur le premier grand bloc visuel, sans prendre le menu ni la carte.
    return Array.from(container.children).find(node =>
      node !== host && !['HEADER', 'NAV', 'FOOTER', 'SCRIPT', 'STYLE'].includes(node.tagName) &&
      visible(node) && (node.querySelector('picture, img, video') || getComputedStyle(node).backgroundImage !== 'none'));
  }
  function mount() {
    if (!isHomePage()) {
      if (recognition) { recognition.abort(); recognition = null; }
      if (host.parentNode) host.remove();
      return;
    }
    const container = document.querySelector('main, [role="main"]') || document.body;
    if (!container) return;
    const hero = findHero(container);
    const style = baseStyle + (hero
      ? 'margin:clamp(-103px,-7.15vw,-48px) auto 32px!important;'
      : 'margin:32px auto!important;');
    if (host.style.cssText !== style) host.style.cssText = style;
    if (hero) {
      if (hero.nextElementSibling !== host) hero.insertAdjacentElement('afterend', host);
    } else if (host.parentNode !== container) container.append(host);
  }
  mount();
  // Les pages publiques peuvent remplacer leur contenu lors de la navigation.
  const observer = new MutationObserver(mount);
  observer.observe(document.body, {childList:true, subtree:true});
  globalThis.CESearch = {host};
  addEventListener('pagehide', () => { recognition?.abort(); observer.disconnect(); }, {once:true});
  addEventListener('pageshow', event => {
    if (event.persisted) { mount(); observer.observe(document.body, {childList:true, subtree:true}); }
  });
  addEventListener('resize', mount);
  addEventListener('popstate', mount);
  document.addEventListener('load', mount, true);
})();
