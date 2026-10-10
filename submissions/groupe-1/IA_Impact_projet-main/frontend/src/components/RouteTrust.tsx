// Indice de fiabilité et avis d'enseignants d'un trajet (données de démonstration, voir reliability.ts)
import { useEffect, useRef } from "react";
import { OFFER_MAX, OFFER_MIN, toClock, type Departure, type Review } from "../reliability";
import { useI18n } from "../i18n";

const fmt = (n: number, locale: string) => n.toLocaleString(locale, { maximumFractionDigits: 1 });

// Départs de la journée, chacun avec son indice ; le détail de fiabilité du choisi ne s'ouvre qu'à la demande
// (survol sur PC, appui sur l'horaire ou sur la pastille déjà choisie sur mobile) pour gagner de la place
export function Departures({ departures, selected, after, onAfter, relOpen, onRel }: { departures: Departure[]; selected: Departure; after: string; onAfter: (v: string) => void; relOpen: boolean; onRel: (open: boolean) => void }) {
  const { t, locale } = useI18n();
  const strip = useRef<HTMLDivElement>(null);
  const chip = useRef<HTMLButtonElement>(null);
  // Le départ choisi reste visible dans la bande (sans faire défiler le panneau lui-même)
  useEffect(() => {
    const s = strip.current, c = chip.current;
    if (s && c) s.scrollTo({ left: c.offsetLeft - s.clientWidth / 2 + c.clientWidth / 2, behavior: "smooth" });
  }, [selected]);
  const rel = selected.rel;
  return (
    <div className="deps">
      <div className="deps-strip" ref={strip}>
        <label className="deps-after">
          <span>{t.depAfter}</span>
          <input type="time" min={OFFER_MIN} max={OFFER_MAX} value={after} onChange={(e) => e.target.value && onAfter(e.target.value < OFFER_MIN ? OFFER_MIN : e.target.value > OFFER_MAX ? OFFER_MAX : e.target.value)} />
        </label>
        {departures.map((d) => (
          <button
            key={d.minute}
            ref={d === selected ? chip : undefined}
            type="button"
            className={`dep-chip rel-${d.rel.level}${d === selected ? " is-on" : ""}`}
            aria-pressed={d === selected}
            aria-label={t.depChip(toClock(d.minute), d.rel.score)}
            onClick={() => (d === selected ? onRel(!relOpen) : onAfter(toClock(d.minute)))}
          >
            <strong>{toClock(d.minute)}</strong>
            <span>{d.rel.score}</span>
          </button>
        ))}
      </div>
      <p className={`rel-line rel-${rel.level}${relOpen ? " is-open" : ""}`} title={t.relObserved(rel.observed)}>
        <b>
          {rel.score}
          <small>/100</small> {t.relLevels[rel.level]}
        </b>
        <span>{t.relOnTime(rel.punctuality)}</span>
        <span>{t.relDelayShort(fmt(rel.avgDelay, locale))}</span>
        <span>{t.relCancelShort(fmt(rel.cancelRate, locale))}</span>
        {rel.missedTransfers > 0 && <span>{t.relMissedShort(rel.missedTransfers)}</span>}
      </p>
    </div>
  );
}

const Stars = ({ n, label }: { n: number; label: string }) => (
  <span className="stars" role="img" aria-label={label}>
    {"★".repeat(n)}
    <span className="stars-off">{"★".repeat(5 - n)}</span>
  </span>
);

export function TeacherReviews({ reviews }: { reviews: Review[] }) {
  const { t, locale } = useI18n();
  const avg = reviews.reduce((s, r) => s + r.rating, 0) / reviews.length;
  return (
    <details className="reviews">
      <summary>
        <span className="reviews-title">{t.reviewsTitle}</span>
        <Stars n={Math.round(avg)} label={t.reviewStars(+avg.toFixed(1))} />
        <span className="reviews-avg">{fmt(avg, locale)}</span>
        <span className="reviews-count">{t.reviewsCount(reviews.length)}</span>
      </summary>
      <span className="demo-tag">{t.demoData}</span>
      <ul>
        {reviews.map((r, i) => (
          <li key={i}>
            <div className="review-head">
              <span className="review-avatar" aria-hidden="true">
                {r.author.split(" ").pop()![0]}
              </span>
              <span className="review-who">
                <strong>{r.author}</strong>
                <small>
                  {r.role[locale]} · {r.school}
                </small>
              </span>
              <Stars n={r.rating} label={t.reviewStars(r.rating)} />
            </div>
            <p>{r.text[locale]}</p>
            <small className="review-meta">
              {r.train !== undefined && <>{t.reviewTrain(toClock(r.train))} · </>}
              {t.reviewAgo(r.monthsAgo)} · {t.reviewGroup(r.group)}
            </small>
          </li>
        ))}
      </ul>
    </details>
  );
}
