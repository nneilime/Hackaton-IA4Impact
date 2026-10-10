"""Recherche des trains liO autorisés aux groupes (SQL + code, sans LLM).

- Jour type : une date hors de la grille horaire est ramenée au même jour de la semaine dans la
  période de référence (le jour de ce type qui compte le plus de circulations).
- Seuls les trains autorisés aux groupes sont chargés (règle R1).
- Itinéraires directs ou avec une correspondance d'au moins 10 min (EF15).
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import date

from .. import config, db, schemas
from .texte import date_fr, fmt_hm, hm


@dataclass(frozen=True)
class Arret:
    gare: str
    arr: int
    dep: int


@dataclass
class Grille:
    ref_date: str
    trains: dict[str, list[Arret]]
    par_gare: dict[str, list[tuple[str, int]]]
    noms: dict[str, str]


@dataclass(frozen=True)
class SegmentI:
    train: str
    gare_dep: str
    gare_arr: str
    dep: int
    arr: int


@dataclass
class Itineraire:
    segments: list[SegmentI] = field(default_factory=list)

    @property
    def dep(self) -> int:
        return self.segments[0].dep

    @property
    def arr(self) -> int:
        return self.segments[-1].arr

    @property
    def duree(self) -> int:
        return self.arr - self.dep

    @property
    def correspondances(self) -> int:
        return len(self.segments) - 1

    @property
    def trains(self) -> tuple[str, ...]:
        return tuple(s.train for s in self.segments)


@dataclass
class DateResolue:
    date_demandee: str
    ref_date: str
    jour_type: bool
    message: str | None


_verrou = threading.Lock()
_cache_grilles: dict[tuple, Grille] = {}
_cache_bornes: dict[tuple, tuple[str, str]] = {}
_cache_ref: dict[tuple, str | None] = {}


def _cle(conn: sqlite3.Connection) -> tuple:
    return (str(config.db_path()), db.version_base(conn))


def vider_caches() -> None:
    with _verrou:
        _cache_grilles.clear()
        _cache_bornes.clear()
        _cache_ref.clear()


def bornes_grille(conn: sqlite3.Connection) -> tuple[str, str]:
    k = _cle(conn)
    if k not in _cache_bornes:
        r = conn.execute("SELECT MIN(date_circulation), MAX(date_circulation) FROM desserte").fetchone()
        _cache_bornes[k] = (r[0], r[1])
    return _cache_bornes[k]


def resoudre_date(conn: sqlite3.Connection, jour: str) -> DateResolue:
    """Date demandée -> date de la grille à utiliser (elle-même ou un jour type)."""
    d = date.fromisoformat(jour)
    debut, fin = bornes_grille(conn)
    if debut and debut <= jour <= fin:
        n = conn.execute("SELECT 1 FROM desserte WHERE date_circulation = ? LIMIT 1", (jour,)).fetchone()
        if n:
            return DateResolue(jour, jour, False, None)
    k = _cle(conn) + (d.isoweekday(),)
    if k not in _cache_ref:
        r = conn.execute(
            """SELECT date_circulation, COUNT(DISTINCT train_numero) AS n FROM desserte
               WHERE jour_semaine = ? GROUP BY date_circulation
               ORDER BY n DESC, date_circulation DESC LIMIT 1""",
            (d.isoweekday(),),
        ).fetchone()
        _cache_ref[k] = r[0] if r else None
    ref = _cache_ref[k] or jour
    msg = (f"Le {date_fr(d)} est en dehors de la grille horaire disponible "
           f"(du {date_fr(debut, False)} au {date_fr(fin, False)}) : horaires indicatifs basés sur "
           f"un {date_fr(ref).split()[0]} type de la grille 2026 ({date_fr(ref)}).")
    return DateResolue(jour, ref, True, msg)


def charger_grille(conn: sqlite3.Connection, ref_date: str) -> Grille:
    k = _cle(conn) + (ref_date,)
    with _verrou:
        if k in _cache_grilles:
            return _cache_grilles[k]
    rows = conn.execute(
        """SELECT d.train_numero, d.ordre, d.gare_uic, d.heure_arrivee, d.heure_depart
           FROM desserte d JOIN train t ON t.numero = d.train_numero
           WHERE d.date_circulation = ? AND t.autorise_groupe = 1
           ORDER BY d.train_numero, d.ordre""",
        (ref_date,),
    ).fetchall()
    trains: dict[str, list[Arret]] = {}
    precedent: dict[str, int] = {}
    for r in rows:
        a, d = hm(r["heure_arrivee"]), hm(r["heure_depart"])
        a = a if a is not None else d
        d = d if d is not None else a
        if a is None:
            continue
        p = precedent.get(r["train_numero"], -1)
        while a < p:
            a += 1440
        while d < a:
            d += 1440
        precedent[r["train_numero"]] = d
        trains.setdefault(r["train_numero"], []).append(Arret(r["gare_uic"], a, d))
    par_gare: dict[str, list[tuple[str, int]]] = {}
    for t, arrets in trains.items():
        for i, a in enumerate(arrets):
            par_gare.setdefault(a.gare, []).append((t, i))
    noms = {r["code_uic"]: r["nom"] for r in conn.execute("SELECT code_uic, nom FROM gare")}
    g = Grille(ref_date, trains, par_gare, noms)
    with _verrou:
        _cache_grilles[k] = g
    return g


def itineraires(grille: Grille, depart: str, arrivee: str, apres: int,
                max_correspondances: int = 1) -> list[Itineraire]:
    """Itinéraires de `depart` à `arrivee` partant à `apres` (minutes) ou plus tard.

    Pour un même premier train, on garde l'itinéraire qui arrive le plus tôt (puis le plus simple).
    Résultat trié par heure de départ.
    """
    if depart == arrivee:
        return []
    trouves: list[Itineraire] = []
    T = grille.trains
    for t1, i in grille.par_gare.get(depart, []):
        arrets1 = T[t1]
        dep = arrets1[i].dep
        if dep < apres or i == len(arrets1) - 1:
            continue
        for k in range(i + 1, len(arrets1)):
            x = arrets1[k]
            if x.gare == depart:
                break
            if x.gare == arrivee:
                trouves.append(Itineraire([SegmentI(t1, depart, arrivee, dep, x.arr)]))
                break
            if max_correspondances < 1:
                continue
            for t2, m in grille.par_gare.get(x.gare, []):
                if t2 == t1:
                    continue
                arrets2 = T[t2]
                dep2 = arrets2[m].dep
                if not (x.arr + config.CORRESP_MIN <= dep2 <= x.arr + config.CORRESP_MAX):
                    continue
                for n in range(m + 1, len(arrets2)):
                    if arrets2[n].gare == depart:
                        break
                    if arrets2[n].gare == arrivee:
                        trouves.append(Itineraire([
                            SegmentI(t1, depart, x.gare, dep, x.arr),
                            SegmentI(t2, x.gare, arrivee, dep2, arrets2[n].arr),
                        ]))
                        break
    meilleurs: dict[str, Itineraire] = {}
    for it in trouves:
        k = it.segments[0].train
        b = meilleurs.get(k)
        if b is None or (it.arr, it.correspondances) < (b.arr, b.correspondances):
            meilleurs[k] = it
    return sorted(meilleurs.values(), key=lambda it: (it.dep, it.arr))


def vers_trajet(it: Itineraire, grille: Grille) -> schemas.Trajet:
    return schemas.Trajet(
        segments=[
            schemas.Segment(train=s.train, gare_depart=grille.noms.get(s.gare_dep, s.gare_dep),
                            gare_arrivee=grille.noms.get(s.gare_arr, s.gare_arr),
                            depart=fmt_hm(s.dep), arrivee=fmt_hm(s.arr))
            for s in it.segments
        ],
        depart=fmt_hm(it.dep),
        arrivee=fmt_hm(it.arr),
        duree_min=it.duree,
        correspondances=it.correspondances,
    )
