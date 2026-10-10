# Références et vulgarisation : protocoles, principes d'IA, mathématiques

Pour chaque brique : **ce que c'est**, **comment on l'explique simplement**, **où elle sert dans le projet**.
Tout ce qui est cité est réellement utilisé dans le code (fichier indiqué).

## 1. Protocoles

| Protocole / standard | En clair | Usage dans le projet |
|---|---|---|
| **HTTP conditionnel** (ETag, Last-Modified, `If-None-Match`, réponse 304) — [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) | On demande à la source « as-tu changé depuis ma dernière visite ? ». Si non, rien n'est retéléchargé. | `polite_http.py` : collecte sobre des bases d'homologation, une requête « inchangé » ne coûte presque rien. |
| **HTTP 429 / 503 + reprise polie** — [RFC 6585](https://www.rfc-editor.org/rfc/rfc6585) | Quand un serveur dit « trop de demandes », on attend au lieu d'insister. | `polite_http.py` : jamais de surcharge d'une source officielle, journal de chaque requête. |
| **REST + OpenAPI** — [OpenAPI](https://www.openapis.org/) | Une adresse par ressource, et un contrat lisible par une machine qui décrit tout. | `api.py` (FastAPI, contrat sur `/openapi.json`) : base d'un connecteur Power Platform. |
| **Dataverse / Microsoft 365** — [Dataverse](https://learn.microsoft.com/power-apps/maker/data-platform/) | La table de comparaison s'ouvre directement dans les outils Microsoft de LPC. | `microsoft365_export.py`, dossier `m365/`. |
| **Ollama (API locale de modèles)** — [Ollama](https://ollama.com/) | Le modèle tourne chez nous, sur notre carte graphique ; aucune donnée ne part chez un tiers. | `llm.py` : modèle remplaçable par simple variable d'environnement. |
| **Qdrant (base vectorielle)** — [Qdrant](https://qdrant.tech/) | Une base qui retrouve les textes par le sens, et pas seulement par les mots. | `qdrant_store.py` : passages et enregistrements indexés, avec filtres (pays, produit). |
| **IPFS (adressage par contenu)** — [IPFS](https://docs.ipfs.tech/) | Le lien est l'empreinte du contenu : si un octet change, l'adresse change. La preuve ne peut pas être modifiée en douce. | Publication de la démo : `ipfs.copylaradio.com/<CID>/index.html`. |
| **Codes EPPO** — [EPPO Global Database](https://gd.eppo.int/) | Un identifiant international unique par culture ou par cible (VITVI = vigne), au lieu de noms qui varient selon les langues. | `eppo_codes.py` : chaque code renvoie à sa fiche officielle `gd.eppo.int/taxon/<CODE>`. |

## 2. Principes d'IA

| Principe | En clair | Usage |
|---|---|---|
| **Le modèle propose, le code décide** | L'IA lit et suggère ; des règles fixes vérifient. L'IA n'a jamais le dernier mot. | Architecture entière (`extraction_loop.py`). |
| **Sortie structurée validée (Pydantic)** — [Pydantic](https://docs.pydantic.dev/) | On impose un formulaire à remplir. Une case mal remplie est refusée. | `models.py` : dose numérique, unités limitées à kg/ha ou L/ha. |
| **Boucle de correction (retry avec motif)** | Si c'est refusé, on renvoie au modèle l'erreur exacte pour qu'il corrige. | `extraction_loop.py` : jusqu'à 3 essais. |
| **Ancrage sur la source (grounding)** | Chaque valeur doit être accompagnée d'une citation retrouvée mot à mot dans le texte d'origine. Citation inventée : rejet. | Contrôle de preuve, `extraction_loop.py`. |
| **Second avis (LLM critique)** | Un deuxième passage relit le premier, comme une relecture à quatre yeux. | `extraction_loop.py` (`VEILLE_LLM_CRITIC`). |
| **Humain dans la boucle (HITL)** | Après trois échecs, un expert tranche. Rien n'est publié sans validation. | `review.py`, `docs/RELECTURE_HUMAINE.md`. |
| **Recherche sémantique et RAG** — [Lewis et al. 2020](https://arxiv.org/abs/2005.11401) | On retrouve d'abord les bons passages, puis on laisse le modèle répondre uniquement à partir d'eux. | `qdrant_store.py`, `question_answering.py`. |
| **Plongements (embeddings)** | Un texte devient une liste de nombres ; deux textes de sens proche donnent deux listes proches. | `llm.embed`, modèle `nomic-embed-text`. |
| **Choisir parmi une liste fermée** | Pour les codes EPPO, le modèle ne peut choisir que dans les candidats proposés ; sinon `null`. Jamais de code deviné. | `eppo_codes.py`. |
| **Déterminisme** | Température 0 et réponses mises en cache : même question, même réponse, résultat vérifiable. | `llm.py`. |

## 3. Mathématiques appliquées

| Notion | En clair | Usage |
|---|---|---|
| **Similarité cosinus** | Mesure l'angle entre deux listes de nombres : angle faible = sens proche. Valeur de 0 à 1. | `qdrant_store.py` (`Distance.COSINE`). |
| **Ressemblance de chaînes (Ratcliff/Obershelp)** — `difflib` | Proportion de lettres communes dans l'ordre, qui rattrape « vignes » et « vigne ». | `eppo_codes.py` : score des candidats, seuil à 0,6. |
| **Normalisation de texte (Unicode NFKD)** | On retire accents et majuscules pour que « Blé » et « ble » soient le même mot. | `eppo_codes.fold`. |
| **Conversion d'unités (facteurs fixes)** | Tout ramené à kg/ha ou L/ha par multiplication ; une unité inconnue n'est pas convertie. | `models.normalize_dose`. |
| **Empreinte SHA-256** | Une signature de longueur fixe : un seul caractère modifié change tout. | Cache des réponses et des vecteurs, `passage_sha256` pour prouver l'origine d'un passage. |
| **Exactitude par champ, taux de rejet** | Pour chaque champ (dose, culture…), part des valeurs identiques à la source structurée ; on compte aussi les rejets et les valeurs inventées (objectif : zéro publiée). | `evaluation.py`, `model_benchmark.py`. |
| **Échantillonnage reproductible (graine fixe)** | Le tirage au sort est identique à chaque exécution, donc l'évaluation est rejouable. | `holdout_test.py` : test sur produits jamais vus. |

## Lecture conseillée pour un jury

1. Une valeur n'est publiée que si elle a une **preuve** (principe d'ancrage + empreinte).
2. Un code EPPO n'est publié que s'il est **confirmé** par la table (liste fermée + similarité).
3. Chaque requête sortante et chaque réponse du modèle est **tracée** (journal, cache déterministe).
