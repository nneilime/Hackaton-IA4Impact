import { useId, useMemo, useState, type InputHTMLAttributes } from "react";
import type { Place } from "../api";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  places: Place[];
  value: string;
  onChange: (v: string) => void;
};

const MAX = 8;
// Sans accents ni casse, tirets et apostrophes comme des espaces : « saint etienne » trouve « Saint-Étienne »
const norm = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-'’]/g, " ").replace(/\s+/g, " ").trim();

// Champ ville / gare avec sa propre liste de suggestions : le <datalist> natif ne s'affiche pas sur iPhone
export default function PlaceInput({ places, value, onChange, className, ...rest }: Props) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  // Un nom par entrée (plusieurs arrêts peuvent partager le même), le plus desservi d'abord
  const index = useMemo(() => {
    const byName = new Map<string, Place>();
    for (const p of places) {
      const seen = byName.get(p.name);
      if (!seen || p.trips_per_day > seen.trips_per_day) byName.set(p.name, p);
    }
    return [...byName.values()].map((p) => ({ p, n: norm(p.name), c: norm(p.commune) }));
  }, [places]);

  const matches = useMemo(() => {
    const q = norm(value);
    if (!q) return [];
    const scored: { p: Place; s: number }[] = [];
    for (const { p, n, c } of index) {
      // Début du nom > début d'un mot du nom > commune > n'importe où dans le nom
      const s = n.startsWith(q) ? 0 : n.includes(" " + q) ? 1 : c.startsWith(q) ? 2 : n.includes(q) ? 3 : -1;
      if (s >= 0) scored.push({ p, s });
    }
    scored.sort((a, b) => a.s - b.s || b.p.trips_per_day - a.p.trips_per_day);
    return scored.slice(0, MAX).map((x) => x.p);
  }, [index, value]);

  // Rien à proposer si le champ contient déjà exactement le seul choix possible
  const show = open && matches.length > 0 && !(matches.length === 1 && matches[0].name === value);

  const pick = (p: Place) => {
    onChange(p.name);
    setOpen(false);
    setActive(-1);
  };

  return (
    <>
      <input
        {...rest}
        className={className}
        value={value}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={show}
        aria-controls={listId}
        aria-activedescendant={show && active >= 0 ? `${listId}-${active}` : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (!show) return;
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            const d = e.key === "ArrowDown" ? 1 : -1;
            setActive((a) => (a + d + matches.length) % matches.length);
          } else if (e.key === "Enter" && active >= 0) {
            e.preventDefault();
            pick(matches[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {show && (
        <ul className="place-suggest" id={listId} role="listbox">
          {matches.map((p, i) => (
            <li
              key={p.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // mousedown plutôt que click : le champ perdrait le focus (et fermerait la liste) avant le click
              onMouseDown={(e) => {
                e.preventDefault();
                pick(p);
              }}
            >
              <span className="place-suggest-name">{p.name}</span>
              {p.commune && norm(p.commune) !== norm(p.name) && <span className="place-suggest-sub">{p.commune}</span>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
