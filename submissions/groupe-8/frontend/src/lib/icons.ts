// Map symbols, generated as SVG so colours come from the CSS tokens.
// Incidents are circles, teams are diamonds. Status is carried by fill style
// AND a glyph, never by colour alone.
import type { IncidentStatus, TeamStatus } from '../data/contract';
import { palette } from './theme';

export type IconDef = { url: string; id: string; width: number; height: number; anchorY: number; mask: false };

const ICON = 64;
const cache = new Map<string, IconDef>();

function def(id: string, body: string): IconDef {
  let d = cache.get(id);
  if (!d) {
    const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="${ICON}" height="${ICON}" viewBox="0 0 ${ICON} ${ICON}">${body}</svg>`,
    )}`;
    d = { id, url, width: ICON, height: ICON, anchorY: ICON / 2, mask: false };
    cache.set(id, d);
  }
  return d;
}

/** Small red badge with a white cross: substation feeding a sensitive client. */
const sensitiveBadge = (p: ReturnType<typeof palette>) =>
  `<circle cx="51" cy="13" r="11" fill="${p.critical}" stroke="${p.surface}" stroke-width="3"/>
   <path d="M51 7.5v11M45.5 13h11" stroke="${p.surface}" stroke-width="3.4" stroke-linecap="round"/>`;

export function incidentIcon(status: IncidentStatus, sensitive: boolean): IconDef {
  const p = palette();
  const c = 32;
  const r = sensitive ? 20 : 27; // leave room for the red ring
  const w = p.surface;
  let shape = '';
  switch (status) {
    case 'waiting':
      // amber disc, white outline, "!"
      shape = `<circle cx="${c}" cy="${c}" r="${r}" fill="${p.waiting}" stroke="${w}" stroke-width="4"/>
        <rect x="${c - 3}" y="${c - r * 0.55}" width="6" height="${r * 0.68}" rx="3" fill="${p.text}"/>
        <circle cx="${c}" cy="${c + r * 0.42}" r="3.4" fill="${p.text}"/>`;
      break;
    case 'enroute':
      // white disc, dashed blue ring, arrow: a team is on its way
      shape = `<circle cx="${c}" cy="${c}" r="${r}" fill="${w}"/>
        <circle cx="${c}" cy="${c}" r="${r - 3}" fill="none" stroke="${p.blue}" stroke-width="5" stroke-dasharray="7 4"/>
        <path d="M${c - r * 0.42} ${c} H${c + r * 0.32} M${c + r * 0.02} ${c - r * 0.3} L${c + r * 0.36} ${c} L${c + r * 0.02} ${c + r * 0.3}" stroke="${p.blue}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
      break;
    case 'repairing':
      // white disc, solid blue ring, wrench
      shape = `<circle cx="${c}" cy="${c}" r="${r - 2}" fill="${w}" stroke="${p.blue}" stroke-width="6"/>
        <g transform="translate(${c} ${c}) rotate(-45) scale(${r / 27})" fill="${p.blue}">
          <rect x="-3.2" y="-2" width="6.4" height="17" rx="3"/>
          <path d="M-8.5 -8 a8.5 8.5 0 0 0 17 0 v-6 l-4.2 3 v4 h-8.6 v-4 l-4.2 -3 z"/>
        </g>`;
      break;
    case 'restored':
      // green disc + check
      shape = `<circle cx="${c}" cy="${c}" r="${r}" fill="${p.green}" stroke="${w}" stroke-width="4"/>
        <path d="M${c - r * 0.45} ${c + 1} l${r * 0.3} ${r * 0.3} l${r * 0.6} -${r * 0.62}" stroke="${w}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
      break;
  }
  const ring = sensitive
    ? `<circle cx="${c}" cy="${c}" r="27" fill="${w}" stroke="${p.critical}" stroke-width="5"/>`
    : '';
  return def(`inc-${status}-${sensitive}`, ring + shape + (sensitive ? sensitiveBadge(p) : ''));
}

export function teamIcon(status: TeamStatus): IconDef {
  const p = palette();
  const w = p.surface;
  const diamond = (fill: string, stroke: string, extra = '') =>
    `<path d="M32 5 L59 32 L32 59 L5 32 Z" fill="${fill}" stroke="${stroke}" stroke-width="4.5" stroke-linejoin="round" ${extra}/>`;
  let body = '';
  switch (status) {
    case 'available':
      body = diamond(p.blue, w) + `<circle cx="32" cy="32" r="7" fill="${w}"/>`;
      break;
    case 'travelling':
      body =
        diamond(w, p.blue) +
        `<path d="M27 21 L38 32 L27 43" stroke="${p.blue}" stroke-width="6.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
      break;
    case 'repairing':
      body = diamond(p.blue, w) + `<rect x="21" y="28.5" width="22" height="7" rx="3" fill="${w}"/>`;
      break;
    case 'resting':
      // hollow
      body =
        diamond(w, p.blue, 'stroke-dasharray="7 5"') +
        `<path d="M25 24 H39 L25 40 H39" stroke="${p.blue}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
      break;
  }
  return def(`team-${status}`, body);
}

/** The sensitive-client badge alone (used on commune clusters). */
export function sensitiveBadgeIcon(): IconDef {
  const p = palette();
  return def(
    'badge-sensitive',
    `<circle cx="32" cy="32" r="26" fill="${p.critical}" stroke="${p.surface}" stroke-width="6"/>
     <path d="M32 18v28M18 32h28" stroke="${p.surface}" stroke-width="8" stroke-linecap="round"/>`,
  );
}

/** Team site: small blue square with a white border (fixed, distinct from moving team diamonds). */
export function siteIcon(): IconDef {
  const p = palette();
  return def('site', `<rect x="5" y="5" width="54" height="54" fill="${p.blue}" stroke="${p.surface}" stroke-width="6"/>`);
}
