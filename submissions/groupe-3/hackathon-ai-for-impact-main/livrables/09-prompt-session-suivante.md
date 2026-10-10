# Prompt pour la session suivante

À coller tel quel dans une nouvelle session Claude Code ouverte sur ce dépôt.

```text
# RÔLE
Tu es développeur full stack senior (FastAPI, React) et expert en prompting et en LLM (RAG, garde-fous).
Tu vas vite et proprement : rendu devant un jury de hackathon aujourd'hui à 15h30. Démo viable avant tout.

# REPRENDRE LE FIL (fais-le en premier, sans rien demander)
1. Dépôt github.com/Verigyk/hackathon-ai-for-impact. Travaille sur la branche Mohamed-Front
   (git checkout Mohamed-Front && git pull). C'est la seule branche qui contient l'application.
2. Récupère les données de la branche main SANS les indexer ni fusionner main :
     git fetch origin
     git restore --source=origin/main --worktree -- data database_embedding database_reduit_embedding reseau_urbain_gare_coordonnees garde-fou
   Ces fichiers sont lourds (jusqu'à 80 Mo) : ne les commite JAMAIS sur Mohamed-Front
   (data/ est déjà dans .gitignore ; ajoute les autres dossiers au .gitignore avant tout commit).
3. Lis dans cet ordre : API_CONTRACT.md (surtout la section « Scène (v3) »), ARCHITECTURE.md,
   livrables/08-audit-phase1.md, frontend/DESIGN.md, garde-fou/README.md, garde-fou/backend/GARDE_FOUS_LLM.md,
   backend/README.md.
4. Lance l'app :
     cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -q
     .venv/bin/uvicorn app.main:app --reload --port 8000
     cd frontend && npm install && npm run dev        (http://localhost:5173)
   Pour l'IA : export ANTHROPIC_API_KEY=… avant de lancer le back (sinon mode démo scripté).

# OÙ EN EST LE PROJET
« Tchouette », chouette-locomotive, copilote qui transforme le projet pédagogique d'un enseignant en sortie
scolaire en train liO (Occitanie) : pertinente, faisable, rassurante, pré-réservable (défi SNCF Voyageurs,
Hackathon For IA, 9 et 10 octobre 2026).
- Front (frontend/) : React 19, Vite, Tailwind 4, daisyUI 5, thème « lio » (rouge #C8102E, bleu nuit #0B2341,
  or #FFCD00, Montserrat). La route / est la SCÈNE « Tchouette est l'interface » (src/scene/) :
  - une réplique à la fois, 2 à 4 grandes cartes-réponses, barre « Écrire ou parler » avec dictée vocale ;
  - puces de critères, carnet de voyage, badges de source sous chaque réplique ;
  - panneaux d'étape (src/scene/panneaux/) : destination, trajet, vote de classe par QR code commenté
    par Tchouette, pré-réservation.
  La mascotte (src/mascot/) a 9 humeurs SVG (dont pointe, loupe, celebre) et glisse sur un rail
  (RailTchouette). L'ancien site reste sur /classique.
- Back (backend/) : FastAPI + SQLite.
  - POST /api/scene est une machine à états (services/scene.py, textes dans scene_textes.py,
    crochets LLM dans scene_llm.py DÉJÀ branchés sur claude-sonnet-5-5 en effort bas : sorties Pydantic
    ComprehensionScene (23 intentions + champs de la demande) et Reformulation, au plus 2 appels par tour,
    0 sur un clic, repli démo sur toute erreur, bilan par tour dans le logger lio.llm ; 25 tests dans
    tests/test_scene_llm.py). Pendant un tour de scène, les appels Opus de recommander/expliquer sont
    coupés (quota de 2) : la scène classe avec ses règles. Jamais testé avec une vraie clé : c'est la
    première chose à vérifier (latence sous 8 s, qualité, cache, option fallbacks acceptée).
  - Règles R1 à R10, indice de confiance (services/confiance.py), pré-réservation, sondages.
  - 89 lieux DATAtourisme importés (etl/import_datatourisme.py, ids « dt- »).
  - Données de DÉMONSTRATION pour les trains (etl/seed_demo.py, reseau_demo.py) tant que les vraies
    ne sont pas chargées. 139 tests verts.
- Le scénario de démo : « Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves
  et 4 accompagnateurs. Sortie à la journée le 12 novembre, départ le matin et retour avant 19h. Nous partons
  du collège de Foix. » Une phrase → Saint-Sernin → trajet de 9h00 → vote → pré-réservation LIO-2026-000001.

# LES DONNÉES À EXPLOITER (inspecte d'abord colonnes et volumes de chaque fichier)
- data/Data_Hackathon.csv (séparateur « ; ») : indicateurs mensuels réels par train (régularité, suppressions,
  respect de l'emport, fréquentation, minutes perdues) → indice de confiance.
- data/Détail desserte (1).xlsx (30 Mo) : arrêts et horaires réels de février à juin 2026. Il faut openpyxl
  (à ajouter à requirements.txt) ou visualisation/scripts/xlsx_to_csv.py.
- data/annuaire_etablissement.xlsx : établissements scolaires. Sert à trouver « collège de Foix » → coordonnées
  → gare la plus proche, sans dépendre d'une API en ligne.
- reseau_urbain_gare_coordonnees/ : GTFS des cars liO (stops.txt, routes.txt, trips.txt, stop_times.txt ;
  shapes.txt fait 80 Mo, ne le charge pas en entier). Sert aux coordonnées des arrêts et au critère
  « accès gare → site par réseau urbain » (R3).
- database_embedding/ :
  - data/datatourisme-reg-occ-clean.csv : catégories en français, descriptions complétées, colonne Mots_cles ;
  - data/web_cache.json : descriptions trouvées sur le web ;
  - embed_pois.py : embeddings locaux sentence-transformers/static-similarity-mrl-multilingual-v1, rapides
    sur CPU, similarité cosinus ;
  - embed_pois_jina.py : variante par API Jina.
  Les fichiers d'embeddings (.npy) ne sont PAS sur main : régénère-les.
- database_reduit_embedding/data/top-des-sites-touristiques-2021-enrichi.json : 58 sites d'Occitanie
  (fréquentation, mots-clés, adresse, coordonnées). Signal de popularité et « coup de cœur ».
- garde-fou/ : paquet de garde-fous LLM (prompts.py, llm_schemas.py, garde_fous.py, llm.py, services
  modifiés, tests adverses). Il a été écrit sur le commit 8b6094b, AVANT la scène : compare fichier par
  fichier avec le code actuel et fusionne sans perdre scene.py ni les correctifs de l'audit.
- ABSENT : la liste officielle des trains ouverts aux groupes, et les données sur les cours (programmes
  scolaires). Garde l'hypothèse actuelle pour R1 (signalée dans /api/sante et dans un badge) et l'adéquation
  pédagogique par mots-clés.

# OBJECTIFS (dans cet ordre de priorité)
1. VRAIES DONNÉES : etl/build_db.py charge desserte, indicateurs, gares (desserte + GTFS + annuaire) et
   DATAtourisme nettoyé dans la même base SQLite. /api/sante répond donnees: "sncf" ; les badges de
   Tchouette passent de « Données de démo » à « SNCF 2026 ». Le mode démo reste le repli. Recalibre les
   barèmes de confiance.py sur les vraies distributions (régularité médiane autour de 86 %, suppressions
   autour de 6,6 %) pour que tout ne passe pas en orange, et signale ce changement de logique métier.
   Le scénario de Foix doit toujours marcher.
2. ULTRA IMPORTANT, LA CARTE : à chaque sélection de destination, une carte est TOUJOURS affichée.
   - Marqueurs : gare de départ, destination présentée (mise en avant), autres candidates numérotées,
     gare d'arrivée, trait de marche gare → site avec ses minutes.
   - Elle suit « Une autre idée », s'affiche aussi à l'étape trajet, et reste lisible à 375 px.
   - Technique : Leaflet + OpenStreetMap (le repo a déjà visualisation/carte en Leaflet) ; clés de tuiles
     interdites. Prévois un fond de repli si le réseau tombe.
   - Contrat : ajoute à ReponseScene un champ `carte` (centre, zoom, points typés avec lat, lon, libellé,
     actif ; traces). Mets à jour API_CONTRACT.md, schemas.py et src/api/types.ts.
3. RAG : Tchouette cherche dans TOUTE la donnée, pas seulement dans 24 sites.
   - Index : DATAtourisme nettoyé + catalogue fait main + top 58, embeddings locaux calculés hors ligne dans
     data/ (non commités), chargés au démarrage.
   - Recherche hybride à chaque demande : similarité sémantique sur le projet pédagogique, puis filtres durs
     (gare liO à distance de marche, trains groupes faisables à la date demandée, niveau, thème),
     puis classement par le moteur Python.
   - Le LLM ne fait que reformuler et justifier à partir des documents retrouvés, et cite le passage
     utilisé (badge « Fiche DATAtourisme »). Le catalogue fait main reste prioritaire à pertinence égale
     (DATAtourisme est presque vide sur Toulouse).
4. LLM FONCTIONNEL AVEC GARDE-FOUS : pars de scene_llm.py (déjà en place) et intègre-y en l'améliorant
   garde-fou/backend/app/garde_fous.py, sans doublon entre les deux.
   - Injection de prompt : message traité comme une donnée, jamais comme une instruction.
   - Sorties : schéma strict, toute valeur extraite prouvée dans le message.
   - Faits protégés : aucun horaire, nombre, place, date ou lieu absent des faits ou des documents
     retrouvés ; identifiants de sites limités aux candidats évalués ; jamais « réservé » ni « confirmé »
     avant la vraie confirmation ; refus et réponses tronquées rejetés ; aucune donnée personnelle
     envoyée au modèle.
   - Repli déterministe à chaque échec. Journal sans contenu brut.
   - Modèle claude-sonnet-5-5 en effort bas, au plus 2 appels par message libre, aucun appel sur un clic.
   - Tests adverses sans clé ni réseau (garde-fou/backend/tests).
5. CONVERSATION GUIDÉE ET PLUS RICHE EN TEXTE :
   - Tchouette dit toujours où on en est et ce qu'on fait ensuite, récapitule quand c'est utile, propose
     des suggestions claires, et ramène gentiment au parcours en cas de hors-sujet ou de plaisanterie.
   - Elle ne doit plus paraître limitée : pour présenter une destination ou expliquer un choix, elle peut
     écrire 2 à 3 phrases vivantes tirées des descriptions retrouvées par le RAG (ce qu'on y voit, pourquoi
     c'est utile pour le programme, une anecdote). La limite de 25 mots reste pour les répliques de
     navigation.
   - Tous les faits restent protégés par les garde-fous.

# RÈGLES DE LA FICHE DE CADRAGE (dans chaque texte et chaque calcul)
- Uniquement des trains liO ouverts aux groupes.
- 50 voyageurs maximum par train, options des autres groupes comprises.
- Gare → site : 20 min à pied pour un groupe, ou réseau urbain.
- Statuts PROPOSITION → OPTION → PRÉ-RÉSERVATION → CONFIRMATION.
- Aucune disponibilité inventée, aucune réservation présentée comme confirmée.
- Tchouette sait dire « pas assez fiable, voici pourquoi, voici une alternative ».
- Le retour d'expérience nourrit l'indice de confiance.
- Charte liO : toujours écrire « liO », ne pas redessiner le logo officiel, un statut = couleur + icône + texte.
- Vouvoiement avec l'enseignant, tutoiement sur la page de vote des élèves.

# MÉTHODE
1. Après la mise en route, donne un plan de 10 lignes au plus, avec horaires, puis attends mon OK.
2. Implémente par lots : données réelles, puis carte, puis RAG, puis garde-fous et LLM, puis conversation.
   Si des sous-agents travaillent en parallèle, donne-leur des fichiers séparés.
3. Après chaque lot :
   - pytest et npx tsc -p tsconfig.app.json --noEmit ;
   - le scénario de Foix dans le navigateur à 1440 et 375 px ;
   - un commit sur Mohamed-Front, sans aucun fichier de données ;
   - un résumé de 5 lignes pour moi.
4. Signale toute modification de logique métier (règles, barèmes, indice) avec fichier:ligne.
5. Garde 30 minutes avant 15h30 pour : base remise à neuf, répétition au clic puis à la voix, push.

# CRITÈRES DE RÉUSSITE
- Le jury comprend en 10 secondes : « une chouette-train aide les profs à organiser leur sortie en train liO ».
- Chaque destination proposée apparaît sur la carte, avec la donnée qui la justifie (SNCF, DATAtourisme).
- Tchouette répond avec des textes riches mais justes : aucun chiffre ni lieu inventé, même face à une
  tentative de manipulation.
- Le parcours se fait de bout en bout à la voix ou au clic, et le vote de classe reste animé par Tchouette.
```
