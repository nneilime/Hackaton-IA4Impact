# Cahier de développement : frontend LPC Regulatory Watch

Ce document dit **quoi** construire dans `frontend/`. Le **comment** (composants, code, découpage fin) est laissé à celui qui code. Il regroupe les décisions prises par l'équipe et le fil « Présentation des réponses ».

## 0. Sources de vérité

| Sujet | Fichier | Règle |
|---|---|---|
| Écrans | `docs/wireframes.html` | **La référence visuelle et fonctionnelle.** Un gabarit par type de question, chaque élément relié au champ d'API qui l'alimente. À ouvrir dans un navigateur avant de commencer. |
| Contrat d'API | `openapi.proposed.yaml` (v0.2.1, OpenAPI 3.1) | Fait foi. Le front ne consomme que ce qui y est décrit. |
| Données de mock | `mocks/examples.yaml` | 19 réponses d'exemple fictives, une par type de question et par route, validées contre le contrat. Servies par Prism, réutilisées pour les tests et le mode démo hors ligne. |
| Ce que fait le back | `docs/cahier-backend.md` | Pour savoir ce que le back calcule, et donc ce que le front ne recalcule jamais. |
| Pourquoi chaque champ existe | `docs/openapi-changes.md` | Contexte. |
| Règles du projet | `CLAUDE.md` | Valables. La consigne « ne pas toucher `frontend/` » s'adresse aux autres ; ici, c'est le travail demandé. Si une ligne cite encore `schema/openapi.yaml` comme contrat, c'est `openapi.proposed.yaml` qui prévaut : `schema/openapi.yaml` est l'ancien contrat du starter, on ne code ni ne mocke dessus. |

## 1. Ce qu'on attend de l'application

### Le besoin

Lallemand Plant Care vend des microorganismes de biocontrôle dans plusieurs pays. Chaque pays publie ses homologations dans sa propre base, sa langue et son format. L'application permet de **poser une question réglementaire en langage naturel et de lire une réponse sourcée**, où chaque valeur renvoie à sa source officielle. C'est une aide à la décision : les Affaires réglementaires valident toujours.

Utilisateurs : Affaires réglementaires (vérifier, valider), R&D (chercher par souche, culture, cible), commerciaux et équipes terrain (savoir vite ce qui est autorisé où). Les premiers lisent le détail, les derniers s'arrêtent à la conclusion : la conclusion doit donc suffire, et le détail doit être à un clic.

**Le différenciant de l'équipe, c'est la présentation** : pour chaque type de question, la forme de réponse qui permet de décider. L'interface n'est pas un chat : c'est une page qui choisit un gabarit selon le type de question détecté.

### Une page, un cadre, un gabarit par question

Une seule page. Le cadre est toujours le même ; seul le bloc central change selon `intent` (voir « Anatomie d'une réponse » dans les wireframes).

| `intent` | Question type | Gabarit à afficher |
|---|---|---|
| `registration_lookup` | Dans quels pays X est-il homologué ? | Une ligne par pays (trouvé, à vérifier, pas trouvé, non couvert) |
| `use_comparison` | Comparer les usages de X entre deux pays | Tableau culture × cible aligné par code EPPO, une colonne par pays |
| `ingredient_search` | Quels produits avec la souche Y sur la tomate ? | Matrice produit × pays |
| `expiry_watch` | Qu'est-ce qui expire dans les 12 mois ? | Liste datée avec compte à rebours |
| `data_quality` | Quels champs sont incertains ? | File de travail priorisée |
| `sister_product` | Quels produits pourraient être sœurs de X ? | Cartes d'hypothèses |
| `source_lookup` | D'où vient chaque donnée ? | Liste de faits, chacun avec sa preuve |
| `other` | Hors périmètre | Message clair et questions suggérées |

### Les questions test du jury (ce que l'écran doit rendre impossible)

| Test | Question | Interdit, donc à rendre impossible à l'écran |
|---|---|---|
| T01 | Dans quels pays le produit pilote est-il homologué ? | Laisser croire « non homologué » parce qu'on n'a rien trouvé |
| T02 | Comparer les usages entre deux pays | Mélanger les valeurs de deux pays |
| T03 | Quels champs sont incertains ? | Cacher l'incertitude |
| T04 | Quels produits pourraient être des produits sœurs ? | Présenter une hypothèse comme un fait |
| T05 | Donne la source officielle de chaque donnée | Afficher une valeur sans preuve accessible |

Produits pilotes : LALSTOP CONTANS WG, LALSTOP G46 WG, LALGUARD M52 OD. Le piège : le même produit ou la même souche porte d'autres noms selon le pays (M52, F52, *M. anisopliae*). L'écran doit montrer sous quel nom chaque résultat a été trouvé.

### Ce que le jury verra

La démo est le seul endroit où le jury voit la traçabilité (20 pts), la normalisation EPPO (15 pts), l'IA ancrée (15 pts) et l'expérience (5 pts). Le scénario de démo enchaîne T01 → T02 → T03 → T04 → T05 **sans taper**, en cliquant sur les questions suggérées.

## 2. Règles d'affichage non négociables

1. **La conclusion d'abord, avec son incertitude.** La phrase `answer` et les compteurs (validés, à vérifier, pas trouvés, non couverts) sont en haut.
2. **Toujours montrer ce qu'on a cherché** : sources interrogées, date de collecte, noms cherchés (alias compris).
3. **« Pas trouvé » ne ressemble jamais à « non homologué ».** Gris hachuré et point d'interrogation. Le rouge est réservé à un statut retiré ou expiré **donné par la source**. Le front n'écrit jamais « non homologué ».
4. **Chaque valeur réglementaire ouvre sa preuve** (statut, dose, culture, cible, date…), dans un panneau unique, le même partout.
5. **L'original à côté du normalisé** : statut d'origine en gras avec le normalisé à côté, culture et cible d'origine sous le nom normalisé, unité d'origine sous l'unité normalisée.
6. **Une colonne par pays, jamais fusionnée.** Aucune moyenne, aucune conversion, aucun regroupement de valeurs fait par le front.
7. **Une hypothèse se lit comme une hypothèse** : trait pointillé, badge « à confirmer », score de confiance, statut de revue.
8. **Confiance IA et validation humaine sont deux choses différentes**, affichées séparément. Une confiance de 0,90 n'est pas un « validé ».
9. **Données fictives et extraits figés sont signalés** par un badge sur chaque valeur concernée.
10. **Le `disclaimer` et les `warnings` sont toujours visibles**, jamais repliés par défaut.
11. **Le front affiche, il ne décide pas.** Couverture, états des cases, priorités, différences entre pays, statuts : tout vient du back. Le front ne déduit aucune donnée réglementaire ; il peut seulement compter et trier ce qu'il reçoit pour l'afficher.

### Légende des états (identique partout)

| État | Rendu | Champ |
|---|---|---|
| Validé | ✓, vert | `validationStatus = validated` |
| À vérifier | !, orange | `to_verify` |
| Extrait automatiquement | neutre, discret | `automatically_extracted` |
| Pas trouvé | ?, gris hachuré | `coverage.outcome = not_found` |
| Source indisponible | gris, icône dédiée | `source_unavailable` |
| Non couvert | gris clair, liste à part | `not_covered` |
| Retiré / expiré (selon la source) | rouge | `statusNormalized = withdrawn / expired` |
| Hypothèse à confirmer | pointillé | `reviewStatus` différent de `validated` |

L'état ne repose jamais sur la couleur seule : toujours une icône et un libellé.

## 3. Ce qui existe déjà dans `frontend/`

- Angular 22 (composants standalone, signals), Tailwind 4, Spartan NG (composants « helm » dans `src/app/ui`, alias `@spartan-ng/helm/*`, à ajouter avec le CLI Spartan), Vitest, Prettier, pnpm.
- `src/environments/environment.ts` est **généré** par `scripts/generate-env.mjs` à partir de `FRONT_API_URL` du `.env` racine : ne pas l'éditer.
- En Docker, nginx (`docker/default.conf.template`) sert l'app et transmet `/api/...` au back, préfixe compris : pas de CORS.
- L'app est encore la page de démarrage (titre + bouton) et le routeur est vide.
- `src/styles.css` importe deux fois Tailwind et le preset Spartan : à dédoublonner.

## 4. Priorité 1 : une interface qui tourne sans API (Prism)

Le back n'existe pas encore. Avant tout le reste, l'app doit tourner entièrement sur un mock de l'API, puis basculer sur le vrai back **sans changer une ligne de code applicatif**.

**À mettre en place**

1. `@stoplight/prism-cli` (version 5, testée en 5.14.2 sur notre contrat) en dépendance de dev du front.
2. Trois scripts dans `package.json` :

| Script | Rôle |
|---|---|
| `mock` | Lance Prism seul sur `../openapi.proposed.yaml`, port 4010. |
| `start:mock` | **La commande de tous les jours tant que le back n'existe pas** : lance Prism et l'app en mode mock, en une seule commande. |
| `start` | L'app branchée sur le back local (port 3000), comme aujourd'hui. |

3. Un proxy de dev avec deux cibles :
   - vers Prism : **retirer le préfixe `/api`** (Prism sert `/ask`, pas `/api/ask`) et ajouter un en-tête `X-API-Key` quelconque, sinon Prism répond 401 ;
   - vers le back : garder `/api` et ajouter la clé lue dans le `.env`.
4. Un indicateur « mode mock » dans `environment.ts` (fichier généré : ajouter une variable `FRONT_MOCK` lue par `scripts/generate-env.mjs`), et un bandeau discret « Mock : données fictives » visible tant qu'il est actif.
5. Le choix de l'exemple, en mode mock uniquement : chaque appel porte l'en-tête `Prefer: example=<nom>`.
   - Pour `/ask`, le nom est l'`intent` de la question cliquée : les exemples de l'accueil et les questions suggérées portent tous leur `intent`. Pour une question tapée librement, une correspondance par mots-clés réservée au mock (comparer → `use_comparison`, incertain ou manquant → `data_quality`, sœur → `sister_product`, source → `source_lookup`, expire → `expiry_watch`, souche, culture, « contre » ou « quel(s) produit(s) » → `ingredient_search`), sinon `registration_lookup`. Un choix dans `clarificationOptions` relance avec `registration_lookup`.
   - Pour `GET /products`, `ingredient_search` quand un filtre substance, culture ou cible est présent, sinon l'exemple par défaut.
   - Hors mode mock, l'en-tête n'est jamais envoyé.

**Exemples disponibles** (`mocks/examples.yaml`)

| Route | Noms d'exemple (le premier est servi par défaut) |
|---|---|
| `POST /ask` | `registration_lookup`, `use_comparison`, `data_quality`, `sister_product`, `source_lookup`, `ingredient_search`, `expiry_watch`, `needs_clarification`, `other` |
| `GET /products` | `name_search`, `ingredient_search` |
| `GET /products/{id}/registrations`, `/products/{id}/sisters`, `/compare` (JSON et CSV), `/issues`, `/expirations`, `/sources`, `POST /reviews` | un exemple chacun |

Chaque réponse `/ask` suggère la question suivante de la démo (T01 → T02 → T03 → T04 → T05) : la chaîne se déroule en cliquant.

**Ce que le mock fait et ne fait pas**
- Il ne filtre rien : toutes les routes renvoient les données de LALGUARD M52 OD, quel que soit l'id, le pays ou le filtre. La réponse de `/ask` ne dépend pas du texte de la question, seulement de l'en-tête.
- Il valide les requêtes : 401 sans clé, 422 si un paramètre obligatoire manque ou si `question` fait moins de 3 caractères.
- `Prefer: code=<statut>` force un code d'erreur décrit dans le contrat (401, 404 sur un produit) : pratique pour développer les états d'erreur.

**Fini quand** `pnpm start:mock` ouvre l'app sur `http://localhost:4200` et que T01 → T05 se déroule en cliquant, sans back.

## 5. Architecture

### Principes

- **Contrat d'abord.** Les types TypeScript sont **générés** depuis `openapi.proposed.yaml` (outil au choix), jamais écrits à la main, et régénérés quand le contrat change.
- **Développer sans attendre le back** : le mock Prism (section 4) pendant le développement, puis le vrai back. Le passage de l'un à l'autre se fait par le script lancé, sans toucher au code.
- **Le gabarit est choisi par `intent`, rien d'autre.** Un composant par gabarit ; un intent inconnu tombe sur le gabarit `other`.
- **Mêmes types partout** : le bloc `comparison` d'une réponse `/ask` a la même forme que la réponse de `GET /compare`. Un gabarit sait donc s'afficher qu'il soit nourri par `/ask` ou par l'appel REST.
- **Pas d'appel à un LLM depuis le front**, pas de clé, pas de logique réglementaire.

### Découpage

| Zone | Responsabilité |
|---|---|
| Client d'API | Un service par groupe de routes du contrat (`ask`, `products`, `compare`, `issues`, `sisters`, `expirations`, `sources`, `reviews`), typé par les types générés, base d'URL lue dans `environment.apiUrl`. |
| État de la page | Question en cours, réponse courante, chargement, erreur, langue, preuve ouverte dans le panneau, fraîcheur des sources. Signals. |
| Coquille de réponse | Le cadre commun : en-tête, barre de question, « ce que l'IA a compris », conclusion et compteurs, périmètre de recherche, emplacement du gabarit, avertissements, questions suggérées, disclaimer. |
| Gabarits | Un par intent : liste de pays, tableau comparatif, matrice produits, liste d'échéances, file de qualité, cartes sœurs, liste de faits, message hors périmètre ou demande de précision. |
| Composants partagés | Badge d'état (un seul, tous les états de la légende), valeur cliquable vers sa preuve, panneau de preuve, ligne de couverture pays, indicateur de confiance, badges « fictif » et « extrait figé », explication d'une case vide. |
| Textes d'interface | Dictionnaire FR / EN simple, bascule à chaud. Les valeurs venues des sources ne sont jamais traduites. |

### Flux

1. L'utilisateur pose une question (ou clique un exemple) → `POST /ask` avec `question` et `language`.
2. La réponse arrive → la coquille s'affiche, le gabarit est choisi par `intent`.
3. « Ce que l'IA a compris » (`parameters`, `intent`) est affiché et **corrigeable** : changer le produit ou les pays renvoie la même question à `/ask` avec `productId` et `countries` renseignés.
4. Les interactions qui n'ont pas besoin de l'IA appellent directement la route REST équivalente : changer un filtre culture ou cible du comparatif (`GET /compare`), filtrer la file de qualité par type (`GET /issues`), télécharger le CSV (`GET /compare?format=csv`).
5. Les questions suggérées (`suggestedQuestions`) relancent `/ask` : c'est ce qui déroule la démo.
6. Au démarrage, `GET /sources` alimente la fraîcheur des sources dans l'en-tête.

### URL

Une seule page, mais l'état est dans l'URL (question, langue, et paramètres corrigés s'il y en a). Un lien copié, ou le lien « Ouvrir le détail dans l'application » renvoyé par Copilot dans Teams, rouvre la même réponse. Précédent et suivant du navigateur fonctionnent.

### Clé d'API

Le front ne connaît **jamais** la clé : tout ce qui est `FRONT_*` finit dans le JavaScript public. C'est nginx qui ajoute l'en-tête `X-API-Key` sur les appels `/api/` transmis au back (une ligne à ajouter dans `docker/default.conf.template` ; le conteneur du front reçoit déjà tout le `.env`, donc `API_KEY`), et le proxy de dev qui le fait en local.

### Proxy de dev

`ng serve` n'a pas de proxy aujourd'hui : `/api` ne mène nulle part en dev. Les deux cibles (Prism ou back local) sont décrites en section 4.

## 6. Les écrans

Tout est dessiné dans `docs/wireframes.html`. Ce qui suit dit ce que chaque partie doit contenir et quels champs l'alimentent.

### Le cadre commun (anatomie, numéros des wireframes)

| # | Élément | Contenu | Champs |
|---|---|---|---|
| 1 | En-tête | Nom de l'app, fraîcheur de chaque source (orange si plus de 24 h ou extrait figé), bascule FR / EN | `GET /sources` : `lastCollectedAt`, `isFrozenExtract`, `availability` |
| 2 | Barre de question | Un seul champ ; vide, il propose les questions test en exemples cliquables | `POST /ask` |
| 3 | Ce que l'IA a compris | Produit, pays, culture, cible, type de question, en puces modifiables | `parameters`, `intent` |
| 4 | Conclusion | Phrase de l'IA, puis compteurs par état (simple décompte des `coverage[].outcome` et des statuts de validation reçus) | `answer`, `answerStatus`, `facts`, `coverage` |
| 5 | Périmètre de recherche | Noms et alias cherchés, sources interrogées | `coverage[].searchedTerms`, `coverage[].sourceIds` |
| 6 | Gabarit | Le bloc propre à l'intent | voir ci-dessous |
| 7 | Avertissements | En clair, jamais repliés | `warnings` |
| 8 | Suite | Questions suggérées en boutons, export CSV quand il a du sens | `suggestedQuestions` |
| – | Pied | Disclaimer, toujours | `disclaimer` |

### Les gabarits

**`registration_lookup` (T01).** Une ligne par pays cible, triées : validé, à vérifier, pas trouvé, source indisponible ; les pays non couverts sont regroupés sur une ligne à part. Chaque ligne trouvée montre le nom du produit dans ce pays, l'autorité, le numéro, le statut d'origine et le normalisé, la source avec lien direct et date. Si le résultat a été trouvé via un alias, la ligne le dit (« trouvé via l'alias … », avec son statut de revue et sa confiance). Une ligne « pas trouvé » dit où, quand et sous combien de noms on a cherché, et rappelle que ça ne prouve pas l'absence d'homologation. Champs : `registrations`, `coverage`, `matchedVia`, `statusOriginal`, `statusNormalized`.

**`use_comparison` (T02).** Tableau : une ligne par culture × cible (nom normalisé, code EPPO, nom d'origine dessous), une colonne par pays avec la source et sa date en en-tête. Une case présente montre la dose avec son unité normalisée, l'unité d'origine dessous, et les conditions (méthode, nombre max d'applications, DAR, restrictions). Une ligne où les pays diffèrent est marquée. Une case vide dit pourquoi elle est vide, et les trois cas se distinguent : homologation pas trouvée, pays non couvert, usage absent des données extraites. Filtres culture et cible ; bouton d'export CSV. Le statut EPPO (`to_verify`, `unmapped`) est visible sur la culture et la cible. Champs : `comparison.rows`, `cells[].state`, `differsAcrossCountries`, `uses`, `cropMappingStatus`, `targetMappingStatus`.

**`data_quality` (T03).** Une file de travail, pas un paragraphe. En haut, les compteurs par type de problème (`countsByType` de `GET /issues`, ou décompte des `issues` reçus via `/ask`), qui servent aussi de filtres. Puis un tableau trié par priorité : priorité, pays, champ, problème, confiance IA, statut de validation, lien « Vérifier » qui ouvre la preuve. Confiance et validation dans deux colonnes distinctes. Champs : `issues`, `countsByType`, `priority`, `confidence`, `validationStatus`.

**`sister_product` (T04).** Une carte par candidat : produit de référence et candidat, type de relation, pays ou marché, confiance, statut de revue, justification citée telle quelle, preuves officielles s'il y en a. Trait pointillé et badge « hypothèse à confirmer » tant que ce n'est pas validé ; trait plein seulement si validé, et le type de relation reste affiché (une formulation liée n'est pas un produit identique). La phrase de conclusion ne parle jamais d'équivalence. Boutons « Confirmer » et « Rejeter » uniquement si `POST /reviews` existe côté back. Champs : `sisterCandidates`, `relationshipType`, `confidenceScore`, `reviewStatus`, `evidenceSummary`, `sharedTraits`.

**`source_lookup` (T05) et le panneau de preuve.** Le panneau de preuve est un composant unique qui s'ouvre au clic sur n'importe quelle valeur, dans n'importe quel gabarit. Il montre : la valeur normalisée et le texte d'origine, la source (nom et lien direct vers la fiche officielle), la date de collecte, le statut de validation, la confiance IA (avec la mention qu'elle n'est pas une validation), le nom par lequel la ligne a été trouvée, l'extrait cité, les badges « fictif » ou « extrait figé ». Quand la question elle-même porte sur les sources, le gabarit liste les faits (`facts`), chacun avec sa ou ses preuves (`evidenceIds` → `evidence`).

**`ingredient_search`.** Matrice : une ligne par produit (nom, substance active avec l'ancien nom résolu, badge LPC ou concurrent, badge « sœur ? » si candidat), une colonne par pays avec l'état et la cible trouvée. Champs : `products[].product`, `products[].registrations`, `isLpcProduct`, `aliases`.

**`expiry_watch`.** Liste triée par date d'échéance : date, jours restants avec couleur selon l'urgence (moins de 3 mois, moins de 9 mois, au-delà), produit, pays, source. Champs : `expirations`, `daysUntilExpiration`.

**`other`, `no_data`, `needs_clarification`.** Hors périmètre : message clair, pas de réponse inventée, questions suggérées. Aucune donnée : dire qu'on n'a rien trouvé **dans nos sources**, avec le périmètre de recherche. Question ambiguë : afficher `clarificationOptions` en boutons ; un clic relance la question avec l'option choisie.

## 7. États de la page

Jamais d'écran blanc.

| État | Ce que voit l'utilisateur |
|---|---|
| Accueil | La barre de question et les questions test en exemples |
| Chargement | Le cadre avec la question, un squelette du gabarit, et les sources en cours d'interrogation |
| Réponse | Le cadre complet |
| Précision demandée | Les options en boutons |
| Erreur réseau ou 5xx | Message clair et bouton « Réessayer », la question reste dans la barre |
| 401 | « Accès à l'API refusé », sans détail technique |
| 404 sur un produit | « Produit inconnu de notre catalogue », jamais formulé comme une absence d'homologation |

## 8. Accessibilité et format

- Tout est utilisable au clavier ; le panneau de preuve garde le focus et se ferme avec Échap.
- Contraste suffisant ; aucun état transmis par la seule couleur.
- Tableaux avec en-têtes de lignes et de colonnes.
- Pensé pour un écran de bureau, lisible sur tablette, et dans un onglet Teams (largeur réduite) : le tableau comparatif défile horizontalement plutôt que de se tasser.

## 9. Données pour développer et pour la démo

- Les réponses d'exemple sont dans `mocks/examples.yaml`, déjà validées contre le contrat : ne pas en recréer ailleurs. Les tests de gabarits les utilisent comme jeux de données.
- Si un gabarit a besoin d'un cas absent (par exemple une source indisponible), l'ajouter dans ce fichier en restant conforme au contrat, et prévenir l'équipe.
- Mode démo hors ligne, en filet de sécurité pour le pitch : rejouer ces mêmes exemples si le back tombe, avec un bandeau visible « démo hors ligne, données fictives ». Activé par configuration, jamais par défaut.

## 10. Jalons

| Jalon | Contenu | Quand |
|---|---|---|
| 0 | Mock Prism (section 4) : dépendance, scripts, proxy, mode mock, bandeau | Tout de suite, avant le reste |
| 1 | Types générés, client d'API, cadre commun, gabarit `registration_lookup`, badge d'état, panneau de preuve | Avant le freeze, obligatoire |
| 2 | Gabarits comparatif, qualité, sœurs, liste de faits ; questions suggérées ; FR / EN ; fraîcheur des sources ; états d'erreur | Avant le freeze, obligatoire |
| 3 | Matrice produits, échéances, export CSV, état dans l'URL, branchement sur le vrai back via nginx, mode démo hors ligne | Si le temps le permet |
| 4 | Boutons de revue (si le back a `/reviews`), onglet Teams | Bonus |

## 11. Définition de « terminé »

- [ ] `pnpm start:mock` lance Prism et l'app ; toute la démo tourne sans back.
- [ ] Le scénario T01 → T02 → T03 → T04 → T05 se déroule en cliquant uniquement sur les questions suggérées, sur LALGUARD M52 OD, en mock puis sur le vrai back.
- [ ] Chaque gabarit s'affiche correctement à partir de sa réponse d'exemple de `mocks/examples.yaml` (tests).
- [ ] Un pays `not_found` n'est jamais rendu en rouge ni avec le mot « non homologué » (test dédié).
- [ ] Toute valeur réglementaire affichée ouvre le panneau de preuve, avec lien source, date et statut.
- [ ] Confiance IA et statut de validation apparaissent séparément partout où les deux existent.
- [ ] Le disclaimer est présent sur chaque réponse ; les avertissements ne sont jamais masqués.
- [ ] FR / EN bascule les textes d'interface sans traduire les valeurs d'origine.
- [ ] `docker compose --profile backend up -d --build` sert l'app sur le port 8080 et elle parle au vrai back, sans clé visible dans le navigateur.
- [ ] `frontend/README.md` explique le lancement en dev (mock ou back) et en Docker.

## 12. À ne pas faire

- Recalculer côté front une couverture, un état de case, une priorité, une différence entre pays ou un statut.
- Convertir, moyenner ou fusionner des valeurs.
- Écrire « non homologué », ou utiliser le rouge pour un `not_found`.
- Traduire les textes d'origine des sources.
- Masquer ou replier par défaut les avertissements, le disclaimer ou les badges d'incertitude.
- Mettre une clé ou un secret dans une variable `FRONT_*` ou dans le code.
- Appeler un LLM depuis le navigateur.
- Éditer `environment.ts` à la main, modifier le back, la base ou les fichiers du starter kit.

## 13. Décisions prises par défaut (à confirmer par l'équipe)

- Le champ s'appelle `intent`, pas `answerType`.
- La liste des pays cibles vient de `coverage` renvoyé par le back, jamais codée en dur dans le front.
- La clé d'API est ajoutée par nginx (`docker/default.conf.template`), jamais par le code Angular.
- L'export utilise `GET /compare?format=csv` (pas de route `/export`).
