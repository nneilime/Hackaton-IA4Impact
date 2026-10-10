import { askExample } from '../../../testing/examples';
import { render, textOf } from '../../../testing/render';
import { RegistrationLookup } from './registration-lookup';

describe('RegistrationLookup (T01)', () => {
  it('affiche une ligne par homologation trouvée, validées en premier', async () => {
    const { element } = await render(RegistrationLookup, { answer: askExample('registration_lookup') });

    const found = Array.from(element.querySelectorAll('[data-row="found"]'));
    expect(found.map((row) => row.getAttribute('data-country'))).toEqual(['FR', 'CA']);
    expect(textOf(found[0])).toContain('Validé');
    expect(textOf(found[1])).toContain('À vérifier');
  });

  it("montre le statut d'origine à côté du normalisé et le nom sous lequel la ligne a été trouvée", async () => {
    const { element } = await render(RegistrationLookup, { answer: askExample('registration_lookup') });
    const [fr, ca] = Array.from(element.querySelectorAll('[data-row="found"]'));

    expect(textOf(fr)).toContain('Autorisé');
    expect(textOf(fr)).toContain('Trouvé sous le nom « LALGUARD M52 OD »');
    expect(textOf(ca)).toContain('Registered');
    expect(textOf(ca)).toContain("Trouvé via l'alias « Metarhizium anisopliae F52 »");
    expect(textOf(ca)).toContain('former_taxonomic_name');
  });

  it("un pays « pas trouvé » n'est jamais rouge et ne dit jamais « non homologué »", async () => {
    const { element } = await render(RegistrationLookup, { answer: askExample('registration_lookup') });
    const notFound = element.querySelector('[data-outcome="not_found"]');

    expect(notFound).not.toBeNull();
    expect(textOf(notFound as Element)).toContain('Pas trouvé');
    expect(textOf(notFound as Element)).toContain("Ne prouve pas l'absence d'homologation");
    // Aucune variante rouge (rejected) dans la ligne, ni de classe de couleur de rejet.
    expect((notFound as Element).querySelector('[data-variant="rejected"]')).toBeNull();
    expect((notFound as Element).innerHTML).not.toMatch(/status-rejected|text-red|bg-red/);
    expect(textOf(element).toLowerCase()).not.toMatch(/non homologu|not registered/);
  });

  it('indique sous combien de noms et lesquels on a cherché', async () => {
    const { element } = await render(RegistrationLookup, { answer: askExample('registration_lookup') });
    const notFound = element.querySelector('[data-outcome="not_found"]') as Element;

    expect(textOf(notFound)).toContain('DE-BVL');
    expect(textOf(notFound)).toContain('4 nom(s)');
    expect(textOf(notFound)).toContain('Metarhizium brunneum Ma 43');
  });

  it('regroupe les pays non couverts sur une ligne à part', async () => {
    const { element } = await render(RegistrationLookup, { answer: askExample('registration_lookup') });
    const group = element.querySelector('[data-group="not-covered"]') as Element;

    expect(group.querySelectorAll('[data-state="not_covered"]')).toHaveLength(7);
  });
});
