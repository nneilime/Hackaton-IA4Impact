import { useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { departuresOf, fromClock, pickDeparture, toClock } from "../reliability";
import { LEVELS, type Booking, type Level } from "../school";
import { sendPrebooking } from "../prebook";
import { usePlaceSheetDrag } from "./Discovery";
import { useViewport } from "./MobileNav";

type Props = { booking: Booking; outAfter: string; backAfter: string; onClose: () => void };

// Pop-up de pré-réservation : rappel du trajet aux heures choisies, formulaire prérempli avec le projet quand on vient
// d'une idée de sortie (sinon il demande aussi le groupe), puis envoi (simulé, voir prebook.ts) et référence de la
// demande. Échap ou le fond ferment. Sur mobile, elle se tire au doigt comme la fiche d'un lieu (deux crans, glissée
// vers le bas pour fermer).
export default function PrebookSheet({ booking, outAfter, backAfter, onClose }: Props) {
  const { t, locale } = useI18n();
  const { project, outbound, inbound, visit } = booking;
  const destination = visit ? visit.title[locale] : outbound.to;
  const out = useMemo(() => pickDeparture(departuresOf(outbound), fromClock(outAfter)), [outbound, outAfter]);
  const back = useMemo(() => inbound && pickDeparture(departuresOf(inbound), fromClock(backAfter)), [inbound, backAfter]);

  const [form, setForm] = useState({
    teacher: "",
    email: "",
    phone: "",
    establishment: project?.establishment ?? "",
    level: (project?.level ?? "") as Level | "",
    classIndex: project?.classIndex ?? 0,
    students: project?.students ?? NaN,
    adults: project?.adults ?? NaN,
    date: project?.date ?? "",
    needs: "",
    message: "",
    consent: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [ref, setRef] = useState<string | null>(null);
  const first = useRef<HTMLInputElement>(null);
  const sheet = useRef<HTMLElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const { mobile, h: viewportH } = useViewport();
  const { snap, toggle } = usePlaceSheetDrag(sheet, scroller, mobile, viewportH, onClose);

  useEffect(() => {
    // Sur mobile, pas de clavier qui surgit sur une fiche encore à mi-hauteur
    if (!mobile) first.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, mobile]);

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setError(null);
  };

  async function submit() {
    if (!form.teacher.trim() || !form.email.trim() || !form.establishment.trim() || !form.level || !form.date || !form.consent) return setError(t.pbErrors.required);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return setError(t.pbErrors.email);
    const total = form.students + form.adults;
    if (!Number.isInteger(form.students) || !Number.isInteger(form.adults) || form.students < 1 || form.adults < 1) return setError(t.schoolErrors.counts);
    if (total > 50) return setError(t.schoolErrors.tooMany);
    if (total < 6) return setError(t.schoolErrors.tooFew);
    setSending(true);
    try {
      setRef(
        await sendPrebooking({
          teacher: form.teacher.trim(),
          email: form.email.trim(),
          phone: form.phone.trim(),
          establishment: form.establishment.trim(),
          level: `${t.schoolLevels[form.level]} · ${t.schoolClasses[form.level][form.classIndex]}`,
          students: form.students,
          adults: form.adults,
          date: form.date,
          destination,
          fromProject: !!project,
          outbound: { from: outbound.from, to: outbound.to, departure: toClock(out.minute), arrival: toClock(out.arrival) },
          inbound: inbound && back && { from: inbound.from, to: inbound.to, departure: toClock(back.minute), arrival: toClock(back.arrival) },
          needs: form.needs.trim(),
          message: form.message.trim(),
        }),
      );
    } finally {
      setSending(false);
    }
  }

  const dateLabel = form.date ? new Date(form.date + "T12:00").toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" }) : "";
  const summary = (
    <div className="pb-trip">
      <strong>{destination}</strong>
      {dateLabel && <span className="pb-date">{dateLabel}</span>}
      <dl>
        <div>
          <dt>{t.tripOut}</dt>
          <dd>
            <b>{toClock(out.minute)}</b> {outbound.from} → <b>{toClock(out.arrival)}</b> {outbound.to}
          </dd>
        </div>
        {inbound && back && (
          <div>
            <dt>{t.tripBack}</dt>
            <dd>
              <b>{toClock(back.minute)}</b> {inbound.from} → <b>{toClock(back.arrival)}</b> {inbound.to}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <article
        ref={sheet}
        className={`sheet sheet-place pb${mobile ? ` is-${snap}` : ""}`}
        role="dialog" aria-modal="true" aria-labelledby="pb-title" onClick={(e) => e.stopPropagation()}>
        {mobile && (
          <button className="place-grip" onClick={toggle} aria-label={snap === "half" ? t.sheetExpand : t.sheetCollapse} aria-expanded={snap === "full"}>
            <span />
          </button>
        )}
        <button className="sheet-close" onClick={onClose} aria-label={t.close}>
          ×
        </button>
        <div ref={scroller} className="sheet-scroll">
          <div className="sheet-body">
            {ref ? (
              <div className="pb-done">
                <span className="pb-check" aria-hidden="true">
                  ✓
                </span>
                <h2 id="pb-title">{t.pbDoneTitle}</h2>
                <p className="pb-ref">{ref}</p>
                <p>{t.pbDone(form.email.trim())}</p>
                {summary}
                <p className="pb-demo">{t.pbDemo}</p>
                <button className="cta" onClick={onClose}>
                  {t.close}
                </button>
              </div>
            ) : (
              <form
                className="school-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void submit();
                }}
              >
                <h2 id="pb-title">{t.pbTitle}</h2>
                <p className="pb-lead">{t.pbLead}</p>
                {summary}

                <h3 className="pb-section">{t.pbContact}</h3>
                <label className="school-field">
                  {t.pbName}
                  <input ref={first} required value={form.teacher} onChange={(e) => set("teacher", e.target.value)} autoComplete="name" />
                </label>
                <div className="school-row">
                  <label className="school-field">
                    {t.pbEmail}
                    <input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} autoComplete="email" />
                  </label>
                  <label className="school-field">
                    {t.pbPhone}
                    <input type="tel" value={form.phone} onChange={(e) => set("phone", e.target.value)} autoComplete="tel" placeholder={t.schoolOptional} />
                  </label>
                </div>

                <h3 className="pb-section">{t.pbGroup}</h3>
                {!project && <p className="school-help">{t.pbNoProject}</p>}
                <label className="school-field">
                  {t.schoolEstablishment}
                  <input required value={form.establishment} onChange={(e) => set("establishment", e.target.value)} />
                </label>
                {/* Niveau et classe : repris du projet, demandés seulement quand on vient de la carte */}
                {!project && (
                  <div className="school-row">
                    <label className="school-field">
                      {t.schoolLevel}
                      <select
                        required
                        value={form.level}
                        onChange={(e) => {
                          set("level", e.target.value as Level);
                          set("classIndex", 0);
                        }}
                      >
                        <option value="" disabled>
                          {t.pbLevelPh}
                        </option>
                        {LEVELS.map((l) => (
                          <option key={l} value={l}>
                            {t.schoolLevels[l]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="school-field">
                      {t.schoolClass}
                      <select required disabled={!form.level} value={form.classIndex} onChange={(e) => set("classIndex", Number(e.target.value))}>
                        {(form.level ? t.schoolClasses[form.level] : []).map((c, i) => (
                          <option key={c} value={i}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
                <div className="school-row">
                  <label className="school-field">
                    {t.schoolStudents}
                    <input type="number" min={1} max={49} required value={Number.isFinite(form.students) ? form.students : ""} onChange={(e) => set("students", e.target.valueAsNumber)} />
                  </label>
                  <label className="school-field">
                    {t.schoolAdults}
                    <input type="number" min={1} max={49} required value={Number.isFinite(form.adults) ? form.adults : ""} onChange={(e) => set("adults", e.target.valueAsNumber)} />
                  </label>
                </div>
                <label className="school-field">
                  {t.schoolDate}
                  <input type="date" required value={form.date} onChange={(e) => set("date", e.target.value)} />
                </label>
                <label className="school-field">
                  {t.schoolAccess}
                  <input value={form.needs} onChange={(e) => set("needs", e.target.value)} placeholder={t.schoolAccessPh} />
                </label>
                <label className="school-field">
                  {t.pbMessage}
                  <textarea rows={3} value={form.message} onChange={(e) => set("message", e.target.value)} placeholder={t.schoolOptional} />
                </label>
                <label className="pb-consent">
                  <input type="checkbox" checked={form.consent} onChange={(e) => set("consent", e.target.checked)} />
                  <span>{t.pbConsent}</span>
                </label>
                {error && <p className="alert">{error}</p>}
                <button className="cta" type="submit" disabled={sending}>
                  {sending ? t.pbSending : t.pbSend}
                </button>
                <p className="pb-demo">{t.pbDemo}</p>
              </form>
            )}
          </div>
        </div>
      </article>
    </div>
  );
}
