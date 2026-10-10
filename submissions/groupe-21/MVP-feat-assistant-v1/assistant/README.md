# Assistant web — Caisse d’Épargne (tout par l’API Gemini)

Assistant pour les clients et prospects de la **Caisse d’Épargne** : il répond aux questions, guide les démarches
(code perdu, carte perdue, réclamation, simulation de crédit, conseil, ouverture de compte, conseiller) et **estime
les projets chiffrés** : mensualités, taux futurs, capacité d’emprunt, projections d’épargne. Il s’appuie sur :

- la **base de connaissances FAQ complète** (`data/faq_corpus.jsonl`, réponses intégrales, indexée dans `rag/index/`) :
  le modèle cherche (`search_faq`), lit la fiche entière (`read_source`) et la cite avec son lien officiel ;
- une **base de données fictive** (`data/finance.db`, voir [../finance/README.md](../finance/README.md)) pour les
  taux, prévisions, simulations, tarifs, cartes, offres et délais.

Aucune opération bancaire, aucun accès aux comptes. Aucune affiliation officielle n’est établie avec le groupe BPCE.

## Lancer

Python ≥ 3.10 et une clé [Gemini](https://aistudio.google.com/apikey).

```sh
python3 -m venv .venv
.venv/bin/pip install -r assistant/requirements.txt
cp .env.example .env            # puis renseigner GEMINI_API_KEY=… (fichier ignoré par git)
.venv/bin/python -m assistant   # → http://localhost:8000 (?vue=mobile)
```

La base `data/finance.db` est livrée ; `python -m finance.build_db` la régénère (déterministe).
Sans clé Gemini, l’interface fonctionne quand même : parcours guidés, réponses pré-rédigées et simulateur.

**Assistance vocale (malvoyants)** : bouton **Vocal** du chat (conversation à la voix) et micro (dictée), dans tous
les navigateurs. Voix neuronale Microsoft « Denise » (edge-tts : le texte des réponses part chez Microsoft), voix locale
Piper en secours ou avec `ASSISTANT_TTS=piper`. Écoute : détection de la parole calibrée sur le bruit, fin de phrase
après 0,75 s de silence, transcription par l'API Gemini (`gemini-3.5-transcribe`). On peut couper la parole à l'assistant ; bips d'écoute et de
réception ; phrase d'attente pendant que le modèle réfléchit. Langue par défaut : français.

| Variable | Rôle | Défaut |
|---|---|---|
| `GEMINI_API_KEY` | clé Gemini (modèle et dictée), lue uniquement par le serveur | — |
| `ASSISTANT_MODEL` | modèle Gemini | `gemini-3.8-flash` |
| `ASSISTANT_FALLBACK_MODEL` | modèle de secours si le principal est saturé ou à court de quota (vide = aucun) | `gemini-3.7-flash` |
| `ASSISTANT_REASONING_EFFORT` | `low`, `medium` ou `high` | `low` |
| `ASSISTANT_HOST`, `ASSISTANT_PORT` | adresse et port d’écoute (aussi `--host`, `--port`) | `127.0.0.1`, `8000` |

## Interface : `front/index.html`

Le serveur sert la maquette Caisse d’Épargne (`front/index.html`, fichier autonome, voir `front/CLAUDE.md`) :
charte Caisse d’Épargne, personas fictifs (Léa, Karim, Hélène), backoffice, journal de démo, tous les réglages
d’accessibilité et le mode vocal.

- **Sélecteur Web | Mobile** dans la barre du haut : *Mobile* affiche la même page dans un cadre de téléphone de
  390 px. Les styles mobiles du site s’appliquent alors vraiment (en-tête compact, assistant en plein écran). Persona,
  Backoffice, Journal et Réinitialiser pilotent la page du téléphone. Le choix est mémorisé ; `?vue=mobile` l’impose.
- Ouverte en fichier local (`file://`), la maquette reste jouable entièrement en mode scripté.

## Parcours d’un message : du moins cher au plus cher

1. **Parcours guidés, dans le navigateur** (0 jeton) : intention d’action nette (code perdu, carte perdue ou volée,
   réclamation, simulation, conseil, ouverture de compte, conseiller). Le formulaire de simulation est calculé par
   `POST /api/simulate` sur la base fictive.
2. **Réponses pré-rédigées, sur le serveur** (0 jeton) : 74 questions simples (taux du Livret A, TAEG, RIB, plafond
   de carte, frais à l’étranger, PEL, PTZ, phishing…) dans `data/reponses_scriptees.json`. Les chiffres sont lus dans
   la base au moment de la réponse. Une question avec des montants, des durées ou une demande de prévision ou de
   comparaison n’est jamais servie ainsi.
3. **Modèle Gemini avec outils** (environ 2 000 à 3 000 jetons par appel, 2 ou 3 appels par question) :
   `search_faq` / `read_source` (FAQ), `simuler_credit`, `capacite_emprunt`, `prevoir_taux`, `simuler_epargne`,
   `catalogue` (base). La réponse est contrôlée par le serveur, puis affichée avec une **carte de résultat** et des
   sources étiquetées (*Constat* pour une page FAQ lue, *Hypothèse* pour la base fictive).

Les étapes réelles (recherche, lecture, calcul, attente de débit) s’affichent sous l’indicateur d’attente.

## Garanties tenues par le serveur, quel que soit le modèle

- Banque unique : Caisse d’Épargne, imposée par le serveur.
- `read_source` n’accepte qu’un `source_id` renvoyé par `search_faq` dans la conversation (ni URL, ni autre banque).
- Une réponse de fond doit reposer sur une page lue avec succès **ou** sur un résultat des outils de la base, et
  **chacun de ses nombres** doit figurer dans ces pages ou résultats (arrondis tolérés). Le modèle ne calcule rien
  lui-même ; une réponse non conforme lui est renvoyée, et après deux corrections un message honnête la remplace.
- Un appel d’outil écrit en texte par le modèle est reconnu d’après ses paramètres et exécuté normalement.
- Les liens affichés viennent des métadonnées du lecteur ; les URL écrites par le modèle sont retirées.
- Pages et résultats de la base sont transmis comme données balisées, jamais comme instructions.
- Un message contenant un code, un mot de passe, un identifiant ou un numéro de carte n’est pas envoyé (masqué dans
  le navigateur, refusé par le serveur).
- La clé reste côté serveur. Conversations en mémoire (30 minutes d’inactivité au plus), rien sur disque, aucun
  contenu de conversation au journal. Politique de sécurité stricte : seul le script de la page, identifié par son
  empreinte, peut s’exécuter ; cadre autorisé seulement depuis la même origine (vue mobile).

## Routes

| Route | Rôle |
|---|---|
| `GET /` | interface (`front/index.html`) |
| `POST /api/chat` | `{conversation_id, message, preferences}` → NDJSON : `start`, `status`…, `result` ou `error` |
| `POST /api/simulate` | `{produit, montant, duree_mois, age?, apport?, revenus_mensuels?, debut?}` → carte de résultat |
| `POST /api/feedback` | avis utile / pas utile (compté, contenu jamais journalisé) |
| `POST /api/reset` | efface une conversation |
| `GET /api/health` | état, modèle, mois de référence de la base, nombre de réponses pré-rédigées |

## Fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | serveur HTTP (bibliothèque standard), routes ci-dessus, CSP calculée sur la page |
| `agent.py` | conversation, boucle d’outils, contrôles des réponses, cartes de résultat |
| `scripted.py` | réponses pré-rédigées (`data/reponses_scriptees.json`) |
| `rag_tools.py` | recherche et lecture des fiches de la base de connaissances (`rag/`) |
| `llm.py` | appel à Gemini (point d’accès compatible OpenAI), modèle de secours, erreurs simples |
| `prompt.py` | consignes de l’assistant et définition des outils |
| `guard.py` | détection des secrets |
| `tests/` | tests automatisés (voir ci-dessous) |
| `scenarios.py` | scénarios de bout en bout avec le vrai modèle |
| `../finance/` | génération de la base fictive et moteur de calcul |

## Vérifications

```sh
.venv/bin/python -m unittest discover -s assistant/tests -t .                        # hors ligne, modèle simulé
ASSISTANT_LIVE_TESTS=1 .venv/bin/python -m unittest discover -s assistant/tests -t .  # + lecture réelle des pages
.venv/bin/python -m assistant.scenarios      # vrai modèle Gemini : ~40 000 jetons, quelques minutes
```

- **Hors ligne** : contrôles FAQ (lecture obligatoire, nombres, échecs, pages piégées, secrets, erreurs), base
  (formule de mensualité, TAEG, scénarios ordonnés, plafonds, règle des 35 %), outils de calcul dans l’agent (carte
  de résultat, chiffre inventé refusé, appel écrit en texte), réponses pré-rédigées (variables remplies, questions
  complexes laissées au modèle), routes, en-têtes de sécurité.

## Limites connues

- **Données fictives** : taux, tarifs, prévisions et grilles de `data/finance.db` sont inventés (ordres de grandeur
  plausibles). Les prévisions suivent des scénarios simples, pas un modèle économique.
- **Quota Gemini** : selon le palier de la clé ; une question chiffrée coûte environ 8 000 jetons. Si le modèle
  principal est saturé ou à court de quota, le modèle de secours répond. Les réponses pré-rédigées et les parcours
  guidés n’en consomment pas.
- **Langues** : parcours guidés et réponses pré-rédigées en français.
- **Backoffice** : historique de 7 jours fictif ; les conversations jouées en direct y apparaissent avec les vrais
  jetons renvoyés par le serveur (`meta.usage`).
- **Recherche FAQ** lexicale (Hit@1 66 %, Hit@5 86 % sur 44 questions) ; corpus FAQ nationale seulement.
- **Déploiement** : serveur de prototype en un seul processus, conversations en mémoire ; pas d’authentification.
- Pas de test automatisé du navigateur pour l’instant (l’ancien `tests/ui_check.py` visait l’interface retirée).
