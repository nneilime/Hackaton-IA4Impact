import { TestBed } from '@angular/core/testing';
import { AnswerStore } from '../../../core/state/answer.store';
import { askExample } from '../../../testing/examples';
import { render, textOf } from '../../../testing/render';
import { UseComparison } from './use-comparison';

describe('UseComparison (T02)', () => {
  const comparison = () => askExample('use_comparison').comparison!;

  it('affiche une ligne par culture × cible et une colonne par pays', async () => {
    const data = comparison();
    const { element } = await render(UseComparison, { comparison: data });

    const rows = element.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(data.rows!.length);
    for (const row of Array.from(rows)) {
      expect(row.querySelectorAll('td[data-country]')).toHaveLength(data.countries.length);
    }
  });

  it("n'utilise que des en-têtes de ligne et de colonne, avec la source et la date par pays", async () => {
    const data = comparison();
    const { element } = await render(UseComparison, { comparison: data });

    expect(element.querySelectorAll('thead th[scope="col"]')).toHaveLength(data.countries.length + 1);
    expect(element.querySelectorAll('tbody th[scope="row"]')).toHaveLength(data.rows!.length);
    for (const code of data.countries) {
      const registration = data.registrations.find((r) => r.countryCode === code)!;
      expect(textOf(element.querySelector('thead') as Element)).toContain(registration.evidence.sourceId);
    }
  });

  it("ne convertit ni ne fusionne aucune valeur : dose et unité sont celles du back, une cellule par pays", async () => {
    const data = comparison();
    const { element } = await render(UseComparison, { comparison: data });

    for (const row of data.rows!) {
      for (const cell of row.cells.filter((c) => c.state === 'present')) {
        const td = element.querySelector(`tr:nth-child(${data.rows!.indexOf(row) + 1}) td[data-country="${cell.countryCode}"]`) as Element;
        for (const use of cell.uses ?? []) {
          expect(textOf(td)).toContain(use.doseUnitNormalized ?? '');
          if (use.doseUnitOriginal) expect(textOf(td)).toContain(`« ${use.doseUnitOriginal} »`);
        }
      }
    }
  });

  it('distingue chaque cause de case vide et signale les lignes qui diffèrent', async () => {
    const data = comparison();
    const { element } = await render(UseComparison, { comparison: data });

    const emptyStates = new Set(data.rows!.flatMap((r) => r.cells.map((c) => c.state)).filter((s) => s !== 'present'));
    for (const state of emptyStates) {
      expect(element.querySelector(`[data-cell-state="${state}"]`)).not.toBeNull();
    }
    expect(element.querySelectorAll('tr[data-differs="true"]')).toHaveLength(
      data.rows!.filter((r) => r.differsAcrossCountries).length,
    );
  });

  it('ouvre le panneau de preuve au clic sur une dose', async () => {
    const { element } = await render(UseComparison, { comparison: comparison() });
    const store = TestBed.inject(AnswerStore);

    (element.querySelector('td[data-country] app-evidence-link button') as HTMLButtonElement).click();

    const view = store.evidence();
    expect(view).not.toBeNull();
    expect(view!.evidence.sourceId).toBeTruthy();
    expect(view!.evidence.collectedAt).toBeTruthy();
  });

  it("n'appelle pas l'API tant qu'on ne filtre pas, puis appelle GET /compare avec les filtres", async () => {
    const { element, http, fixture } = await render(UseComparison, { comparison: comparison() });
    http.expectNone(() => true);

    const crop = element.querySelector('input[name="crop"]') as HTMLInputElement;
    crop.value = 'LYPES';
    crop.dispatchEvent(new Event('input'));
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();

    const request = http.expectOne((r) => r.url.endsWith('/compare'));
    expect(request.request.params.get('crop')).toBe('LYPES');
    expect(request.request.params.get('countries')).toBe(comparison().countries.join(','));
    request.flush(comparison());
  });
});
