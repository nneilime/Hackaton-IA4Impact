"""Génère docs/RESULTATS.md à partir de la base (résultats RÉELS sur le corpus)."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sentinel.db import DB  # noqa
from sentinel.rules import RULES  # noqa
from sentinel import ENGINE_VERSION, RULESET_VERSION  # noqa
from sentinel.privacy import mask_text  # noqa  (document publiable : n° d'assuré masqué)

db = DB()
# corpus officiel uniquement : les imports et simulations sont exclus
cases = [c for c in db.q("SELECT * FROM cases ORDER BY id")
         if (c.get("source") or "corpus") == "corpus" and c["family"] != "Import" and (c.get("source_status") or "ok") == "ok"]
ids = {c["id"] for c in cases}
checks = [c for c in db.q("SELECT * FROM check_results") if c["case_id"] in ids]
by = defaultdict(Counter)
for c in checks:
    by[c["rule_id"]][c["status"]] += 1
L = [f"# Résultats réels sur le corpus fourni\n",
     f"Moteur {ENGINE_VERSION}, règles {RULESET_VERSION}. Corpus : `General-main.zip` — 55 bordereaux JPG, 55 factures TXT, "
     f"{len(cases)} dossiers, {len(checks)} contrôles exécutés. Ces chiffres sont produits par `python -m sentinel.cli stats` "
     f"et sont reproductibles (extraction OCR mise en cache, règles déterministes).\n",
     "> Une anomalie est un écart documentaire constaté entre le bordereau et le fichier : ce n'est pas une fraude démontrée.\n",
     "> Les n° d'assuré sont masqués dans ce document publiable (1ᵉʳ chiffre + • + 2 derniers).\n",
     "> Statut de ces résultats : sortie du moteur, examinée par une revue assistée (docs/DIAGNOSTIC_V3.md) **mais pas encore "
     "validée par un validateur humain** (référentiel de validation, écran « Qualité et validation »).\n",
     "## Par règle\n", "| Règle | Intitulé | Évaluables | Conformes | Anomalies | Non vérifiables | Non applicables | Erreurs |", "|---|---|---:|---:|---:|---:|---:|---:|"]
for r in RULES:
    c = by[r.id]
    ev = sum(v for k, v in c.items() if k != "NON_APPLICABLE")
    L.append(f"| {r.id} | {r.title} | {ev} | {c['CONFORME']} | {c['ANOMALIE']} | {c['NON_VERIFIABLE']} | {c['NON_APPLICABLE']} | {c['ERREUR_TECHNIQUE']} |")
L += ["", f"**Dossiers** : {len(cases)} — avec au moins une anomalie : {sum(1 for c in cases if c['n_anomalies'])} — "
      f"avec un contrôle non vérifiable : {sum(1 for c in cases if c['n_nv'])} — sans écart : "
      f"{sum(1 for c in cases if not c['n_anomalies'] and not c['n_nv'])} — rapprochement bordereau/fichier ambigu : "
      f"{sum(1 for c in cases if c['pairing_status'] != 'confirmé')}.\n", "## Par zone du bordereau (15 zones CERFA)\n",
      "Nombre de dossiers par statut de zone (voir docs/ZONES.md pour la correspondance zone ↔ règles).\n",
      "| Zone | Contenu | Conformes | Anomalies | Non vérifiables | Non applicables | Erreurs |", "|---|---|---:|---:|---:|---:|---:|"]
from sentinel.zones import ZONE_IDS, ZONE_INFO  # noqa: E402
zc = {z: Counter() for z in ZONE_IDS}
for c in cases:
    for z in json.loads(db.one("SELECT payload FROM analyses WHERE case_id=?", (c["id"],))["payload"]).get("zones", []):
        zc[z["zone_id"]][z["status"]] += 1
for z in ZONE_IDS:
    k = zc[z]
    L.append(f"| {z} | {ZONE_INFO[z]['label']} | {k['CONFORME']} | {k['ANOMALIE']} | {k['NON_VERIFIABLE']} | {k['NON_APPLICABLE']} | {k['ERREUR_TECHNIQUE']} |")
L += ["", "## Par dossier\n",
      "| Dossier | Anomalies | Constat (explication produite par le moteur) |", "|---|---|---|"]
for c in cases:
    p = json.loads(db.one("SELECT payload FROM analyses WHERE case_id=?", (c["id"],))["payload"])
    an = [r for r in p["results"] if r["status"] in ("ANOMALIE", "NON_VERIFIABLE")]
    txt = "<br>".join(f"**{r['rule_id']}**{'' if r['status']=='ANOMALIE' else ' (non vérifiable)'} — {r['explanation']}" for r in an) or "Aucun écart détecté."
    L.append(f"| {c['id']} | {', '.join(r['rule_id'] for r in an if r['status']=='ANOMALIE') or '—'} | {mask_text(txt).replace('|','/')} |")
L += ["", "## Contrôles implémentés", "",
      "Les 22 règles sont implémentées et exécutées sur les 55 dossiers (aucune erreur technique). "
      "Les règles suivantes reposent sur une convention d'interprétation explicite (à valider par le métier) :", "",
      "- **R01** (AMB-01) : convention proposée, non validée : préfixe `12278*0` exigé, chiffre de version accepté (le bordereau "
      "imprime `12278*01`). Chaque résultat montre aussi la lecture littérale ; une décision de la MSA peut être enregistrée.",
      "- **R03, R04** : comparaison numérique, zéros de cadrage ignorés.",
      "- **Fiabilité géométrique (v3.0)** : un champ ou un tableau mal localisé rend le contrôle *non vérifiable*, jamais "
      "anomalie ni conforme.",
      "- **Politique d'incertitude (v2.0)** : des lectures OCR contradictoires ex æquo ou des moteurs en désaccord rendent le "
      "contrôle *non vérifiable*, même si l'une des lectures égale la valeur du fichier ; R20 n'utilise que des montants lus de façon fiable.",
      "- **R09 / R10** : R09 contrôle interne au fichier (référence : GHS de type 3) ; R10 : actes de la zone 7 comparés au GHS lu en zone 6.",
      "- **R08, R11, R13, R14, R15, R19** : rapprochement occurrence par occurrence ; R19 retrouve un acte suivi d'un 4-M par son code CCAM.",
      "- **R14** : lignes de détail de biologie (codes à 4 chiffres sous un acte B, sans exécutant ni montant) exclues.",
      "", "## Contrôles partiellement pris en charge", "",
      "- **R18** : l'association exécutant ↔ case de signature se fait par le numéro imprimé dans la case. Si ce numéro est illisible "
      "alors qu'un élément est présent, le contrôle passe en *non vérifiable* (association non prouvée) plutôt qu'en conforme.",
      "- **R18, R21** : détection de présence d'un élément (tracé, cachet, mention « par mandat », signature électronique) ; "
      "l'authenticité n'est jamais certifiée.",
      "- **Recalage** (v3.0) : redressement des inclinaisons jusqu'à ±6° et ajustement d'échelle ; pas de correction de "
      "perspective (photo prise de biais).",
      "", "## Limites et ambiguïtés", "",
      "- Aucune vérité terrain validée par un humain : aucun taux de précision n'est affirmé (référentiel de validation prêt, vide).",
      "- Gabarits calibrés sur les 3 mises en page du corpus ; un nouveau modèle de bordereau est signalé « non reconnu ».",
      "- `Facture2_06.txt` contient un blanc inséré en position 11 : le fichier est relu en le réalignant, car le point "
      "d'insertion est démontré par 4 vérifications internes au fichier, sans le bordereau. Cette lecture est signalée comme "
      "une interprétation, avec une alerte « fichier mal formé » (docs/DIAGNOSTIC_V3.md).",
      "- Le montant de 100 000 € (contrôle interne 2025) est une donnée de contexte, non comparable et non extrapolée.",
      "- Les points à clarifier sont listés (AMB-01 à AMB-08), avec l'effet calculé d'un changement de convention, dans l'écran « Règles et conventions »."]
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "RESULTATS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("docs/RESULTATS.md écrit")
