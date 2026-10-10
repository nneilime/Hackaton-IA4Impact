#!/usr/bin/env python3
"""Évalue la recherche sur des questions formulées « comme un client ».

Une requête réussit si une fiche dont l'intitulé correspond au motif attendu
apparaît dans les k premiers résultats (Hit@1, Hit@3, Hit@6, MRR).

    .venv/bin/python -m rag.eval_retrieval
"""
import re
import sys

from rag.retriever import Retriever

# Questions hors périmètre de la FAQ : la recherche doit les signaler comme peu fiables.
OUT_OF_SCOPE = [
    ("quel est le taux de votre prêt immobilier", "CE"),
    ("simuler un crédit auto", "BP"),
    ("acheter du bitcoin", "CE"),
    ("quelle est la météo demain", "BP"),
    ("recette de la tarte aux pommes", "CE"),
    ("rembourser mon prêt immobilier par anticipation", "CE"),
]

# (requête client, banque, motif regex attendu dans l'intitulé de la fiche)
CASES = [
    ("j'ai perdu ma cb", "CE", r"perdu|perte|vol|opposition"),
    ("on m'a volé mon portefeuille avec ma carte dedans", "BP", r"perdu|perte|vol|opposition"),
    ("j'ai oublié le code de ma carte", "CE", r"code.*(carte|confidentiel)|oubli"),
    ("je n'arrive plus à me connecter à mon appli", "CE", r"connect|identifiant|accès|acc[eè]der|mot de passe|code"),
    ("comment envoyer de l'argent à un ami", "CE", r"virement|bénéficiaire|paylib|wero"),
    ("ajouter un nouveau destinataire pour virer de l'argent", "BP", r"bénéficiaire"),
    ("combien de temps pour qu'un virement arrive", "BP", r"délai|combien de temps|crédité"),
    ("retirer des billets sans ma carte", "CE", r"retrait|retir"),
    ("retirer de l'argent au distributeur sans carte", "BP", r"retrait|retir"),
    ("augmenter la limite de paiement de ma carte", "CE", r"plafond"),
    ("payer avec mon iphone", "CE", r"apple pay|mobile|smartphone"),
    ("payer avec mon téléphone android", "BP", r"google pay|mobile|smartphone"),
    ("c'est quoi sécur'pass", "CE", r"sécur.?pass"),
    ("je change de téléphone, comment je fais pour sécur'pass", "CE", r"sécur.?pass|téléphone|appareil"),
    ("je veux mon rib", "CE", r"rib|iban"),
    ("télécharger mes relevés de compte", "BP", r"relevé|document|e-document"),
    ("bloquer temporairement ma carte", "BP", r"verrouill|bloqu|opposition"),
    ("déclarer un accident de voiture", "CE", r"sinistre|accident|déclar"),
    ("ajouter mon fils comme conducteur sur mon assurance auto", "BP", r"conducteur"),
    ("dégât des eaux dans mon appartement", "CE", r"sinistre|dégât|habitation|déclar"),
    ("ouvrir un livret A", "CE", r"livret|épargne|ouvrir|souscri"),
    ("faire un versement sur mon assurance vie", "BP", r"versement|assurance vie"),
    ("transférer mon PEL", "CE", r"pel|épargne|transf"),
    ("chèque encaissé quand", "CE", r"chèque"),
    ("commander un chéquier", "BP", r"chéquier|chèque"),
    ("prélèvement que je ne reconnais pas", "CE", r"prélèvement|contest|opposition"),
    ("j'ai reçu un sms bizarre qui me demande mes codes", "CE", r"fraude|hameçonnage|phishing|arnaque|sécurité|frauduleu|communiquer un code"),
    ("mon compte a été piraté", "BP", r"fraude|pirat|frauduleu|sécurité|usurpation"),
    ("changer mon adresse", "CE", r"adresse|coordonnées|informations personnelles"),
    ("changer mon numéro de téléphone", "BP", r"téléphone|coordonnées|numéro"),
    ("modifier le bénéficiaire de mon contrat", "BP", r"bénéficiaire"),
    ("mettre de l'argent de côté automatiquement", "CE", r"épargne|versement|programm|virement"),
    ("je veux joindre mon conseiller", "CE", r"contacter.*conseiller|rendez-vous"),
    ("prendre rdv avec ma conseillère", "BP", r"rendez-vous|contacter"),
    ("faire opposition sur un chèque perdu", "CE", r"opposition.*chèque|chèque"),
    ("envoyer de l'argent avec wero", "BP", r"wero"),
    ("débloquer mon appli avec mon visage", "CE", r"biométri|face id"),
    ("augmenter le montant max de mes virements", "BP", r"plafond"),
    ("virement immédiat", "CE", r"instantané"),
    ("être prévenu quand je reçois de l'argent", "CE", r"notif|alert|averti"),
    ("mon ado peut-il augmenter les plafonds de sa carte", "BP", r"mineur|enfant"),
    ("me plaindre de mon assurance", "CE", r"réclamation"),
    ("navigateur pour signer un document", "CE", r"navigateur|safari|firefox|signature|document"),
    ("utiliser ma carte à l'étranger", "BP", r"étranger|voyage|international"),
]


def main(k=6):
    r = Retriever()
    hits1 = hits3 = hitsk = 0
    mrr = 0.0
    fails = []
    for query, bank, pattern in CASES:
        res = r.search(query, bank=bank, k=k)
        rank = next((i for i, x in enumerate(res) if re.search(pattern, x["question"], re.I)), None)
        if rank is None:
            fails.append((query, bank, [x["question"] for x in res[:3]]))
            continue
        hits1 += rank == 0
        hits3 += rank < 3
        hitsk += 1
        mrr += 1 / (rank + 1)
    n = len(CASES)
    print(f"Hit@1 {hits1/n:.0%} | Hit@3 {hits3/n:.0%} | Hit@{k} {hitsk/n:.0%} | MRR {mrr/n:.3f}  ({n} requêtes)")
    for q, b, top in fails:
        print(f"  ✗ [{b}] {q}\n      → {top}")
    return hitsk / n


if __name__ == "__main__":
    sys.exit(0 if main() >= 0.8 else 1)
