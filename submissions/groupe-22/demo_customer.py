"""The fictional customers of the demo login (Connexion démo): accounts, cards and
operations, for the app's screens (GET /api/customer) and the assistant's tools
(get_accounts, search_transactions, get_cards in bank_tools.py), so both always give the
same figures.

Only for a logged-in session, and only its own customer. Read-only seeds: what a
session changes (a card locked or opposed) is in its sandbox (bank_store.py), applied by
customer(). Keys in camelCase, like the page's types (web/src/lib/types.ts).
"""

from datetime import UTC, datetime, timedelta

CUSTOMER = {"firstName": "Camille", "displayName": "Camille Martin", "initials": "CM"}

ACCOUNTS = [
    {
        "id": "acc_cc",
        "type": "COMPTE_COURANT",
        "label": "Compte courant",
        "maskedIban": "FR76 •••• •••• •••• 4521",
        "balanceCents": 124580,
        "status": "OPEN",
    },
    {
        "id": "acc_livret",
        "type": "LIVRET_A",
        "label": "Livret A",
        "maskedIban": "FR76 •••• •••• •••• 8830",
        "balanceCents": 865000,
        "status": "OPEN",
    },
]

CARDS = [
    {
        "id": "card_visa",
        "accountId": "acc_cc",
        "label": "Carte Visa",
        "kind": "PHYSICAL",
        "network": "VISA",
        "maskedNumber": "4821",
        "holder": "CAMILLE MARTIN",
        "expiry": "09/28",
        "status": "ACTIVE",
        "paymentLimitCents": 150000,
        "withdrawalLimitCents": 50000,
        "spentThisPeriodCents": 41207,
        "onlinePayments": True,
        "contactless": True,
    },
    {
        "id": "card_virtual",
        "accountId": "acc_cc",
        "label": "Carte virtuelle",
        "kind": "VIRTUAL",
        "network": "VISA",
        "maskedNumber": "7310",
        "holder": "CAMILLE MARTIN",
        "expiry": "03/27",
        "status": "ACTIVE",
        "paymentLimitCents": 50000,
        "withdrawalLimitCents": 0,
        "spentThisPeriodCents": 1349,
        "onlinePayments": True,
        "contactless": False,
    },
]

CARD = "Carte Visa •••• 4821"
VIRTUAL = "Carte virtuelle •••• 7310"
IN_STORE = "Paiement par carte en magasin."

# (id, account, merchant, statement label, amount in cents, category, description,
# payment channel, pending). One line each: a table.
# fmt: off
THIS_MONTH = [
    # days ago, hour (UTC)
    ((0, 6), ("tx_boulangerie", "acc_cc", "Boulangerie", "CB BOULANGERIE DU MARCHE", -680, "Alimentation", IN_STORE, CARD, False)),
    ((0, 5), ("tx_essence", "acc_cc", "Station-service", "CB STATION RELAIS A7", -5200, "Transports", "Paiement par carte en attente de débit définitif.", CARD, True)),
    ((1, 16), ("tx_supermarche", "acc_cc", "Supermarché", "CB SUPERMARCHE DES HALLES", -4250, "Alimentation", IN_STORE, CARD, False)),
    # The one to contest: the assistant takes the complaint (fiche Réclamation).
    ((2, 21), ("tx_inconnu", "acc_cc", "Paiement inconnu", "CB PAIEMENT EN LIGNE REF 4471-XK", -8900, "Non catégorisé", "Paiement par carte à distance (internet). Le libellé transmis par le commerçant ne permet pas de l'identifier.", f"{CARD}, paiement à distance", False)),
    ((3, 11), ("tx_restaurant", "acc_cc", "Restaurant", "CB LE COMPTOIR DES HALLES", -2490, "Restaurants", IN_STORE, CARD, False)),
    ((4, 18), ("tx_brasserie", "acc_cc", "Brasserie du Parc", "CB BRASSERIE DU PARC", -3640, "Restaurants", IN_STORE, CARD, False)),
    ((4, 7), ("tx_virement_recu", "acc_cc", "Virement reçu", "VIR RECU L. DUBOIS", 2500, "Virements reçus", "Remboursement d'une soirée.", "Virement SEPA", False)),
    ((5, 4), ("tx_netflix", "acc_cc", "Netflix", "PRLV NETFLIX.COM", -1349, "Abonnements", "Prélèvement mensuel d'abonnement.", VIRTUAL, False)),
    ((6, 9), ("tx_sncf", "acc_cc", "SNCF", "CB SNCF CONNECT", -3800, "Transports", "Achat de billet de train en ligne.", CARD, False)),
    ((7, 15), ("tx_pharmacie", "acc_cc", "Pharmacie", "CB PHARMACIE CENTRALE", -1290, "Santé", IN_STORE, CARD, False)),
    ((8, 5), ("tx_salaire", "acc_cc", "Virement salaire", "VIR SEPA SALAIRE ATELIER LUMIERE SAS", 185000, "Revenus", "Salaire mensuel.", "Virement SEPA", False)),
    ((9, 4), ("tx_mobile", "acc_cc", "Forfait mobile", "PRLV SEPA OPERATEUR MOBILE", -1999, "Abonnements", "Prélèvement mensuel.", "Prélèvement SEPA", False)),
]
LAST_MONTH = [
    # day of the month, hour (UTC)
    ((1, 3), ("tx_livret_interets", "acc_livret", "Intérêts", "INTERETS ANNUELS LIVRET A", 18200, "Épargne", "Intérêts capitalisés (montant fictif).", "Opération interne", False)),
    ((2, 5), ("tx_lm_salaire", "acc_cc", "Virement salaire", "VIR SEPA SALAIRE ATELIER LUMIERE SAS", 185000, "Revenus", "Salaire mensuel.", "Virement SEPA", False)),
    ((3, 7), ("tx_lm_loyer", "acc_cc", "Agence Immo Lumière", "VIR LOYER AGENCE IMMO LUMIERE", -72000, "Logement", "Virement permanent : loyer.", "Virement SEPA", False)),
    ((6, 16), ("tx_lm_super1", "acc_cc", "Supermarché", "CB SUPERMARCHE DES HALLES", -6830, "Alimentation", IN_STORE, CARD, False)),
    ((9, 18), ("tx_lm_pizzeria", "acc_cc", "Restaurant", "CB PIZZERIA BELLA", -1890, "Restaurants", IN_STORE, CARD, False)),
    ((10, 4), ("tx_lm_mobile", "acc_cc", "Forfait mobile", "PRLV SEPA OPERATEUR MOBILE", -1999, "Abonnements", "Prélèvement mensuel.", "Prélèvement SEPA", False)),
    ((12, 4), ("tx_lm_netflix", "acc_cc", "Netflix", "PRLV NETFLIX.COM", -1349, "Abonnements", "Prélèvement mensuel d'abonnement.", VIRTUAL, False)),
    ((14, 4), ("tx_lm_energie", "acc_cc", "Fournisseur d'énergie", "PRLV SEPA ENERGIE", -6400, "Logement", "Prélèvement mensuel.", "Prélèvement SEPA", False)),
    ((17, 8), ("tx_lm_sncf", "acc_cc", "SNCF", "CB SNCF CONNECT", -6400, "Transports", "Achat de billet de train en ligne.", CARD, False)),
    ((20, 11), ("tx_lm_restaurant", "acc_cc", "Restaurant", "CB LE COMPTOIR DES HALLES", -2750, "Restaurants", IN_STORE, CARD, False)),
    ((23, 14), ("tx_lm_vetements", "acc_cc", "Boutique de vêtements", "CB MODE ET COMPAGNIE", -5990, "Shopping", IN_STORE, CARD, False)),
    ((26, 16), ("tx_lm_super2", "acc_cc", "Supermarché", "CB SUPERMARCHE DES HALLES", -5410, "Alimentation", IN_STORE, CARD, False)),
]
# fmt: on


def _this_month(now, days_ago, hour):
    """A few days ago, but in this month and in the past: the demo always shows a fresh
    « ce mois-ci »."""
    when = (now - timedelta(days=days_ago)).replace(hour=hour, minute=12, second=0)
    if when > now:
        when = now - timedelta(minutes=days_ago + 1)
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(when, first)


def _last_month(now, day, hour):
    end = now.replace(day=1) - timedelta(days=1)  # the last day of last month
    return end.replace(day=min(day, end.day), hour=hour, minute=30, second=0)


def _transaction(when, row):
    id, account, merchant, label, amount, category, description, channel, pending = row
    return {
        "id": id,
        "accountId": account,
        "merchant": merchant,
        "label": label,
        "amountCents": amount,
        "timestamp": when.isoformat(timespec="seconds"),
        "category": category,
        "status": "PENDING" if pending else "COMPLETED",
        "description": description,
        "channel": channel,
    }


# A second profile, so that one customer reaching another's data can be tested.
LUCAS = {"firstName": "Lucas", "displayName": "Lucas Bernard", "initials": "LB"}
LUCAS_ACCOUNTS = [
    {
        "id": "acc_lb_cc",
        "type": "COMPTE_COURANT",
        "label": "Compte courant",
        "maskedIban": "FR76 •••• •••• •••• 6107",
        "balanceCents": 312040,
        "status": "OPEN",
    },
    {
        "id": "acc_lb_livret",
        "type": "LIVRET_A",
        "label": "Livret A",
        "maskedIban": "FR76 •••• •••• •••• 2294",
        "balanceCents": 230000,
        "status": "OPEN",
    },
]
LUCAS_CARDS = [
    {
        "id": "card_lb_mastercard",
        "accountId": "acc_lb_cc",
        "label": "Carte Mastercard",
        "kind": "PHYSICAL",
        "network": "MASTERCARD",
        "maskedNumber": "9054",
        "holder": "LUCAS BERNARD",
        "expiry": "11/27",
        "status": "ACTIVE",
        "paymentLimitCents": 200000,
        "withdrawalLimitCents": 60000,
        "spentThisPeriodCents": 23870,
        "onlinePayments": True,
        "contactless": True,
    },
]
LUCAS_CARD = "Carte Mastercard •••• 9054"
# fmt: off
LUCAS_THIS_MONTH = [
    ((0, 9), ("tx_lb_cafe", "acc_lb_cc", "Café", "CB CAFE DE LA GARE", -420, "Restaurants", IN_STORE, LUCAS_CARD, False)),
    ((1, 17), ("tx_lb_librairie", "acc_lb_cc", "Librairie", "CB LIBRAIRIE DU CENTRE", -2350, "Shopping", IN_STORE, LUCAS_CARD, False)),
    ((3, 8), ("tx_lb_salaire", "acc_lb_cc", "Virement salaire", "VIR SEPA SALAIRE BUREAU D ETUDES", 241000, "Revenus", "Salaire mensuel.", "Virement SEPA", False)),
    ((5, 12), ("tx_lb_supermarche", "acc_lb_cc", "Supermarché", "CB SUPERMARCHE DU PORT", -6120, "Alimentation", IN_STORE, LUCAS_CARD, False)),
]
LUCAS_LAST_MONTH = [
    ((4, 7), ("tx_lb_lm_loyer", "acc_lb_cc", "Loyer", "VIR LOYER SCI DES TILLEULS", -81000, "Logement", "Virement permanent : loyer.", "Virement SEPA", False)),
    ((15, 4), ("tx_lb_lm_energie", "acc_lb_cc", "Fournisseur d'énergie", "PRLV SEPA ENERGIE", -5800, "Logement", "Prélèvement mensuel.", "Prélèvement SEPA", False)),
]
# fmt: on

# id: (customer, accounts, cards, this month, last month)
CUSTOMERS = {
    "camille": (CUSTOMER, ACCOUNTS, CARDS, THIS_MONTH, LAST_MONTH),
    "lucas": (LUCAS, LUCAS_ACCOUNTS, LUCAS_CARDS, LUCAS_THIS_MONTH, LUCAS_LAST_MONTH),
}
# What the login dialog shows: names, and what's in each profile, nothing more.
PROFILES = [
    {
        "id": "camille",
        "displayName": CUSTOMER["displayName"],
        "description": "Compte courant, Livret A, carte Visa",
    },
    {
        "id": "lucas",
        "displayName": LUCAS["displayName"],
        "description": "Compte courant, Livret A, carte Mastercard",
    },
]


def customer(customer_id, now=None, card_statuses=None):
    """One customer's data, with the card statuses of their session's sandbox."""
    person, accounts, cards, this_month, last_month = CUSTOMERS[customer_id]
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    transactions = [
        _transaction(_this_month(now, *when), row) for when, row in this_month
    ] + [_transaction(_last_month(now, *when), row) for when, row in last_month]
    transactions.sort(key=lambda t: t["timestamp"], reverse=True)
    statuses = card_statuses or {}
    return {
        "customer": {"id": customer_id, **person},
        "accounts": accounts,
        "cards": [
            {**card, "status": statuses.get(card["id"], card["status"])}
            for card in cards
        ],
        "transactions": transactions,
    }
