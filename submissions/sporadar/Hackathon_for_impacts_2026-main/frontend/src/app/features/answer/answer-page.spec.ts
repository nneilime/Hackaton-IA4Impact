import { HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { convertToParamMap } from '@angular/router';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';
import { askExample, type AskExample, sourcesExample } from '../../testing/examples';
import { render, textOf } from '../../testing/render';
import { AnswerPage } from './answer-page';

/** Monte la page avec une réponse déjà reçue (sans réseau). */
async function pageWith(name: AskExample, lang: 'fr' | 'en' = 'fr') {
  const rendered = await render(AnswerPage, {}, lang);
  const store = TestBed.inject(AnswerStore);
  store.answer.set(askExample(name));
  store.status.set('success');
  rendered.fixture.detectChanges();
  await rendered.fixture.whenStable();
  return { ...rendered, store };
}

describe('AnswerPage : le cadre commun', () => {
  const cases: [AskExample, string][] = [
    ['registration_lookup', 'registration_lookup'],
    ['use_comparison', 'use_comparison'],
    ['data_quality', 'data_quality'],
    ['sister_product', 'sister_product'],
    ['source_lookup', 'source_lookup'],
    ['ingredient_search', 'ingredient_search'],
    ['expiry_watch', 'expiry_watch'],
  ];

  it.each(cases)('le gabarit de %s est choisi par intent', async (example, template) => {
    const { element, http } = await pageWith(example);
    http.match(() => true); // appels de fond (sources, issues…)

    expect(element.querySelector('[data-template]')?.getAttribute('data-template')).toBe(template);
    expect(element.querySelector(`app-${template.replace('_', '-')}, app-${template.replaceAll('_', '-')}`)).not.toBeNull();
  });

  it.each(cases)('%s : conclusion, disclaimer et avertissements sont toujours visibles', async (example) => {
    const { element, http } = await pageWith(example);
    http.match(() => true);
    const answer = askExample(example);

    expect(textOf(element.querySelector('[data-answer]') as Element)).toBe(answer.answer);
    expect(textOf(element.querySelector('[data-section="disclaimer"]') as Element)).toContain(answer.disclaimer);
    // Jamais repliés : aucun <details> fermé, et chaque avertissement est dans le texte rendu.
    expect(element.querySelector('details')).toBeNull();
    for (const warning of answer.warnings) {
      expect(textOf(element.querySelector('[data-section="warnings"]') as Element)).toContain(warning);
    }
  });

  it('le sommaire reprend les titres de la réponse et défile vers la section choisie', async () => {
    const { element, http, fixture } = await pageWith('registration_lookup');
    http.match(() => true);
    await new Promise((resolve) => requestAnimationFrame(resolve));
    fixture.detectChanges();

    const links = [...element.querySelectorAll<HTMLAnchorElement>('[data-toc-nav] a')];
    const labels = links.map((link) => textOf(link));
    expect(labels).toContain('Conclusion');
    expect(labels).toContain('Homologations');

    const target = element.querySelector<HTMLElement>(links[1].getAttribute('href')!);
    expect(target).not.toBeNull();
    const scroll = vi.fn();
    target!.scrollIntoView = scroll;
    links[1].click();
    expect(scroll).toHaveBeenCalledOnce();
  });

  it('la chaîne de démo T01 → T05 passe par la première suggestion de chaque réponse', () => {
    const chain: AskExample[] = ['registration_lookup', 'use_comparison', 'data_quality', 'sister_product'];
    const next: AskExample[] = ['use_comparison', 'data_quality', 'sister_product', 'source_lookup'];
    chain.forEach((example, index) => {
      expect(askExample(example).suggestedQuestions![0].intent).toBe(next[index]);
    });
  });

  it('un intent inconnu tombe sur le message « hors périmètre »', async () => {
    const rendered = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    store.answer.set({ ...askExample('other'), intent: 'inconnu' as never });
    store.status.set('success');
    rendered.fixture.detectChanges();

    expect(rendered.element.querySelector('[data-message="out_of_scope"]')).not.toBeNull();
  });

  it('une précision demandée affiche les options, pas de gabarit', async () => {
    const rendered = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    store.answer.set(askExample('needs_clarification'));
    store.status.set('success');
    rendered.fixture.detectChanges();

    expect(rendered.element.querySelector('[data-message="clarification"]')).not.toBeNull();
    expect(rendered.element.querySelector('app-registration-lookup')).toBeNull();
  });

  it('les compteurs de conclusion décomptent états de validation et couverture reçus', async () => {
    const { element, http } = await pageWith('registration_lookup');
    http.match(() => true);
    const counters = Array.from(element.querySelectorAll('app-conclusion app-status-badge')).map(textOf);

    expect(counters).toEqual(['1 Validé', '1 À vérifier', '1 Pas trouvé', '7 Non couvert']);
  });

  it('un « pas trouvé » ne devient jamais rouge ni « non homologué » dans toute la page', async () => {
    const { element, http } = await pageWith('registration_lookup');
    http.match(() => true);

    for (const badge of Array.from(element.querySelectorAll('[data-state="not_found"]'))) {
      expect(badge.getAttribute('data-variant')).not.toBe('rejected');
    }
    expect(textOf(element).toLowerCase()).not.toMatch(/non homologu|not registered/);
  });
});

describe('AnswerPage : états', () => {
  it('chargement : le cadre reste, avec un squelette', async () => {
    const rendered = await render(AnswerPage);
    TestBed.inject(AnswerStore).status.set('loading');
    rendered.fixture.detectChanges();

    expect(rendered.element.querySelector('[data-state="loading"]')).not.toBeNull();
    expect(rendered.element.querySelector('app-ask-bar')).not.toBeNull();
  });

  it("erreur réseau : message clair, « Réessayer », la question reste dans la barre", async () => {
    const rendered = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    store.question.set('Dans quels pays est-il homologué ?');
    store.errorKind.set('network');
    store.status.set('error');
    rendered.fixture.detectChanges();

    const error = rendered.element.querySelector('[data-state="error"]') as Element;
    expect(textOf(error)).toContain('Réessayer');
    expect((rendered.element.querySelector('#question') as HTMLInputElement).value).toBe(
      'Dans quels pays est-il homologué ?',
    );
  });

  it("401 : « Accès à l'API refusé », sans détail technique", async () => {
    const rendered = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    store.errorKind.set('unauthorized');
    store.status.set('error');
    rendered.fixture.detectChanges();

    const text = textOf(rendered.element.querySelector('[data-state="error"]') as Element);
    expect(text).toContain("Accès à l'API refusé");
    expect(text).not.toMatch(/401|X-API-Key/);
  });

  it("404 sur un produit : jamais formulé comme une absence d'homologation", async () => {
    const rendered = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    store.errorKind.set('notFound');
    store.status.set('error');
    rendered.fixture.detectChanges();

    const text = textOf(rendered.element.querySelector('[data-state="error"]') as Element);
    expect(text).toContain('Produit inconnu de notre catalogue');
    expect(text.toLowerCase()).not.toMatch(/non homologu/);
  });

  it('accueil : les 5 questions test sont proposées avec leur intention', async () => {
    const { element } = await render(AnswerPage);
    const intents = Array.from(element.querySelectorAll('[data-examples] button')).map((b) => b.getAttribute('data-intent'));

    expect(intents).toEqual(['registration_lookup', 'use_comparison', 'data_quality', 'sister_product', 'source_lookup']);
  });
});

describe('AnswerPage : FR / EN', () => {
  it('la bascule traduit les textes d\'interface sans toucher aux valeurs d\'origine', async () => {
    const { element, http, fixture } = await pageWith('registration_lookup');
    http.match(() => true);
    const before = textOf(element);
    expect(before).toContain('Pas trouvé');
    expect(before).toContain('Autorisé');
    expect(before).toContain('Registered');

    TestBed.inject(I18n).lang.set('en');
    fixture.detectChanges();
    await fixture.whenStable();
    const after = textOf(element);

    expect(after).toContain('Not found');
    expect(after).not.toContain('Pas trouvé');
    // Valeurs venues des sources : jamais traduites.
    expect(after).toContain('Autorisé');
    expect(after).toContain('Registered');
    expect(after).toContain('SYNTHETIC F52 PRODUCT');
  });
});

describe('AnswerStore : URL et appels', () => {
  it("lit la question dans l'URL et appelle POST /ask avec la langue", async () => {
    await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    const http = TestBed.inject(HttpTestingController);

    store.syncFromUrl(convertToParamMap({ q: 'Dans quels pays est-il homologué ?', lang: 'en', product: 'P-LPC-M52', countries: 'FR,CA' }));

    const request = http.expectOne((r) => r.url.endsWith('/ask') && r.method === 'POST');
    expect(request.request.body).toEqual({
      question: 'Dans quels pays est-il homologué ?',
      language: 'en',
      productId: 'P-LPC-M52',
      countries: ['FR', 'CA'],
    });
    // Hors mock, l'en-tête Prefer n'est jamais envoyé.
    expect(request.request.headers.has('Prefer')).toBe(false);
    request.flush(askExample('registration_lookup'));
    expect(store.status()).toBe('success');
  });

  it('classe les erreurs HTTP : 401, 404, réseau', async () => {
    await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);
    const http = TestBed.inject(HttpTestingController);

    for (const [status, kind] of [
      [401, 'unauthorized'],
      [404, 'notFound'],
      [500, 'network'],
    ] as const) {
      store.syncFromUrl(convertToParamMap({ q: `question ${status}` }));
      http.expectOne((r) => r.url.endsWith('/ask')).flush('', { status, statusText: 'x' });
      expect(store.status()).toBe('error');
      expect(store.errorKind()).toBe(kind);
      expect(store.answer()).toBeNull();
    }
  });

  it('charge la fraîcheur des sources au démarrage (GET /sources)', async () => {
    const { http } = await render(AnswerPage);
    const store = TestBed.inject(AnswerStore);

    store.loadSources();
    http.expectOne((r) => r.url.endsWith('/sources')).flush(sourcesExample());
    expect(store.sources().length).toBeGreaterThan(0);
  });
});
