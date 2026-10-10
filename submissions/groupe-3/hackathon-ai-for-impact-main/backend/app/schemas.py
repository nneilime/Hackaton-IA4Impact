"""Contrat d'API en Pydantic : miroir champ pour champ de API_CONTRACT.md (snake_case)."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

Niveau = Literal["vert", "orange", "rouge"]
Statut = Literal["OPTION", "PRE_RESERVATION", "CONFIRMATION", "CONTRE_PROPOSITION", "ANNULE"]


class Modele(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Gare(Modele):
    code_uic: str
    nom: str
    lat: float
    lon: float
    distance_m: Optional[float] = None


class LieuDepart(Modele):
    libelle: str
    lat: Optional[float] = None
    lon: Optional[float] = None


class Demande(Modele):
    niveau: Optional[str] = None
    theme: Optional[str] = None
    nb_eleves: Optional[int] = None
    nb_accompagnateurs: Optional[int] = None
    date: Optional[str] = None
    duree: Optional[Literal["journee", "demi-journee"]] = None
    heure_depart_min: Optional[str] = None
    heure_retour_max: Optional[str] = None
    lieu_depart: Optional[LieuDepart] = None
    gare_depart: Optional[Gare] = None
    destination_souhaitee: Optional[str] = None
    champs_manquants: list[str] = Field(default_factory=list)

    @field_validator("niveau", "theme", "date", "duree", "heure_depart_min", "heure_retour_max",
                     "destination_souhaitee", "nb_eleves", "nb_accompagnateurs",
                     "lieu_depart", "gare_depart", mode="before")
    @classmethod
    def _vide_en_null(cls, v):
        # Un champ de formulaire vide arrive souvent sous la forme "" : on le traite comme absent.
        if isinstance(v, str) and not v.strip():
            return None
        return v


class AccesGareSite(Modele):
    mode: Literal["pied", "urbain"]
    minutes_groupe: int
    niveau: Niveau
    message: str


class Destination(Modele):
    site_id: str
    nom: str
    commune: str
    gare: Gare
    interet_pedagogique: str
    activites: list[str]
    themes: list[str]
    niveaux: list[str]
    temps_trajet_min: Optional[int] = None
    correspondances: int
    acces_gare_site: AccesGareSite
    indice_confiance: int
    niveau: Niveau


class Segment(Modele):
    train: str
    gare_depart: str
    gare_arrivee: str
    depart: str
    arrivee: str


class Trajet(Modele):
    segments: list[Segment]
    depart: str
    arrivee: str
    duree_min: int
    correspondances: int


class Jauge(Modele):
    capacite: int
    sous_option: int
    disponibles: int
    groupes_positionnes: int
    besoin: int
    niveau: Niveau


class Controle(Modele):
    regle: str
    libelle: str
    niveau: Niveau
    message: str


class CritereIndice(Modele):
    critere: str
    points: int
    max: int
    explication: str


class Indice(Modele):
    score: int
    niveau: Niveau
    details: list[CritereIndice]


class Proposition(Modele):
    proposition_id: str
    site_id: str
    date: str
    aller: Trajet
    retour: Trajet
    jauge_aller: Jauge
    jauge_retour: Jauge
    marge_avant_visite_min: int
    controles: list[Controle]
    indice: Indice
    explication_ia: str
    est_alternative: bool
    remplace: Optional[str] = None


class EtapeDossier(Modele):
    statut: Statut
    date: str
    message: str


class Dossier(Modele):
    reference: str
    statut: Statut
    message: str
    email: str
    demande: Demande
    site: Destination
    proposition: Proposition
    historique: list[EtapeDossier]
    cree_le: str


class MessageChat(Modele):
    role: Literal["user", "assistant"]
    content: str


# --- Corps et réponses des routes -----------------------------------------------------------

class Sante(Modele):
    ok: bool
    mode: Literal["llm", "demo"]
    donnees: Literal["demo", "sncf"]


class RequeteChat(Modele):
    messages: list[MessageChat] = Field(default_factory=list)
    demande: Optional[Demande] = None


class ReponseChat(Modele):
    reponse: str
    demande: Demande
    complete: bool
    suggestions: list[str]
    mode: Literal["llm", "demo"]


class RequeteDemande(Modele):
    demande: Demande


class ReponseDestinations(Modele):
    destinations: list[Destination]
    message: str


class RequeteTrajets(Modele):
    demande: Demande
    site_id: str


class ReponseTrajets(Modele):
    site: Destination
    propositions: list[Proposition]
    message: str


class RequetePreReservation(Modele):
    proposition_id: str
    email: str
    demande: Optional[Demande] = None


class RequeteSimulation(Modele):
    decision: Literal["confirmer", "contre-proposition"]


class RequeteRetour(Modele):
    reference: str
    satisfaction: int = Field(ge=1, le=5)
    adaptation_train: int = Field(ge=1, le=5)
    acces_gare_site: int = Field(ge=1, le=5)
    confiance: int = Field(ge=1, le=5)
    recommande: bool
    commentaire: Optional[str] = ""


class ReponseRetour(Modele):
    ok: bool
    indice_avant: int
    indice_apres: int
    message: str


# --- Vote en classe (v2) --------------------------------------------------------------------

class OptionSondage(Modele):
    site_id: str
    nom: str
    commune: str
    interet_pedagogique: str
    indice_confiance: int
    niveau: Niveau
    votes: int                 # total = QR + saisie manuelle
    votes_qr: int = 0
    votes_manuels: int = 0


class Sondage(Modele):
    code: str
    titre: str
    statut: Literal["ouvert", "ferme"]
    options: list[OptionSondage]
    total_votes: int
    gagnant: Optional[str] = None
    cree_le: str
    effectif: Optional[int] = None     # élèves de la classe : plafond des votes
    votes_qr: int = 0
    votes_manuels: int = 0


class RequeteVotesManuels(Modele):
    votes: dict[str, int]              # site_id -> nombre de votes saisis en classe (remplace la saisie précédente)


class RequeteSondage(Modele):
    demande: Demande
    destinations: list[Destination]


class RequeteVote(Modele):
    site_id: str
    votant_id: str


class Reseau(Modele):
    ip_locale: Optional[str] = None


# --- Scène « Tchouette est l'interface » (v3) ------------------------------------------------
# Miroir de la section « Scène (v3) » de API_CONTRACT.md. Modèles stricts : un champ inconnu est
# refusé (422) au lieu d'être ignoré en silence.

Etape = Literal["accueil", "theme", "criteres", "destination", "trajet", "vote", "prereservation", "fin"]
HumeurScene = Literal["repos", "reflexion", "parle", "joie", "inquiete", "salue", "pointe", "loupe", "celebre"]
AncreScene = Literal["centre", "gauche", "droite", "haut-droite", "bas-droite"]
IconeScene = Literal["chateau", "os", "colonnes", "planete", "feuille", "palette", "ampoule", "pin",
                     "etincelles", "train", "qr", "coeur", "oui", "non", "retour", "loupe", "calendrier",
                     "groupe"]


class ModeleStrict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Replique(ModeleStrict):
    qui: Literal["tchouette", "enseignant"]
    texte: str


class EtatScene(ModeleStrict):
    etape: Etape
    demande: Demande = Field(default_factory=Demande)
    candidats: list[str] = Field(default_factory=list)
    rang: int = 0
    site_id: Optional[str] = None
    proposition_id: Optional[str] = None
    vote_code: Optional[str] = None
    dossier_reference: Optional[str] = None
    carnet: list[Replique] = Field(default_factory=list)
    tours: int = 0


class EvDemarrer(ModeleStrict):
    type: Literal["demarrer"]


class EvTexte(ModeleStrict):
    type: Literal["texte"]
    texte: str


class EvChoix(ModeleStrict):
    type: Literal["choix"]
    id: str


class EvValeur(ModeleStrict):
    type: Literal["valeur"]
    champ: Literal["effectif", "date", "lieu_depart"]
    valeur: dict[str, str | int]


class EvRetour(ModeleStrict):
    type: Literal["retour"]


class EvVoteTermine(ModeleStrict):
    type: Literal["vote_termine"]
    site_id: str


class EvPrereservationFaite(ModeleStrict):
    type: Literal["prereservation_faite"]
    reference: str


class EvSoumettreVote(ModeleStrict):
    """L'enseignant coche 1 à 4 destinations candidates : 1 = choix direct, 2 à 4 = vote de la classe."""
    type: Literal["soumettre_vote"]
    ids: list[str] = Field(min_length=1, max_length=4)


EvenementScene = Annotated[
    Union[EvDemarrer, EvTexte, EvChoix, EvValeur, EvRetour, EvVoteTermine, EvPrereservationFaite,
          EvSoumettreVote],
    Field(discriminator="type")]


class RequeteScene(ModeleStrict):
    etat: Optional[EtatScene] = None
    evenement: EvenementScene


class CarteScene(ModeleStrict):
    id: str
    titre: str
    sous_titre: Optional[str] = None
    icone: Optional[IconeScene] = None
    style: Optional[Literal["primaire", "neutre"]] = None


class SaisieEffectif(ModeleStrict):
    type: Literal["effectif"] = "effectif"
    min: Literal[6] = 6
    max: Literal[50] = 50
    eleves: Optional[int] = None
    accompagnateurs: Optional[int] = None


class SaisieDate(ModeleStrict):
    type: Literal["date"] = "date"
    min: str
    aide: Optional[str] = None


class SaisieLieu(ModeleStrict):
    type: Literal["lieu"] = "lieu"
    suggestions: list[str]


Saisie = Annotated[Union[SaisieEffectif, SaisieDate, SaisieLieu], Field(discriminator="type")]


class BadgeSource(ModeleStrict):
    icone: Literal["chart", "database", "shield", "train", "pin", "euro", "users", "clock"]
    texte: str
    source: Literal["sncf", "datatourisme", "catalogue", "calcul", "demo"]


class PuceCritere(ModeleStrict):
    cle: str
    libelle: str
    valeur: str


class LigneDetail(ModeleStrict):
    libelle: str
    valeur: str
    niveau: Optional[Niveau] = None


class DetailScene(ModeleStrict):
    titre: str
    lignes: list[LigneDetail]


class PointCarte(ModeleStrict):
    lat: float
    lon: float
    libelle: str
    type: Literal["depart", "arrivee", "destination", "candidate"]
    numero: Optional[int] = None
    actif: bool = False


class CarteGeo(ModeleStrict):
    centre: list[float]                # [lat, lon]
    zoom: int
    points: list[PointCarte]
    traces: list[list[list[float]]] = Field(default_factory=list)   # traces[0] = marche gare -> site


# --- Trajet modifiable et dates proches (ajout) ---------------------------------------------

class OptionHoraire(ModeleStrict):
    id: str                       # numéros de train joints par « + » : à renvoyer dans changer_aller:<id>
    depart: str
    arrivee: str
    duree_min: int
    correspondances: int
    places_disponibles: int
    besoin: int
    niveau: Niveau
    score: int
    actuel: bool = False


class AlternativesTrajet(ModeleStrict):
    aller: list[OptionHoraire] = Field(default_factory=list)
    retour: list[OptionHoraire] = Field(default_factory=list)


class DateProche(ModeleStrict):
    date: str                     # AAAA-MM-JJ
    ecart_jours: int              # signé : -2 = deux jours avant la date demandée
    aller: Trajet
    retour: Trajet
    niveau: Niveau
    score: int


class DatesProchesRequete(ModeleStrict):
    date: str
    gare_depart: str                           # code UIC ou nom de la gare de départ
    site_id: Optional[str] = None              # destination (ou, à défaut, gare d'arrivée ci-dessous)
    gare_arrivee: Optional[str] = None
    effectif: int = Field(ge=1, le=200)
    heure_retour_max: Optional[str] = None
    heure_depart_min: Optional[str] = None


class DatesProchesReponse(ModeleStrict):
    date_demandee: str
    propositions: list[DateProche]


class ReponseScene(ModeleStrict):
    etat: EtatScene
    etape: Etape
    replique: str
    humeur: HumeurScene
    ancre: AncreScene
    cartes: list[CarteScene] = Field(default_factory=list, max_length=4)
    saisie: Optional[Saisie] = None
    badges: list[BadgeSource] = Field(default_factory=list, max_length=4)
    puces: list[PuceCritere] = Field(default_factory=list)
    manquants: list[str] = Field(default_factory=list)
    destination: Optional[Destination] = None
    proposition: Optional[Proposition] = None
    detail: Optional[DetailScene] = None
    mode: Literal["llm", "demo"]
    alternatives: Optional[AlternativesTrajet] = None   # horaires aller / retour de rechange (étape trajet)
    dates_proches: list[DateProche] = Field(default_factory=list)  # si aucun train fiable à la date demandée
    choix_destinations: list[Destination] = Field(default_factory=list)   # candidates à cocher (étape destination)
    carte: Optional[CarteGeo] = None
