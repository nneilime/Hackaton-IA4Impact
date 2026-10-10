import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crise.loaders.loaders import DataLoader
from crise.preparation.jointure import preparer_pannes, derouler_equipes
from crise.simulation.moteur import comparer_simulations

@pytest.fixture(scope="module")
def data():
    loader = DataLoader(data_dir=str(ROOT_DIR))
    agents_df, postes_df, coupures_df, insee_df = loader.load_all()
    equipes = derouler_equipes(agents_df)
    return coupures_df, postes_df, insee_df, equipes

def test_ia_optimale_performance(data):
    """
    Vérifie que la stratégie IA Optimale bat les heuristiques simples 
    sur un échantillon de crises pour assurer la qualité.
    """
    coupures_df, postes_df, insee_df, equipes = data
    
    # On teste sur un petit échantillon (3 premières crises) pour que le test unitaire soit rapide
    numeros = coupures_df["numero_crise"].unique()[:3]
    
    scores = {"distance": [], "score_pondere": [], "ia_optimale": [], "premier_arrive": []}
    
    for numero in numeros:
        pannes, _, _ = preparer_pannes(coupures_df, postes_df, str(numero))
        if pannes.empty:
            continue
            
        res = comparer_simulations(
            pannes=pannes,
            equipes=equipes,
            pas_min=30,
            nb_pas=96,
            coeff_detour=1.3,
            vitesse_kmh=60.0
        )
        
        for strat in scores.keys():
            scores[strat].append(res[strat]["indicateurs"]["score_objectif"])
            
    moy_ia = np.mean(scores["ia_optimale"])
    moy_dist = np.mean(scores["distance"])
    moy_pond = np.mean(scores["score_pondere"])
    
    # L'IA doit avoir moins de clients-heures de coupure
    assert moy_ia <= moy_dist, f"L'IA ({moy_ia}) est moins performante que la Distance ({moy_dist})"
    assert moy_ia <= moy_pond, f"L'IA ({moy_ia}) est moins performante que le Score Pondéré ({moy_pond})"
