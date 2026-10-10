import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, type Place } from "../api";
import { useI18n } from "../i18n";
import { CategoryIcon } from "./CategoryIcon";
import PlaceInput from "./PlaceInput";
import { OFFER_MAX, OFFER_MIN } from "../reliability";
import { INITIAL_PROJECT, LEVELS, THEMES, TRIP_TYPES, searchSchoolTrips, travellers, validateProject, type Proposal, type SchoolProject } from "../school";

type Props = {
  places: Place[];
  byId: Map<string, Place>;
  onResults: (found: Proposal[] | null) => void; // null : plus de résultats (formulaire modifié, nouvelle recherche)
};

// Formulaire du projet de sortie scolaire (repris de la branche d'Aymeric), sous les champs départ / arrivée tant
// qu'aucun trajet n'est affiché. Les idées trouvées partent dans le bandeau du bas et sur la carte (voir RecoPanel).
export default function SchoolForm({ places, byId, onResults }: Props) {
  const { t } = useI18n();
  const [project, setProject] = useState<SchoolProject>({ ...INITIAL_PROJECT });
  const [results, setResults] = useState<Proposal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const stations = useMemo(() => places.filter((p) => p.network === "sncf"), [places]);

  function change<K extends keyof SchoolProject>(key: K, value: SchoolProject[K]) {
    pending.current?.abort();
    setLoading(false);
    setProject((p) => ({ ...p, [key]: value }));
    if (results) onResults(null);
    setResults(null);
    setError(null);
  }

  async function search() {
    const invalid = validateProject(project);
    if (invalid) return setError(t.schoolErrors[invalid]);
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError(null);
    setResults(null);
    onResults(null);
    try {
      const found = await searchSchoolTrips(project, byId, controller.signal);
      if (controller.signal.aborted) return;
      setResults(found);
      onResults(found);
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(t.schoolErrors[e instanceof ApiError && e.code === "unknown_place" ? "unknown_place" : "network"]);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  const total = travellers(project);
  return (
    <>
      <div className="school-body">
        <h2 className="school-title">{t.schoolEyebrow}</h2>
        <p className="school-lead">{t.schoolLead}</p>
        <form
          className="school-form"
          onSubmit={(e) => {
            e.preventDefault();
            void search();
          }}
        >
          <label className="school-field">
            {t.schoolEstablishment}
            <input required value={project.establishment} onChange={(e) => change("establishment", e.target.value)} />
          </label>
          <label className="school-field">
            {t.schoolOrigin}
            <PlaceInput required places={stations} value={project.origin} onChange={(v) => change("origin", v)} />
          </label>
          <p className="school-help">{t.schoolOriginHelp}</p>
          <div className="school-row">
            <label className="school-field">
              {t.schoolLevel}
              <select
                value={project.level}
                onChange={(e) => {
                  change("level", e.target.value as SchoolProject["level"]);
                  change("classIndex", 0);
                }}
              >
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {t.schoolLevels[l]}
                  </option>
                ))}
              </select>
            </label>
            <label className="school-field">
              {t.schoolClass}
              <select value={project.classIndex} onChange={(e) => change("classIndex", Number(e.target.value))}>
                {t.schoolClasses[project.level].map((c, i) => (
                  <option key={c} value={i}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {/* Mêmes thèmes et mêmes icônes que les filtres de la carte */}
          <div className="school-field">
            <span id="school-theme">{t.schoolTheme}</span>
            <div className="school-themes" role="radiogroup" aria-labelledby="school-theme">
              {THEMES.map((th) => (
                <button
                  key={th}
                  type="button"
                  role="radio"
                  aria-checked={project.theme === th}
                  className={`cat-chip-${th}${project.theme === th ? " is-on" : ""}`}
                  onClick={() => change("theme", th)}
                >
                  {th !== "all" && <CategoryIcon category={th} />}
                  {t.schoolThemes[th]}
                </button>
              ))}
            </div>
          </div>
          <div className="school-row">
            <label className="school-field">
              {t.schoolStudents}
              <input type="number" required min="1" max="50" value={project.students} onChange={(e) => change("students", e.target.valueAsNumber)} />
            </label>
            <label className="school-field">
              {t.schoolAdults}
              <input type="number" required min="1" max="50" value={project.adults} onChange={(e) => change("adults", e.target.valueAsNumber)} />
            </label>
          </div>
          <p className={total > 50 || total < 6 ? "school-total invalid" : "school-total"}>
            {t.schoolTotal(Number.isFinite(total) ? String(total) : "—")} <span>{t.schoolLimit}</span>
          </p>
          <label className="school-field">
            {t.schoolDate}
            <input type="date" required value={project.date} onChange={(e) => change("date", e.target.value)} />
          </label>
          <fieldset className="school-field school-choice">
            <legend>{t.schoolTripType}</legend>
            <div>
              {TRIP_TYPES.map((k) => (
                <label key={k} className={project.tripType === k ? "is-on" : undefined}>
                  <input type="radio" name="school-trip-type" value={k} checked={project.tripType === k} onChange={() => change("tripType", k)} />
                  {t.schoolTripTypes[k]}
                </label>
              ))}
            </div>
          </fieldset>
          <div className={project.tripType === "round" ? "school-row" : undefined}>
            <label className="school-field">
              {t.schoolDeparture}
              <input type="time" required min={OFFER_MIN} max={OFFER_MAX} value={project.departure} onChange={(e) => change("departure", e.target.value)} />
            </label>
            {project.tripType === "round" && (
              <label className="school-field">
                {t.schoolReturn}
                <input type="time" required min={OFFER_MIN} max={OFFER_MAX} value={project.returnBy} onChange={(e) => change("returnBy", e.target.value)} />
              </label>
            )}
          </div>
          {error && <p className="alert">{error}</p>}
          <div className="school-actions">
            <button className="cta" type="submit" disabled={loading || !places.length}>
              {loading ? t.schoolSearching : !places.length ? t.schoolConnecting : t.schoolSearch}
            </button>
          </div>
        </form>

        {results && (
          <p className="school-summary" aria-live="polite">
            <strong>{t.schoolResults(results.length)}</strong> {results.length ? t.schoolBelow : t.schoolEmpty}
          </p>
        )}
      </div>
    </>
  );
}
