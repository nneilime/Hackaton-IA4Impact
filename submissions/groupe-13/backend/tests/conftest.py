import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp(prefix="sentinel-test-")
os.environ.setdefault("SENTINEL_DB", str(Path(_tmp) / "test.db"))
# isolation : les dossiers importés et les sauvegardes de l'utilisateur ne doivent jamais influencer les tests
os.environ["SENTINEL_IMPORTS"] = str(Path(_tmp) / "imports")
os.environ["SENTINEL_BACKUPS"] = str(Path(_tmp) / "backups")

# Corpus : extraction sûre de l'archive si l'application n'a pas encore été lancée
from sentinel.corpus import corpus_root, safe_extract  # noqa: E402
try:
    corpus_root()
except FileNotFoundError:
    safe_extract()
