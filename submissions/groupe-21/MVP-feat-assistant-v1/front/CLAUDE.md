# Prototype assistant IA Caisse d'Epargne (Hackathon IA for Impact, défi BPCE SI)

## Contexte
- Hackathon IA for Impact, La Mêlée Numérique, Toulouse, 9-10 octobre 2026.
- Défi BPCE Solutions informatiques : « l'assistant IA qui transforme chaque intention bancaire en action ».
- Promesse du sponsor : une réponse contextualisée qui conduit au résultat sans errance.
- Livrable attendu par BPCE : un assistant démontré sur 2 à 3 parcours réels, avec sources, garde-fous et relais humain.
- Le PM de l'équipe (Riyan) cadre et pitche. Les devs branchent le vrai agent plus tard.

## Ce que BPCE a demandé (slides du brief)
- Cas d'usage : Réclamation, Code perdu, Crédit, Gestion privée / Conseil.
- 5 étapes : Exprimer → Comprendre (reformuler, préciser) → Expliquer (simplement, avec sources) → Agir (lien, formulaire, simulation) → Relayer (humain avec le contexte).
- Critères : Efficacité, Compréhension (pas de jargon non expliqué), Confiance (sources, limites, choix visibles), Continuité (le contexte suit), Accessibilité, Apprentissage (incompréhensions et abandons mesurables), Sécuriser (limites, consentement, traçabilité, données).

## AXE PRINCIPAL : ACCESSIBILITÉ (décision PM)
L'accessibilité est l'angle du pitch, pas un critère parmi d'autres. Toute nouvelle fonctionnalité doit être utilisable au clavier, au lecteur d'écran, en grand texte et en contraste renforcé.
- Socle technique (RGAA / WCAG 2.2 AA) : contrastes ≥ 4,5:1, zones cliquables ≥ 40 px, focus visible, liens d'évitement, modales avec piège de focus, `aria-modal` sur mobile (plein écran), journal démo `inert` quand fermé.
- Lecteur d'écran : chaque réponse est construite hors du DOM puis ajoutée d'un bloc au `role="log"` (une seule annonce), préfixes « Vous : » / « L'assistant : », `aria-busy` pendant l'attente, annonces dans `#srStatus` via `announce()`. Après une action dans le fil (choix, carte, confirmation), le focus va sur la nouvelle réponse.
- Réglages dans l'assistant (bouton accessibilité de l'en-tête, module `A11y`) : taille du texte A / A+ / A++ (variable CSS `--fs`), contraste renforcé (suit `prefers-contrast`), lecture à voix haute (`speechSynthesis`), dictée (`SpeechRecognition`, bouton micro, masqué si non supporté). Réglages mémorisés en `localStorage`. Raccourci Alt + Maj + A.
- Les réglages partent au backend dans `context.a11y` pour que l'agent adapte ses réponses.
- Hypothèse à valider avec BPCE : la dictée de Chrome passe par un service Google (question de données).
- Règle : aucune info portée seulement par la couleur ou une icône ; toute icône est `aria-hidden`.
- Mode vocal (module `Voice`, bouton « Vocal » du composer) : conversation mains libres écoute → réponse lue → réécoute. Choix à la voix (« le deuxième » ou le nom du choix), commandes « répète », « pause », « stop », « fermer », « calculer », « annuler ». Tout reste écrit dans le fil.
- RÈGLE : une opération n'est JAMAIS validée à la voix. « Je confirme » met le focus sur la case ou le bouton : l'utilisateur valide par un geste (Entrée). À valider avec BPCE.

## Décisions produit (validées par le PM)
- L'assistant vit sur le site public et sert prospects ET clients connectés.
- Texte libre + suggestions.
- AUCUNE transaction dans le chat : il simplifie et guide.
- Toute action passe par une carte de confirmation que l'utilisateur clique lui-même (style Shopify). Ensuite : message de succès + lien vers l'écran concerné.
- Icône : bulle de chat avec une étoile IA. Nom neutre : « Assistant IA ».
- Bandeau « Prototype, données fictives » visible.
- Design pixel-proche de la charte Caisse d'Epargne.
- Front only, maquette propre et simple. Prévoir le branchement de l'agent.
- 3 versions : web non connecté, web connecté (sélecteur de persona), mobile (sélecteur **Web | Mobile** de la barre démo : la page est affichée dans un cadre de téléphone de 390 px, les styles mobiles s'appliquent). Caisse d'Épargne uniquement.

## Règles de travail (non négociables)
- Zéro invention : pas de fonctionnalité, donnée, métrique, URL ou API BPCE supposée sans confirmation. Sinon, marquer « hypothèse » ou « à confirmer avec BPCE ».
- Légende dans l'UI : `constat` (vu dans un document ou une capture), `hypothese`, `exemple` (lien ou contenu à brancher). Données clients = toujours fictives.
- Ne jamais committer de capture contenant des données personnelles réelles (nom, numéro de compte). Flouter ou remplacer par du fictif.
- Pas de secret ni de clé API dans le repo.
- Le front n'exécute jamais d'opération : le clic « Confirmer » envoie `{type:'confirm', id}`. Le serveur exécute et trace. L'identité client vient de la session serveur, jamais du modèle.

## Structure de `index.html` (un seul fichier, vanilla HTML/CSS/JS)
1. Tokens CSS : `--ce-red #C5000E`, `--ce-red-dark #9E000B` (CTA), `--ce-text #666`, `--ce-ink #3E454A`. Police Ubuntu (approximation de la police propriétaire du site).
2. `PERSONAS` : Léa (prospecte), Karim (client), Hélène (cliente gestion privée). Tout est fictif.
3. `AgentClient` : mode `hybrid` quand la page est servie par `python -m assistant` (parcours guidés ici, autres questions → `POST /api/chat` en NDJSON : réponse pré-rédigée à 0 token, sinon modèle Groq avec la FAQ et la base fictive `data/finance.db`), mode `mock` en `file://`. Simulation du parcours crédit : `POST /api/simulate`. Suggestions `{type:'ask', text}` et choix `key:'llm'` partent au serveur.
4. `MockAgent` : moteur scripté (détection d'intention par regex pondérées, parcours, sous-étapes). `routeToServer()` envoie au serveur les questions d'information, chiffrées ou non reconnues ; l'urgence carte reste toujours scriptée.
5. `Chat` : rendu des blocs (le contrat de réponse est documenté en tête du script).
6. Site : persona, header connecté/non connecté, écrans cibles simulés (`Screens`), `Journal` (traçabilité et KPIs démo), `View` (Web | Mobile ; dans le cadre, `window.__demo` expose persona, backoffice, journal et réinitialisation à la barre démo).

## Avis, backoffice, consommation
- Chaque réponse (sauf l'accueil) a une barre : Copier, Utile, Pas utile, Écouter. « Pas utile » ouvre les raisons (`FB_REASONS`, choix multiples + commentaire facultatif filtré par `guard`). La raison « conseiller » déclenche le relais.
- `Store` garde les conversations (en mémoire) + un historique FICTIF de 7 jours (`SEED`, clients pseudonymisés). `BO` = backoffice plein écran (bouton « Backoffice » de la barre démo) : vue d'ensemble (KPIs, tokens par jour, raisons des avis, intentions, issues, aides d'accessibilité) et conversations (filtres, fil complet, tokens par message, avis).
- Tokens = estimation fictive (1 token ≈ 4 caractères, prompt système 900 tokens, historique renvoyé à chaque tour), tarif fictif 3 € / 15 € par million. Le vrai backend renverra `meta.usage`.
- Images : intégrées en base64 dans `index.html` (fichier autonome) ; `assets/` garde les sources.

## Ajouts du 10/10 (après retours PM)
- Avertissement IA visible : pied du chat (« L'assistant est une IA : il peut se tromper ») + 1er message d'accueil. Bouton « Vos données » → écran RGPD (finalités, 6 mois de conservation à valider avec le DPO, droits, effacement de la conversation).
- Zéro jargon : textes du MockAgent réécrits en langage courant. Option « Langage simplifié » (FALC) : un bloc text peut fournir `simple` ; sinon `plainify()` remplace le jargon (table PLAIN). Mention légale crédit conservée mot pour mot (obligation légale).
- Conseiller joignable partout : bouton d'en-tête, proposé après 2 incompréhensions de suite ou en cas de frustration détectée. Canaux : téléphone, agence, écrit, visio avec interprète LSF (à confirmer) + besoin particulier (LSF, sous-titres, accès fauteuil, aidant, explications simples).
- Réglages : langue (FR / EN / ES, `I18N`, `t()`, `lang` sur le panneau), taille, police (Atkinson Hyperlegible, Lexend), espacement du texte (WCAG 1.4.12), contraste, animations réduites, langage simplifié, lecture vocale + vitesse. Sélecteur de langue aussi dans la barre de contexte. Parcours scriptés en français uniquement (message affiché en EN/ES).
- Modèles : Groq en principal + fournisseur de secours (routage FICTIF dans `Store.route`). Backoffice : carte « Modèles », taux de bascule, latences fictives ; onglet « À améliorer » pour produit/devs (avis négatifs + incompréhensions, statut, réponse attendue, export JSONL et CSV).

## Contrat de réponse de l'agent
`{ blocks: Block[], meta?: { intent, confidence, step, request? } }`
Blocs : `text`, `chips`, `choices`, `form`, `result`, `confirm`, `success`, `login`, `links`, `sources`, `warning` (`feedback` ignoré : la barre d'avis est automatique).
`meta.usage = {input_tokens, output_tokens}` optionnel. Avis : `AgentClient.feedback({messageId, value, reasons, comment})` (route `/feedback` à définir).
Actions envoyées par le front : `start`, `choice`, `form`, `confirm`, `cancel`, `handoff`, `login_done`, `thumbs_down_reason`, `welcome`.

## Constats vs hypothèses actuels
- Constat : textes et offres de la page « Ouvrir un compte » (Initial, Confort Classic, Confort Premier), justificatifs demandés, accès rapides Banxo (Wero, RIB/IBAN, Code CB, Plafond CB), mention « Gestion Privée (Vision Patrimoine) ».
- Hypothèses : procédures réelles (code par courrier, opposition en ligne), délais, frais, seuils gestion privée, numéro d'opposition. Taux, tarifs et prévisions : base fictive `data/finance.db` (repli local 4 % immo, 6 % perso si le serveur est absent).
- Footer reconstruit sans capture.

## Prochaines étapes possibles
- Version app mobile Banxo (attendre les captures du PM : Cartes, Code CB, Plafond CB, Virements).
- Resserrer la démo sur 2 parcours joués de bout en bout.

## Lancer en local
`.venv/bin/python -m assistant` à la racine du dépôt, puis http://localhost:8000 (`?vue=mobile` pour la version mobile). Ouvrir `index.html` directement reste possible : tout est alors scripté.

## Sécurité de la page
Servie avec une CSP stricte : un seul `<script>` intégré, autorisé par son empreinte SHA-256 (recalculée par le serveur) ; aucun gestionnaire en attribut (`onclick="…"`), aucun script externe.

## Présentation
- `../docs/Presentation-Assistant-IA-Caisse-Epargne.pptx` : premier jet (26 slides, notes orateur), à importer dans Google Slides. À mettre à jour à chaque évolution du prototype.
