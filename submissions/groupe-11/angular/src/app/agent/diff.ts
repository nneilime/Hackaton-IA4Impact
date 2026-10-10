/** Character diff between the reference value and the suspect one, to highlight what differs (like `git diff`). */

export interface Segment { text: string; diff: boolean }

/**
 * Diff between two lists of codes ('GHS, PH8, EMI' vs 'GHS, PH7, PH8, EMI'): each item present on one side
 * only is marked as a whole. A character diff would be misleading there ('PH7' / 'PH8' share two letters but
 * are two different prestations). A side reading "aucun" (empty list) is shown as is, unmarked.
 * `markReference` / `markSuspect`: whether that side's extra items are marked. A one-way check only marks the
 * side it verifies (C9 only requires zone 7 items to be in the file, so a file item absent from zone 7 is fine).
 */
export function listDiffSegments(reference: string, suspect: string, markReference = true, markSuspect = true):
  { reference: Segment[]; suspect: Segment[] } | null {
  const items = (v: string) => (NO_VALUE.test(v.trim()) ? [] : v.split(/,\s*/).filter(Boolean));
  const [a, b] = [items(reference), items(suspect)];
  if (reference === suspect) return null;
  const segs = (value: string, mine: string[], other: string[], mark: boolean): Segment[] =>
    mine.length
      ? mine.flatMap((it, i) => [...(i ? [{ text: ', ', diff: false }] : []),
                                  { text: it, diff: mark && !other.includes(it) }])
      : [{ text: value, diff: false }];
  return { reference: segs(reference, a, b, markReference), suspect: segs(suspect, b, a, markSuspect) };
}

/** Leading French amount of a display value: '398,30', '847,77 (818,97 + 28,80)' */
const AMOUNT = /^\s*(\d+),(\d{2})\b/;

/**
 * Difference between two amounts, for the money checks ('398,30' vs '398,31' -> '0,01 €'),
 * so the agent sees at once whether it is a cent or a hundred euros. null if either is not an amount.
 */
export function montantEcart(a: string, b: string): string | null {
  const [ma, mb] = [AMOUNT.exec(a), AMOUNT.exec(b)];
  if (!ma || !mb) return null;
  const cents = Math.abs((+ma[1] * 100 + +ma[2]) - (+mb[1] * 100 + +mb[2]));
  if (!cents) return null;
  return `${Math.floor(cents / 100).toLocaleString('fr-FR')},${String(cents % 100).padStart(2, '0')} €`;
}

/**
 * B2 numbers are zero-padded ('000491917') while the form prints '491917', and the backend checks already
 * treat them as equal. When both values are plain integers, drop the padding so it is neither shown nor
 * highlighted as a difference. Amounts, codes and free text are left untouched.
 */
export function trimLeadingZeros(a: string, b: string): [string, string] {
  const integer = /^\d+$/;
  if (!integer.test(a) || !integer.test(b)) return [a, b];
  const trim = (v: string) => v.replace(/^0+(?=\d)/, '');
  return [trim(a), trim(b)];
}

/** Values that carry no comparable content: nothing to highlight */
const NO_VALUE = /^(—|non lu|aucun|scan non traité \(OCR\))$/i;

/** Below this share of common characters the two values are unrelated, and highlighting everything helps nobody */
const MIN_SIMILARITY = 0.4;

/** Longer values are not diffed (the LCS table is O(n·m)) */
const MAX_LENGTH = 200;

/**
 * Splits both values into segments, `diff: true` on characters that are not part of their longest common
 * subsequence. Returns null when there is nothing useful to highlight (equal, missing or unrelated values).
 */
export function diffSegments(reference: string, suspect: string): { reference: Segment[]; suspect: Segment[] } | null {
  if (reference === suspect || NO_VALUE.test(reference.trim()) || NO_VALUE.test(suspect.trim())) return null;
  if (reference.length > MAX_LENGTH || suspect.length > MAX_LENGTH) return null;

  const [a, b] = [reference, suspect];
  // lcs[i][j] = length of the longest common subsequence of a[i:] and b[j:]
  const lcs = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  if (lcs[0][0] / Math.max(a.length, b.length) < MIN_SIMILARITY) return null;

  // Same length: a typo or misread is a substitution, best shown position by position. The LCS has several
  // equally long solutions there and may pick one the eye does not expect ('260800[0]16' for one changed
  // digit, '1228[0]*01' / '122[7]8*01' for '80' misread from '78': the LCS shifts to reuse the 8). Keep the
  // LCS only when it marks less than half as many characters (e.g. a character inserted and another dropped).
  if (a.length === b.length) {
    const same = [...a].map((ch, i) => ch === b[i]);
    if (same.filter(x => !x).length <= 2 * (a.length - lcs[0][0])) {
      return { reference: segments(a, same), suspect: segments(b, same) };
    }
  }

  const inA = new Array<boolean>(a.length).fill(false);
  const inB = new Array<boolean>(b.length).fill(false);
  for (let i = 0, j = 0; i < a.length && j < b.length;) {
    if (a[i] === b[j]) { inA[i++] = inB[j++] = true; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) i++;
    else j++;
  }
  return { reference: segments(a, inA), suspect: segments(b, inB) };
}

/** Groups consecutive characters with the same state: '26080|60|16' rather than one span per character */
function segments(text: string, common: boolean[]): Segment[] {
  const out: Segment[] = [];
  for (let i = 0; i < text.length; i++) {
    const diff = !common[i];
    const last = out[out.length - 1];
    if (last && last.diff === diff) last.text += text[i];
    else out.push({ text: text[i], diff });
  }
  return out;
}
