import { diffSegments, listDiffSegments, montantEcart, trimLeadingZeros } from './diff';

const marked = (segs: { text: string; diff: boolean }[]) => segs.map(s => (s.diff ? `[${s.text}]` : s.text)).join('');

describe('diffSegments', () => {
  it('highlights a changed digit in a long number on both sides', () => {
    const d = diffSegments('2540699281003', '2540699281004')!;
    expect(marked(d.reference)).toBe('254069928100[3]');
    expect(marked(d.suspect)).toBe('254069928100[4]');
  });

  it('compares same-length values position by position (one substituted digit)', () => {
    const d = diffSegments('260806016', '260800016')!;
    expect(marked(d.reference)).toBe('26080[6]016');
    expect(marked(d.suspect)).toBe('26080[0]016');
  });

  it('keeps a two-character substitution in place rather than shifting to reuse a digit', () => {
    const d = diffSegments('12280*01', '12278*01')!;
    expect(marked(d.reference)).toBe('122[80]*01');
    expect(marked(d.suspect)).toBe('122[78]*01');
    const shifted = diffSegments('12345678', '1234X567')!; // one inserted, one dropped: LCS still wins
    expect(marked(shifted.reference)).toBe('1234567[8]');
  });

  it('highlights inserted or missing characters', () => {
    const d = diffSegments('818,97', '818,987')!;
    expect(marked(d.reference)).toBe('818,97');
    expect(marked(d.suspect)).toBe('818,9[8]7');
  });

  it('works on lists of codes', () => {
    const d = diffSegments('GHS, PH8', 'GHS, PH8, EMI')!;
    expect(marked(d.suspect)).toBe('GHS, PH8[, EMI]');
  });

  it('returns null when there is nothing useful to highlight', () => {
    expect(diffSegments('574', '574')).toBeNull();                      // equal
    expect(diffSegments('260800016', 'scan non traité (OCR)')).toBeNull(); // missing value
    expect(diffSegments('—', '28,80')).toBeNull();
    expect(diffSegments('JVRP008', 'aucun')).toBeNull();
    expect(diffSegments('12345', 'ABCDE')).toBeNull();                  // unrelated
  });
});

describe('trimLeadingZeros', () => {
  it('drops the B2 zero padding when both values are integers, so only real differences are highlighted', () => {
    expect(trimLeadingZeros('491907', '000491917')).toEqual(['491907', '491917']);
    const [a, b] = trimLeadingZeros('491907', '000491917');
    expect(diffSegments(a, b)!.suspect.map(s => (s.diff ? `[${s.text}]` : s.text)).join('')).toBe('4919[1]7');
  });

  it('keeps a lone zero and leaves amounts, codes and text untouched', () => {
    expect(trimLeadingZeros('0', '000')).toEqual(['0', '0']);
    expect(trimLeadingZeros('028,80', '28,80')).toEqual(['028,80', '28,80']);
    expect(trimLeadingZeros('0960', 'GHS')).toEqual(['0960', 'GHS']);
  });
});

describe('montantEcart', () => {
  it('gives the difference between two amounts in euros', () => {
    expect(montantEcart('398,30', '398,31')).toBe('0,01 €');
    expect(montantEcart('847,77 (818,97 + 28,80)', '947,77')).toBe('100,00 €');
  });

  it('is null for equal amounts or values that are not amounts', () => {
    expect(montantEcart('50,48', '50,48')).toBeNull();
    expect(montantEcart('260800016', '260806016')).toBeNull();
    expect(montantEcart('—', '28,80')).toBeNull();
  });
});

describe('listDiffSegments', () => {
  it('marks whole items present on one side only', () => {
    const d = listDiffSegments('GHS, PH8, EMI', 'GHS, PH7, PH8, EMI')!;
    expect(marked(d.reference)).toBe('GHS, PH8, EMI');
    expect(marked(d.suspect)).toBe('GHS, [PH7], PH8, EMI');
  });

  it('marks a substituted item on both sides, as whole codes', () => {
    const d = listDiffSegments('GHS, PH8', 'GHS, PH7')!;
    expect(marked(d.reference)).toBe('GHS, [PH8]');
    expect(marked(d.suspect)).toBe('GHS, [PH7]');
  });

  it('marks only the side a one-way check verifies', () => {
    // C9: zone 7 of the scan ('PH8, EMI') must be in the file ('GHS, PH7, EMI'); GHS is printed in zone 6, not an error
    const d = listDiffSegments('PH8, EMI', 'GHS, PH7, EMI', true, false)!;
    expect(marked(d.reference)).toBe('[PH8], EMI');
    expect(marked(d.suspect)).toBe('GHS, PH7, EMI');
  });

  it('shows an empty side ("aucun") as is and marks every item of the other one', () => {
    const d = listDiffSegments('aucun', 'GHS')!;
    expect(marked(d.reference)).toBe('aucun');
    expect(marked(d.suspect)).toBe('[GHS]');
  });
});
