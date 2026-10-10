import pytest
import os
import pandas as pd
from crise.loaders.loaders import DataLoader

def test_data_loader():
    # Vérifie que le loader s'initialise et charge les fichiers sans erreur
    loader = DataLoader(data_dir=".")
    
    agents = loader.load_agents()
    postes = loader.load_postes()
    coupures = loader.load_coupures()
    insee = loader.load_insee()
    
    # Assertions sur les DataFrames
    assert isinstance(agents, pd.DataFrame)
    assert not agents.empty
    assert "id_site" in agents.columns or "id_site" in [c.replace('\ufeff', '') for c in agents.columns]
    
    assert isinstance(postes, pd.DataFrame)
    assert not postes.empty
    assert "id_poste" in postes.columns
    
    assert isinstance(coupures, pd.DataFrame)
    assert not coupures.empty
    assert "numero_crise" in coupures.columns
    
    assert isinstance(insee, pd.DataFrame)
    assert not insee.empty
    assert "code_insee" in insee.columns