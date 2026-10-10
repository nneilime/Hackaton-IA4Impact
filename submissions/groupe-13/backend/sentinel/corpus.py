"""Ingestion du corpus : lecture sûre de l'archive, manifeste SHA-256, appariement JPG/TXT.

- extraction protégée (chemins absolus, « .. », liens symboliques et bombes ZIP refusés) ;
- originaux conservés en lecture seule ;
- l'appariement par nom de fichier n'est qu'une HYPOTHÈSE : il est ensuite confirmé par les
  identifiants (voir rules.pairing_check).
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .config import ARCHIVE_PATH, CORPUS_DIR, JPG_SUBDIR, TXT_SUBDIR

MAX_TOTAL_UNCOMPRESSED = 300 * 1024 * 1024
MAX_FILES = 2000
_NAME_RE = re.compile(r"^(Facture(\d+)_(\d+))\.(jpg|txt)$", re.I)


def _fix_name(name: str) -> str:
    """Les noms de l'archive encodent les accents en « #U00f4 » (convention de certains outils)."""
    return re.sub(r"#U([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), name)


def safe_extract(archive: Path = ARCHIVE_PATH, dest: Path = CORPUS_DIR) -> dict:
    archive = Path(archive)
    if not archive.exists():
        raise FileNotFoundError(f"Archive introuvable : {archive}")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    report = {"archive": str(archive.name), "archive_sha256": sha256_file(archive), "extracted": 0,
              "skipped": [], "refused": []}
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"Archive corrompue (premier membre en erreur : {bad})")
        infos = z.infolist()
        if len(infos) > MAX_FILES:
            raise ValueError("Archive refusée : trop de fichiers")
        if sum(i.file_size for i in infos) > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("Archive refusée : taille décompressée excessive")
        for info in infos:
            name = info.filename
            p = PurePosixPath(name)
            mode = (info.external_attr >> 16) & 0o170000
            if p.is_absolute() or ".." in p.parts or name.startswith(("/", "\\")) or ":" in p.parts[0]:
                report["refused"].append({"name": name, "reason": "chemin non sûr"}); continue
            if mode == stat.S_IFLNK:
                report["refused"].append({"name": name, "reason": "lien symbolique"}); continue
            target = (root / _fix_name(name)).resolve()
            if not str(target).startswith(str(root)):
                report["refused"].append({"name": name, "reason": "sortie du répertoire"}); continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True); continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.chmod(target, 0o644)
            with z.open(info) as src, open(target, "wb") as out:
                out.write(src.read())
            os.chmod(target, 0o444)        # originaux en lecture seule
            report["extracted"] += 1
    return report


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_root(dest: Path = CORPUS_DIR) -> Path:
    """Répertoire contenant « Bordereaux jpg » et « Factures txt »."""
    for cand in [dest] + [p for p in Path(dest).iterdir() if p.is_dir()] if Path(dest).exists() else []:
        if (cand / JPG_SUBDIR).exists() and (cand / TXT_SUBDIR).exists():
            return cand
    raise FileNotFoundError("Structure du corpus non reconnue (dossiers « Bordereaux jpg » / « Factures txt »)")


def build_manifest(dest: Path = CORPUS_DIR) -> dict:
    root = corpus_root(dest)
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            files.append({"path": rel, "size": p.stat().st_size, "sha256": sha256_file(p),
                          "kind": ("bordereau_jpg" if rel.startswith(JPG_SUBDIR) and p.suffix.lower() == ".jpg" else
                                   "facture_txt" if rel.startswith(TXT_SUBDIR) and p.suffix.lower() == ".txt" else
                                   "specification" if p.suffix.lower() in (".docx", ".pdf") else
                                   "documentation" if p.suffix.lower() == ".md" else "autre"),
                          "read_only": not os.access(p, os.W_OK)})
    # doublons de contenu
    by_hash = {}
    for f in files:
        by_hash.setdefault(f["sha256"], []).append(f["path"])
    dups = [v for v in by_hash.values() if len(v) > 1]
    return {"root": root.name, "files": files, "duplicates": dups,
            "counts": {k: sum(1 for f in files if f["kind"] == k) for k in
                       ("bordereau_jpg", "facture_txt", "specification", "documentation", "autre")}}


def pair_documents(dest: Path = CORPUS_DIR) -> list:
    root = corpus_root(dest)
    jpgs = {m.group(1): p for p in (root / JPG_SUBDIR).iterdir() if (m := _NAME_RE.match(p.name)) and p.suffix.lower() == ".jpg"}
    txts = {m.group(1): p for p in (root / TXT_SUBDIR).iterdir() if (m := _NAME_RE.match(p.name)) and p.suffix.lower() == ".txt"}
    keys = sorted(set(jpgs) | set(txts), key=lambda k: (int(_NAME_RE.match(k + ".jpg").group(2)),
                                                         int(_NAME_RE.match(k + ".jpg").group(3))))
    pairs = []
    for k in keys:
        m = _NAME_RE.match(k + ".jpg")
        pairs.append({"id": k, "family": f"Facture{m.group(2)}", "jpg": jpgs.get(k), "txt": txts.get(k),
                      "status": "paire" if k in jpgs and k in txts else ("jpg seul" if k in jpgs else "txt seul")})
    return pairs
