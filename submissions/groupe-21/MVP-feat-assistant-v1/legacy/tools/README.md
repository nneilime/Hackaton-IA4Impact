# Brancher les sources officielles au chatbot

`faq_runtime.py` utilise uniquement la bibliothèque standard Python 3.9 ou supérieure. Il ne nécessite pas de clé API et ne consulte que les FAQ publiques indiquées dans le corpus.

## Chercher une question

Depuis le dossier RAG :

```sh
python3 tools/faq_runtime.py search "Retrait SMS sans carte" --bank CE --limit 3
python3 tools/faq_runtime.py search "SMART retrait jeton" --bank BP --limit 3
```

La recherche renvoie des candidats. Le chatbot doit vérifier la correspondance entre la question du client, le produit, l’opération et la source. Un score lexical ne suffit pas à établir cette correspondance.

## Lire la preuve officielle

```sh
python3 tools/faq_runtime.py read CE-f4ebc36eec0b --bank CE
python3 tools/faq_runtime.py read BP-3a449fc3bca5 --bank BP
```

Ces deux identifiants concernent le retrait sans carte. Pour une autre intention, prendre l’identifiant renvoyé par la recherche.

Dans l’application du chatbot :

```python
from faq_runtime import search_faq, read_source

candidates = search_faq(question_client, bank_code="CE", limit=5)
# Sélectionner l’intention et la portée pertinentes parmi les candidats.
evidence = read_source(source_id_selectionne, bank_code="CE")
if evidence["status"] == "ok" and evidence["factual_answer_allowed"]:
    # Transmettre answer_blocks au modèle, avec la provenance et les limites.
    # Le modèle paraphrase les faits utiles et cite source_url.
    pass
else:
    # Signaler ce qui n’a pas pu être vérifié et fournir le lien connu.
    pass
```

Le champ `answer_blocks` conserve l’ordre des paragraphes, listes, tableaux et descriptions vidéo. Les paragraphes de public visé et les conditions font partie de la preuve. Les cellules vides et les sous-listes sont préservées. `reference_text` est une commodité textuelle ; le format structuré conserve davantage d’information sur les listes et tableaux.

Les illustrations et vidéos ne sont pas transcrites. Les documents liés ne sont pas lus automatiquement. Toute information dépendant de ces éléments reste à vérifier.

Une lecture via `--cache-dir` est réservée aux tests : elle est marquée historique et ne reçoit pas l’autorisation de produire une condition bancaire actuelle. Une erreur HTTP, une redirection hors du périmètre ou un contenu éditorial non reconnu empêche cette autorisation.

`html_changed_since_snapshot` indique un changement du HTML, qui peut inclure des éléments techniques. Le hash structuré de la réponse a une méthode différente du hash de texte de la première collecte ; les deux ne doivent pas être directement comparés.

## Validation réalisée

- 921 extractions depuis les HTML du cache : aucun texte perdu ou ajouté détecté.
- 44 listes imbriquées et huit tableaux contrôlés.
- Vidéos intercalées entre deux blocs de texte : ordre conservé.
- Recherche testée sur les retraits, les bénéficiaires, les contacts d’assurance, les navigateurs et les opérations de prévoyance.
- Lecture HTTP réelle réussie sur une page de chaque banque.
- Banque incorrecte et identifiant de source inconnu refusés.

Le connecteur est fourni pour intégration. Aucun chatbot hébergé ni dialogue de production n’a été déployé ou testé.
