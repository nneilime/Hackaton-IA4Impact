import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { Place } from "../api";
import { useI18n } from "../i18n";
import { CategoryIcon } from "./CategoryIcon";
import { useViewport } from "./MobileNav";
import { WALK_LIMIT_KM, creditOf, distanceKm, imageOf, modelCreditOf, modelOf, walkMinutes, type Discovery } from "../data/discoveries";

const ModelViewer = lazy(() => import("./ModelViewer"));

// Photo du lieu ; si elle manque (pas encore téléchargée, hors ligne), un aplat aux couleurs de la charte
export function DiscoveryImage({ d, className }: { d: Discovery; className?: string }) {
  const { t, locale } = useI18n();
  const [failed, setFailed] = useState(false);
  return failed ? (
    <div className={`disc-img disc-img-empty cat-${d.category} ${className ?? ""}`} aria-hidden="true">
      <CategoryIcon category={d.category} />
      <span>{t.categories[d.category]}</span>
    </div>
  ) : (
    <img className={`disc-img ${className ?? ""}`} src={imageOf(d)} alt={d.title[locale]} loading="lazy" onError={() => setFailed(true)} />
  );
}

// « À 12 min à pied de Nîmes Centre », ou la distance quand c'est trop loin pour marcher
export function useDistanceLabel() {
  const { t, locale } = useI18n();
  return (d: Discovery, station: Place | undefined) => {
    if (!station) return "";
    const km = distanceKm(d, station);
    return km <= WALK_LIMIT_KM
      ? t.walkFrom(walkMinutes(km), station.name)
      : t.farFrom(km.toLocaleString(locale, { maximumFractionDigits: 1 }), station.name);
  };
}

type CardProps = { d: Discovery; station: Place | undefined; onOpen: (d: Discovery) => void; layout: "tile" | "row" };

// Vignette cliquable : « tile » dans le carrousel, « row » sous une gare sélectionnée
export function DiscoveryCard({ d, station, onOpen, layout }: CardProps) {
  const { locale } = useI18n();
  const distance = useDistanceLabel();
  return (
    <button className={`disc-card disc-${layout}`} onClick={() => onOpen(d)}>
      <DiscoveryImage d={d} />
      <span className="disc-text">
        <strong>{d.title[locale]}</strong>
        <span className="disc-distance">{distance(d, station)}</span>
        <span className="disc-summary">{d.summary[locale]}</span>
      </span>
    </button>
  );
}

// Sur téléphone, la fiche est un panneau qui monte du bas, à deux crans (à moitié, puis presque plein écran).
// On l'attrape n'importe où au doigt, comme le panneau principal : à moitié, un glissé vertical la déplace ;
// ouverte en grand, le texte défile, et tirer vers le bas une fois en haut du texte la ramène. Lâchée sous le
// premier cran (ou d'un coup de pouce franc vers le bas), elle glisse hors de l'écran et se ferme.
type PlaceSnap = "half" | "full";

// Partagé avec la pré-réservation (PrebookSheet.tsx), pour que toutes les fiches mobiles se tiennent pareil
export function usePlaceSheetDrag(
  sheet: React.RefObject<HTMLElement>,
  scroller: React.RefObject<HTMLElement>,
  enabled: boolean,
  viewportH: number,
  onClose: () => void,
) {
  const [snap, setSnap] = useState<PlaceSnap>("half");
  const latest = useRef({ snap, onClose });
  latest.current = { snap, onClose };
  const heights = { half: Math.round(viewportH * 0.55), full: Math.round(viewportH * 0.92) };
  const hs = useRef(heights);
  hs.current = heights;

  // Hauteur suivie par le doigt ; sous le premier cran, la fiche ne rétrécit plus, elle descend (et le fond s'éclaircit)
  const place = (h: number, animate: boolean) => {
    const el = sheet.current;
    if (!el) return;
    const { half, full } = hs.current;
    h = Math.min(full, h);
    el.classList.toggle("dragging", !animate);
    el.style.height = `${Math.max(half, h)}px`;
    el.style.translate = `0 ${Math.max(0, half - h)}px`;
    const backdrop = el.parentElement;
    if (backdrop) backdrop.style.backgroundColor = `rgba(15, 33, 73, ${0.55 * Math.max(0, Math.min(1, h / half))})`;
  };

  const settle = (next: PlaceSnap) => {
    place(hs.current[next], true);
    setSnap(next);
  };

  const dismiss = () => {
    place(-hs.current.half * 0.2, true);
    const el = sheet.current;
    if (el) el.style.translate = "0 100%";
    window.setTimeout(() => latest.current.onClose(), 220);
  };

  // Le cran suit la hauteur de l'écran (rotation, barre d'adresse qui se replie)
  useEffect(() => {
    if (enabled) place(hs.current[latest.current.snap], true);
    else if (sheet.current) {
      sheet.current.style.height = sheet.current.style.translate = "";
      if (sheet.current.parentElement) sheet.current.parentElement.style.backgroundColor = "";
    }
  }, [enabled, viewportH]);

  useEffect(() => {
    const el = sheet.current;
    if (!enabled || !el) return;
    let g: { x0: number; y0: number; h0: number; t0: number; mode: "?" | "sheet" | "other" } | null = null;
    const start = (e: TouchEvent) => {
      // Le modèle 3D se tourne au doigt : il garde ses gestes
      if (e.touches.length !== 1 || (e.target as HTMLElement).closest(".model-viewer")) return (g = null);
      const t = e.touches[0];
      g = { x0: t.clientX, y0: t.clientY, h0: el.offsetHeight, t0: performance.now(), mode: "?" };
    };
    const move = (e: TouchEvent) => {
      if (!g || g.mode === "other") return;
      const t = e.touches[0];
      const dx = t.clientX - g.x0;
      const dy = g.y0 - t.clientY; // > 0 : vers le haut
      if (g.mode === "?") {
        if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        const atTop = (scroller.current?.scrollTop ?? 0) <= 0;
        g.mode = Math.abs(dx) > Math.abs(dy) ? "other" : latest.current.snap === "half" || (dy < 0 && atTop) ? "sheet" : "other";
        if (g.mode === "other") return;
        g.y0 = t.clientY;
        g.t0 = performance.now();
      }
      if (e.cancelable) e.preventDefault();
      place(g.h0 + (g.y0 - t.clientY), false);
    };
    const end = (e: TouchEvent) => {
      if (g?.mode === "sheet") {
        const dy = g.y0 - e.changedTouches[0].clientY;
        const target = g.h0 + dy + (dy / Math.max(1, performance.now() - g.t0)) * 180;
        const { half, full } = hs.current;
        if (target < half * 0.7) dismiss();
        else settle(Math.abs(full - target) < Math.abs(half - target) ? "full" : "half");
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
  }, [enabled]);

  return { snap, toggle: () => settle(latest.current.snap === "half" ? "full" : "half") };
}

type SheetProps = {
  d: Discovery;
  station: Place | undefined;
  onClose: () => void;
  onPick: (which: "from" | "to", name: string, visit?: Discovery) => void;
};

// Fiche complète d'un lieu, en surimpression ; Échap ou un clic sur le fond la ferment
export function DiscoverySheet({ d, station, onClose, onPick }: SheetProps) {
  const { t, locale } = useI18n();
  const distance = useDistanceLabel();
  const closeBtn = useRef<HTMLButtonElement>(null);
  const sheet = useRef<HTMLElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const { mobile, h: viewportH } = useViewport();
  const { snap, toggle } = usePlaceSheetDrag(sheet, scroller, mobile, viewportH, onClose);
  const model = modelOf(d);
  const [show3d, setShow3d] = useState(false);
  const credit = show3d ? modelCreditOf(d) : creditOf(d);

  useEffect(() => {
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [d, onClose]);

  useEffect(() => setShow3d(false), [d]);

  const pick = (which: "from" | "to") => {
    if (!station) return;
    onPick(which, station.name, d); // le lieu suit jusqu'à la pré-réservation
    onClose();
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <article
        ref={sheet}
        className={`sheet sheet-place${mobile ? ` is-${snap}` : ""}`}
        role="dialog" aria-modal="true" aria-labelledby="sheet-title" onClick={(e) => e.stopPropagation()}>
        {mobile && (
          <button className="place-grip" onClick={toggle} aria-label={snap === "half" ? t.sheetExpand : t.sheetCollapse} aria-expanded={snap === "full"}>
            <span />
          </button>
        )}
        {/* Hors de la zone qui défile : la croix et les deux boutons restent visibles. */}
        <button ref={closeBtn} className="sheet-close" onClick={onClose} aria-label={t.close}>
          ×
        </button>
        <div ref={scroller} className="sheet-scroll">
          <div className={`sheet-hero${show3d ? " sheet-hero-3d" : ""}`}>
            {show3d && model ? (
              <Suspense fallback={null}>
                <ModelViewer src={model} label={t.model3dOf(d.title[locale])} />
              </Suspense>
            ) : (
              <DiscoveryImage d={d} />
            )}
            {model && (
              <button className="sheet-3d" onClick={() => setShow3d(!show3d)} aria-pressed={show3d}>
                {show3d ? t.showPhoto : t.show3d}
              </button>
            )}
            {credit && (
              <a className="sheet-credit" href={credit.source} target="_blank" rel="noreferrer">
                {show3d ? t.modelBy(credit.author) : t.photoBy(credit.author)}
                {credit.license && ` · ${credit.license}`}
              </a>
            )}
          </div>
          <div className="sheet-body">
            <div className="sheet-tags">
              <span className={`disc-cat cat-${d.category}`}>
                <CategoryIcon category={d.category} />
                {t.categories[d.category]}
              </span>
              <span className="disc-era">{d.era[locale]}</span>
            </div>
            <h2 id="sheet-title">{d.title[locale]}</h2>
            {station && <p className="sheet-distance">{distance(d, station)}</p>}
            <p className="sheet-lead">{d.summary[locale]}</p>
            {d.description.map((para, i) => (
              <p key={i}>{para[locale]}</p>
            ))}
            <aside className="sheet-fact">
              <strong>{t.didYouKnow}</strong>
              <p>{d.didYouKnow[locale]}</p>
            </aside>
          </div>
        </div>
        {station && (
          <div className="sheet-actions">
            <button onClick={() => pick("from")}>{t.leaveFromStation}</button>
            <button onClick={() => pick("to")}>{t.goToStation}</button>
          </div>
        )}
      </article>
    </div>
  );
}
