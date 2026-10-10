import pandas as pd
import os
from typing import Tuple

class DataLoader:
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir

    def _clean_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie les noms de colonnes (suppression du BOM éventuel et des espaces)."""
        df.columns = df.columns.str.replace('\ufeff', '').str.strip()
        return df

    def _resolve_csv(self, filename: str) -> str:
        """Cherche le CSV dans data/raw, puis à la racine du dossier de données."""
        raw_path = os.path.join(self.data_dir, "data", "raw", filename)
        if os.path.isfile(raw_path):
            return raw_path
        return os.path.join(self.data_dir, filename)

    def _read_csv(self, filename: str) -> pd.DataFrame:
        path = self._resolve_csv(filename)
        df = pd.read_csv(path, sep=None, engine="python")
        return self._clean_columns(df)

    def load_agents(self) -> pd.DataFrame:
        """Charge le fichier des agents/sites opérationnels."""
        return self._read_csv("agents_v2.csv")

    def load_postes(self) -> pd.DataFrame:
        """Charge le référentiel des postes électriques."""
        return self._read_csv("poste_v2.csv")

    def load_coupures(self) -> pd.DataFrame:
        """Charge les incidents / coupures de crise."""
        return self._read_csv("coupures_v2_100_crises.csv")

    def load_insee(self) -> pd.DataFrame:
        """Charge le référentiel INSEE des communes."""
        return self._read_csv("insee_v2.csv")

    def load_all(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Charge l'ensemble des jeux de données du projet."""
        return self.load_agents(), self.load_postes(), self.load_coupures(), self.load_insee()