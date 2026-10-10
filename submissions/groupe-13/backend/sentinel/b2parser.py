"""Parseur déterministe des fichiers de facturation B2 à positions fixes.

Toutes les positions sont celles du cahier des charges « Les contrôles à implémenter » :
numérotées à partir de 1 et INCLUSIVES. Conversion Python : line[start-1:end].

Principes :
- aucune suppression globale d'espaces (strip) : les espaces de positionnement sont conservés ;
- les identifiants restent des chaînes (zéros initiaux préservés) ;
- les montants (deux décimales implicites) sont manipulés en centimes entiers ;
- aucune ligne n'est perdue : les enregistrements inconnus ou ambigus sont conservés et signalés ;
- chaque valeur garde sa provenance (numéro de ligne, positions).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------------------
# Table des champs (cahier des charges, section « Détail du fichier »)
# --------------------------------------------------------------------------------------
# (nom, type d'enregistrement, sous-type, début, fin, nature)  nature: id | code | amount
FIELD_SPECS = [
    ("NumeroTiers", "1", "", 2, 10, "id"),
    ("NumeroLot", "1", "", 20, 22, "id"),
    ("NumeroAssure", "2", "", 12, 24, "id"),
    ("NumeroFacture", "2", "", 30, 38, "id"),
    ("Acte", "3", "", 56, 60, "code"),
    ("NumeroGH", "3", "", 110, 113, "id"),
    ("Acte", "4", "", 76, 80, "code"),
    ("NumeroGH", "4", "S", 120, 123, "id"),
    ("CodeCCAM", "4", "M", 43, 55, "code"),
    ("TotalPrestations", "5", "", 42, 49, "amount"),
    ("TotalHonoraires", "5", "", 58, 65, "amount"),
    # Positions citées dans la colonne « Commentaire » du cahier des charges ; utilisées
    # uniquement pour des OBSERVATIONS complémentaires (somme des bases de remboursement).
    ("BaseRemboursement", "3", "", 83, 90, "amount"),
    ("HonorairesLigne", "4", "", 115, 121, "amount"),
]

RECORD_LABELS = {
    "0": "En-tête de fichier",
    "1": "Début de lot",
    "2": "Début de facture",
    "2S": "Début de facture — complément (2-S)",
    "3": "Prestation hospitalière",
    "3S": "Prestation hospitalière — complément (3-S)",
    "3H": "Prestation hospitalière — complément (3-H)",
    "4": "Acte",
    "4S": "Acte — complément (4-S)",
    "4M": "Acte — code CCAM (4-M)",
    "4B": "Acte — biologie (4-B)",
    "5": "Fin de facture",
    "6": "Fin de lot",
}


@dataclass
class FieldValue:
    name: str
    raw: Optional[str]          # chaîne exacte aux positions (None si ligne trop courte)
    value: Optional[str]        # valeur normalisée (code sans blancs de complément, etc.)
    cents: Optional[int]        # montant en centimes si nature == amount
    line_no: int
    start: int                  # 1-based inclusive
    end: int
    status: str                 # ok | line_too_short | blank | not_numeric

    def to_dict(self):
        return asdict(self)


@dataclass
class Record:
    line_no: int
    raw: str
    rtype: str
    subtype: str
    length: int
    fields: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    raw_original: Optional[str] = None   # ligne telle qu'elle figure dans le fichier, si elle a été réalignée

    @property
    def kind(self) -> str:
        return self.rtype + self.subtype

    def to_dict(self):
        return {
            "line_no": self.line_no,
            "raw": self.raw,
            "raw_original": self.raw_original,
            "rtype": self.rtype,
            "subtype": self.subtype,
            "kind": self.kind,
            "label": RECORD_LABELS.get(self.kind, "Type inconnu"),
            "length": self.length,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "issues": self.issues,
        }


@dataclass
class Observation:
    code: str
    severity: str          # info | warning
    message: str
    line_nos: list = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class ParsedB2:
    path: str
    sha256: str
    size: int
    line_ending: str
    records: list
    observations: list
    # Vue facture (une facture attendue par fichier dans ce corpus)
    numero_tiers: Optional[FieldValue] = None
    numero_lot: Optional[FieldValue] = None
    numero_assure: Optional[FieldValue] = None
    numero_facture: Optional[FieldValue] = None
    invoice_headers: list = field(default_factory=list)   # tous les enregistrements 2 (hors 2-S)
    acts3: list = field(default_factory=list)              # [{acte, gh, base, line_no}]
    acts4: list = field(default_factory=list)              # [{acte, line_no, honoraires}]
    ccam4m: list = field(default_factory=list)             # [{code, line_no}]
    gh4s: list = field(default_factory=list)               # [{gh, line_no}]
    total_prestations: Optional[FieldValue] = None
    total_honoraires: Optional[FieldValue] = None
    alignment_shift: int = 0                               # décalage détecté NON résolu (observation)
    realignment: Optional[dict] = None                     # décalage résolu et démontré (lecture réalignée)

    def to_dict(self):
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "line_ending": self.line_ending,
            "records": [r.to_dict() for r in self.records],
            "observations": [o.to_dict() for o in self.observations],
            "numero_tiers": _fv(self.numero_tiers),
            "numero_lot": _fv(self.numero_lot),
            "numero_assure": _fv(self.numero_assure),
            "numero_facture": _fv(self.numero_facture),
            "invoice_headers": [
                {"line_no": h.line_no, "NumeroFacture": _fv(h.fields.get("NumeroFacture")),
                 "NumeroAssure": _fv(h.fields.get("NumeroAssure"))}
                for h in self.invoice_headers
            ],
            "acts3": self.acts3,
            "acts4": self.acts4,
            "ccam4m": self.ccam4m,
            "gh4s": self.gh4s,
            "total_prestations": _fv(self.total_prestations),
            "total_honoraires": _fv(self.total_honoraires),
            "alignment_shift": self.alignment_shift,
            "realignment": self.realignment,
        }


def _fv(f: Optional[FieldValue]):
    return f.to_dict() if f else None


# --------------------------------------------------------------------------------------
def classify(line: str) -> tuple[str, str]:
    """Type et sous-type selon les priorités du cahier des charges."""
    if not line:
        return "", ""
    t = line[0]

    def at(pos: int) -> str:
        return line[pos - 1] if len(line) >= pos else ""

    if t == "2":
        return ("2", "S") if at(39) == "S" else ("2", "")
    if t == "3":
        if at(39) == "S":
            return "3", "S"
        if at(36) == "H":
            return "3", "H"
        return "3", ""
    if t == "4":
        c = at(36)
        if c in ("S", "M", "B"):
            return "4", c
        return "4", ""
    return t, ""


def extract_field(line: str, line_no: int, name: str, start: int, end: int, nature: str) -> FieldValue:
    if len(line) < end:
        raw = line[start - 1:end] if len(line) >= start else None
        return FieldValue(name, raw, None, None, line_no, start, end, "line_too_short")
    raw = line[start - 1:end]
    cents = None
    status = "ok"
    if nature == "code":
        value = raw.strip()  # code cadré à gauche complété par des blancs (strip LOCAL au champ)
    else:
        value = raw
    if not raw.strip():
        status = "blank"
        value = ""
    if nature == "amount" and status == "ok":
        if raw.isdigit():
            cents = int(raw)
        else:
            status = "not_numeric"
    return FieldValue(name, raw, value, cents, line_no, start, end, status)


def parse_b2(path: Path | str, display_path: Optional[str] = None) -> ParsedB2:
    path = Path(path)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    text = data.decode("latin-1")  # décodage sans perte octet → caractère
    if "\r\n" in text:
        line_ending = "CRLF"
        lines = text.split("\r\n")
    else:
        line_ending = "LF"
        lines = text.split("\n")
    # dernière ligne vide due au séparateur final : ignorée mais rien d'autre n'est retiré
    if lines and lines[-1] == "":
        lines = lines[:-1]

    records: list[Record] = []
    observations: list[Observation] = []
    realign = detect_insertion(lines)
    originals = list(lines)
    if realign:
        lines = [realign_line(l, realign["index"]) for l in lines]
    for i, line in enumerate(lines, start=1):
        if line == "":
            observations.append(Observation("LIGNE_VIDE", "info", f"Ligne {i} vide.", [i]))
            continue
        rtype, sub = classify(line)
        rec = Record(i, line, rtype, sub, len(line))
        if realign and originals[i - 1] != line:
            rec.raw_original = originals[i - 1]
        if rtype not in "0123456" or len(rtype) != 1:
            rec.issues.append("Type d'enregistrement inconnu")
        for (name, ftype, fsub, s, e, nature) in FIELD_SPECS:
            if ftype == rtype and fsub == sub:
                fv = extract_field(line, i, name, s, e, nature)
                rec.fields[name] = fv
                if fv.status == "line_too_short":
                    rec.issues.append(f"Ligne trop courte pour {name} (positions {s}-{e}, longueur {len(line)})")
        records.append(rec)

    p = ParsedB2(str(display_path or path.name), sha, len(data), line_ending, records, observations)
    p.realignment = realign
    _build_invoice_view(p)
    _structural_checks(p)
    return p


def _build_invoice_view(p: ParsedB2):
    current_gh_for_acts = None
    for r in p.records:
        k = r.kind
        if k == "1" and p.numero_tiers is None:
            p.numero_tiers = r.fields.get("NumeroTiers")
            p.numero_lot = r.fields.get("NumeroLot")
        elif k == "2":
            p.invoice_headers.append(r)
            if p.numero_facture is None:
                p.numero_facture = r.fields.get("NumeroFacture")
                p.numero_assure = r.fields.get("NumeroAssure")
        elif k == "3":
            a = r.fields.get("Acte")
            gh = r.fields.get("NumeroGH")
            base = r.fields.get("BaseRemboursement")
            p.acts3.append({
                "line_no": r.line_no,
                "acte": a.value if a else None,
                "acte_raw": a.raw if a else None,
                "gh": gh.value if gh else None,
                "gh_status": gh.status if gh else "absent",
                "base_cents": base.cents if base else None,
            })
        elif k == "4":
            a = r.fields.get("Acte")
            h = r.fields.get("HonorairesLigne")
            p.acts4.append({
                "line_no": r.line_no,
                "acte": a.value if a else None,
                "acte_raw": a.raw if a else None,
                "honoraires_cents": h.cents if h else None,
            })
            current_gh_for_acts = None
        elif k == "4M":
            c = r.fields.get("CodeCCAM")
            code = c.value if c else None
            p.ccam4m.append({
                "line_no": r.line_no,
                "code": code,
                "code_raw": c.raw if c else None,
                "code7": (c.raw[:7].strip() if c and c.raw else None),
                "parent_line": p.acts4[-1]["line_no"] if p.acts4 else None,
            })
        elif k == "4S":
            gh = r.fields.get("NumeroGH")
            p.gh4s.append({"line_no": r.line_no, "gh": gh.value if gh else None,
                           "gh_status": gh.status if gh else "absent",
                           "parent_line": p.acts4[-1]["line_no"] if p.acts4 else None})
        elif k == "5" and p.total_prestations is None:
            p.total_prestations = r.fields.get("TotalPrestations")
            p.total_honoraires = r.fields.get("TotalHonoraires")


def _structural_checks(p: ParsedB2):
    obs = p.observations
    kinds = [r.kind for r in p.records]
    if "0" not in kinds:
        obs.append(Observation(
            "SANS_ENTETE_0", "info",
            "Aucun enregistrement de type 0 (en-tête de fichier). Le cahier des charges ne précise pas "
            "s'il est obligatoire : non considéré comme une erreur.", []))
    for need, label in (("1", "début de lot"), ("2", "début de facture"), ("5", "fin de facture"), ("6", "fin de lot")):
        if need not in kinds:
            obs.append(Observation("ENREG_MANQUANT", "warning", f"Aucun enregistrement {need} ({label}).", []))

    # Ordre : 3/4 doivent suivre un 2 ; 5 doit suivre un 2
    seen2 = False
    for r in p.records:
        if r.rtype == "2":
            seen2 = True
        if r.rtype in ("3", "4", "5") and not seen2:
            obs.append(Observation("NON_RATTACHE", "warning",
                                   f"Ligne {r.line_no} (type {r.kind}) non rattachée à un début de facture.",
                                   [r.line_no]))

    # Débuts de facture multiples
    if len(p.invoice_headers) > 1:
        nums = [h.fields["NumeroFacture"].raw if "NumeroFacture" in h.fields else None for h in p.invoice_headers]
        obs.append(Observation(
            "DEBUT_FACTURE_REPETE", "warning",
            f"{len(p.invoice_headers)} enregistrements de type 2 classés « début de facture » "
            f"(lignes {', '.join(str(h.line_no) for h in p.invoice_headers)}). Valeurs lues en NumeroFacture : "
            f"{nums}. Le fichier n'est pas interprété automatiquement comme deux factures distinctes.",
            [h.line_no for h in p.invoice_headers], {"numeros": nums}))

    # Lignes trop courtes
    for r in p.records:
        for msg in r.issues:
            obs.append(Observation("LIGNE_INCOMPLETE", "warning", f"Ligne {r.line_no} : {msg}.", [r.line_no]))

    # Doublons exacts de lignes « acte » (observation, jamais une fraude)
    seen = {}
    for r in p.records:
        if r.kind in ("3", "4"):
            seen.setdefault(r.raw, []).append(r.line_no)
    for raw, lns in seen.items():
        if len(lns) > 1:
            obs.append(Observation("LIGNES_IDENTIQUES", "info",
                                   f"Lignes {', '.join(map(str, lns))} strictement identiques (actes répétés : "
                                   f"peut correspondre à des actes réellement multiples).", lns))

    if p.realignment:
        ra = p.realignment
        obs.append(Observation(
            "FICHIER_REALIGNE", "alerte",
            f"Fichier B2 mal formé : un caractère blanc supplémentaire figure en position {ra['position']} sur "
            f"{ra['lignes_realignees']} ligne(s) ; tous les champs situés après cette position sont décalés d'un "
            f"caractère. Le décalage est démontré par {len(ra['preuves'])} vérifications indépendantes internes au "
            f"fichier ({'; '.join(x['libelle'] for x in ra['preuves'])}). Les contrôles utilisent la lecture "
            f"réalignée : c'est une interprétation, à confirmer. Le fichier d'origine reste non conforme au format "
            f"et doit être signalé à l'établissement.",
            ra["lignes"][:50], ra))
        return
    # Détection d'un décalage de positionnement : marqueurs de sous-type trouvés à pos+1
    shifted, normal = [], []
    for r in p.records:
        L = r.raw
        if r.rtype in ("2", "3") and len(L) >= 40:
            if L[38] == "S":
                normal.append(r.line_no)
            elif L[39] == "S":
                shifted.append(r.line_no)
        if r.rtype == "4" and len(L) >= 37:
            if L[35] in "SMB":
                normal.append(r.line_no)
            elif L[36] in "SMB":
                shifted.append(r.line_no)
    if shifted and len(shifted) > len(normal):
        p.alignment_shift = 1
        obs.append(Observation(
            "DECALAGE_POSITIONS", "warning",
            f"Les marqueurs de sous-type attendus en position 39 (types 2/3) ou 36 (type 4) apparaissent "
            f"une position plus loin sur {len(shifted)} ligne(s). Le fichier semble décalé d'un caractère, mais "
            f"le point d'insertion n'a pas pu être démontré : les valeurs lues aux positions officielles peuvent être "
            f"fausses. Les contrôles restent appliqués aux positions du cahier des charges ; une vérification "
            f"humaine du fichier est nécessaire.",
            shifted[:50], {"shift": 1, "lignes_decalees": len(shifted), "lignes_normales": len(normal)}))

    # Observation : somme des bases de remboursement type 3 vs TotalPrestations
    if p.total_prestations and p.total_prestations.cents is not None:
        bases = [a["base_cents"] for a in p.acts3 if a["base_cents"] is not None]
        if bases:
            s = sum(bases)
            if s != p.total_prestations.cents:
                obs.append(Observation(
                    "SOMME_BASES_3", "info",
                    f"Somme des positions 83-90 des enregistrements 3 = {s/100:.2f} € ; TotalPrestations = "
                    f"{p.total_prestations.cents/100:.2f} €.", [a["line_no"] for a in p.acts3],
                    {"somme_cents": s, "total_cents": p.total_prestations.cents}))


# --------------------------------------------------------------------------------------
# Réalignement d'un fichier dans lequel un caractère blanc a été inséré
# --------------------------------------------------------------------------------------
def realign_line(line: str, index: int) -> str:
    """Retire le caractère inséré (blanc) à l'indice donné ; ligne inchangée si ce n'est pas un blanc."""
    if len(line) > index and line[index] == " ":
        return line[:index] + line[index + 1:]
    return line


def _evidence(lines: list) -> dict:
    """Vérifications de structure INTERNES au fichier (le bordereau n'intervient jamais) :
    chacune est indépendante des autres et ne dépend d'aucune valeur attendue."""
    recs = [(l, classify(l)) for l in lines if l]
    # 1. Marqueurs de sous-type à leur position officielle (39 pour 2/3, 36 pour 4)
    ok_m = sh_m = 0
    for l, _ in recs:
        if l[0] in "23" and len(l) >= 40:
            ok_m += l[38] == "S"
            sh_m += l[39] == "S"
        if l[0] == "4" and len(l) >= 37:
            ok_m += l[35] in "SMB"
            sh_m += l[36] in "SMB"
    # 2. Un seul NumeroFacture (30-38) pour les enregistrements 2 et 2-S d'une même facture
    nums = {l[29:38] for l, (t, _) in recs if t == "2" and len(l) >= 38}
    # 3. Codes d'actes (3 : 56-60, 4 : 76-80) commençant par une lettre
    codes = [l[55:60] for l, (t, sub) in recs if t == "3" and sub == "" and len(l) >= 60] + \
            [l[75:80] for l, (t, sub) in recs if t == "4" and sub == "" and len(l) >= 80]
    codes_ok = bool(codes) and all(c[:1].isalpha() for c in codes if c.strip())
    # 4. Dates de prestation (AAMMJJ, positions 44-49 et 50-55 des enregistrements 3) valides
    def _date(x):
        return len(x) == 6 and x.isdigit() and 1 <= int(x[2:4]) <= 12 and 1 <= int(x[4:6]) <= 31
    dates = [(l[43:49], l[49:55]) for l, (t, sub) in recs if t == "3" and sub == "" and len(l) >= 55]
    dates_ok = bool(dates) and all(_date(a) and _date(b) for a, b in dates)
    # 5. Somme des bases de remboursement des prestations (83-90) = TotalPrestations (42-49)
    bases = [l[82:90] for l, (t, sub) in recs if t == "3" and sub == "" and len(l) >= 90]
    tots = [l[41:49] for l, (t, _) in recs if t == "5" and len(l) >= 49]
    somme_ok = (bool(bases) and len(tots) == 1 and all(b.isdigit() for b in bases) and tots[0].isdigit()
                and sum(int(b) for b in bases) == int(tots[0]))
    # 6. Identifiants numériques (n° d'assuré 12-24, n° de facture 30-38) sur les enregistrements 2 et 3
    ids = [l for l, (t, sub) in recs if t in "23" and sub == "" and len(l) >= 38]
    ids_ok = bool(ids) and all(l[11:24].isdigit() and l[29:38].isdigit() for l in ids)
    return {"marqueurs": (ok_m, sh_m), "numeros_facture": len(nums), "codes": codes_ok, "dates": dates_ok,
            "somme": somme_ok, "identifiants": ids_ok}


def detect_insertion(lines: list) -> Optional[dict]:
    """Détecte un caractère blanc inséré au même endroit dans les lignes du fichier.

    La réalignement n'est retenu que s'il est DÉMONTRÉ par au moins trois vérifications internes indépendantes
    qui échouent sur le fichier tel quel et réussissent une fois le caractère retiré. Le bordereau n'est jamais
    utilisé pour choisir la lecture (on ne cherche pas la lecture « qui arrange »)."""
    lines = [l for l in lines]
    before = _evidence(lines)
    if not (before["marqueurs"][1] > before["marqueurs"][0]):
        return None                                   # aucun indice de décalage
    nonempty = [l for l in lines if l]
    for idx in range(1, 45):
        blanks = sum(1 for l in nonempty if len(l) > idx and l[idx] == " ")
        if blanks < 0.9 * len(nonempty):
            continue
        cand = [realign_line(l, idx) for l in lines]
        after = _evidence(cand)
        proofs = []
        if after["marqueurs"][1] == 0 and after["marqueurs"][0] > 0:
            proofs.append({"code": "marqueurs", "libelle": f"marqueurs de sous-type à leur position officielle "
                           f"({after['marqueurs'][0]} ligne(s), contre {before['marqueurs'][0]} avant)"})
        if after["numeros_facture"] == 1 and before["numeros_facture"] != 1:
            proofs.append({"code": "facture", "libelle": "même n° de facture dans les enregistrements 2 et 2-S"})
        if after["codes"] and not before["codes"]:
            proofs.append({"code": "codes", "libelle": "codes d'actes commençant par une lettre"})
        if after["dates"] and not before["dates"]:
            proofs.append({"code": "dates", "libelle": "dates de prestation valides (enregistrements 3)"})
        if after["somme"] and not before["somme"]:
            proofs.append({"code": "somme", "libelle": "somme des prestations égale au TotalPrestations"})
        # condition impérative : le caractère retiré ne doit pas couper un identifiant (sinon la lecture
        # « réalignée » serait fausse entre ce point et le véritable point d'insertion)
        if len(proofs) >= 3 and after["marqueurs"][1] == 0 and after["identifiants"]:
            changed = [i + 1 for i, (a, b) in enumerate(zip(lines, cand)) if a != b]
            return {"index": idx, "position": idx + 1, "caractere": "espace", "lignes": changed,
                    "lignes_realignees": len(changed), "lignes_total": len(nonempty), "preuves": proofs,
                    "statut": "interprétation à confirmer"}
    return None


def original_position(p: ParsedB2, pos: int) -> int:
    """Position dans la ligne d'ORIGINE d'une position de la lecture réalignée (pour le surlignage)."""
    if p.realignment and pos > p.realignment["index"]:
        return pos + 1
    return pos


def shifted_reading(p: ParsedB2, shift: int = 1) -> dict:
    """Lecture ALTERNATIVE (hypothèse) des identifiants avec un décalage donné.
    Présentée uniquement comme aide à l'instruction, jamais utilisée par les règles."""
    out = {}
    for r in p.records:
        L = r.raw
        if r.rtype == "1" and "NumeroLot" not in out:
            out["NumeroLot"] = L[19 + shift:22 + shift]
        if r.rtype == "2" and "NumeroFacture" not in out:
            out["NumeroAssure"] = L[11 + shift:24 + shift]
            out["NumeroFacture"] = L[29 + shift:38 + shift]
    return out
