import { TestBed } from '@angular/core/testing';
import { AnswerStore } from '../../../core/state/answer.store';
import { askExample, issuesExample, reviewExample } from '../../../testing/examples';
import { render, textOf } from '../../../testing/render';
import { DataQuality } from './data-quality';
import { ExpiryWatch } from './expiry-watch';
import { IngredientSearch } from './ingredient-search';
import { MessageTemplate } from './message-template';
import { SisterProduct } from './sister-product';
import { SourceLookup } from './source-lookup';

describe('DataQuality (T03)', () => {
  it("affiche une file triée par priorité, avec confiance IA et validation dans deux colonnes distinctes", async () => {
    const answer = askExample('data_quality');
    const { element, http } = await render(DataQuality, { answer });
    http.expectOne((r) => r.url.endsWith('/issues')).flush(issuesExample());

    const headers = Array.from(element.querySelectorAll('thead th')).map(textOf);
    expect(headers).toContain('Confiance IA');
    expect(headers).toContain('Validation');
    expect(element.querySelectorAll('tbody tr')).toHaveLength(answer.issues!.length);

    const ranks = Array.from(element.querySelectorAll('tbody tr')).map((row) => {
      const text = textOf(row.querySelector('td') as Element);
      return text.includes('Haute') ? 0 : text.includes('Moyenne') ? 1 : 2;
    });
    expect(ranks).toEqual([...ranks].sort());
  });

  it('affiche les compteurs par type de problème, qui servent de filtres', async () => {
    const { element, http } = await render(DataQuality, { answer: askExample('data_quality') });
    http.expectOne((r) => r.url.endsWith('/issues')).flush(issuesExample());

    const filters = Array.from(element.querySelectorAll('[data-issue-type]')).map((el) => el.getAttribute('data-issue-type'));
    expect(filters).toEqual(expect.arrayContaining(['not_validated', 'uncertain', 'unmapped', 'missing']));
  });

  it('un lien « Vérifier » ouvre la preuve', async () => {
    const { element, http } = await render(DataQuality, { answer: askExample('data_quality') });
    http.expectOne((r) => r.url.endsWith('/issues')).flush(issuesExample());

    const link = Array.from(element.querySelectorAll('app-evidence-link button')).find((b) => textOf(b).includes('Vérifier'));
    (link as HTMLButtonElement).click();
    expect(TestBed.inject(AnswerStore).evidence()).not.toBeNull();
  });
});

describe('SisterProduct (T04)', () => {
  it('présente chaque candidat non validé comme une hypothèse : pointillé et badge « à confirmer »', async () => {
    const answer = askExample('sister_product');
    const { element } = await render(SisterProduct, { answer });

    const cards = Array.from(element.querySelectorAll('[data-candidate]'));
    expect(cards).toHaveLength(answer.sisterCandidates!.length);
    for (const card of cards) {
      const candidate = answer.sisterCandidates!.find((c) => c.candidateId === card.getAttribute('data-candidate'))!;
      const link = card.querySelector('[data-link]') as Element;
      if (candidate.reviewStatus === 'validated') {
        expect(card.getAttribute('data-hypothesis')).toBeNull();
        expect(link.className).toContain('border-solid');
      } else {
        expect(card.getAttribute('data-hypothesis')).toBe('true');
        expect(link.className).toContain('border-dashed');
        expect(textOf(card)).toContain('Hypothèse à confirmer');
      }
      // Le type de relation reste toujours affiché, et la confiance n'est pas un statut de revue.
      expect(textOf(card)).toContain(candidate.relationshipType);
      expect(textOf(card)).toContain('Revue :');
    }
  });

  it("n'enregistre une décision qu'après la réponse du back (rien d'optimiste)", async () => {
    const { element, http, fixture } = await render(SisterProduct, { answer: askExample('sister_product') });

    (element.querySelector('[data-candidate] button') as HTMLButtonElement).click();
    const request = http.expectOne((r) => r.url.endsWith('/reviews'));
    expect(request.request.body).toMatchObject({ targetType: 'sister_candidate', decision: 'validated' });
    expect(element.querySelector('[role="status"]')).toBeNull();

    request.flush(reviewExample());
    await fixture.whenStable();
    expect(element.querySelector('[role="status"]')).not.toBeNull();
  });

  it('cache les boutons si POST /reviews est absent côté back', async () => {
    const { element, http, fixture } = await render(SisterProduct, { answer: askExample('sister_product') });

    (element.querySelector('[data-candidate] button') as HTMLButtonElement).click();
    http.expectOne((r) => r.url.endsWith('/reviews')).flush('', { status: 404, statusText: 'Not Found' });
    await fixture.whenStable();

    expect(element.querySelector('[data-candidate] button')).toBeNull();
    expect(textOf(element)).toContain("La revue n'est pas encore disponible");
  });
});

describe('SourceLookup (T05)', () => {
  it('relie chaque fait à une preuve accessible', async () => {
    const answer = askExample('source_lookup');
    const { element } = await render(SourceLookup, { answer });

    const facts = Array.from(element.querySelectorAll('[data-fact]'));
    expect(facts).toHaveLength(answer.facts!.length);
    for (const fact of facts) {
      expect(fact.querySelectorAll('app-evidence-link').length).toBeGreaterThan(0);
      expect(fact.querySelector('a[href]')).not.toBeNull();
    }
  });

  it('signale une preuve annoncée mais absente de la réponse', async () => {
    const answer = askExample('source_lookup');
    answer.evidence = [];
    const { element } = await render(SourceLookup, { answer });

    expect(textOf(element)).toContain('introuvable dans la réponse');
    expect(element.querySelector('[data-fact] app-evidence-link')).toBeNull();
  });
});

describe('IngredientSearch', () => {
  it('affiche une ligne par produit, avec LPC / concurrent et l\'ancien nom résolu', async () => {
    const answer = askExample('ingredient_search');
    const { element } = await render(IngredientSearch, { answer });

    expect(element.querySelectorAll('tbody tr')).toHaveLength(answer.products!.length);
    expect(textOf(element)).toMatch(/LPC|concurrent/);
    expect(textOf(element)).toContain('ancien nom');
  });

  it('une case sans résultat se lit « pas trouvé », jamais « non homologué »', async () => {
    const { element } = await render(IngredientSearch, { answer: askExample('ingredient_search') });
    expect(textOf(element).toLowerCase()).not.toMatch(/non homologu/);
  });
});

describe('ExpiryWatch', () => {
  it("trie par échéance et colore selon l'urgence", async () => {
    const answer = askExample('expiry_watch');
    const { element } = await render(ExpiryWatch, { answer });

    const dates = answer.expirations!.map((e) => e.expirationDate).sort();
    expect(element.querySelectorAll('tbody tr')).toHaveLength(dates.length);
    const first = element.querySelector('tbody tr') as Element;
    const days = answer.expirations!.find((e) => e.expirationDate === dates[0])!.daysUntilExpiration!;
    expect(first.querySelector('[data-urgency]')?.getAttribute('data-urgency')).toBe(
      days <= 90 ? 'rejected' : days <= 270 ? 'review' : 'secondary',
    );
  });
});

describe('MessageTemplate', () => {
  it('propose les options de précision en boutons qui relancent la question', async () => {
    const answer = askExample('needs_clarification');
    const { fixture, element } = await render(MessageTemplate, { answer });
    const chosen: string[] = [];
    fixture.componentInstance.clarify.subscribe((option) => chosen.push(option));

    const buttons = Array.from(element.querySelectorAll('button'));
    expect(buttons.map(textOf)).toEqual(answer.clarificationOptions);
    buttons[0].click();
    expect(chosen).toEqual([answer.clarificationOptions![0]]);
  });

  it('hors périmètre : message clair, sans réponse inventée', async () => {
    const { element } = await render(MessageTemplate, { answer: askExample('other') });
    expect(element.querySelector('[data-message="out_of_scope"]')).not.toBeNull();
    expect(element.querySelectorAll('button')).toHaveLength(0);
  });

  it("aucune donnée : « rien trouvé dans nos sources », pas une preuve d'absence", async () => {
    const answer = { ...askExample('registration_lookup'), answerStatus: 'no_data' as const };
    const { element } = await render(MessageTemplate, { answer });
    expect(textOf(element)).toContain('Rien trouvé dans nos sources');
    expect(textOf(element)).toContain("pas une preuve d'absence d'homologation");
  });
});
