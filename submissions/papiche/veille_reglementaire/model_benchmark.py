# SPDX-License-Identifier: AGPL-3.0-or-later
"""Comparatif de modèles d'IA sur la MÊME chaîne d'extraction, pour dimensionner GPU et stockage.

MESURÉ (sur le service d'IA de l'essaim) : qualité (exactitude vs source structurée), essais, latence,
tokens/s, taille disque et mémoire GPU du modèle chargé (API Ollama).
ESTIMÉ (toujours étiqueté comme tel) : VRAM d'un autre contexte ou d'un autre nombre de requêtes parallèles,
et débit sur d'autres cartes. L'efficacité utilisée pour ces estimations est CALIBRÉE sur la mesure réelle.
Le script se rejoue tel quel sur la machine GPU cible : `./veille bench`.
"""
from __future__ import annotations

import json
import os
import shutil
import time

import requests

from . import config, evaluation, extraction_loop, llm, qdrant_store

DEFAULT_MODELS = ["llama3.2:latest", "qwen2.5:latest", "gemma3:12b"]
SAMPLE_SIZE_PER_SOURCE = {"ephy": 20, "pmra": 10, "epa": 10}
CONTEXT_TOKENS = 4096        # fenêtre de contexte utilisée par l'extraction
GPU_OVERHEAD_GB = 0.8        # contexte CUDA et tampons de calcul : marge d'ingénierie, pas une mesure
ACCEPTED_TOLERANCE = 2       # un modèle plus petit est « aussi bon » s'il rejette au plus 2 passages de plus


# ── Échantillon et accès à l'API du service d'IA ─────────────────────────────

def pick_sample(passages, size_per_source: dict | None = None) -> list:
    """Échantillon déterministe, identique pour tous les modèles : pas régulier dans chaque source."""
    size_per_source = size_per_source or SAMPLE_SIZE_PER_SOURCE
    sample = []
    for source_id, wanted in size_per_source.items():
        in_source = sorted((p for p in passages if p.source_id == source_id), key=lambda p: p.passage_id)
        step = max(1, len(in_source) // wanted)
        sample += in_source[::step][:wanted]
    return sample


def call_ollama_api(path: str, payload: dict | None = None) -> dict:
    url = config.OLLAMA_HOST.rstrip("/") + path
    response = requests.post(url, json=payload, timeout=60) if payload else requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


# ── Faits sur un modèle (taille, architecture, coût du cache KV) ─────────────

def read_model_facts(model_name: str) -> dict:
    installed = {m["name"]: m for m in call_ollama_api("/api/tags")["models"]}
    if model_name not in installed and f"{model_name}:latest" in installed:
        model_name = f"{model_name}:latest"
    info = call_ollama_api("/api/show", {"model": model_name})
    details, model_info = info["details"], info["model_info"]
    architecture = model_info["general.architecture"]

    def arch_value(key, default=None):
        return model_info.get(f"{architecture}.{key}", default)

    layers = arch_value("block_count")
    heads = arch_value("attention.head_count")
    kv_heads = arch_value("attention.head_count_kv", heads)
    head_dim = arch_value("attention.key_length") or (arch_value("embedding_length") // heads if heads else None)
    # Cache KV par token = clés + valeurs (×2), en demi-précision (2 octets). Borne haute (ignore les fenêtres glissantes).
    kv_bytes_per_token = 2 * layers * kv_heads * head_dim * 2 if layers and kv_heads and head_dim else None
    return {"model": model_name, "params": details.get("parameter_size"), "quant": details.get("quantization_level"),
            "disk_gb": round(installed[model_name]["size"] / 1e9, 2) if model_name in installed else None,
            "arch": architecture, "layers": layers, "kv_heads": kv_heads, "head_dim": head_dim,
            "context_max": arch_value("context_length"), "kv_bytes_per_token": kv_bytes_per_token}


def read_loaded_memory(model_name: str) -> dict:
    """Mémoire réellement occupée par le modèle chargé (poids + cache KV), et part qui est en VRAM."""
    for loaded in call_ollama_api("/api/ps").get("models", []):
        if model_name in (loaded["name"], loaded["model"]):
            return {"total_gb": round(loaded["size"] / 1e9, 2), "vram_gb": round(loaded.get("size_vram", 0) / 1e9, 2)}
    return {"total_gb": None, "vram_gb": None}


# ── Mesure d'un modèle ───────────────────────────────────────────────────────

def summarize_by_source(traces: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for trace in traces:
        source = summary.setdefault(trace["passage"]["source_id"], {"n": 0, "accepted": 0, "attempts": 0, "verifie_auto": 0})
        source["n"] += 1
        source["accepted"] += trace["outcome"] == "accepted"
        source["attempts"] += len(trace["attempts"])
        source["verifie_auto"] += bool(trace["record"]) and trace["record"]["validation_status"] == "verifie_auto"
    for source in summary.values():
        source["accept_rate"] = round(source["accepted"] / source["n"], 3)
        source["mean_attempts"] = round(source["attempts"] / source["n"], 2)
    return summary


def measure_model(model_name: str, passages: list) -> dict:
    """Passe tous les passages de l'échantillon dans la chaîne complète avec ce modèle (sans cache)."""
    config.MODEL, llm.DIRECT, llm.BYPASS_CACHE = model_name, True, True
    llm.COUNTERS.update({key: 0 for key in llm.COUNTERS})

    traces, seconds_per_passage = [], []
    for number, passage in enumerate(passages, 1):
        started = time.time()
        trace = extraction_loop.extract_passage(passage)
        seconds_per_passage.append(time.time() - started)
        traces.append(trace)
        print(f"  [{model_name}] {number}/{len(passages)} {passage.source_id} {trace['outcome']} "
              f"essais={len(trace['attempts'])} {seconds_per_passage[-1]:.1f}s", flush=True)

    counters = dict(llm.COUNTERS)
    expected = {p.passage_id: p.gold for p in passages if p.gold}
    quality = evaluation.score_against_source(traces, expected)
    by_source = summarize_by_source(traces)
    count = len(passages)
    return {
        "model": model_name, "passages": count,
        "accepted": sum(s["accepted"] for s in by_source.values()), "hitl": count - sum(s["accepted"] for s in by_source.values()),
        "verifie_auto": sum(s["verifie_auto"] for s in by_source.values()), "by_source": by_source,
        "accuracy_vs_structured": quality["exactitude_par_champ"], "invented_values_published": quality["valeurs_inventees_publiees"],
        "s_per_passage_mean": round(sum(seconds_per_passage) / count, 2),
        "s_per_passage_p95": round(sorted(seconds_per_passage)[int(0.95 * (count - 1))], 2),
        "llm_calls": counters["calls"], "prompt_tokens_per_passage": round(counters["prompt_tokens"] / count),
        "gen_tokens_per_passage": round(counters["gen_tokens"] / count),
        "decode_tok_s": round(counters["gen_tokens"] / counters["decode_s"], 1) if counters["decode_s"] else None,
        "prefill_tok_s": round(counters["prompt_tokens"] / counters["prefill_s"], 1) if counters["prefill_s"] else None,
        "load_s": round(counters["load_s"], 1), "memory_loaded": read_loaded_memory(model_name),
    }


# ── Estimations : VRAM, débit par carte, recommandation ──────────────────────

def estimate_vram(facts: dict, parallel_requests: int = 1) -> dict:
    """VRAM = poids + cache KV (contexte × requêtes parallèles) + marge. ESTIMATION."""
    kv_gb = (facts["kv_bytes_per_token"] or 0) * CONTEXT_TOKENS * parallel_requests / 1e9
    return {"parallel": parallel_requests, "weights_gb": facts["disk_gb"], "kv_gb": round(kv_gb, 2),
            "vram_gb": round(facts["disk_gb"] + kv_gb + GPU_OVERHEAD_GB, 2)}


def load_gpu_catalog() -> list[dict]:
    return json.loads((config.CONFIG / "gpu_catalog.json").read_text())["gpus"]


def find_declared_gpu() -> dict | None:
    """La carte du service d'IA est déclarée (VEILLE_GPU) : l'API Ollama ne donne pas son nom."""
    declared = config.SERVICE_GPU.casefold()
    return next((g for g in load_gpu_catalog() if declared and declared in g["name"].casefold()), None)


def calibrate_efficiency(results: dict, facts_by_model: dict, gpu: dict | None) -> float | None:
    """Part de la bande passante de la carte réellement utilisée en génération, mesurée sur le plus gros modèle.

    Débit effectif (Go/s) = tokens/s mesurés × taille des poids. Efficacité = débit effectif / bande passante de la fiche.
    """
    if not gpu:
        return None
    biggest = max(results, key=lambda m: facts_by_model[m]["disk_gb"])
    effective_gb_s = results[biggest]["decode_tok_s"] * facts_by_model[biggest]["disk_gb"]
    return round(effective_gb_s / gpu["bandwidth_gb_s"], 2)


def estimate_gpu_table(results: dict, facts_by_model: dict, efficiency: float | None) -> list[dict]:
    efficiency = efficiency or 0.6          # valeur prudente si aucune carte n'est déclarée
    rows = []
    for gpu in load_gpu_catalog():
        for model, facts in facts_by_model.items():
            vram_needed = estimate_vram(facts)["vram_gb"]
            fits = vram_needed <= gpu["vram_gb"]
            tokens_per_second = efficiency * gpu["bandwidth_gb_s"] / facts["disk_gb"]
            seconds_per_passage = results[model]["gen_tokens_per_passage"] / tokens_per_second
            rows.append({"gpu": gpu["name"], "model": model, "fits": fits, "vram_needed_gb": vram_needed,
                         "est_tok_s": round(tokens_per_second),
                         "est_passages_per_hour": round(3600 / seconds_per_passage) if fits else None})
    return rows


def recommend(results: dict, facts_by_model: dict) -> dict:
    """Le plus petit modèle dont la qualité est à moins de ACCEPTED_TOLERANCE du meilleur."""
    best_accepted = max(r["accepted"] for r in results.values())
    good_enough = [m for m, r in results.items() if r["accepted"] >= best_accepted - ACCEPTED_TOLERANCE]
    chosen = min(good_enough, key=lambda m: facts_by_model[m]["disk_gb"])
    fitting_gpus = [g for g in load_gpu_catalog() if estimate_vram(facts_by_model[chosen], 4)["vram_gb"] <= g["vram_gb"]]
    return {"model": chosen, "vram_1_request_gb": estimate_vram(facts_by_model[chosen], 1)["vram_gb"],
            "vram_4_parallel_gb": estimate_vram(facts_by_model[chosen], 4)["vram_gb"],
            "smallest_gpu": min(fitting_gpus, key=lambda g: g["vram_gb"])["name"] if fitting_gpus else None,
            "rule": f"plus petit modèle à moins de {ACCEPTED_TOLERANCE} passages du meilleur ({best_accepted} acceptés)"}


# ── Stockage ─────────────────────────────────────────────────────────────────

def folder_size_mb(folder) -> float:
    if not folder.exists():
        return 0.0
    return round(sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6, 1)


def measure_storage() -> dict:
    """Volumes réels de ce dépôt, puis extrapolation linéaire (hypothèses écrites dans la note)."""
    raw_mb = {source: folder_size_mb(config.RAW / source) for source in ("ephy", "pmra", "epa")}
    passages_now = len(qdrant_store.all_passages())
    vector_dimensions = 768
    kb_per_passage = (vector_dimensions * 4 + 2200) / 1024      # vecteur f32 + charge utile typique (~2 Ko), hors index
    index_margin = 1.6                                           # index HNSW et réplication
    scenarios = [("MVP actuel (3 sources, produits LPC)", passages_now),
                 ("Catalogues complets FR + CA + US", 400_000), ("Monde (≈ 10 pays)", 1_000_000)]
    return {"raw_mb": raw_mb, "raw_total_mb": round(sum(raw_mb.values()), 1),
            "processed_mb": folder_size_mb(config.PROCESSED), "llm_cache_mb": folder_size_mb(config.CACHE),
            "passages_now": passages_now, "kb_per_passage": round(kb_per_passage, 1),
            "extrapolation": [{"scenario": name, "passages": n, "qdrant_gb_est": round(n * kb_per_passage * index_margin / 1e6, 2)}
                              for name, n in scenarios],
            "note": "Extrapolation linéaire (×1,6 pour l'index et la réplication), à recalibrer sur le volume réel."}


# ── Rapport ──────────────────────────────────────────────────────────────────

def describe_service(results: dict, gpu: dict | None, efficiency: float | None) -> dict:
    on_gpu = any((r["memory_loaded"]["vram_gb"] or 0) > 0 for r in results.values())
    client_cpu = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "")
    return {"accelerator": "GPU" if on_gpu else "CPU", "gpu_declared": gpu["name"] if gpu else (config.SERVICE_GPU or None),
            "gpu_bandwidth_gb_s": gpu["bandwidth_gb_s"] if gpu else None, "efficiency_measured": efficiency,
            "endpoint": config.OLLAMA_HOST,
            "client": {"cpu": client_cpu, "threads": os.cpu_count(), "has_local_nvidia": bool(shutil.which("nvidia-smi")),
                       "note": "le poste client n'exécute pas le modèle : le calcul se fait sur le service d'IA de l'essaim"}}


def write_report(results: dict, facts_by_model: dict, sample_passages: list) -> dict:
    gpu = find_declared_gpu()
    efficiency = calibrate_efficiency(results, facts_by_model, gpu)
    for model, result in results.items():
        result["facts"] = facts_by_model[model]
        result["sizing"] = {"1 requête": estimate_vram(facts_by_model[model], 1),
                            "4 requêtes parallèles": estimate_vram(facts_by_model[model], 4)}
    report = {
        "service": describe_service(results, gpu, efficiency),
        "sample": {"passages": len(sample_passages),
                   "by_source": {s: sum(p.source_id == s for p in sample_passages) for s in SAMPLE_SIZE_PER_SOURCE}},
        "results": results, "recommendation": recommend(results, facts_by_model),
        "gpu_table": estimate_gpu_table(results, facts_by_model, efficiency),
        "storage": measure_storage(), "embedding": read_model_facts(config.EMBED_MODEL)}
    report_dir = config.PROCESSED / "bench"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (config.ROOT / "docs").mkdir(exist_ok=True)
    (config.ROOT / "docs" / "BENCHMARK.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def run(models: list[str] | None = None, size_per_source: dict | None = None) -> dict:
    models = models or DEFAULT_MODELS
    sample_passages = pick_sample(qdrant_store.all_passages(), size_per_source)
    print(f"[bench] {len(sample_passages)} passages, modèles : {', '.join(models)}", flush=True)
    results, facts_by_model = {}, {}
    try:
        for model in models:
            facts_by_model[model] = read_model_facts(model)
            results[model] = measure_model(model, sample_passages)
    finally:
        llm.DIRECT = llm.BYPASS_CACHE = False
    return write_report(results, facts_by_model, sample_passages)


def render_markdown(report: dict) -> str:
    service, results = report["service"], report["results"]
    reco = report["recommendation"]
    lines = [
        "# Comparatif de modèles et dimensionnement GPU / stockage", "",
        f"**Service d'IA mesuré** : {service['accelerator']} {service['gpu_declared'] or ''} "
        f"(essaim Astroport.ONE, joint via `{service['endpoint']}`). Le poste client ({service['client']['cpu']}) n'exécute pas le modèle.",
        f"Échantillon identique pour tous les modèles : {report['sample']['passages']} passages ({report['sample']['by_source']}).", "",
        "> **Mesuré** : qualité, essais, latence, tokens/s, disque, mémoire GPU du modèle chargé.",
        f"> **Estimé** : VRAM d'autres réglages et débit d'autres cartes. Efficacité de bande passante calibrée sur la mesure : {service['efficiency_measured']}.", "",
        "## 1. Qualité et vitesse (mesurées)", "",
        "| Modèle | Taille | Disque | Acceptés | Vers l'expert | Dose exacte (e-Phy) | Valeurs inventées | s / passage | tokens/s |",
        "|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        accuracy = r["accuracy_vs_structured"]["dose_value"]
        lines.append(f"| {name} | {r['facts']['params']} | {r['facts']['disk_gb']} Go | {r['accepted']}/{r['passages']} | {r['hitl']} | "
                     f"{'–' if accuracy is None else f'{round(accuracy * 100)} %'} | {r['invented_values_published']} | "
                     f"{r['s_per_passage_mean']} | {r['decode_tok_s']} |")
    lines += ["", "## 2. Mémoire GPU : mesurée et estimée", "",
              "| Modèle | Poids | VRAM mesurée (chargé, 1 requête) | VRAM estimée, 1 requête | VRAM estimée, 4 requêtes // |", "|---|---|---|---|---|"]
    for name, r in results.items():
        lines.append(f"| {name} | {r['facts']['disk_gb']} Go | {r['memory_loaded']['vram_gb']} Go | "
                     f"{r['sizing']['1 requête']['vram_gb']} Go | {r['sizing']['4 requêtes parallèles']['vram_gb']} Go |")
    lines += ["", "Cache KV = 2 × couches × têtes KV × dimension × 2 octets × 4096 jetons × requêtes parallèles (borne haute).", "",
              f"**Recommandation** : `{reco['model']}` ({reco['rule']}). VRAM : {reco['vram_1_request_gb']} Go pour 1 requête, "
              f"{reco['vram_4_parallel_gb']} Go pour 4 en parallèle. Plus petite carte du catalogue qui convient : {reco['smallest_gpu']}.", "",
              "## 3. Quelle carte ? (estimation)", "",
              "| GPU | Modèle | Tient en VRAM | Débit estimé (tok/s) | Passages / heure |", "|---|---|---|---|---|"]
    for row in report["gpu_table"]:
        lines.append(f"| {row['gpu']} | {row['model']} | {'oui' if row['fits'] else 'non'} ({row['vram_needed_gb']} Go) | "
                     f"{row['est_tok_s']} | {row['est_passages_per_hour'] or '–'} |")
    storage = report["storage"]
    lines += ["", "## 4. Stockage", "",
              f"Mesuré : données brutes {storage['raw_total_mb']} Mo ({storage['raw_mb']}), sorties {storage['processed_mb']} Mo, "
              f"cache IA {storage['llm_cache_mb']} Mo, {storage['passages_now']} passages indexés.", "",
              "| Scénario | Passages | Qdrant (estimé) |", "|---|---|---|"]
    lines += [f"| {e['scenario']} | {str(f'{e['passages']:,}').replace(',', ' ')} | {e['qdrant_gb_est']} Go |" for e in storage["extrapolation"]]
    lines += ["", storage["note"], "",
              "Modèles à héberger : " + ", ".join(f"{n} ({r['facts']['disk_gb']} Go)" for n, r in results.items())
              + f" ; embedding {report['embedding']['model']} ({report['embedding']['disk_gb']} Go)."]
    return "\n".join(lines) + "\n"
