import { useEffect, useRef, useState, type RefObject } from "react";
import { useI18n } from "../i18n";

// Petit écran (téléphone) : la carte occupe tout l'écran, à la Google Maps — un en-tête flottant en haut,
// une barre de navigation en bas, et entre les deux un panneau qui coulisse sur trois crans.
export const MOBILE_QUERY = "(max-width: 760px)";

export type Snap = "peek" | "half" | "full";
export type NavKey = "route" | "places" | "chat";

const PEEK = 104; // la poignée + la première ligne du panneau : de quoi savoir où l'on est sans cacher la carte

export function useViewport() {
  const read = () => ({ mobile: window.matchMedia(MOBILE_QUERY).matches, h: window.innerHeight });
  const [v, setV] = useState(read);
  useEffect(() => {
    const on = () => setV((o) => {
      const n = read();
      return n.mobile === o.mobile && n.h === o.h ? o : n;
    });
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return v;
}

// Hauteur occupée en haut par la barre de recherche flottante (départ + arrivée, ou la recherche de lieux)
const topRoom = (tab: "route" | "places") => (tab === "route" ? 100 : 58);

// …mesurée pour de vrai : repliée sur une ligne après un trajet trouvé, la recherche d'itinéraire ne fait plus que
// la hauteur de la recherche de lieux, et les filtres de la carte doivent remonter avec elle. topRoom ne sert que
// tant que la barre n'est pas encore affichée (le bandeau de l'assistant, lui aussi en .hero, n'est pas visé)
export function useTopRoom(sheet: RefObject<HTMLElement | null>, tab: "route" | "places", mobile: boolean) {
  const [measured, setMeasured] = useState(0);
  useEffect(() => {
    const el = sheet.current?.querySelector<HTMLElement>(".hero:not(.chat-head)");
    if (!mobile || !el) return setMeasured(0);
    const read = () => {
      const b = el.getBoundingClientRect().bottom;
      setMeasured(el.offsetHeight ? Math.round(b) + 2 : 0);
    };
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [sheet, tab, mobile]);
  return measured || topRoom(tab);
}

// Hauteur de chaque cran, au-dessus de la barre de navigation ; plein écran, le panneau s'arrête sous la recherche
// …et jamais plus haut que son contenu (`content`, mesuré par sheetContentHeight) : un trajet court ne laisse pas
// un grand vide blanc sous les boutons quand on tire le panneau tout en haut
export function sheetHeights(viewportH: number, navH: number, top: number, content = Infinity): Record<Snap, number> {
  const full = Math.max(PEEK, Math.min(viewportH - navH - top - 6, Math.ceil(content)));
  return { peek: PEEK, half: Math.min(full, Math.round(viewportH * 0.48)), full };
}

// Hauteur qu'aurait le panneau s'il montrait tout son contenu sans défiler. On ne peut pas lire offsetHeight :
// les zones qui défilent sont étirées (flex: 1) ou coupées à la hauteur du cran. On additionne donc leurs enfants,
// en descendant dans les colonnes flex et les blocs qui défilent ; le reste (bandes horizontales, grilles,
// éléments simples) compte pour sa hauteur affichée.
function naturalHeight(el: HTMLElement): number {
  const cs = getComputedStyle(el);
  const column = cs.display.endsWith("flex") && cs.flexDirection.startsWith("column");
  const scrollingBlock = cs.display === "block" && cs.overflowY !== "visible";
  if (!column && !scrollingBlock) return el.offsetHeight;
  const px = (v: string) => parseFloat(v) || 0;
  let h = px(cs.paddingTop) + px(cs.paddingBottom) + px(cs.borderTopWidth) + px(cs.borderBottomWidth);
  let n = 0;
  for (const c of Array.from(el.children) as HTMLElement[]) {
    const ccs = getComputedStyle(c);
    if (ccs.display === "none" || ccs.position === "absolute" || ccs.position === "fixed") continue;
    h += naturalHeight(c) + px(ccs.marginTop) + px(ccs.marginBottom);
    n++;
  }
  if (column && n > 1) h += px(cs.rowGap) * (n - 1);
  return h;
}

export function sheetContentHeight(sheet: HTMLElement): number {
  // La note de bas de panneau n'apparaît qu'en plein écran : on la compte quand même, c'est là qu'on la verra
  const note = sheet.querySelector<HTMLElement>(":scope > .data-note");
  const hidden = note && getComputedStyle(note).display === "none";
  if (hidden) note.style.display = "block";
  const h = naturalHeight(sheet);
  if (hidden) note.style.display = "";
  return h;
}

type SheetProps = {
  sheet: RefObject<HTMLElement>;
  heights: Record<Snap, number>;
  snap: Snap;
  onSnap: (s: Snap) => void;
};

// Hauteur suivie par le doigt, puis posée sur un cran : partagé par la poignée (souris, clavier) et le panneau (doigt)
function sheetMotion({ sheet, heights, onSnap }: SheetProps) {
  const follow = (h: number) => {
    const el = sheet.current;
    if (!el) return;
    h = Math.min(heights.full, Math.max(heights.peek - 40, h));
    el.classList.add("dragging");
    el.style.height = `${h}px`;
    document.documentElement.style.setProperty("--sheet-h", `${h}px`);
  };
  const settle = (next: Snap) => {
    const el = sheet.current;
    if (el) {
      el.classList.remove("dragging");
      // React ne réécrit pas la hauteur si le cran ne change pas : on la remet nous-mêmes
      el.style.height = `${heights[next]}px`;
    }
    document.documentElement.style.setProperty("--sheet-h", `${heights[next]}px`);
    onSnap(next);
  };
  // Cran le plus proche de la position projetée d'après la vitesse : un coup de pouce franc passe au cran suivant
  const release = (h0: number, dy: number, ms: number) => {
    const target = h0 + dy + (dy / Math.max(1, ms)) * 180;
    settle((Object.keys(heights) as Snap[]).reduce((a, b) => (Math.abs(heights[b] - target) < Math.abs(heights[a] - target) ? b : a)));
  };
  return { follow, settle, release };
}

// Tout le panneau s'attrape au doigt, comme dans Google Maps : replié ou à moitié, un glissé vertical n'importe où
// le déplace (le contenu ne défile pas) ; ouvert en grand, le contenu défile, et tirer vers le bas une fois en haut
// de la liste referme le panneau. Les glissés horizontaux restent aux bandes défilantes (lieux, horaires).
export function useSheetDrag(props: SheetProps, enabled: boolean) {
  const latest = useRef(props);
  latest.current = props;
  useEffect(() => {
    const el = props.sheet.current;
    if (!enabled || !el) return;
    let g: { x0: number; y0: number; h0: number; t0: number; mode: "?" | "sheet" | "other"; scroller: HTMLElement | null } | null = null;
    const start = (e: TouchEvent) => {
      // La recherche du haut vit dans le panneau mais flotte sur la carte : elle ne l'entraîne pas
      if (e.touches.length !== 1 || (e.target as HTMLElement).closest(".hero")) return (g = null);
      const t = e.touches[0];
      const scroller = (e.target as HTMLElement).closest<HTMLElement>(".route-scroll, .panel-body");
      g = { x0: t.clientX, y0: t.clientY, h0: el.offsetHeight, t0: performance.now(), mode: "?", scroller };
    };
    const move = (e: TouchEvent) => {
      if (!g || g.mode === "other") return;
      const t = e.touches[0];
      const dx = t.clientX - g.x0;
      const dy = g.y0 - t.clientY; // > 0 : vers le haut
      if (g.mode === "?") {
        if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        const { snap } = latest.current;
        const atTop = !g.scroller || g.scroller.scrollTop <= 0;
        g.mode = Math.abs(dx) > Math.abs(dy) ? "other" : snap !== "full" || (dy < 0 && atTop) ? "sheet" : "other";
        if (g.mode === "other") return;
        // On repart d'ici : le panneau ne saute pas des quelques pixels du seuil
        g.y0 = t.clientY;
        g.t0 = performance.now();
      }
      if (e.cancelable) e.preventDefault();
      sheetMotion(latest.current).follow(g.h0 + (g.y0 - t.clientY));
    };
    const end = (e: TouchEvent) => {
      if (g?.mode === "sheet") {
        const y = e.changedTouches[0].clientY;
        sheetMotion(latest.current).release(g.h0, g.y0 - y, performance.now() - g.t0);
      }
      g = null;
    };
    el.addEventListener("touchstart", start, { passive: true });
    el.addEventListener("touchmove", move, { passive: false });
    el.addEventListener("touchend", end);
    el.addEventListener("touchcancel", end);
    return () => {
      el.removeEventListener("touchstart", start);
      el.removeEventListener("touchmove", move);
      el.removeEventListener("touchend", end);
      el.removeEventListener("touchcancel", end);
    };
  }, [enabled, props.sheet]);
}

// Poignée du panneau : à la souris on la fait glisser (au doigt, c'est tout le panneau qui s'attrape), et on la
// touche ou on l'active au clavier pour basculer replié / à moitié
export function SheetGrip(props: SheetProps) {
  const { t } = useI18n();
  const { snap } = props;
  const { follow, settle, release } = sheetMotion(props);
  const drag = useRef<{ y0: number; h0: number; t0: number; moved: boolean } | null>(null);
  const toggle = () => settle(snap === "peek" ? "half" : "peek");

  return (
    <div
      className="sheet-grip"
      role="button"
      tabIndex={0}
      aria-label={snap === "peek" ? t.sheetExpand : t.sheetCollapse}
      aria-expanded={snap !== "peek"}
      onClick={(e) => e.detail === 0 || drag.current || toggle()}
      onPointerDown={(e) => {
        const el = props.sheet.current;
        if (!el || e.pointerType !== "mouse") return;
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = { y0: e.clientY, h0: el.offsetHeight, t0: performance.now(), moved: false };
      }}
      onPointerMove={(e) => {
        const d = drag.current;
        if (!d) return;
        if (Math.abs(d.y0 - e.clientY) > 5) d.moved = true;
        if (d.moved) follow(d.h0 + d.y0 - e.clientY);
      }}
      onPointerUp={(e) => {
        const d = drag.current;
        if (!d) return;
        if (d.moved) release(d.h0, d.y0 - e.clientY, performance.now() - d.t0);
        // Laisse passer le clic qui suit le relâcher, puis oublie le geste
        setTimeout(() => (drag.current = null));
        if (!d.moved) drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
        settle(snap);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        } else if (e.key === "ArrowUp") settle(snap === "peek" ? "half" : "full");
        else if (e.key === "ArrowDown") settle(snap === "full" ? "half" : "peek");
      }}
    >
      <span />
    </div>
  );
}

// Pictogrammes Material Symbols (Apache 2.0)
const ICON: Record<NavKey, string> = {
  route: "M6 3a3 3 0 0 0-1 5.83V15a5 5 0 0 0 5 5h4a1 1 0 0 0 0-2h-4a3 3 0 0 1-3-3V8.83A3 3 0 0 0 6 3zm12 0a3 3 0 0 0-3 3c0 2.25 3 6 3 6s3-3.75 3-6a3 3 0 0 0-3-3zm0 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2z",
  places: "M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z",
  chat: "M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9l-5 4V5a1 1 0 0 1 1-1z",
};

type NavProps = { active: NavKey; onChange: (k: NavKey) => void; navRef: RefObject<HTMLElement> };

// Barre de navigation du bas (mobile seulement) : itinéraire, lieux, assistant
export function BottomNav({ active, onChange, navRef }: NavProps) {
  const { t } = useI18n();
  const label: Record<NavKey, string> = { route: t.tabRoute, places: t.tabPlaces, chat: t.navAssistant };
  return (
    <nav ref={navRef} className="bottom-nav" aria-label={t.navLabel}>
      {(["route", "places", "chat"] as NavKey[]).map((k) => (
        <button key={k} className={active === k ? "is-on" : ""} aria-current={active === k ? "page" : undefined} onClick={() => onChange(k)}>
          <span className="bottom-nav-icon">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d={ICON[k]} />
            </svg>
          </span>
          {label[k]}
        </button>
      ))}
    </nav>
  );
}
