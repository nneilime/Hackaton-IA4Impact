"""Toutes les répliques scriptées de Tchouette, au même endroit.

Règles de ton : vouvoiement, phrases courtes, une pointe d'humour ferroviaire de temps en temps,
25 mots au plus par réplique, jamais « réservé » ni « confirmé » (une pré-réservation n'est qu'une
demande tant que SNCF ne l'a pas confirmée), jamais d'horaire ni de place qui ne vienne du calcul :
les chiffres arrivent par les paramètres `{...}`, calculés par le moteur.

Chaque situation a plusieurs variantes ; `pick` en choisit une de façon déterministe à partir de
`etat.tours` (pas de hasard : mêmes entrées, mêmes sorties).
"""
from __future__ import annotations

import re
import zlib

from .texte import JOURS, MOIS, normaliser

MAX_MOTS = 25

TEXTES: dict[str, list[str]] = {
    # --- Accueil ---------------------------------------------------------------------------
    "accueil": [
        "Bonjour, je suis Tchouette ! Votre sortie en train liO, je m'en occupe. Par où commençons-nous ?",
        "En voiture ! Je suis Tchouette, copilote des sorties scolaires liO. Comment voulez-vous démarrer ?",
        "Tchouette, à votre service ! Je transforme votre projet de classe en sortie en train. Par quelle porte ?",
    ],
    "accueil_retour": [
        "Retour au départ ! Par quelle porte voulez-vous entrer ?",
        "Nous voici au quai de départ. Comment voulez-vous commencer ?",
    ],
    "recommencer": [
        "Nouveau voyage, nouveau billet ! Par où commençons-nous ?",
        "Je remets le compteur à zéro. Une nouvelle sortie, c'est parti : par où commençons-nous ?",
    ],
    # --- Thème / lieu ------------------------------------------------------------------------
    "theme_question": [
        "Quel thème pour votre classe ? Choisissez une carte, ou écrivez le vôtre.",
        "Sur quel thème voulez-vous travailler ? Une carte, ou vos propres mots.",
        "Quel grand thème pour cette sortie ? Cliquez, ou dites-le-moi.",
    ],
    "lieu_question": [
        "Quel lieu souhaitez-vous visiter ? Choisissez-en un, ou écrivez son nom.",
        "Où voulez-vous aller ? Un lieu ci-dessous, ou son nom en toutes lettres.",
    ],
    "theme_ok": [
        "{theme}, excellent choix.",
        "Va pour {theme} !",
        "{theme}, bien noté.",
    ],
    "theme_ambigu": [
        "« {texte} » n'existe pas tel quel. Je connais {a} et {b} : lequel vous convient ?",
        "Je ne vais pas deviner pour « {texte} ». Plutôt {a} ou {b} ?",
    ],
    "theme_hors_catalogue": [
        "« {texte} » n'est pas dans mon catalogue. Voici les thèmes que je connais.",
        "Je n'ai pas de sites sur « {texte} ». Voici ce que je peux vous proposer.",
    ],
    "lieu_hors_catalogue": [
        "« {texte} » n'est pas dans mon catalogue. Voici des lieux que je connais.",
        "Je n'ai pas « {texte} » à vous proposer. Voici des lieux de mon catalogue.",
    ],
    "lieu_ok": [
        "{lieu}, noté.",
        "Cap sur {lieu} !",
    ],
    "theme_surprise": [
        "Une surprise, alors ! Je choisirai pour vous.",
        "Carte blanche : je vous prépare une surprise.",
    ],
    # --- Critères ----------------------------------------------------------------------------
    "q_niveau": [
        "Avec quelle classe partez-vous ? Choisissez une carte ou écrivez le niveau.",
        "Quel niveau pour cette sortie ? Une carte, ou tapez-le : 3e, seconde…",
    ],
    "q_effectif": [
        "Combien d'élèves et d'accompagnateurs ? Un train liO accueille 50 voyageurs au plus.",
        "Combien de voyageurs, adultes compris ? Je compte 50 au maximum par train.",
    ],
    "q_effectif_acc": [
        "Et combien d'accompagnateurs ? Les adultes comptent dans les 50 places.",
        "Combien d'adultes encadrent le groupe ? Ils comptent aussi.",
    ],
    "q_effectif_eleves": [
        "Combien d'élèves partent ?",
        "Combien d'élèves dans le groupe ?",
    ],
    "q_date": [
        "Quelle date pour la sortie ? Idéalement 21 jours avant.",
        "Pour quel jour ? Il faut s'y prendre 21 jours avant, de préférence.",
    ],
    "q_lieu": [
        "D'où partez-vous ? Le nom de l'établissement et sa commune suffisent.",
        "Quel est votre lieu de départ ? J'en déduis la gare la plus proche.",
    ],
    "ack_niveau": ["Classe de {niveau}, noté.", "Les {niveau}, parfait."],
    "ack_effectif": ["{total} voyageurs, noté.", "{total} voyageurs : c'est parti."],
    "ack_date": ["Le {date}, noté.", "Rendez-vous le {date}."],
    "ack_lieu": ["Départ de {gare}, noté.", "Gare de {gare} : j'ai ce qu'il faut."],
    "ack_plusieurs": ["J'ai tout noté d'un coup !", "Plusieurs infos d'un coup : bien reçu."],
    "effectif_trop": [
        "{n} voyageurs : un train liO en accueille 50 au plus. Pouvez-vous partir en deux groupes ?",
        "{n} voyageurs, c'est trop pour un train liO (50 au plus). Deux groupes, peut-être ?",
    ],
    "effectif_peu": [
        "Avec {n} voyageurs, c'est trop peu : l'offre groupe commence à 6, adultes compris.",
        "L'offre groupe démarre à 6 voyageurs, adultes compris. Vous en comptez {n}.",
    ],
    "effectif_invalide": [
        "Je n'ai pas compris l'effectif. Indiquez le nombre d'élèves et d'accompagnateurs.",
    ],
    "date_passee": [
        "Le {date} est déjà passé : je ne remonte pas le temps ! Une date à partir de demain ?",
        "Le {date} est dans le passé. Choisissez une date à venir, dès demain.",
    ],
    "date_trop_proche": [
        "Je ne peux pas partir aujourd'hui : choisissez une date à partir de demain.",
    ],
    "date_illisible": [
        "Je n'ai pas compris la date. Choisissez-la dans le calendrier, ou écrivez « 12 novembre ».",
    ],
    "date_court": [
        "À moins de 21 jours, SNCF étudie la demande au cas par cas.",
        "Moins de 21 jours avant : SNCF regardera au cas par cas.",
    ],
    "lieu_introuvable": [
        "Je ne trouve pas de gare liO près de « {lieu} ». Dans quelle commune d'Occitanie êtes-vous ?",
        "Aucune gare liO trouvée pour « {lieu} ». Pouvez-vous préciser la commune ?",
    ],
    "pourquoi_info": [
        "J'ai besoin de ces infos pour vérifier trains, places et règles de l'offre groupe. Rien d'autre.",
        "C'est pour calculer trains, places et horaires : je ne garde rien d'autre.",
    ],
    "pas_compris": [
        "Je n'ai pas bien saisi. ",
        "Pardon, j'ai raté l'aiguillage. ",
    ],
    # --- Destination ---------------------------------------------------------------------
    "dest_presente": [
        "Je vous propose {nom}, à {commune} : {duree} de train depuis {gare}.",
        "Cap sur {nom} ({commune}) ! {duree} de train depuis {gare}.",
        "Pour vous : {nom}, à {commune}. {duree} de train depuis {gare}.",
    ],
    "dest_presente_sans_duree": [
        "Je vous propose {nom}, à {commune}, accessible en train depuis {gare}.",
        "Cap sur {nom} ({commune}), accessible en train depuis {gare}.",
    ],
    "dest_surprise": [
        "Ma surprise : {nom}, à {commune}. {duree} de train depuis {gare}.",
        "Surprise ! {nom}, à {commune}, à {duree} de train de {gare}.",
    ],
    "dest_souhaitee_absente": [
        "« {souhait} » n'est pas accessible depuis votre gare. Je vous propose plutôt {nom}, à {commune}.",
    ],
    "dest_note_vert": ["", ""],
    "dest_note_orange": ["Faisable, avec des points à surveiller.", "À surveiller de près, mais faisable."],
    "dest_note_rouge": ["Attention : pas assez fiable à cette date.", "Pas assez fiable ce jour-là, je préfère vous le dire."],
    "dest_note_theme": ["Le thème y est peu présent.", "Le thème y est abordé de loin."],
    "dest_autre": [
        "Une autre idée : {nom}, à {commune}. {duree} de train depuis {gare}.",
        "Autre piste : {nom}, à {commune}, à {duree} de train.",
        "Changeons de quai : {nom}, à {commune}. {duree} de train.",
    ],
    "dest_autre_boucle": [
        "C'était ma dernière idée. Je reprends depuis le début : {nom}, à {commune}.",
        "J'ai fait le tour de mes idées. Retour à {nom}, à {commune}.",
    ],
    "dest_aucune_autre": [
        "Je n'ai pas d'autre idée pour ces critères. Changer la date ou le thème ?",
        "C'est ma seule piste pour ces critères. Voulez-vous changer la date ou le thème ?",
    ],
    "dest_aucune": [
        "Aucun train liO pour groupes ne convient ce jour-là. Essayons une autre date ?",
        "Je ne trouve aucune destination accessible en train liO ce jour-là. Une autre date ?",
    ],
    "dest_pourquoi": [
        "Voici mes chiffres : tout vient du calcul, rien n'est inventé.",
        "Je lis les données… et voici le détail, critère par critère.",
        "Je sors la loupe : voici comment j'ai calculé.",
    ],
    "dest_mise_a_jour": [
        "Noté, je relance la recherche. {nom}, à {commune} : {duree} de train.",
        "Compris, je recalcule. Cap sur {nom}, à {commune}.",
    ],
    # --- Trajet --------------------------------------------------------------------------
    "trajet_vert": [
        "Trajet fiable ! Départ à {dep}, retour à {ret}. {dispo} places pour vos {besoin} voyageurs.",
        "Voie libre ! Aller à {dep}, retour à {ret}, {dispo} places pour {besoin} voyageurs.",
        "Ça roule : départ à {dep}, retour à {ret}. {besoin} voyageurs, {dispo} places disponibles.",
    ],
    "trajet_orange": [
        "Faisable, avec des points à surveiller. Départ à {dep}, retour à {ret}, {dispo} places pour {besoin}.",
        "Possible, mais restons vigilants : départ à {dep}, retour à {ret}, {dispo} places pour {besoin}.",
    ],
    "trajet_autre": [
        "Autre option : départ à {dep}, retour à {ret}. {dispo} places pour {besoin} voyageurs.",
        "Un autre train : aller à {dep}, retour à {ret}, {dispo} places pour {besoin}.",
    ],
    "trajet_autre_jour": [
        "Pas assez fiable ce jour-là ({raison}). Autre jour : le {jour}, départ à {dep}, retour à {ret}.",
        "Ce jour-là : {raison}, pas assez fiable. Autre jour possible, le {jour} : départ à {dep}, retour à {ret}.",
    ],
    "trajet_sans_alternative": [
        "Pas assez fiable : {raison}. Je n'ai pas d'alternative sûre. Une autre destination ?",
        "Je préfère vous le dire : {raison}. Aucune alternative sûre. Voulez-vous une autre destination ?",
    ],
    "trajet_aucun": [
        "Aucun aller-retour liO ne tient dans vos horaires. Essayons une autre destination ?",
    ],
    "trajet_aucun_autre": [
        "Je n'ai pas d'autre train fiable pour cette date. Celui-ci reste le meilleur.",
        "C'est le seul train fiable que je trouve. Voulez-vous une autre destination ?",
    ],
    "trajet_indicatif": [" Horaires indicatifs.", " Horaires donnés à titre indicatif."],
    "trajet_pourquoi": [
        "Voici le détail du trajet, chiffres à l'appui.",
        "Je déplie le calcul : tout est là, rien d'inventé.",
    ],
    # --- Vote ----------------------------------------------------------------------------
    "vote_amorce": [
        "Projetez le code : vos élèves votent sur leur téléphone. Je compte les voix !",
        "À vos téléphones, les élèves ! Scannez le code et choisissez votre destination.",
        "Le vote est ouvert. Les élèves scannent le code, je compte les voix.",
    ],
    "vote_un_seul": [
        "Il me faut au moins deux destinations pour un vote. Je n'en ai qu'une.",
    ],
    "vote_termine": [
        "Les élèves ont voté : cap sur {nom} ! {suite}",
        "La classe a parlé : {nom} ! {suite}",
    ],
    "vote_termine_autre_jour": [
        "La classe a choisi {nom}, mais le jour demandé est bloqué ({raison}). Le {jour} fonctionne.",
        "Vote pour {nom} ! Le jour demandé est bloqué ({raison}), pas le {jour}.",
    ],
    "vote_termine_bloque": [
        "La classe a choisi {nom}, mais le trajet n'est pas assez fiable : {raison}. Une autre destination ?",
        "Vote pour {nom} ! Hélas, pas assez fiable : {raison}. Voulez-vous une autre destination ?",
    ],
    "vote_annule": [
        "Vote annulé. Reprenons : voici la destination.",
        "Vote refermé. Revenons aux destinations.",
    ],
    "vote_en_cours": [
        "Le vote est en cours. Terminez-le sur l'écran, puis je reprends.",
    ],
    # --- Pré-réservation -----------------------------------------------------------------
    "prereservation": [
        "C'est une demande de pré-réservation : SNCF doit encore la confirmer. Complétez vos coordonnées.",
        "Je transmets une demande, rien n'est acquis : SNCF doit la confirmer. Il me faut votre e-mail.",
        "Pré-réservation : une demande, pas un billet. SNCF devra la confirmer. Votre e-mail ?",
    ],
    "prereservation_date": ["Va pour le {jour} ! "],
    "fin": [
        "Demande transmise ! La confirmation de SNCF est en attente : rien n'est acquis d'ici là. Dossier {ref}.",
        "C'est parti : votre demande de pré-réservation {ref} est transmise. Confirmation de SNCF en attente.",
        "Demande {ref} transmise à SNCF. La confirmation est en attente : patience, les bons trains arrivent.",
    ],
    "fin_autre_statut": [
        "Dossier {ref} enregistré, statut : {statut}. SNCF reste seule à pouvoir le confirmer.",
    ],
    "fin_retour_exp": [
        "Après la sortie, revenez me raconter : votre retour affine mes notes.",
        "Après le voyage, dites-moi comment c'était : cela aide les prochaines classes.",
    ],
    "fin_texte": [
        "Votre demande est transmise, SNCF doit la confirmer. Une autre sortie en vue ?",
    ],
    # --- Conversation libre ----------------------------------------------------------------
    "salut": [
        "Bonjour ! Je suis à l'heure, moi.",
        "Salut ! Bien arrivé·e en gare de Tchouette.",
    ],
    "merci": [
        "Avec plaisir, c'est mon métier d'oiseau cheminot !",
        "Je vous en prie. Pas de supplément pour la gentillesse.",
    ],
    "blague": [
        "Pourquoi le train est bon élève ? Il suit toujours sa ligne !",
        "Je suis une chouette-locomotive : je vois clair la nuit et je ne rate pas mes correspondances.",
        "Mon secret : je ne siffle jamais en classe, seulement en gare.",
    ],
    "retard": [
        "Les retards, je ne les cache pas : je les mesure et ils comptent dans mon indice.",
        "Je ne promets pas le beau temps, mais je note la régularité de chaque train.",
    ],
    "identite": [
        "Je suis Tchouette, chouette-locomotive : je cherche des trains, pas des histoires.",
        "Tchouette, copilote des sorties scolaires liO. Je vérifie trains, places et règles.",
    ],
    "ca_va": [
        "Ça roule ! Et vous ?",
        "Au quai et en forme, merci !",
    ],
    "insulte": [
        "Aïe ! Je reste sur mes rails. Aidez-moi à mieux vous comprendre.",
        "Je garde mon calme de chouette. Reprenons.",
    ],
    "aide": [
        "Je cherche des sites accessibles en train liO, je vérifie places et horaires, puis je prépare une demande.",
        "Trois étapes : votre projet, une destination, un trajet fiable. Ensuite, une demande de pré-réservation.",
    ],
    "hors_sujet": [
        "Là, je déraille : je ne parle que de sorties scolaires en train liO.",
        "Hors des rails, je suis perdue ! Mon domaine : les sorties scolaires en train.",
        "Joli détour, mais je ne connais que les sorties scolaires en train liO.",
    ],
    "rappel_accueil": ["On démarre ?", "Par où commencer ?"],
    "rappel_theme": ["Alors, quel thème ?", "Quel thème choisissez-vous ?"],
    "rappel_lieu": ["Quel lieu ?", "Où voulez-vous aller ?"],
    "rappel_niveau": ["Quelle classe ?", "Quel niveau ?"],
    "rappel_effectif": ["Combien de voyageurs ?", "Quel effectif ?"],
    "rappel_date": ["Pour quelle date ?", "Quelle date ?"],
    "rappel_lieu_depart": ["D'où partez-vous ?", "Quel lieu de départ ?"],
    "rappel_destination": ["Celle-ci vous plaît ?", "Qu'en dites-vous ?"],
    "rappel_trajet": ["On pré-réserve ?", "Ce trajet vous va ?"],
    "rappel_vote": ["Le vote est en cours.", "Les élèves votent."],
    "rappel_prereservation": ["Il me faut juste votre e-mail.", "Plus qu'une étape."],
    "rappel_fin": ["Une autre sortie ?", "On repart ?"],
    "incomprise_destination": [
        "Je n'ai pas compris : celle-ci, une autre idée, ou pourquoi ?",
        "Pardon ? Dites « celle-ci », « une autre idée » ou « pourquoi ».",
    ],
    "incomprise_trajet": [
        "Je n'ai pas compris : pré-réserver, un autre train, ou pourquoi ?",
        "Pardon ? Dites « pré-réserver », « un autre train » ou « pourquoi ».",
    ],
    "indisponible": [
        "Ce n'est pas possible à cette étape. Utilisez les cartes ou « retour ».",
        "Pas à cette étape, désolée. Les cartes vous montrent la voie.",
    ],
    "modif_bloquee": [
        "Pour modifier le projet, utilisez « retour » ou recommencez.",
    ],
    "trajet_reserver_bloque": [
        "Ce trajet n'est pas assez fiable, je ne le transmets pas.",
    ],
}
# Mots de remplissage supprimés au moment de découper un texte pour le limiter.
_FIN_PHRASE = re.compile(r"(?<=[.!?…])\s+")


def compter(texte: str) -> int:
    return len(texte.split())


def limiter(texte: str, maximum: int = MAX_MOTS) -> str:
    """Garantit `maximum` mots au plus : on retire d'abord les dernières phrases, puis on coupe."""
    texte = " ".join(texte.split())
    if compter(texte) <= maximum:
        return texte
    phrases = _FIN_PHRASE.split(texte)
    while len(phrases) > 1 and compter(" ".join(phrases)) > maximum:
        phrases.pop()
    court = " ".join(phrases)
    if compter(court) > maximum:
        court = " ".join(court.split()[:maximum]).rstrip(",;:") + "…"
    return court


def pick(cle: str, tours: int, **kw) -> str:
    """Variante `cle` choisie de façon déterministe à partir du nombre de tours."""
    variantes = TEXTES[cle]
    i = (tours + zlib.crc32(cle.encode())) % len(variantes)
    return variantes[i].format(**kw) if kw else variantes[i]


def de(nom: str) -> str:
    """« de Foix », « d'Albi »."""
    n = normaliser(nom)
    return f"d'{nom}" if n[:1] in "aeiouyh" else f"de {nom}"


def date_courte(d) -> str:
    """« jeudi 12 novembre » (sans l'année)."""
    return f"{JOURS[d.weekday()]} {'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]}"


_ABREV = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def date_puce(d) -> str:
    """« 12 nov. »."""
    return f"{'1er' if d.day == 1 else d.day} {_ABREV[d.month - 1]}"
