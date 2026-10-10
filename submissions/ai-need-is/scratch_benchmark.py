import sys
from pathlib import Path
import pandas as pd
import numpy as np
from tqdm import tqdm

ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crise.loaders.loaders import DataLoader
from crise.preparation.jointure import preparer_pannes, derouler_equipes
from crise.simulation.moteur import comparer_simulations
from crise.strategies.allocator import STRATEGIES

def run_benchmark():
    loader = DataLoader(data_dir=str(ROOT_DIR))
    agents_df, postes_df, coupures_df, insee_df = loader.load_all()
    equipes = derouler_equipes(agents_df)
    
    # Obtenir tous les numéros de crise
    numeros = coupures_df["numero_crise"].unique()
    
    print(f"Démarrage des simulations sur {len(numeros)} crises...")
    
    resultats = {strat: {"clients_retablis": [], "score_objectif": []} for strat in STRATEGIES}
    
    for numero in tqdm(numeros):
        pannes, _, _ = preparer_pannes(coupures_df, postes_df, str(numero))
        if pannes.empty:
            continue
            
        res = comparer_simulations(
            pannes=pannes,
            equipes=equipes,
            pas_min=30,
            nb_pas=96,  # 48h
            coeff_detour=1.3,
            vitesse_kmh=60.0
        )
        
        for strat in STRATEGIES:
            ind = res[strat]["indicateurs"]
            # Clients coupés restants + (clients*heures pour ceux rétablis) -> score_objectif 
            # Note: The jury was talking about "Clients rétablis moyens" and "Clients-heures moyens"
            # Here clients_retablis is total count. We want % maybe?
            total_clients = sum(pd.to_numeric(pannes["nb_clients"], errors="coerce").fillna(0))
            taux = (ind["clients_retablis"] / total_clients * 100) if total_clients > 0 else 0
            
            resultats[strat]["clients_retablis"].append(taux)
            resultats[strat]["score_objectif"].append(ind["score_objectif"])
            
    print("\n=== RÉSULTATS MOYENS SUR 100 CRISES ===")
    print(f"{'Stratégie':<20} | {'Clients rétablis (%)':<20} | {'Clients-heures (score)':<20}")
    print("-" * 65)
    for strat in STRATEGIES:
        moy_clients = np.mean(resultats[strat]["clients_retablis"])
        moy_score = np.mean(resultats[strat]["score_objectif"])
        print(f"{strat:<20} | {moy_clients:>19.3f}% | {moy_score:>20.0f}")

if __name__ == "__main__":
    run_benchmark()

