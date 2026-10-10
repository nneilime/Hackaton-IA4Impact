"""Contrat explicite entre les CSV métier et les tables lisibles de Supabase."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "DATA 2 _le kit étudiants" / "BatIA_Kit_Hackathon" / "donnees"
SOURCES = {
    "residences": (
        "01_residences.csv",
        "residence_id",
        "residence_id nom localisation annee_construction nb_batiments nb_logements surface_habitable_totale_m2 ascenseur energie_chauffage type_chauffage generateur_chauffage production_ecs ventilation etiquette_dpe_majoritaire conso_ep_moyenne_kwh_m2_an ges_moyen_kgco2_m2_an",
    ),
    "batiments": (
        "02_batiments.csv",
        "batiment_id",
        "batiment_id residence_id nb_niveaux nb_logements ascenseur",
    ),
    "logements": (
        "03_logements.csv",
        "logement_id",
        "logement_id batiment_id residence_id typologie surface_habitable_m2 etage dpe_methode dpe_date dpe_conso_ep_kwh_m2_an dpe_ges_kgco2_m2_an dpe_etiquette_energie dpe_etiquette_ges dpe_etiquette_globale nb_changements_locataire_2018_2025 date_entree_locataire_actuel statut_occupation",
    ),
    "equipements": (
        "04_equipements.csv",
        "equipement_id",
        "equipement_id famille libelle_famille niveau_rattachement residence_id batiment_id logement_id date_pose origine_date_pose date_pose_precedente nb_remplacements_2018_2025 duree_vie_reference_ans sous_contrat_entretien visite_annuelle_prevue code_metier prestataire_id dans_perimetre_prediction",
    ),
    "demandes": (
        "05_demandes_locataires.csv",
        "demande_id",
        "demande_id date_creation date_cloture logement_id batiment_id residence_id parties canal motif objet texte_demande priorite nb_echanges demande_reouverte delai_resolution_h",
    ),
    "interventions": (
        "06_interventions.csv",
        "intervention_id",
        "intervention_id date_intervention residence_id batiment_id logement_id equipement_id type_intervention code_metier prestataire_id symptome gravite resultat commentaire_technicien demande_id_liee",
    ),
    "commandes": (
        "07_commandes.csv",
        "commande_id",
        "commande_id date_commande residence_id logement_id libelle type_commande nature corps_etat prestataire_id montant_ttc date_facture montant_facture_ttc statut",
    ),
    "investissements": (
        "08_plan_investissement.csv",
        "operation_id",
        "operation_id residence_id type_operation perimetre annee_souhaitee cout_estime_ttc gain_conso_ep_estime_kwh_m2_an nb_logements_concernes date_inscription_demande origine_demande statut rang_actuel_chronologique",
    ),
    "prestataires": (
        "09_prestataires.csv",
        "prestataire_id",
        "prestataire_id nom domaine type_contrat",
    ),
    "metiers": ("10_ref_codes_metiers.csv", "code_metier", "code_metier libelle"),
    "familles": (
        "10_ref_familles_equipements.csv",
        "famille",
        "famille libelle niveau code_metier duree_vie_reference_ans sous_contrat_entretien visite_annuelle cout_remplacement_min_ttc cout_remplacement_max_ttc dans_perimetre_prediction",
    ),
    "motifs": (
        "10_ref_motifs_demandes.csv",
        "motif parties",
        "motif parties nb_demandes_2019_2025",
    ),
    "seuils_dpe": (
        "10_ref_seuils_dpe.csv",
        "classe",
        "classe energie_primaire_kwh_m2_an ges_kgco2_m2_an",
    ),
}
DOCS = {
    "dictionnaire": (
        "table_source colonne",
        "table_source colonne type description equivalent_reel",
    ),
    "hypotheses": ("numero_ligne", "numero_ligne theme regle niveau_preuve source"),
    "documentation": (
        "numero_ligne",
        "numero_ligne colonne_1 colonne_2 colonne_3 colonne_4 colonne_5 colonne_6",
    ),
}
EXTRA_SOURCES = {
    "prix_interventions": (
        "prix_interventions.csv",
        "famille type_intervention type_panne",
        "famille type_intervention type_panne prix",
    ),
}
IMPORT_SOURCES = {**SOURCES, **EXTRA_SOURCES}
TABLES = {
    name: (key.split(), columns.split())
    for name, (_, key, columns) in IMPORT_SOURCES.items()
}
TABLES.update(
    {name: (key.split(), columns.split()) for name, (key, columns) in DOCS.items()}
)
BOOLS = {
    "ascenseur",
    "sous_contrat_entretien",
    "visite_annuelle_prevue",
    "visite_annuelle",
    "dans_perimetre_prediction",
    "demande_reouverte",
}
INTS = {
    "annee_construction",
    "nb_batiments",
    "nb_logements",
    "nb_niveaux",
    "etage",
    "nb_changements_locataire_2018_2025",
    "nb_remplacements_2018_2025",
    "duree_vie_reference_ans",
    "nb_echanges",
    "annee_souhaitee",
    "nb_logements_concernes",
    "rang_actuel_chronologique",
    "nb_demandes_2019_2025",
    "numero_ligne",
}
NUMBERS = {
    "prix",
    "surface_habitable_totale_m2",
    "conso_ep_moyenne_kwh_m2_an",
    "ges_moyen_kgco2_m2_an",
    "surface_habitable_m2",
    "dpe_conso_ep_kwh_m2_an",
    "dpe_ges_kgco2_m2_an",
    "delai_resolution_h",
    "montant_ttc",
    "montant_facture_ttc",
    "cout_estime_ttc",
    "gain_conso_ep_estime_kwh_m2_an",
    "cout_remplacement_min_ttc",
    "cout_remplacement_max_ttc",
}
DATES = {
    "dpe_date",
    "date_pose",
    "date_pose_precedente",
    "date_commande",
    "date_facture",
    "date_inscription_demande",
}
TIMESTAMPS = {"date_creation", "date_cloture", "date_intervention"}
# Les dates du kit sont des heures locales sans fuseau : aucun décalage à l'import.
REQUIRED = {
    "prix_interventions": {"prix"},
    "batiments": {"residence_id"},
    "logements": {"batiment_id", "residence_id"},
    "equipements": {
        "famille",
        "residence_id",
        "batiment_id",
        "duree_vie_reference_ans",
        "dans_perimetre_prediction",
    },
    "demandes": {"residence_id", "batiment_id", "date_creation", "motif", "parties"},
    "interventions": {
        "equipement_id",
        "residence_id",
        "batiment_id",
        "date_intervention",
        "type_intervention",
    },
    "commandes": {"residence_id"},
    "investissements": {"residence_id"},
}
RELATIONS = {
    "prix_interventions": [("famille", "familles", "famille")],
    "batiments": [("residence_id", "residences", "residence_id")],
    "logements": [
        ("residence_id", "residences", "residence_id"),
        ("batiment_id", "batiments", "batiment_id"),
    ],
    "familles": [("code_metier", "metiers", "code_metier")],
    "equipements": [
        ("residence_id", "residences", "residence_id"),
        ("batiment_id", "batiments", "batiment_id"),
        ("logement_id", "logements", "logement_id"),
        ("famille", "familles", "famille"),
        ("code_metier", "metiers", "code_metier"),
        ("prestataire_id", "prestataires", "prestataire_id"),
    ],
    "demandes": [
        ("residence_id", "residences", "residence_id"),
        ("batiment_id", "batiments", "batiment_id"),
        ("logement_id", "logements", "logement_id"),
    ],
    "interventions": [
        ("equipement_id", "equipements", "equipement_id"),
        ("residence_id", "residences", "residence_id"),
        ("batiment_id", "batiments", "batiment_id"),
        ("logement_id", "logements", "logement_id"),
        ("demande_id_liee", "demandes", "demande_id"),
        ("prestataire_id", "prestataires", "prestataire_id"),
        ("code_metier", "metiers", "code_metier"),
    ],
    "commandes": [
        ("residence_id", "residences", "residence_id"),
        ("logement_id", "logements", "logement_id"),
        ("prestataire_id", "prestataires", "prestataire_id"),
    ],
    "investissements": [("residence_id", "residences", "residence_id")],
}


def column_type(column: str) -> str:
    if column in BOOLS:
        return "boolean"
    if column in INTS:
        return "integer"
    if column in NUMBERS:
        return "numeric"
    if column in DATES:
        return "date"
    if column in TIMESTAMPS:
        return "timestamp without time zone"
    return "text"


def source_ddl() -> str:
    statements = []
    for table, (keys, columns) in TABLES.items():
        required = set(keys) | REQUIRED.get(table, set())
        fields = [
            f"{col} {column_type(col)}" + (" not null" if col in required else "")
            for col in columns
        ]
        fields += [f'primary key ({", ".join(keys)})']
        if table == "equipements":
            fields += ["check (duree_vie_reference_ans > 0)"]
        statements.append(f'create table public.{table} ({", ".join(fields)});')
        statements.append(
            f"comment on table public.{table} is 'Source : {IMPORT_SOURCES[table][0] if table in IMPORT_SOURCES else 'CSV documentaire du kit'}';"
        )
    for table, relations in RELATIONS.items():
        for col, parent, key in relations:
            statements.append(
                f"alter table public.{table} add foreign key ({col}) references public.{parent}({key}) deferrable initially deferred;"
            )
            statements.append(f"create index on public.{table} ({col});")
    statements += [
        "alter table public.batiments add unique(batiment_id,residence_id);",
        "alter table public.logements add unique(logement_id,batiment_id,residence_id);",
        "alter table public.logements add unique(logement_id,residence_id);",
        "alter table public.equipements add unique(equipement_id,batiment_id,residence_id);",
        "alter table public.logements add foreign key(batiment_id,residence_id) references public.batiments(batiment_id,residence_id) deferrable initially deferred;",
        "alter table public.demandes add foreign key(motif,parties) references public.motifs(motif,parties) deferrable initially deferred;",
    ]
    for table in ("equipements", "demandes", "interventions"):
        statements += [
            f"alter table public.{table} add foreign key(batiment_id,residence_id) references public.batiments(batiment_id,residence_id) deferrable initially deferred;",
            f"alter table public.{table} add foreign key(logement_id,batiment_id,residence_id) references public.logements(logement_id,batiment_id,residence_id) deferrable initially deferred;",
        ]
    statements += [
        "alter table public.interventions add foreign key(equipement_id,batiment_id,residence_id) references public.equipements(equipement_id,batiment_id,residence_id) deferrable initially deferred;",
        "alter table public.commandes add foreign key(logement_id,residence_id) references public.logements(logement_id,residence_id) deferrable initially deferred;",
        "create index on public.interventions(equipement_id,date_intervention);",
        "create index on public.demandes(date_creation);",
    ]
    return "\n".join(statements)
