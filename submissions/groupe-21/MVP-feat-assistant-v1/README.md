# RAG — FAQ Caisse d'Épargne et Banque Populaire

Prototype étudiant (hackathon BPCE-SI IA4Impact 2026), non officiel. Voir [context.md](context.md) pour le cadre du projet.

> **Assistant IA Caisse d’Épargne** (maquette `front/index.html`, versions web et mobile) : **tout passe par l’API Gemini**.
> Le modèle (`gemini-3.8-flash`, secours automatique `gemini-3.7-flash`) cherche dans la base de connaissances
> complète ci-dessous (outil `search_faq`), lit la fiche intégrale (`read_source`), calcule sur la base fictive
> (`finance/`) et répond avec ses connaissances générales quand la FAQ ne couvre pas la question (réponse signalée).
> La dictée passe par `gemini-3.5-transcribe`. Aucun modèle n’est exécuté localement.
> Voir [assistant/README.md](assistant/README.md).
>
> ```sh
> python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
> cp .env.example .env    # renseigner GEMINI_API_KEY
> .venv/bin/python -m assistant   # http://localhost:8000 (?vue=mobile pour la version mobile)
> ```

Base de connaissances complète et moteur de recherche (RAG) pour alimenter une IA d'aide au parcours client.

```
scraper/   collecte complète des FAQ (texte intégral)        → data/
rag/       index lexical (BM25), recherche, éval → rag/index/
legacy/    ancienne version (extraits tronqués), archivée
```

## Démarrage rapide

```sh
/opt/homebrew/bin/python3.12 -m venv .venv          # Python ≥ 3.10
.venv/bin/pip install -r requirements.txt

# 1. Collecte (≈ 10 min, 2 req/s par site ; cache dans .cache/html)
python3 scraper/scrape_faq.py
# 2. Index lexical (quelques secondes, aucun modèle)
.venv/bin/python rag/build_index.py
# 3. Évaluation de la recherche
.venv/bin/python -m rag.eval_retrieval
# 4. Interroger
.venv/bin/python -m rag "j'ai perdu ma carte" --bank CE --context
```

Les étapes 1–2 sont déjà faites : `data/` et `rag/index/` sont livrés.

## 1. Données (`data/`)

| Fichier | Contenu |
|---|---|
| `faq_corpus.jsonl` | 1 ligne = 1 question : banque, rubrique, sous-rubrique, question, public visé, **réponse intégrale en Markdown** (`answer_markdown`) et en texte (`answer_text`), vidéos, liens, URL, dates de publication / modification, empreinte |
| `markdown/faq_ce.md`, `faq_bp.md` | Les mêmes FAQ en un document lisible, classé par rubrique |
| `scrape_report.json` | Couverture : pages, questions, URLs du sitemap non collectées, erreurs |

Le scraper combine **crawl récursif** des liens `/faq-particuliers/` et **sitemaps officiels** pour ne rien manquer, respecte `robots.txt`, limite à 2 requêtes/s par site, et convertit le HTML en Markdown fidèle (listes numérotées et imbriquées, tableaux, encadrés « Bon à savoir », vidéos YouTube avec description). `--sections faq-particuliers faq-independants` ajoute d'autres FAQ.

## 2. RAG (`rag/`)

- **Découpage** : une fiche = un fragment si ≤ 220 mots, sinon découpage aux frontières de blocs avec recouvrement. Chaque fragment est préfixé de son contexte (banque › rubrique › sous-rubrique › question) — technique dite *contextual chunking*.
- **Recherche lexicale** fusionnée par RRF (*Reciprocal Rank Fusion*) : BM25 sur les fragments + BM25 sur les intitulés. Normalisation française (accents, pluriels, synonymes métier : « cb » → carte, « prêt » → crédit, « arnaque » → fraude…).
- **Compréhension par l’API** : aucun embedding local. Le modèle de langage (Gemini) reformule ses recherches avec le vocabulaire de la FAQ, choisit parmi les candidats et lit la fiche complète avant de répondre.
- **Filtre banque strict** : jamais de mélange CE/BP, sauf comparaison explicite.
- `eval_retrieval.py` : 44 questions formulées comme un client, sans le vocabulaire de la FAQ → Hit@1/3/6 et MRR.

## 3. Utilisation par une IA

```python
from rag.retriever import Retriever
r = Retriever()
r.search("j'ai perdu ma carte", bank="CE", k=5)                # fiches classées (+ score)
ctx = r.context("j'ai perdu ma carte", bank="CE", k=3)          # contexte prêt pour le prompt
ctx["context"]   # fiches complètes entre balises <source ...> (url, date, rubrique)
r.get("CE-c57506ebca77")                                        # fiche complète
```

CLI : `.venv/bin/python -m rag "retirer sans carte" --bank BP --context`.
Prompt système recommandé : [rag/prompt_systeme.md](rag/prompt_systeme.md).
Fragments prêts à indexer ailleurs : `rag/index/chunks.jsonl`. Pour une IA à base de fichiers (Claude Projects, GPT, Copilot Studio) : `data/markdown/`.

**Qualité mesurée de la recherche seule** (44 questions formulées comme un client, sans reformulation) : Hit@1 70 %, Hit@3 80 %, **Hit@6 91 %**, MRR 0,77. L’assistant affiche 6 candidats au modèle, qui reformule si besoin.

## Limites

- Contenu : FAQ nationales particuliers à la date de collecte ; pas les variantes régionales ni les espaces connectés. Les vidéos et images ne sont pas transcrites (titre et description seulement). Relancer le scraper pour rafraîchir.
- Les FAQ ne couvrent pas les prêts (immobilier, conso) : l'IA doit le signaler plutôt que répondre à côté.
- Les textes des FAQ appartiennent à leurs éditeurs (groupe BPCE) ; usage limité au prototype.
