import os
import sys
import joblib
from pathlib import Path

# Ajouter le projet au PYTHONPATH
ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crise.strategies.ia_optimizer import _entrainer_modele_ia

def main():
    print("Debut de l'entrainement du modele IA (Knowledge Distillation)...")
    
    # Entraînement
    model = _entrainer_modele_ia()
    
    # Sauvegarde
    checkpoints_dir = ROOT_DIR / "checkpoints"
    checkpoints_dir.mkdir(exist_ok=True)
    
    model_path = checkpoints_dir / "ia_model.joblib"
    joblib.dump(model, model_path)
    
    print(f"Modele entraine avec succes !")
    print(f"Sauvegarde dans : {model_path}")

if __name__ == "__main__":
    main()
