"""Vote en classe : l'enseignant fait voter ses élèves entre les destinations proposées.

Les votes sont anonymes : les votants sont des mineurs, on ne stocke donc aucune donnée
personnelle. Le navigateur de l'élève tire un identifiant aléatoire (votant_id) ; on n'en garde
qu'une empreinte SHA-256 salée par le code du vote, qui sert seulement à remplacer son vote
s'il change d'avis (un élève = un vote).
"""
from __future__ import annotations

import hashlib
import re
import secrets
import socket
import sqlite3

from fastapi import HTTPException

from .. import db, schemas

# 6 caractères lisibles au tableau et sur un téléphone : ni 0/O, ni 1/I.
ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGUEUR_CODE = 6
MIN_OPTIONS = 2
MAX_OPTIONS = 4
_VOTANT = re.compile(r"[A-Za-z0-9_-]{8,64}")

_TABLES = ("sondage", "sondage_option", "sondage_vote", "sondage_manuel", "sondage_effectif")
_bases_pretes: set[str] = set()


def _assurer_schema(conn: sqlite3.Connection) -> None:
    """Crée les tables du vote sur une base construite avant leur ajout (une fois par fichier)."""
    fichier = conn.execute("PRAGMA database_list").fetchone()["file"] or ":memory:"
    if fichier in _bases_pretes:
        return
    presentes = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?, ?, ?)", _TABLES)}
    if len(presentes) < len(_TABLES):
        for instruction in db.SCHEMA_SONDAGES.split(";"):
            if instruction.strip():
                conn.execute(instruction)
    _bases_pretes.add(fichier)


def _nouveau_code(conn: sqlite3.Connection) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET_CODE) for _ in range(LONGUEUR_CODE))
        if conn.execute("SELECT 1 FROM sondage WHERE code = ?", (code,)).fetchone() is None:
            return code


def _normaliser_code(code: str) -> str:
    return (code or "").strip().upper()


_THEMES = {
    "Moyen Âge": "le Moyen Âge",
    "Antiquité": "l'Antiquité",
    "Préhistoire": "la Préhistoire",
    "Espace et astronomie": "l'espace et l'astronomie",
    "Sciences et nature": "les sciences et la nature",
    "Arts": "les arts",
    "Temps modernes": "les Temps modernes",
    "Première Guerre mondiale": "la Première Guerre mondiale",
}


def titre(demande: schemas.Demande) -> str:
    """« Où part la 5e pour le Moyen Âge ? », avec des replis si le niveau ou le thème manquent."""
    niveau = (demande.niveau or "").strip()
    if not niveau:
        classe = "la classe"
    elif niveau.upper() in ("CP", "CE1", "CE2", "CM1", "CM2"):
        classe = f"le {niveau.upper()}"
    else:
        classe = f"la {niveau}"
    theme = (demande.theme or "").strip()
    if not theme:
        return f"Où part {classe} en sortie ?"
    return f"Où part {classe} pour {_THEMES.get(theme, f'le thème « {theme} »')} ?"


def _lire(conn: sqlite3.Connection, code: str) -> schemas.Sondage:
    s = conn.execute("SELECT * FROM sondage WHERE code = ?", (code,)).fetchone()
    if s is None:
        raise HTTPException(404, f"Aucun vote ne correspond au code {code or '(vide)'}. "
                                 "Vérifiez les 6 caractères affichés au tableau.")
    rows = conn.execute(
        """SELECT o.*, COUNT(v.site_id) AS votes_qr,
                  COALESCE((SELECT m.nb FROM sondage_manuel m
                            WHERE m.sondage_code = o.sondage_code AND m.site_id = o.site_id), 0) AS votes_manuels
           FROM sondage_option o
           LEFT JOIN sondage_vote v ON v.sondage_code = o.sondage_code AND v.site_id = o.site_id
           WHERE o.sondage_code = ?
           GROUP BY o.site_id
           ORDER BY o.ordre""",
        (code,),
    ).fetchall()
    options = [schemas.OptionSondage(
        site_id=r["site_id"], nom=r["nom"], commune=r["commune"],
        interet_pedagogique=r["interet_pedagogique"], indice_confiance=r["indice_confiance"],
        niveau=r["niveau"], votes=r["votes_qr"] + r["votes_manuels"], votes_qr=r["votes_qr"],
        votes_manuels=r["votes_manuels"]) for r in rows]
    eff = conn.execute("SELECT effectif FROM sondage_effectif WHERE sondage_code = ?", (code,)).fetchone()
    return schemas.Sondage(code=s["code"], titre=s["titre"], statut=s["statut"], options=options,
                           total_votes=sum(o.votes for o in options), gagnant=s["gagnant"],
                           cree_le=s["cree_le"], effectif=eff["effectif"] if eff else None,
                           votes_qr=sum(o.votes_qr for o in options),
                           votes_manuels=sum(o.votes_manuels for o in options))


def creer(conn: sqlite3.Connection, req: schemas.RequeteSondage) -> schemas.Sondage:
    _assurer_schema(conn)
    uniques: list[schemas.Destination] = []
    for d in req.destinations:
        if d.site_id not in {u.site_id for u in uniques}:
            uniques.append(d)
    if len(uniques) < MIN_OPTIONS:
        raise HTTPException(422, "Il faut au moins 2 destinations différentes pour faire voter la classe.")
    # Les destinations arrivent triées par pertinence : on garde les 4 premières.
    retenues = uniques[:MAX_OPTIONS]
    code = _nouveau_code(conn)
    conn.execute("INSERT INTO sondage (code, titre, statut, cree_le) VALUES (?, ?, 'ouvert', ?)",
                 (code, titre(req.demande), db.maintenant_iso()))
    conn.executemany(
        """INSERT INTO sondage_option (sondage_code, ordre, site_id, nom, commune, interet_pedagogique,
             indice_confiance, niveau) VALUES (?,?,?,?,?,?,?,?)""",
        [(code, i, d.site_id, d.nom, d.commune or "", d.interet_pedagogique or "", d.indice_confiance,
          d.niveau) for i, d in enumerate(retenues)],
    )
    if req.demande.nb_eleves:
        conn.execute("INSERT INTO sondage_effectif (sondage_code, effectif) VALUES (?, ?)",
                     (code, req.demande.nb_eleves))
    return _lire(conn, code)


def lire(conn: sqlite3.Connection, code: str) -> schemas.Sondage:
    _assurer_schema(conn)
    return _lire(conn, _normaliser_code(code))


def _empreinte(code: str, votant_id: str) -> str:
    return hashlib.sha256(f"{code}:{votant_id}".encode()).hexdigest()


def voter(conn: sqlite3.Connection, code: str, req: schemas.RequeteVote) -> schemas.Sondage:
    _assurer_schema(conn)
    code = _normaliser_code(code)
    sondage = _lire(conn, code)
    if sondage.statut == "ferme":
        raise HTTPException(409, "Le vote est terminé : il n'est plus possible de voter ni de changer d'avis.")
    votant = (req.votant_id or "").strip()
    if not _VOTANT.fullmatch(votant):
        raise HTTPException(422, "Identifiant de votant invalide : rechargez la page pour en obtenir un nouveau.")
    if req.site_id not in {o.site_id for o in sondage.options}:
        raise HTTPException(422, "Cette destination ne fait pas partie du vote.")
    conn.execute(
        """INSERT INTO sondage_vote (sondage_code, votant_empreinte, site_id, vote_le) VALUES (?,?,?,?)
           ON CONFLICT(sondage_code, votant_empreinte) DO UPDATE SET site_id = excluded.site_id,
             vote_le = excluded.vote_le""",
        (code, _empreinte(code, votant), req.site_id, db.maintenant_iso()),
    )
    return _lire(conn, code)


def votes_manuels(conn: sqlite3.Connection, code: str, req: schemas.RequeteVotesManuels) -> schemas.Sondage:
    """Saisie à la main des votes (classes trop jeunes pour un téléphone) ; s'ajoute aux votes par QR.

    La saisie REMPLACE la précédente. Le total (saisie + QR) ne peut pas dépasser l'effectif de la classe.
    """
    _assurer_schema(conn)
    code = _normaliser_code(code)
    sondage = _lire(conn, code)
    if sondage.statut == "ferme":
        raise HTTPException(409, "Le vote est terminé : la saisie des votes n'est plus possible.")
    ids = {o.site_id for o in sondage.options}
    inconnus = [k for k in req.votes if k not in ids]
    if inconnus:
        raise HTTPException(422, "Cette destination ne fait pas partie du vote.")
    if any(n < 0 for n in req.votes.values()):
        raise HTTPException(422, "Un nombre de votes ne peut pas être négatif.")
    if sondage.effectif is not None and sum(req.votes.values()) + sondage.votes_qr > sondage.effectif:
        raise HTTPException(
            422, f"Trop de votes : la classe compte {sondage.effectif} élèves "
                 f"({sondage.votes_qr} ont déjà voté par QR code).")
    for sid in ids:
        conn.execute(
            """INSERT INTO sondage_manuel (sondage_code, site_id, nb) VALUES (?,?,?)
               ON CONFLICT(sondage_code, site_id) DO UPDATE SET nb = excluded.nb""",
            (code, sid, int(req.votes.get(sid, 0))))
    return _lire(conn, code)


def gagnant(options: list[schemas.OptionSondage]) -> str | None:
    """Le plus de votes ; en cas d'égalité, le meilleur indice de confiance, puis l'ordre proposé."""
    if not options:
        return None
    return max(enumerate(options), key=lambda io: (io[1].votes, io[1].indice_confiance, -io[0]))[1].site_id


def fermer(conn: sqlite3.Connection, code: str) -> schemas.Sondage:
    _assurer_schema(conn)
    code = _normaliser_code(code)
    sondage = _lire(conn, code)
    if sondage.statut == "ferme":
        return sondage  # déjà fermé : on ne redésigne pas le gagnant
    conn.execute("UPDATE sondage SET statut = 'ferme', gagnant = ?, ferme_le = ? WHERE code = ?",
                 (gagnant(sondage.options), db.maintenant_iso(), code))
    return _lire(conn, code)


def ip_locale() -> str | None:
    """Adresse IP de la machine sur le réseau local, pour l'URL du QR code.

    Une socket UDP « connectée » choisit l'interface de sortie sans envoyer le moindre paquet.
    """
    for cible in (("8.8.8.8", 80), ("10.255.255.255", 1)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(cible)
                ip = s.getsockname()[0]
        except OSError:
            continue
        if ip and not ip.startswith("127.") and ip != "0.0.0.0":
            return ip
    return None
