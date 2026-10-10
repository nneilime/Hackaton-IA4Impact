"""Catalogue des sites : lecture, accès gare -> site (R3), adéquation pédagogique, satisfaction."""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass

from .. import config, schemas
from . import themes
from .texte import capitaliser, normaliser


@dataclass
class Acces:
    mode: str           # "pied" ou "urbain"
    minutes: int        # temps pour le groupe
    niveau: str         # vert / orange / rouge
    message: str
    points: int         # critère « Accès gare → site » (sur 15)
    a_pied_ok: bool     # R3 respectée à pied

    def schema(self) -> schemas.AccesGareSite:
        return schemas.AccesGareSite(mode=self.mode, minutes_groupe=self.minutes,
                                     niveau=self.niveau, message=self.message)


def liste(champ: str | None) -> list[str]:
    if not champ:
        return []
    if champ.strip().startswith("["):
        return list(json.loads(champ))
    return [x.strip() for x in champ.split(";") if x.strip()]


def charger_site(conn: sqlite3.Connection, site_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM site_culturel WHERE id = ?", (site_id,)).fetchone()


def tous_les_sites(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM site_culturel ORDER BY id").fetchall()


def acces(site: sqlite3.Row) -> Acces:
    """R3 : 20 min à pied au plus (temps de groupe), sinon réseau urbain (< 2 corresp., 1 h max)."""
    mpg = site["minutes_pied_groupe"]
    seul = site["minutes_pied"]
    if mpg is not None and mpg <= config.MARCHE_MAX_GROUPE:
        return Acces("pied", mpg, "vert",
                     f"{mpg} min à pied pour le groupe (environ {seul} min seul, temps approximatif).",
                     15, True)
    urb, mu, cu = site["acces_urbain"], site["minutes_urbain"], site["correspondances_urbain"] or 0
    if urb and mu is not None and mu <= config.URBAIN_MAX_MIN and cu <= config.URBAIN_MAX_CORRESP:
        return Acces("urbain", mu, "orange",
                     f"Site à {mpg} min à pied pour le groupe : prévoir le réseau urbain. {urb}, "
                     f"environ {mu} min (titres de transport à prévoir).", 10, False)
    return Acces("pied", mpg or 0, "rouge",
                 f"{mpg} min à pied pour le groupe, sans réseau urbain adapté connu : accès "
                 f"difficile sans car.", 0, False)


_verrou = threading.Lock()
_notes_llm: dict[tuple[str, str, str], tuple[int, str]] = {}


def memoriser_note_llm(site_id: str, theme: str | None, niveau: str | None, note: int, texte: str) -> None:
    with _verrou:
        _notes_llm[(site_id, normaliser(theme or ""), niveau or "")] = (max(0, min(3, note)), texte)


def note_llm(site_id: str, theme: str | None, niveau: str | None) -> tuple[int, str] | None:
    return _notes_llm.get((site_id, normaliser(theme or ""), niveau or ""))


def adequation(site: sqlite3.Row, demande: schemas.Demande) -> tuple[int, str]:
    """Note de 0 à 3. Donnée par le LLM à l'étape « recommander » si disponible, sinon par règles :
    2 points si le thème est un thème principal du site (1 s'il est secondaire), 1 point si le
    niveau de la classe figure dans les niveaux du site."""
    llm = note_llm(site["id"], demande.theme, demande.niveau)
    if llm is not None:
        return llm[0], llm[1] or f"Note d'adéquation proposée par l'IA à partir du catalogue : {llm[0]}/3."
    themes_site = liste(site["themes"])
    norm_site = [normaliser(t) for t in themes_site]
    note, raisons = 0, []
    canon = themes.canonique(demande.theme)
    if demande.theme:
        cible = normaliser(canon or demande.theme)
        if cible in norm_site[:2]:
            note += 2
            raisons.append(f"thème « {canon or demande.theme} » au cœur du site")
        elif cible in norm_site or any(cible in t or t in cible for t in norm_site if len(t) > 3) \
                or cible in normaliser(site["interet_pedagogique"] or ""):
            note += 1
            raisons.append(f"thème « {canon or demande.theme} » abordé")
        else:
            raisons.append(f"thème « {demande.theme} » peu présent")
    elif demande.destination_souhaitee:
        note += 1
        raisons.append("destination choisie par l'enseignant")
    if demande.niveau:
        if demande.niveau in liste(site["niveaux"]):
            note += 1
            raisons.append(f"adapté au niveau {demande.niveau}")
        else:
            raisons.append(f"niveau {demande.niveau} hors des niveaux conseillés")
    note = min(3, note)
    if not raisons:
        return note, "Pas de thème ni de niveau précisé."
    return note, capitaliser(", ".join(raisons)) + "."


def satisfaction(conn: sqlite3.Connection, site_id: str) -> tuple[float | None, int, int, int]:
    """(moyenne de satisfaction sur 5, nb de retours, nb de coups de cœur, nb de retours simulés)."""
    r = conn.execute(
        """SELECT AVG(satisfaction), COUNT(*), COALESCE(SUM(recommande), 0),
                  COALESCE(SUM(est_simule), 0)
           FROM retour_experience WHERE site_id = ?""",
        (site_id,),
    ).fetchone()
    return (r[0], r[1], r[2], r[3]) if r[1] else (None, 0, 0, 0)


def gare_du_site(conn: sqlite3.Connection, site: sqlite3.Row) -> schemas.Gare:
    g = conn.execute("SELECT * FROM gare WHERE code_uic = ?", (site["gare_uic"],)).fetchone()
    return schemas.Gare(code_uic=g["code_uic"], nom=g["nom"], lat=g["lat"] or 0.0, lon=g["lon"] or 0.0,
                        distance_m=None)
