const nf = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const timeFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' });
const dayFmt = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Paris',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
});

// fr-FR groups thousands with a narrow no-break space (U+202F) that Sora has no glyph for ("14054"):
// use a regular no-break space instead, which every font draws.
const nbsp = (s: string) => s.replace(/ /g, ' ');
export const fmtInt = (n: number) => nbsp(nf.format(Math.round(n)));
export const fmt1 = (n: number) => nbsp(nf1.format(n));

/** "14h40" */
export const fmtHour = (d: string | number | Date) => timeFmt.format(new Date(d)).replace(':', 'h');
/** Same form as fmtHour everywhere: "14h40" */
export const fmtClock = (d: string | number | Date) => fmtHour(d);

const axisDayFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', weekday: 'short' });
const axisHourFmt = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', hourCycle: 'h23' });
/** Axis tick: "dim. 04h" */
export const fmtAxis = (d: number) =>
  `${axisDayFmt.format(d)} ${axisHourFmt.formatToParts(d).find((p) => p.type === 'hour')?.value ?? ''}h`;
/** Hour of day in Paris (0-23) */
export const parisHour = (d: number) => Number(axisHourFmt.formatToParts(d).find((p) => p.type === 'hour')?.value ?? 0);
/** "dim. 9 oct." (built from parts: some engines add the year for past dates) */
export const fmtDay = (d: string | number | Date) => {
  const p = Object.fromEntries(dayFmt.formatToParts(new Date(d)).map((x) => [x.type, x.value]));
  return `${p.weekday} ${p.day} ${p.month}`;
};

/** 95 -> "1 h 35", 40 -> "40 min" */
export function fmtMinutes(min: number): string {
  const m = Math.round(min);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${String(r).padStart(2, '0')}` : `${h} h`;
}

export const fmtHours = (h: number) => (Number.isInteger(h) ? `${h} h` : `${fmt1(h)} h`);

/** Signed customer-hours: "+42", "−12" */
export function fmtDelta(n: number): string {
  const r = Math.round(n);
  if (r === 0) return '±0';
  return `${r > 0 ? '+' : '−'}${nf.format(Math.abs(r))}`;
}

/** "−22,6 %" */
export function fmtPct(p: number): string {
  const s = nf1.format(Math.abs(p));
  if (Math.abs(p) < 0.05) return '0,0 %';
  return `${p > 0 ? '+' : '−'}${s} %`;
}

export const plural = (n: number, one: string, many: string) => (Math.abs(n) >= 2 ? many : one);
