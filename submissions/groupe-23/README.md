# Maya — dossier hackathon

**Architecture :** extension Chrome Manifest V3. Le panneau de chat et les adaptateurs de formulaires sont injectés sur le site Caisse d’Épargne. Le service worker échange avec n8n et conserve la conversation et la collecte par onglet dans le stockage Chrome. Le crédit immobilier peut être prérempli automatiquement ; l’envoi final reste manuel.

**n8n :** `maya-credit-immobilier.json` décrit Webhook → modèle → réponse JSON. L’extension envoie les messages, la collecte et le contexte ; elle reçoit une réponse et une fiche immobilière structurée. Ce workflow ne produit pas de fiche de réclamation.

**Installation :** charger `chrome-extension/` via le mode développeur de `chrome://extensions`. Importer le JSON dans n8n, sélectionner une connexion OpenAI et publier le webhook `ia-impact-modele-minimal`. L’URL actuelle est dans `chrome-extension/shared.js` ; pour changer d’hôte, adapter aussi `manifest.json`.

**Participants :** voir `participants.txt`.
