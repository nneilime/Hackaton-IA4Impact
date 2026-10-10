import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { AgentComponent, cropsFor, mergeTouching } from './agent';
import { Check } from '../models/invoice.model';

describe('mergeTouching', () => {
  it('merges overlapping boxes, even through a chain, and keeps separate ones apart', () => {
    const merged = mergeTouching([
      [103, 416, 142, 443], // 'GHS'
      [127, 415, 180, 442], // '9606', overlaps 'GHS'
      [175, 410, 190, 420], // overlaps '9606' only
      [486, 413, 555, 446], // '374,47', far away
    ]);
    expect(merged).toEqual([
      [103, 410, 190, 443],
      [486, 413, 555, 446],
    ]);
  });

  it('leaves non-overlapping boxes untouched', () => {
    expect(mergeTouching([[0, 0, 10, 10], [20, 0, 30, 10]])).toEqual([[0, 0, 10, 10], [20, 0, 30, 10]]);
  });
});

describe('AgentComponent.comparison', () => {
  const check = (code: string, attendu: string, lu: string): Check =>
    ({ code, libelle: '', statut: 'KO', attendu, lu, zones: [], boxes: [], confiance: null });
  let agent: AgentComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])] });
    agent = TestBed.runInInjectionContext(() => new AgentComponent());
  });

  it('puts the scan (source of truth) left and the B2 value (suspect) right', () => {
    const { reference, suspect } = agent.comparison(check('C4', '260800016', '260806016'));
    expect(reference).toEqual({ label: "Image (lu par l'IA)", value: '260806016', confiance: null });
    expect(suspect).toEqual({ label: 'Fichier B2 (facture)', value: '260800016' });
  });

  it('C0: malformed B2 file left, expected format right', () => {
    const { reference, suspect } = agent.comparison(check('C0', 'fichier conforme', 'Fichier B2 mal formé'));
    expect(reference).toEqual({ label: 'Fichier B2 (constaté)', value: 'Fichier B2 mal formé' });
    expect(suspect).toEqual({ label: 'Attendu', value: 'fichier conforme' });
  });

  it('shows the OCR confidence on the scan side (always left)', () => {
    const withConf = (code: string): Check => ({ ...check(code, 'a1', 'a2'), confiance: 0.999 });
    const b2 = agent.comparison(withConf('C6'));
    expect([b2.reference.confiance, b2.suspect.confiance]).toEqual([0.999, undefined]); // scan left
    const rule = agent.comparison(withConf('C16'));
    expect([rule.reference.confiance, rule.suspect.confiance]).toEqual([0.999, undefined]); // scan left
    expect(agent.confiancePct(0.999)).toBe(99);
    expect(agent.confiancePct(1)).toBe(100);
  });

  it('gives the amount difference on money cards and selects a card on demand', () => {
    expect(agent.comparison(check('C13', '50,49', '50,48')).ecart).toBe('0,01 €');
    expect(agent.comparison(check('C4', '260800016', '260806016')).ecart).toBeNull();
    expect(agent.selectedCode()).toBeNull();
    agent.select('C13');
    expect(agent.selectedCode()).toBe('C13');
  });

  it('does not underline letters on verdict checks (signatures, B2 format)', () => {
    expect(agent.comparison(check('C16', 'signature présente', 'signature absente')).diff).toBeNull();
    expect(agent.comparison(check('C14', 'signature requise (201400330)', 'aucune signature')).diff).toBeNull();
    expect(agent.comparison(check('C4', '260800016', '260806016')).diff).not.toBeNull();
  });

  it('form rules: scan left, rule right', () => {
    const { reference, suspect } = agent.comparison(check('C16', 'signature présente', 'signature absente'));
    expect(reference).toEqual({ label: "Image (lu par l'IA)", value: 'signature absente', confiance: null });
    expect(suspect).toEqual({ label: 'Attendu (règle du formulaire)', value: 'signature présente' });
  });
});

describe('cropsFor', () => {
  it('crops around a box with some context, zoomed at most x1.5, as CSS background geometry', () => {
    // 1190 x 1684 scan, one small box: margin 0.02 * 1190 = 23.8 px around it (half vertically)
    const [k] = cropsFor([[524, 92, 608, 109]], 1190, 1684);
    expect(k.width).toBe(Math.round((608 - 524 + 2 * 23.8) * 1.5));
    expect(k.backgroundSize).toBe(`${1190 * 1.5}px ${1684 * 1.5}px`);
    expect(k.backgroundPosition).toBe(`${Math.round(-(524 - 23.8) * 1.5)}px ${Math.round(-(92 - 11.9) * 1.5)}px`);
  });

  it('stretches a value box to the printed label left of it on the same row', () => {
    // "sous-total 4" label at x 931-1033, its value at x 1040-1100 on the same row (Facture3_12)
    const [withLabel] = cropsFor([[1040, 2008, 1100, 2032]], 1684, 2382, [[931, 2008, 1033, 2032]]);
    const [bare] = cropsFor([[1040, 2008, 1100, 2032]], 1684, 2382);
    expect(withLabel.width).toBeGreaterThan(bare.width);
    // a label on another row is ignored
    expect(cropsFor([[1040, 2008, 1100, 2032]], 1684, 2382, [[931, 1500, 1033, 1520]])).toEqual([bare]);
  });

  it('shrinks tall zones to fit, merges touching boxes and keeps at most 4 crops', () => {
    const [tall] = cropsFor([[980, 900, 1170, 1460]], 1190, 1684); // the 8 signature boxes
    expect(tall.height).toBeLessThanOrEqual(160);
    expect(cropsFor([[100, 100, 150, 120], [140, 100, 200, 120]], 1190, 1684)).toHaveLength(1);
    const far = [0, 1, 2, 3, 4, 5].map(i => [100, 100 + i * 200, 150, 120 + i * 200] as [number, number, number, number]);
    expect(cropsFor(far, 1190, 1684)).toHaveLength(4);
  });
});
