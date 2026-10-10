from crise.geo.distance import calculer_distance_haversine
from crise.strategies.allocator import IncidentAllocator
import pandas as pd

def test_haversine_zero():
    # Toulouse vers Toulouse = 0
    dist = calculer_distance_haversine(43.6047, 1.4442, 43.6047, 1.4442)
    assert dist == 0.0

def test_allocator_basique():
    eq_df = pd.DataFrame([{
        'id_site': 'SITE_01', 'commune': 'Toulouse', 'latitude': 43.60, 'longitude': 1.44, 'disponible': True
    }])
    inc_df = pd.DataFrame([{
        'id_incident': 'INC_01', 'id_poste': 'POSTE_01', 'latitude': 43.61, 'longitude': 1.45, 'nb_clients': 100
    }])
    
    allocator = IncidentAllocator(coeff_detour=1.2)
    decisions = allocator.affecter_incidents(eq_df, inc_df, strategie="distance")
    
    assert len(decisions) == 1
    assert decisions[0]['id_incident'] == 'INC_01'
    assert decisions[0]['id_site'] == 'SITE_01'
    assert decisions[0]['id_equipe'] == 'SITE_01'
    assert decisions[0]['nb_clients'] == 100


def test_une_equipe_deux_pannes_une_seule_decision() -> None:
    eq_df = pd.DataFrame([{
        'id_equipe': 'SITE_01_1',
        'id_site': 'SITE_01',
        'commune': 'Toulouse',
        'latitude': 43.60,
        'longitude': 1.44,
        'disponible': True,
    }])
    inc_df = pd.DataFrame([
        {
            'id_incident': 'INC_01',
            'id_poste': 'POSTE_01',
            'latitude': 43.61,
            'longitude': 1.45,
            'nb_clients': 100,
            'date_incident': pd.Timestamp('2016-01-09 14:08'),
        },
        {
            'id_incident': 'INC_02',
            'id_poste': 'POSTE_02',
            'latitude': 43.70,
            'longitude': 1.50,
            'nb_clients': 20,
            'date_incident': pd.Timestamp('2016-01-09 18:00'),
        },
    ])
    allocator = IncidentAllocator(coeff_detour=1.2, vitesse_kmh=60.0)
    decisions = allocator.affecter_incidents(eq_df, inc_df, strategie="distance")
    assert len(decisions) == 1
    assert decisions[0]['id_incident'] == 'INC_01'


def test_premier_arrive_suit_l_ordre_des_dates() -> None:
    eq_df = pd.DataFrame([
        {
            'id_equipe': 'SITE_01_1',
            'id_site': 'SITE_01',
            'commune': 'Toulouse',
            'latitude': 43.60,
            'longitude': 1.44,
            'disponible': True,
        },
        {
            'id_equipe': 'SITE_02_1',
            'id_site': 'SITE_02',
            'commune': 'Foix',
            'latitude': 42.96,
            'longitude': 1.60,
            'disponible': True,
        },
    ])
    inc_df = pd.DataFrame([
        {
            'id_incident': 'RECENT',
            'id_poste': 'POSTE_02',
            'latitude': 43.61,
            'longitude': 1.45,
            'nb_clients': 500,
            'date_incident': pd.Timestamp('2016-01-09 18:00'),
            'duree_heures': 4.0,
            'poste_avec_client_sensible': 0,
        },
        {
            'id_incident': 'ANCIEN',
            'id_poste': 'POSTE_01',
            'latitude': 42.97,
            'longitude': 1.61,
            'nb_clients': 5,
            'date_incident': pd.Timestamp('2016-01-09 08:00'),
            'duree_heures': 8.0,
            'poste_avec_client_sensible': 1,
        },
    ])
    allocator = IncidentAllocator(coeff_detour=1.2, vitesse_kmh=60.0)
    decisions = allocator.affecter_incidents(eq_df, inc_df, strategie="premier_arrive")
    assert [decision['id_incident'] for decision in decisions] == ['ANCIEN', 'RECENT']


def test_heures_restantes_insuffisantes_refusent_la_mission() -> None:
    eq_df = pd.DataFrame([{
        'id_equipe': 'E1', 'id_site': 'S1', 'commune': 'Toulouse',
        'latitude': 43.60, 'longitude': 1.44, 'disponible': True,
        'heures_restantes': 0.1,
    }])
    inc_df = pd.DataFrame([{
        'id_incident': 'LONGUE', 'id_poste': 'P1',
        'latitude': 43.61, 'longitude': 1.45,
        'nb_clients': 10, 'duree_heures': 5.0,
    }])

    decisions = IncidentAllocator(coeff_detour=1.2, vitesse_kmh=60).affecter_incidents(
        eq_df, inc_df, strategie="distance"
    )

    assert decisions == []