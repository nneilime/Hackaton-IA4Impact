# Prompt de reprise (v2, MVP, économe en tokens)

À coller tel quel dans une session Claude Code ouverte sur ce dépôt.
Clé LLM : jamais dans un fichier ni un commit, uniquement `export GROQ_API_KEY=…` (ou variable d'environnement cloud).

```text
# RÔLE
Dev full stack senior (FastAPI, React) + expert LLM. Rendu jury aujourd'hui 15h30 (Paris) : un MVP démontrable
vaut mieux que du complet. Réponds court, sans récapitulatif de ce que tu viens de faire.

# ÉCONOMIE DE TOKENS (règles dures)
- Ne relis pas tout : lis seulement API_CONTRACT.md (section « Scène (v3) ») et livrables/10-charte-lio-train.md ;
  le reste par grep ciblé. Jamais de cat sur un fichier de plus de 150 lignes : utilise offset/limit.
- Lance les tests en mode silencieux (pytest -q -x | tail -5, npx tsc … | head -20).
- Pas de capture d'écran ni de navigateur sauf pour le scénario final ; un seul passage à 375 px et un à 1440 px.
- Pas d'explication longue : 1 commit par lot, résumé de 3 lignes.
- Données lourdes : GTFS stop_times/shapes lus en flux et filtrés, jamais chargés en entier.
- Sous-agents seulement pour des lots indépendants et sur des fichiers séparés.

# MISE EN ROUTE (silencieuse)
Branche mohamed-front-7a7m3h (ou Mohamed-Front). Données : git restore --source=origin/main --worktree --
data database_embedding database_reduit_embedding reseau_urbain_gare_coordonnees garde-fou (ignorés par git, ne
JAMAIS les commiter). Backend : cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
openpyxl. Front : cd frontend && npm install. 139 tests backend verts au départ.

# LLM : GROQ (remplace Anthropic)
- API compatible OpenAI : POST https://api.groq.com/openai/v1/chat/completions, Authorization: Bearer $GROQ_API_KEY,
  modèle configurable par LLM_MODEL (défaut llama-3.3-70b-versatile), response_format json_object, temperature 0.2.
- Adapte scene_llm.py derrière une interface unique (un client, deux fonctions : comprendre, reformuler) ; garde les
  schémas Pydantic, le repli démo sur toute erreur/timeout (6 s), au plus 2 appels par message libre, 0 sur un clic.
- Vérifie que la clé répond (1 appel de test) puis mesure la latence. Sans clé : mode démo scripté.
- Garde-fous MVP (reprendre garde-fou/backend/app/garde_fous.py, seulement ce qui sert) : message traité comme donnée,
  JSON strict, identifiants limités aux candidats, aucun chiffre/horaire/lieu absent des faits, jamais « réservé »
  ou « confirmé » avant la vraie confirmation, aucune donnée personnelle envoyée, journal sans contenu brut.

# PRIORITÉS (dans cet ordre ; coupe ce qui ne tient pas, signale-le)
1. VRAIES DONNÉES (data/) : build_db.py charge Data_Hackathon.csv (« ; », % à virgule), « Détail desserte (1).xlsx »
   (openpyxl, mode lecture seule), annuaire_etablissement.xlsx (collège → coordonnées → gare), GTFS (coordonnées
   d'arrêts), DATAtourisme. /api/sante → donnees: "sncf" ; badges « SNCF 2026 ». Recalibre confiance.py sur les
   vraies distributions (régularité médiane ≈ 86 %, suppressions ≈ 6,6 %) et signale-le (fichier:ligne). Foix marche.
2. SÉLECTION MULTIPLE + VOTE (le cœur pédagogique) :
   a. L'enseignant ne choisit plus UNE destination : il coche 2 à 4 destinations candidates (cartes multi-sélection,
      compteur « 2 à 4 choisies », bouton « Soumettre au vote »). Une seule choisie = pas de vote, passage direct.
   b. La page de vote élève (tutoiement) propose ces candidates ; résultat = destination gagnante, égalité tranchée
      par l'indice de confiance, puis par le professeur.
   c. SAISIE MANUELLE : sur le panneau de vote, l'enseignant peut saisir à la main les votes (compteur +/- par
      destination, total ≤ effectif de la classe) pour les classes sans téléphone ; les votes manuels et les votes
      QR s'additionnent, chaque source est affichée (icône + texte). Endpoint dédié, validé côté serveur.
3. TRAJET MODIFIABLE : aujourd'hui le train est figé jusqu'à l'étape suivante. Le panneau trajet doit toujours
   proposer : aller et retour modifiables (« Autre horaire », liste de 3 à 5 circulations faisables), changer
   la gare de départ, le retour avant l'heure limite, et retour arrière à n'importe quelle étape sans perdre l'état
   (le carnet de voyage reste cliquable). Chaque circulation affiche heures, places restantes (≤ 50 voyageurs options
   comprises), indice de confiance (couleur + icône + texte).
4. DATES INDISPONIBLES : si aucun train faisable à la date demandée, Tchouette ne s'arrête pas : endpoint
   /api/dates-proches (date, gare, effectif, contraintes) qui cherche la date faisable la plus proche (avant et après,
   fenêtre ±21 jours, jours ouvrés d'école), affiche 2 à 3 propositions « Jeudi 14 nov. (+2 j) » en cartes
   cliquables, et relance le parcours avec la date choisie. Texte : « Pas de train fiable le 12, voici le plus proche. »
5. CARTE (Leaflet + OpenStreetMap, aucune clé de tuiles, fond de repli hors ligne) à chaque destination : gare de
   départ, destination mise en avant, candidates numérotées (pour la sélection multiple), gare d'arrivée, trait
   de marche + minutes. Champ `carte` dans ReponseScene (schemas.py, API_CONTRACT.md, types.ts). Lisible à 375 px.
6. ICONOGRAPHIE liO : voir livrables/10-charte-lio-train.md. Elle ne fournit AUCUN jeu de pictogrammes : utiliser
   un seul jeu d'icônes en trait (lucide-react, déjà léger) pour train, gare, marche, horloge, groupe, vote, carte,
   alerte, coche, et appliquer la règle WCAG de la charte : tout statut = couleur + icône + libellé. Ne jamais
   redessiner le logo liO ; écrire « liO » ; jaune #FFCD00 jamais en texte sur blanc ; chiffres tabulaires pour
   les horaires ; Montserrat en repli de Marianne.
7. RAG LÉGER (MVP) : embeddings locaux (static-similarity-mrl-multilingual-v1) sur DATAtourisme nettoyé + catalogue
   + top 58, calculés une fois hors ligne dans data/ ; recherche hybride (sémantique → filtres durs gare à 20 min
   à pied ou réseau urbain, trains faisables, niveau → classement Python). Le LLM reformule seulement à partir des
   documents retrouvés. Si le temps manque : mots-clés + catalogue, et garde le RAG pour après la démo.
8. CONVERSATION : Tchouette dit où on en est et ce qui vient ensuite, ramène au parcours après un hors-sujet,
   2 à 3 phrases vivantes tirées des fiches pour présenter une destination (navigation ≤ 25 mots).

# RÈGLES MÉTIER (inchangées)
Trains liO ouverts aux groupes uniquement ; 50 voyageurs max par train (options comprises) ; gare → site 20 min
à pied ou réseau urbain ; statuts PROPOSITION → OPTION → PRÉ-RÉSERVATION → CONFIRMATION ; aucune disponibilité
inventée ni réservation présentée comme confirmée ; « pas assez fiable, voici pourquoi, voici une alternative » ;
vouvoiement enseignant, tutoiement élèves. Toute modification de règle ou de barème : signalée avec fichier:ligne.

# MÉTHODE
Un plan de 8 lignes au plus avec horaires, puis tu enchaînes sans attendre d'OK (le temps est compté).
Lots : 1 données · 2 sélection multiple + vote manuel · 3 trajet modifiable + dates proches · 4 carte + icônes ·
5 Groq + garde-fous · 6 RAG si le temps le permet. Après chaque lot : pytest, tsc, scénario de Foix, commit sur la
branche (jamais de données, jamais de lio.db, jamais de clé), 3 lignes de résumé. À 14h00 Paris : arrêt des
développements, base remise à neuf, répétition au clic puis à la voix, push.

# CRITÈRES DE RÉUSSITE
En 10 secondes le jury voit « une chouette-train aide les profs à organiser une sortie liO, et la classe vote ».
Scénario de bout en bout : une phrase → 2 à 4 destinations sur la carte → vote (QR ou saisie manuelle) → trajet
modifiable → pré-réservation, avec une date de repli si le jour demandé est impossible. Aucun chiffre ou lieu inventé.
```
