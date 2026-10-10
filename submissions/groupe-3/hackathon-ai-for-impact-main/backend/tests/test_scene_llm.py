"""Scène branchée sur Claude Sonnet 5.5, avec un client Anthropic SIMULÉ (aucune clé, aucun réseau)."""
import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app import llm, schemas
from app.services import scene_llm
from app.services.scene_llm import ComprehensionScene, Reformulation

PHRASE = ("Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et "
          "4 accompagnateurs. Sortie à la journée le 12 novembre, départ le matin et retour avant 19h. "
          "Nous partons du collège de Foix.")
VIDE = dict(niveau=None, theme=None, nb_eleves=None, nb_accompagnateurs=None, date=None, duree=None,
            heure_depart_min=None, heure_retour_max=None, lieu_depart=None, commune_depart=None,
            destination_souhaitee=None)


def comp(intention="donne_infos", **champs) -> ComprehensionScene:
    return ComprehensionScene(**{**VIDE, **champs, "intention": intention})


def reponse(parsed, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, parsed_output=parsed, stop_details=None,
                           usage=SimpleNamespace(input_tokens=700, output_tokens=60,
                                                 cache_read_input_tokens=650, cache_creation_input_tokens=0))


class FauxClient:
    """Imite `client.with_options(...).beta.messages.parse(...)` ; répond selon le format demandé."""

    def __init__(self):
        self.comprendre = lambda kw: reponse(comp("inconnu"))
        self.reformuler = lambda kw: reponse(Reformulation(texte=None))
        self.appels: list[dict] = []
        self.options: list[dict] = []

    def with_options(self, **kw):
        self.options.append(kw)
        return self

    @property
    def beta(self):
        return self

    @property
    def messages(self):
        return self

    def parse(self, **kw):
        self.appels.append(kw)
        f = self.comprendre if kw["output_format"] is ComprehensionScene else self.reformuler
        if kw["output_format"] not in (ComprehensionScene, Reformulation):
            raise AssertionError("appel LLM inattendu pendant la scène : " + kw["model"])
        r = f(kw)
        if isinstance(r, BaseException):
            raise r
        return r

    def formats(self):
        return [a["output_format"].__name__ for a in self.appels]


@pytest.fixture
def ia(monkeypatch, base):
    faux = FauxClient()
    monkeypatch.setattr(llm, "mode", lambda: "llm")
    monkeypatch.setattr(llm, "_get_client", lambda: faux)
    return faux


class Pilote:
    def __init__(self, client):
        self.client, self.etat, self.rep = client, None, None

    def go(self, ev):
        r = self.client.post("/api/scene", json={"etat": self.etat, "evenement": ev})
        assert r.status_code == 200, r.text
        j = r.json()
        assert len(j["replique"].split()) <= 25 and j["etat"]["carnet"][-1]["texte"] == j["replique"]
        self.etat, self.rep = j["etat"], j
        return j

    def texte(self, t):
        return self.go({"type": "texte", "texte": t})

    def choix(self, i):
        return self.go({"type": "choix", "id": i})


@pytest.fixture
def p(client, ia):
    pil = Pilote(client)
    pil.go({"type": "demarrer"})
    return pil


def vers_criteres(p):
    p.choix("theme")
    p.choix("theme:moyen-age")
    return p.choix("niveau:5e")


def vers_destination(p):
    vers_criteres(p)
    p.go({"type": "valeur", "champ": "effectif", "valeur": {"eleves": 42, "accompagnateurs": 4}})
    p.go({"type": "valeur", "champ": "date", "valeur": {"date": "2026-11-12"}})
    return p.go({"type": "valeur", "champ": "lieu_depart", "valeur": {"libelle": "Collège de Foix"}})


ERREUR_RESEAU = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
DELAI = anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


# --- Extraction --------------------------------------------------------------------------------

def test_extraction_du_scenario_de_foix_en_deux_appels_sonnet(p, ia, caplog):
    ia.comprendre = lambda kw: reponse(comp(
        niveau="5e", theme="Moyen Âge", nb_eleves=42, nb_accompagnateurs=4, date="2026-11-12",
        duree="journee", heure_retour_max="19:00", lieu_depart="Collège de Foix", commune_depart="Foix"))
    with caplog.at_level(logging.INFO, logger="lio.llm"):
        j = p.texte(PHRASE)
    assert j["mode"] == "llm" and j["etape"] == "destination"
    d = j["etat"]["demande"]
    assert (d["niveau"], d["theme"], d["nb_eleves"], d["nb_accompagnateurs"], d["date"], d["heure_retour_max"]) \
        == ("5e", "Moyen Âge", 42, 4, "2026-11-12", "19:00")
    assert d["gare_depart"]["nom"] == "Foix"
    # 2 appels au plus : comprendre puis reformuler, tous deux sur Sonnet 5.5 (jamais l'Opus « classique »)
    assert ia.formats() == ["ComprehensionScene", "Reformulation"]
    for a in ia.appels:
        assert a["model"] == "claude-sonnet-5-5"
        assert a["output_config"] == {"effort": "low"}
        assert a["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert a["fallbacks"] == "default" and a["betas"] == ["server-side-fallback-2026-07-01"]
    assert all(o == {"timeout": 8.0, "max_retries": 0} for o in ia.options)
    contenu = ia.appels[0]["messages"][0]["content"]
    assert "Date du jour : 2026-10-10" in contenu and "Étape : accueil" in contenu
    # prompt système figé : identique d'un tour à l'autre (cache)
    assert "2026" not in ia.appels[0]["system"][0]["text"]
    assert "Scène : 2 appel(s) LLM" in caplog.text and "cache lu 1300" in caplog.text


def test_texte_dicte_compris_par_le_llm(p, ia):
    vers_criteres(p)
    ia.comprendre = lambda kw: reponse(comp(nb_eleves=42, nb_accompagnateurs=4))
    j = p.texte("Alors on sera quarante-deux gamins avec quatre adultes")
    d = j["etat"]["demande"]
    assert (d["nb_eleves"], d["nb_accompagnateurs"]) == (42, 4)
    assert j["saisie"]["type"] == "date"


def test_aucune_invention_n_est_transmise_au_moteur():
    etat = schemas.EtatScene(etape="criteres")
    r = comp(nb_eleves=99, heure_depart_min="08:00", heure_retour_max="19:00", lieu_depart="Collège de Foix",
             commune_depart="Pamiers", destination_souhaitee="Carcassonne", niveau="5e", date="12/11/2026")
    out = scene_llm.traduire(r, "Nous partons le matin du collège de Foix, retour avant 19h", etat)
    assert out == {"extrait": {"niveau": "5e", "heure_retour_max": "19:00",
                               "lieu_depart": {"libelle": "Collège de Foix", "commune": None}}}


# --- Intentions --------------------------------------------------------------------------------

def test_intention_autre_idee(p, ia):
    j = vers_destination(p)
    premier = j["destination"]["site_id"]
    ia.comprendre = lambda kw: reponse(comp("autre_idee"))
    j = p.texte("Bof, vous n'auriez pas quelque chose de plus original pour mes élèves ?")
    assert j["etape"] == "destination" and j["etat"]["rang"] == 1
    assert j["destination"]["site_id"] != premier
    assert "Étape : destination" in ia.appels[0]["messages"][0]["content"]


def test_intention_faire_voter(p, ia):
    vers_destination(p)
    ia.comprendre = lambda kw: reponse(comp("faire_voter"))
    j = p.texte("Et si c'étaient mes élèves qui décidaient eux-mêmes ?")
    assert j["etape"] == "vote" and j["etat"]["vote_code"]


def test_intention_pre_reserver_et_autre_train_au_trajet():
    etat = schemas.EtatScene(etape="trajet")
    assert scene_llm.traduire(comp("pre_reserver"), "allez, on fonce", etat) == {"choix": "reserver"}
    assert scene_llm.traduire(comp("autre_train"), "plus tard ?", etat) == {"choix": "autre_train"}
    assert scene_llm.traduire(comp("autre_idee"), "ailleurs", etat) == {"choix": "retour"}
    # une carte absente de l'étape n'est jamais proposée au moteur
    assert "choix" not in scene_llm.traduire(comp("pre_reserver"), "go", schemas.EtatScene(etape="accueil"))


def test_plaisanterie_ramene_a_l_etape(p, ia):
    vers_criteres(p)
    ia.comprendre = lambda kw: reponse(comp("plaisanterie", nb_eleves=12))  # champ parasite : écarté
    ia.reformuler = lambda kw: reponse(Reformulation(
        texte="Hou-hou, aucun poinçon pour vos élèves ! Combien d'élèves et d'accompagnateurs partent ?"))
    j = p.texte("Le contrôleur va-t-il poinçonner mes élèves ?")
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "effectif"
    assert j["etat"]["demande"]["nb_eleves"] is None
    assert j["replique"].startswith("Hou-hou, aucun poinçon")
    # le reformulateur voit le message de l'enseignant (pour l'humour)
    assert "poinçonner" in ia.appels[1]["messages"][0]["content"]


# --- Reformulation -----------------------------------------------------------------------------

def test_reformulation_inventee_refusee(p, ia):
    vers_criteres(p)
    ia.comprendre = lambda kw: reponse(comp("merci"))
    ia.reformuler = lambda kw: reponse(Reformulation(texte="Merci ! Il reste 12 places, combien êtes-vous ?"))
    j = p.texte("merci beaucoup")
    assert "12" not in j["replique"] and j["etape"] == "criteres"
    assert len(ia.appels) == 2


@pytest.mark.parametrize("texte, ok", [
    ("Avec plaisir ! Quelle classe emmenez-vous ?", True),
    ("Il reste douze places, quelle classe ?", False),          # nombre en lettres absent des faits
    ("Direction Carcassonne ! Quelle classe ?", False),         # nom de lieu absent des faits
    ("C'est réservé, quelle classe ?", False),
    ("Votre trajet est confirmé.", False),
    (" ".join(["tchou"] * 26), False),
])
def test_garde_fou_de_reformulation(texte, ok):
    assert scene_llm.reformulation_valide(texte, "Merci ! Quelle classe emmenez-vous ?", {}) is ok


def test_reformulation_garde_les_chiffres_et_lieux_des_faits():
    faits = {"destination": "Basilique Saint-Sernin", "voyageurs": 46}
    assert scene_llm.reformulation_valide("Cap sur Saint-Sernin avec vos 46 voyageurs ! On regarde le train ?",
                                          "Saint-Sernin vous attend.", faits)


# --- Replis --------------------------------------------------------------------------------------

@pytest.mark.parametrize("panne", [ERREUR_RESEAU, DELAI, "refus", "tronque", ValueError("schéma")])
def test_repli_demo_sur_panne(p, ia, panne):
    vers_destination(p)
    if panne == "refus":
        ia.comprendre = ia.reformuler = lambda kw: reponse(None, stop="refusal")
    elif panne == "tronque":
        ia.comprendre = ia.reformuler = lambda kw: reponse(None, stop="max_tokens")
    else:
        ia.comprendre = ia.reformuler = lambda kw: panne
    j = p.texte("une autre idée")  # les règles du mode démo prennent le relais
    assert j["etape"] == "destination" and j["etat"]["rang"] == 1
    assert j["mode"] == "llm" and len(ia.appels) == 2


def test_hooks_renvoient_none_sur_panne(ia):
    etat = schemas.EtatScene(etape="accueil")
    for panne in (ERREUR_RESEAU, DELAI):
        ia.comprendre = ia.reformuler = lambda kw, e=panne: e
        assert scene_llm.comprendre_texte("bonjour", etat) is None
        assert scene_llm.reformuler("Bonjour.", {}, etat) is None
    ia.comprendre = lambda kw: reponse(None, stop="refusal")
    assert scene_llm.comprendre_texte("bonjour", etat) is None


# --- Frugalité ---------------------------------------------------------------------------------

def test_aucun_appel_sur_les_clics(p, ia):
    vers_destination(p)
    p.choix("autre")
    p.choix("pourquoi")
    p.choix("choisir")
    assert p.rep["etape"] == "trajet"
    assert ia.appels == []


def test_commande_globale_sans_appel_de_comprehension(p, ia):
    vers_criteres(p)
    p.texte("retour")
    assert ia.formats() == ["Reformulation"]


def test_quota_de_deux_appels_par_tour(ia):
    with llm.tour_de_scene() as bilan:
        for _ in range(3):
            llm.appel_scene("test", "système", "contenu", Reformulation)
    assert len(ia.appels) == 2 and bilan["appels"] == 2


def test_mode_demo_intact(base, monkeypatch):
    def interdit():
        raise AssertionError("aucun client en mode démo")
    monkeypatch.setattr(llm, "_get_client", interdit)
    etat = schemas.EtatScene(etape="accueil")
    assert llm.mode() == "demo"
    assert scene_llm.comprendre_texte("bonjour", etat) is None
    assert scene_llm.reformuler("Bonjour.", {}, etat) is None
