import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { WALK, type ErrorCode, type Place, type Route } from "../api";
import { formatMinutes, useI18n } from "../i18n";
import Trame from "./Trame";
import PlaceInput from "./PlaceInput";
import { Departures, TeacherReviews } from "./RouteTrust";
import { departuresOf, fromClock, pickDeparture, reliabilityOf, reviewsOf, toClock } from "../reliability";
import type { TrainSim } from "../sim";

export type TripDir = "out" | "back";
// Aller + retour, chacun avec son heure choisie : une idée de sortie du projet scolaire, ou un trajet simple
// auquel on a ajouté le retour (retirable)
type Trip = {
  outbound: Route;
  inbound: Route | null; // null : idée de sortie en aller simple, pas de bascule
  dir: TripDir;
  outAfter: string;
  backAfter: string;
  onDir: (d: TripDir) => void;
  onRemove?: () => void; // retire le retour (l'aller reste) ; « Vous revenez aussi ? » le remet
};

type Props = {
  places: Place[];
  from: string;
  to: string;
  setFrom: (v: string) => void;
  setTo: (v: string) => void;
  onSearch: () => void;
  loading: boolean;
  route: Route | null;
  error: ErrorCode | null;
  departAfter: string; // « HH:MM »
  setDepartAfter: (v: string) => void;
  trip: Trip | null;
  sim: TrainSim | null;
  onSimulate: () => void;
  onBack: () => void;
  onAddReturn: () => void;
  addingReturn: boolean;
  // Pré-réservation, ouverte aux deux parcours (idée de sortie ou trajet trouvé sur la carte). Absente : le trajet
  // n'est pas faisable en groupe (car, TGV, correspondance trop courte) et on dit pourquoi
  onPrebook?: () => void;
  fromProject: boolean; // le lien du haut ramène au projet, ou simplement à une nouvelle recherche
  children?: ReactNode; // affiché sous le formulaire tant qu'aucun trajet n'est là (le projet de sortie scolaire)
};

const slug = (mode: string) => mode.replace(/\s+/g, "-").toLowerCase();
// Au-delà, une correspondance est signalée comme longue sur la frise
const LONG_WAIT = 30;

export default function RoutePanel({ places, from, to, setFrom, setTo, onSearch, loading, route, error, departAfter, setDepartAfter, trip, sim, onSimulate, onBack, onAddReturn, addingReturn, onPrebook, fromProject, children }: Props) {
  const { t } = useI18n();
  const nameOf = useMemo(() => new Map(places.map((p) => [p.id, p.name])), [places]);
  const [first, ...rest] = t.headline.split(" ");
  // Un nouveau trajet s'affiche depuis le haut (le formulaire du dessous a pu être défilé)
  const body = useRef<HTMLElement>(null);
  useEffect(() => {
    body.current?.scrollTo({ top: 0 });
  }, [route]);
  // Détail de la jauge de confiance : replié par défaut, ouvert par un appui sur l'horaire ; tout appui ailleurs le referme
  const [relOpen, setRelOpen] = useState(false);
  // Recherche pliable : repliée dès qu'un trajet s'affiche (on ne garde que « départ → arrivée »), rouverte sans trajet
  const [folded, setFolded] = useState(false);
  useEffect(() => {
    setFolded(!!route);
  }, [route]);
  useEffect(() => {
    if (!relOpen) return;
    const close = (e: PointerEvent) => {
      if (!(e.target as Element).closest?.(".total, .dep-chip.is-on, .rel-line")) setRelOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [relOpen]);
  const rel = useMemo(() => (route ? reliabilityOf(route) : null), [route]);
  const departures = useMemo(() => (route ? departuresOf(route) : []), [route]);
  const dep = departures.length ? pickDeparture(departures, fromClock(departAfter)) : null;
  // Les avis suivent le départ choisi : changer d'horaire change les avis et leur note
  const reviews = useMemo(
    () => (route && rel ? (dep ? reviewsOf(route, dep.rel, dep.minute) : reviewsOf(route, rel)) : []),
    [route, rel, dep],
  );
  // Heure de passage à chaque arrêt pour le départ choisi : départ + accès, puis attente + trajet de chaque tronçon
  const legStarts = useMemo(() => {
    if (!route || !dep) return [];
    let at = dep.minute + route.access_minutes;
    return route.legs.map((leg) => {
      at += leg.wait_minutes;
      const start = at;
      at += leg.minutes;
      return start;
    });
  }, [route, dep]);
  // Heures retenues pour l'aller et le retour, affichées dans le sélecteur même quand l'autre sens est à l'écran
  const legs = useMemo(() => {
    if (!trip?.inbound) return null;
    const out = pickDeparture(departuresOf(trip.outbound), fromClock(trip.outAfter));
    const back = pickDeparture(departuresOf(trip.inbound), fromClock(trip.backAfter));
    // Même règle que l'heure de retour proposée pour une idée de sortie (scheduleOf) : au moins une heure sur place
    return { out, back, tooEarly: back.minute < out.arrival + 60 };
  }, [trip]);

  return (
    <>
      <form
        className={folded ? "hero is-folded" : "hero"}
        onSubmit={(e) => {
          e.preventDefault();
          onSearch();
        }}
      >
        {folded ? (
          <button type="button" className="hero-summary" onClick={() => setFolded(false)} aria-expanded={false} title={t.unfoldSearch}>
            <span className="hero-summary-od">
              <span className="dot dot-yellow" aria-hidden="true" />
              <span className="hero-summary-name">{from}</span>
              <span className="hero-summary-arrow" aria-hidden="true">→</span>
              <span className="dot dot-red" aria-hidden="true" />
              <span className="hero-summary-name">{to}</span>
            </span>
            <span className="sr-only">{t.unfoldSearch}</span>
            <Chevron />
          </button>
        ) : (
          <div className="hero-head">
            <h1>
              <u>{first}</u> {rest.join(" ")}
            </h1>
            {route && (
              <button type="button" className="fold-toggle" onClick={() => setFolded(true)} aria-expanded={true} title={t.foldSearch} aria-label={t.foldSearch}>
                <Chevron />
              </button>
            )}
          </div>
        )}
        <div className="od" hidden={folded}>
          <label className="field">
            <span className="dot dot-yellow" aria-hidden="true" />
            <span className="sr-only">{t.from}</span>
            <PlaceInput places={places} value={from} onChange={setFrom} placeholder={t.fromPh} />
          </label>
          <label className="field">
            <span className="dot dot-red" aria-hidden="true" />
            <span className="sr-only">{t.to}</span>
            <PlaceInput places={places} value={to} onChange={setTo} placeholder={t.toPh} />
          </label>
          <button
            type="button"
            className="swap"
            title={t.swap}
            aria-label={t.swap}
            onClick={() => {
              setFrom(to);
              setTo(from);
            }}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 4v16M8 4 4 8M8 4l4 4M16 20V4M16 20l-4-4M16 20l4-4" />
            </svg>
          </button>
        </div>
        <button className="cta" type="submit" hidden={folded} disabled={loading || !from.trim() || !to.trim()} aria-label={loading ? t.searching : t.search}>
          {/* Sur mobile, le bouton n'est plus qu'une loupe au bout du champ d'arrivée */}
          <svg className="cta-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M10.5 4a6.5 6.5 0 0 1 5.2 10.4l4.4 4.4-1.4 1.4-4.4-4.4A6.5 6.5 0 1 1 10.5 4zm0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z" />
          </svg>
          <span className="cta-label">{loading ? t.searching : t.search}</span>
        </button>
        {!folded && <Trame className="hero-trame" rows={2} columns={30} />}
      </form>

      <section ref={body} className={route ? "panel-body has-route" : "panel-body"} aria-live="polite">
        {(route || error) && (
          <button type="button" className="back-link" onClick={onBack}>
            ← {fromProject ? t.schoolBackToProject : t.newSearch}
          </button>
        )}
        {error && <p className="alert">{t.errors[error]}</p>}
        {/* Gardé monté (caché) pour ne pas perdre le projet saisi quand on regarde un trajet */}
        <div hidden={!!(route || error)}>{children}</div>
        {route && (
          <>
            {trip && legs && (
              <div className="trip-dirs" role="tablist">
                {(["out", "back"] as TripDir[]).map((d) => {
                  const dep = d === "out" ? legs.out : legs.back;
                  return (
                    <button key={d} type="button" role="tab" aria-selected={trip.dir === d} className={trip.dir === d ? "is-on" : undefined} onClick={() => trip.onDir(d)}>
                      <span>{d === "out" ? t.tripOut : t.tripBack}</span>
                      <strong>
                        {toClock(dep.minute)} → {toClock(dep.arrival)}
                      </strong>
                    </button>
                  );
                })}
              </div>
            )}
            {trip?.onRemove && trip.inbound && (
              <button type="button" className="trip-remove" onClick={trip.onRemove}>
                ✕ {t.returnRemove}
              </button>
            )}
            {legs?.tooEarly && <p className="alert trip-warn">{t.tripTooEarly}</p>}
            <div className={dep ? "total has-rel" : "total"} onClick={dep ? () => setRelOpen((o) => !o) : undefined}>
              <span className="total-label">{t.total}</span>
              <span className="total-value">{formatMinutes(route.minutes)}</span>
              {dep && !legs && (
                <span className="total-clock">
                  {toClock(dep.minute)} → {toClock(dep.arrival)}
                </span>
              )}
              <span className={route.transfers ? "total-sub" : "total-sub is-direct"}>
                {route.transfers ? t.transfers(route.transfers) : t.direct}
              </span>
            </div>
            {!trip?.inbound && (
              <div className="return-ask">
                <span className="return-ask-icon" aria-hidden="true">⇄</span>
                <span className="return-ask-text" title={t.returnAskSub}>
                  <strong>{t.returnAsk}</strong>
                </span>
                <button type="button" onClick={onAddReturn} disabled={addingReturn}>
                  {addingReturn ? t.returnAdding : `+ ${t.returnAdd}`}
                </button>
              </div>
            )}
            {dep && <Departures departures={departures} selected={dep} after={departAfter} onAfter={setDepartAfter} relOpen={relOpen} onRel={setRelOpen} />}
            <div className="route-scroll">
            <ol className="timeline">
              {route.legs.map((leg, i) => (
                <li key={i} className={i === 0 ? "first" : undefined}>
                  {i === 0 && route.access_minutes > 0 && <span className="change access">{t.access(formatMinutes(route.access_minutes))}</span>}
                  {i === 0 && (
                    <span className="stop">
                      {leg.from}
                      {dep && <time className="stop-clock">{toClock(legStarts[i])}</time>}
                    </span>
                  )}
                  {/* Attente en correspondance : la frise s'interrompt (pointillés) autour d'une horloge, rouge si l'attente est longue */}
                  {i > 0 && leg.wait_minutes > 0 && (
                    <span className={leg.wait_minutes >= LONG_WAIT ? "change wait long" : "change wait"}>{t.change(formatMinutes(leg.wait_minutes))}</span>
                  )}
                  <span className="leg">
                    <span className={`mode mode-${slug(leg.mode)}`}>{leg.network || (t.modes[leg.mode] ?? leg.mode)}</span>
                    <span className="leg-time">{formatMinutes(leg.minutes)}</span>
                    {leg.mode === WALK ? (
                      <span className="leg-meta">{leg.line}</span>
                    ) : (
                      <>
                        <span className="leg-meta">{t.perDay(leg.trips_per_day ?? 0)}</span>
                        {leg.line && <span className="leg-line">{leg.line}</span>}
                        {/* Arrêts intermédiaires, repliés par défaut, avec leur temps depuis le départ */}
                        {leg.stops.length > 2 ? (
                          <details className="leg-stops">
                            <summary>{t.stopsCount(leg.stops.length - 2)}</summary>
                            <ol>
                              {leg.stops.slice(1, -1).map((id, k) => (
                                <li key={id}>
                                  <span>{nameOf.get(id) ?? id}</span>
                                  <span className="leg-stop-time">{dep ? toClock(legStarts[i] + leg.times[k + 1]) : `+${formatMinutes(leg.times[k + 1])}`}</span>
                                </li>
                              ))}
                            </ol>
                          </details>
                        ) : (
                          <span className="leg-line">{t.stopsCount(0)}</span>
                        )}
                      </>
                    )}
                  </span>
                  <span className={i === route.legs.length - 1 ? "stop last" : "stop"}>
                    {leg.to}
                    {dep && <time className="stop-clock">{toClock(legStarts[i] + leg.minutes)}</time>}
                  </span>
                  {i === route.legs.length - 1 && route.egress_minutes > 0 && (
                    <span className="change access">{t.egress(formatMinutes(route.egress_minutes))}</span>
                  )}
                </li>
              ))}
            </ol>
            {reviews.length > 0 && <TeacherReviews reviews={reviews} />}
            </div>
            {route.transfers > 0 && <p className="estimate">{t.estimateNote}</p>}
            {!onPrebook && <p className="estimate">{t.prebookNotGroup}</p>}
            <div className="route-actions">
              {onPrebook && (
                <button className="cta" onClick={onPrebook}>
                  {t.prebook}
                </button>
              )}
              {!sim && (
                <button className={onPrebook ? "cta sim-cta is-secondary" : "cta sim-cta"} onClick={onSimulate}>
                  <span aria-hidden="true">▶</span> {t.simulate}
                </button>
              )}
            </div>
          </>
        )}
      </section>
    </>
  );
}

function Chevron() {
  return (
    <svg className="chevron" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
