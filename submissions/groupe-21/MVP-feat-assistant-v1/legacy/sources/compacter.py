#!/usr/bin/env python3
"""Fusion contrôlée des questions ; aucune nouvelle requête HTTP."""
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit
from collecter import Tree, unique

BASE = Path(__file__).resolve().parent
CACHE = Path(tempfile.gettempdir()) / "collecte-aides-banques-cache"
BANK_CODES = {"Caisse d’Épargne": "CE", "Banque Populaire": "BP"}

# Rapprochements examinés sur les réponses HTML par l'agent de contrôle.
# Les variantes de portée restent explicites dans les noms de liens.
MERGES = [
    ("Peut-on activer ou désactiver le paiement sans contact ?", "thème commun, portée différente", {
        "comment-desactiver-le-paiement-sans-contact-sur-ma-carte-bancaire": "sans contact",
    }),
    ("Comment alimenter Wise par un virement SEPA depuis mon compte ?", "questions similaires", {
        "comment-effectuer-le-virement-sepa-vers-wise": "procédure détaillée",
        "comment-faire-pour-regler-wise-par-un-virement-sepa-a-partir-de-mon-compte": "règlement Wise",
    }),
    ("Comment ajouter un bénéficiaire de virement ou son IBAN ?", "questions similaires", {
        "comment-puis-je-ajouter-un-beneficiaire-de-virement": "bénéficiaire",
        "comment-ajouter-un-iban-pour-realiser-un-virement": "IBAN",
    }),
    ("Quand puis-je virer de l’argent à un nouveau bénéficiaire ?", "questions similaires", {
        "lajout-dun-nouveau-beneficiaire-est-il-immediat-sur-mon-application-mobile": "activation",
        "quand-puis-je-envoyer-un-virement-a-destination-dun-nouveau-beneficiaire": "premier virement",
    }),
    ("L’assurance auto est-elle obligatoire et pourquoi assurer son véhicule ?", "questions similaires", {
        "lassurance-auto-est-elle-obligatoire": "obligation",
        "pourquoi-doit-on-assurer-son-vehicule": "motif",
    }),
    ("À quoi sert l’ajout de comptes détenus dans une autre banque ?", "questions similaires", {
        "on-me-propose-dajouter-une-banque-en-quoi-cela-consiste-t-il": "ajout d’une banque",
        "quest-ce-que-le-service-dagregation-de-comptes-detenus-dans-des-banques-externes": "agrégation",
    }),
    ("Qu’est-ce que la version digitale de ma carte et à quoi sert-elle ?", "questions similaires", {
        "quest-ce-lutilisation-digitale-de-ma-carte-bancaire": "présentation",
        "a-quoi-sert-lutilisation-digitale-de-ma-carte-bancaire": "usages",
    }),
    ("Où retrouver un fichier téléchargé ?", "même incident, variantes navigateur", {
        "jai-telecharge-un-fichier-mais-je-ne-le-retrouve-pas": "général",
        "jutilise-safari-jai-telecharge-un-fichier-mais-je-ne-le-retrouve-pas": "Safari",
        "jutilise-firefox-jai-telecharge-un-fichier-mais-je-ne-le-retrouve-pas": "Firefox",
    }),
    ("Comment adhérer à un plan d’épargne retraite individuel en ligne ?", "questions similaires", {
        "comment-souscrire-a-un-plan-epargne-retraite": "procédure",
        "puis-je-adherer-a-un-contrat-plan-depargne-retraite-individuel-en-ligne": "possibilité en ligne",
    }),
]

LONG_LABELS = {
    "un-message-derreur-me-signale-que-le-mot-de-passe-de-lun-de-mes-comptes-externes-nest-pas-a-jour-sur-mon-espace-client-que-faire": "Mot de passe d’un compte externe non actualisé : que faire ?",
    "les-donnees-de-ma-carte-bancaire-ont-ete-utilisees-sans-mon-accord-pour-effectuer-des-achats-en-ligne-alors-meme-que-ma-carte-bancaire-est-toujours-en-ma-possession-comment-est-ce-possible": "Comment des achats frauduleux sont-ils possibles alors que je possède encore ma carte ?",
    "a-venir-bloque-execute-limite-nouveau-rejete-sans-activite-quels-sont-les-differents-statuts-associes-a-un-mandat-de-prelevement": "Que signifient les différents statuts d’un mandat de prélèvement ?",
    "que-faire-si-je-recois-le-message-la-banque-du-beneficiaire-nous-informe-que-le-nom-ou-la-raison-sociale-ne-correspond-pas-a-liban-renseigne": "Nom du bénéficiaire ne correspondant pas à l’IBAN : que faire ?",
    "que-faire-si-je-recois-le-message-la-banque-du-beneficiaire-nest-pas-en-mesure-de-verifier-la-concordance-entre-le-nom-ou-la-raison-sociale-et-liban-du-beneficiaire": "Vérification du nom du bénéficiaire impossible : que faire ?",
    "que-faire-si-je-recois-le-message-la-banque-du-beneficiaire-nous-informe-que-le-nom-ou-la-raison-sociale-associe-a-liban-est": "Nom du bénéficiaire partiellement concordant avec l’IBAN : que faire ?",
}


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def brand_normalize(text):
    text = normalize(text)
    for old, replacement in [
        ("caisse d epargne", "banque marque"),
        ("banque populaire", "banque marque"),
        ("direct ecureuil internet pro", "service pro marque"),
        ("cyberplus entrepreneurs individuels", "service pro marque"),
    ]:
        text = re.sub(r"\b" + re.escape(old) + r"\b", replacement, text)
    return text


def source_text(url):
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".html")
    raw = path.read_text()
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", raw, flags=re.S | re.I)
    title = html.unescape(re.sub(r"<[^>]+>", " ", h1.group(1)))
    title = re.sub(r"\s+", " ", title).strip()
    tree = Tree(raw).root
    main = next(tree.all("main"))
    text = "\n\n".join(n.text() for section in main.all(cls="wp-block-bpce-block-rte") for n in section.all(cls="wysiwyg"))
    media_text = unique(p.text() for section in main.all(cls="video-description") for p in section.all("p") if "video-mask-info" not in p.attrs.get("class", "").split())
    if media_text:
        text += "\n\n" + "\n\n".join(media_text)
    return title, text


def factual_signature(facts):
    result = {}
    for key, values in facts.items():
        normalized = []
        for value in values:
            if key == "téléphones":
                value = re.sub(r"\D", "", value)
                if value.startswith("0033"):
                    value = "0" + value[4:]
                elif value.startswith("33"):
                    value = "0" + value[2:]
            elif key == "montants":
                value = re.sub(r"\s+", "", value.casefold()).replace("euros", "€").replace("euro", "€").replace(",", ".")
            else:
                value = normalize(value)
            normalized.append(value)
        result[key] = sorted(set(normalized))
    return result


def table_escape(text):
    return text.replace("|", "\\|").replace("\n", " ").replace("[", "\\[").replace("]", "\\]")


def main():
    manifest = json.loads((BASE / "manifest.json").read_text())
    entries, title_groups, slug_index = [], defaultdict(list), defaultdict(list)
    lookup = {}
    categories = {}
    subcategories = {}
    for bank, data in manifest.items():
        for url, p in data["pages"].items():
            parts = urlsplit(url).path.strip("/").split("/")
            if p["kind"] == "rubrique" and len(parts) == 2:
                categories[parts[1]] = p["title"]
            if p["kind"] == "rubrique" and len(parts) == 3:
                subcategories[(parts[1], re.sub(r"-2$", "", parts[2]))] = p["title"]
            if p["kind"] != "question":
                continue
            title, body = source_text(url)
            assert hashlib.sha256(body.encode()).hexdigest() == p["answer_sha256"], url
            row = {"url": url, "bank": bank, "slug": parts[-1], "category": parts[1], "subcategory": re.sub(r"-2$", "", parts[2]), "label": LONG_LABELS.get(parts[-1], p["title"])}
            entries.append(row)
            lookup[url] = {"raw_hash": p["answer_sha256"], "normalized": brand_normalize(body), "facts": factual_signature(p["facts"])}
            title_groups[normalize(title)].append(url)
            slug_index[parts[-1]].append(url)
            if len(entries) % 150 == 0:
                print(f"Analyse des réponses : {len(entries)} / 921", flush=True)

    row_by_url = {row["url"]: row for row in entries}
    groups = [{"label": row_by_url[urls[0]]["label"], "match": "question équivalente", "urls": urls, "variants": {}} for urls in title_groups.values()]
    before_groups = len(groups)
    merges_report = []
    for label, match, slugs in MERGES:
        chosen = {url for slug in slugs for url in slug_index[slug]}
        assert chosen and all(slug_index[slug] for slug in slugs), label
        selected = [group for group in groups if chosen.intersection(group["urls"])]
        assert len(selected) >= 2, (label, selected)
        urls = unique(url for group in selected for url in group["urls"])
        assert set(urls) == chosen, (label, "fusion imprévue")
        groups = [group for group in groups if group not in selected]
        variants = {url: slugs[row_by_url[url]["slug"]] for url in urls}
        if "sans contact" in label:
            variants = {url: "activation/désactivation" if row_by_url[url]["bank"] == "Caisse d’Épargne" else "désactivation" for url in urls}
        groups.append({"label": label, "match": match, "urls": urls, "variants": variants})
        merges_report.append({"label": label, "groups_before": len(selected), "source_count": len(urls), "match": match})

    for group in groups:
        members = [row_by_url[url] for url in group.pop("urls")]
        group["members"] = sorted(members, key=lambda row: (list(BANK_CODES).index(row["bank"]), row["url"]))
        bank_set = {row["bank"] for row in members}
        first = members[0]
        group["category"], group["subcategory"] = first["category"], first["subcategory"]
        group["common"] = len(bank_set) == 2
        signatures = [lookup[row["url"]] for row in members]
        group["fact_differences"] = [key for key in ["montants", "pourcentages", "durées", "téléphones", "courriels"] if len({json.dumps(s["facts"].get(key, []), ensure_ascii=False) for s in signatures}) > 1]
        if not group["common"]:
            group["comparison"] = "CE uniquement" if "Caisse d’Épargne" in bank_set else "BP uniquement"
        elif len({s["raw_hash"] for s in signatures}) == 1:
            group["comparison"] = "Identiques"
        elif len({s["normalized"] for s in signatures}) == 1:
            group["comparison"] = "Adaptées"
        elif group["fact_differences"]:
            group["comparison"] = "Repères à comparer"
        else:
            group["comparison"] = "Rédaction différente"
        if "portée différente" in group["match"] or "navigateur" in group["match"]:
            group["comparison"] += " · portée précisée"

    groups.sort(key=lambda g: (not g["common"], g["category"], g["subcategory"], normalize(g["label"])))
    for i, group in enumerate(groups, 1):
        group["id"] = f"Q{i:03d}"
    all_urls = [member["url"] for group in groups for member in group["members"]]
    assert len(all_urls) == len(set(all_urls)) == len(entries) == 921
    assert set(all_urls) == set(row_by_url)
    # Same answer text alone never merges different user intents.
    for a, b in [
        ("comment-realiser-une-simulation-pour-un-nouveau-contrat-dassurance-prevoyance-deces-invalidite-incapacite-ou-maladie-grave", "comment-modifier-le-montant-du-capital-garanti-ou-le-niveau-de-protection-de-mon-contrat-dassurance-prevoyance"),
    ]:
        for group in groups:
            slugs = [row["slug"] for row in group["members"]]
            assert not (a in slugs and b in slugs)
    report = {
        "source_questions": len(entries), "exact_title_groups_before_review": before_groups,
        "compact_groups": len(groups), "common_groups": sum(g["common"] for g in groups),
        "bank_specific_groups": sum(not g["common"] for g in groups),
        "avoided_repeated_entries": len(entries) - len(groups),
        "manual_reviewed_merges": merges_report,
        "comparison_counts": dict(Counter(g["comparison"] for g in groups)),
        "omitted_urls": [], "duplicated_urls": [],
        "banks": {bank: sum(row["bank"] == bank for row in entries) for bank in BANK_CODES},
    }
    lines = ["# FAQ compactée — Caisse d’Épargne et Banque Populaire", "",
             f"**{len(entries)} questions sources → {len(groups)} groupes** : {report['common_groups']} communs aux deux banques et {report['bank_specific_groups']} spécifiques. Toutes les questions de la collecte initiale conservent leur lien, une seule fois.", "",
             "CE = Caisse d’Épargne ; BP = Banque Populaire. Une ligne regroupe une question équivalente ou des formulations proches vérifiées. Les libellés des liens indiquent les variantes de procédure ou de navigateur.", "",
             "**Identiques** : même texte de réponse. **Adaptées** : même texte après remplacement des seuls noms de banque et du service professionnel de banque à distance, ainsi que normalisation de la ponctuation. **Rédaction différente** : les textes diffèrent ; leur équivalence complète n’est pas affirmée. **Repères à comparer** : les montants, délais ou coordonnées détectés diffèrent ou ne sont pas tous mentionnés dans chaque source. Cela n’implique pas automatiquement une contradiction.", "",
             "Les questions similaires peuvent avoir des réponses propres à chaque banque. Les liens, médias, contrats et conditions restent à vérifier sur la source choisie. Aucun regroupement n’est décidé à partir du seul fait que deux réponses ont le même texte.", "",
             "## Questions communes", ""]
    previous = None
    for common in [True, False]:
        if not common:
            lines.extend(["", "## Questions spécifiques à une seule banque", ""])
            previous = None
        for group in groups:
            if group["common"] != common:
                continue
            heading = (group["category"], group["subcategory"])
            if heading != previous:
                lines.append("")
                if previous is None or heading[0] != previous[0]:
                    lines.extend([f"### {categories[heading[0]]}", ""])
                lines.extend([f"#### {subcategories.get(heading, heading[1])}", "", "| Question ou sujet | Sources | Réponses |", "|---|---|---|"])
                previous = heading
            links = []
            for row in group["members"]:
                label = BANK_CODES[row["bank"]]
                if row["url"] in group["variants"]:
                    label += " · " + group["variants"][row["url"]]
                links.append(f"[{label}]({row['url']})")
            label = table_escape(group["label"])
            if group["match"] != "question équivalente":
                label += " **(questions similaires)**"
            lines.append(f"| {label} | {' · '.join(links)} | {group['comparison']} |")
    lines.extend(["", "## Méthode", "",
                  "La fusion compare les intitulés complets des pages HTML du cache, y compris lorsque le premier inventaire affichait un titre abrégé. Les différences de numérotation d’URL ou d’emplacement de rubrique ne créent pas de doublon. Neuf regroupements supplémentaires ont été examinés sur les réponses sources ; les variantes Safari/Firefox et activation/désactivation sont conservées dans les liens.", "",
                  "L’identité ou l’adaptation des réponses est vérifiée sur leur texte HTML, descriptions de vidéos incluses. Les quatre substitutions autorisées sont : Caisse d’Épargne / Banque Populaire, et Direct Ecureuil Internet PRO / CyberPlus Entrepreneurs Individuels. Les noms de produits, montants, délais et coordonnées ne sont pas remplacés.", "",
                  "Périmètre : les deux FAQ nationales particuliers de la collecte initiale. Aucun nouvel accès réseau. Ce document fournit un index compact avec sources ; les réponses intégrales et vidéos ne sont pas reproduites.", ""])
    md = "\n".join(lines)
    assert all(md.count(f"]({url})") == 1 for url in all_urls)
    (BASE / "questions-compactees.md").write_text(md)
    (BASE / "fusion.json").write_text(json.dumps({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "groups": groups}, ensure_ascii=False, indent=2))
    (BASE / "rapport-fusion.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
