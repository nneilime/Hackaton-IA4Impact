# Édition RAG - chatbot FAQ

Lire [contexte-rag.md](contexte-rag.md) pour les règles de précision et le branchement du lecteur de sources.

L’index contient 921 fiches par banque et 458 groupes. Les enregistrements statiques sont partiels : le chatbot doit lire la réponse officielle complète avec `read_source` avant une réponse de fond. Les huit contextes factuels vérifiés restent des notes datées, pas des réponses actuelles complètes.

- `corpus.jsonl` : 921 unités documentaires avec provenance et filtre de banque.
- `groupes.jsonl` : 458 rapprochements de questions, sans réponse fusionnée.
- `chunks/` : alternative Markdown au JSONL ; ne pas indexer les deux.
- `tools/faq_runtime.py` : recherche locale et lecture HTML à la demande.
- `sources/` : copie exacte du dossier d’origine, exclue de l’indexation.
- `rapport-validation.json` : contrôles de structure, de recherche et de lecture.

Ce dossier prépare les connaissances et les outils ; il ne déploie pas le chatbot. Activer le connecteur dans la plateforme choisie est nécessaire pour obtenir des réponses de fond sourcées et actuelles.
