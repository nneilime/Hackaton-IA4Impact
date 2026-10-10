# Hackathon IA for Impact — application « Équipes »

Application qui permet aux participants de **former leurs équipes** par adresse email, de **choisir un défi** et d'accéder aux énoncés. Tout est regroupé dans ce dossier.

- Front (GitHub Pages) : https://nneilime.github.io/Hackaton-IA4Impact/
- API (Vercel) : https://hackaton-ia4impact-team-app.vercel.app

## Structure

```
team-app/
├── front/                    # site statique (hébergé sur GitHub Pages)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── config.js             # à renseigner : URL backend, owner/repo
│   ├── data/challenges.json  # galerie des défis
│   └── assets/logos/         # logos des partenaires
├── api/                      # fonctions serverless (hébergées sur Vercel)
│   ├── auth/{login,callback}.js # OAuth web GitHub (redirection)
│   ├── me.js                    # profil + empreintes d'emails
│   ├── teams/{index,join,leave,members}.js
│   └── _lib/                    # helpers (GitHub, CORS, auth, chiffrement)
├── scripts/email-key.js      # gestion de la clé de chiffrement des emails
├── scripts/build-front.js    # minification HTML/CSS/JS du front → dist/
├── vercel.json
└── package.json
```

## Fonctionnement

1. Le participant se connecte avec GitHub via le **flow OAuth web** : le site redirige vers
   GitHub, puis le backend échange le code contre un token. **Aucun code à copier-coller.**
2. Le backend Vercel lit son **login** et ses **emails vérifiés**, puis ne conserve les emails
   que sous forme **hashée + chiffrée** dans `participants.csv` (jamais en clair). `teams.json`
   ne stocke que les **profils publics** : `login`, `status` (`joined`/`invited`) et `created_at`.
3. Il crée une équipe (`teams.json`), crée le dossier `submissions/<équipe>/` et invite le
   créateur comme collaborateur. Les emails déclarés alimentent `participants.csv`, qui sert de
   source de vérité pour le matching des adhésions.
4. Un coéquipier rejoint l'équipe en cliquant sur **Rejoindre** : tout participant connecté
   peut rejoindre une équipe librement (son login est enregistré dans `teams.json` et l'empreinte
   de son email GitHub dans `participants.csv`, puis il est invité comme collaborateur). S'il
   avait été déclaré par email, son adhésion est simplement confirmée.
5. Le **créateur** peut ajouter des emails à son équipe à tout moment : les personnes
   concernées deviennent *membres en attente* et pourront rejoindre en se connectant avec
   cet email GitHub.
6. Un participant ne peut être **membre confirmé que d'une seule équipe** à la fois : créer
   ou rejoindre une nouvelle équipe est refusé (`409`) tant qu'il n'a pas quitté la
   précédente. Les emails simplement *déclarés* (membres en attente) ne bloquent pas.
7. Un membre confirmé peut **déposer un `.zip`** depuis le site : l'archive est décompressée
   dans le navigateur (JSZip) puis poussée directement sur `main` (API Git Data GitHub, token
   de l'utilisateur) dans `submissions/<équipe>/`. Si `main` est protégée, une Pull Request est
   ouverte automatiquement.

Le backend tient aussi à jour un registre `participants.csv` (`email_hash`, `email_enc`, `login`,
`team_name`) qui couvre **tous les participants déclarés**, y compris les membres invités qui
n'ont pas encore rejoint l'équipe. C'est ce fichier qui sert de source de vérité pour le matching
des adhésions et la règle « une seule équipe active par personne ».

Aucun email n'est envoyé par l'application.

## Emails : chiffrement et clé

Les emails ne sont jamais stockés en clair. Chaque email donne :

- un **hash** HMAC-SHA256 (déterministe, utilisé pour le matching et affiché tronqué sur le site) ;
- une valeur **chiffrée** AES-256-GCM (permet aux organisateurs de retrouver l'email).

La clé (32 octets) vit **hors du dépôt**, dans le dossier parent :

```
../hackathon-email.key
```

- Générer/afficher la clé : `node team-app/scripts/email-key.js init`
- Exporter les emails en clair : `node team-app/scripts/email-key.js export`
- Calculer l'empreinte d'un email : `node team-app/scripts/email-key.js hash <email>`

La même valeur doit être définie dans Vercel sous `EMAIL_SECRET_KEY`. **Ne jamais committer la clé.**

## Build du front (minification)

Le front est servi **minifié**. Le workflow GitHub Pages installe les dépendances et lance le
build ; en local :

```bash
cd team-app
npm install
npm run build   # génère team-app/dist/ (HTML/CSS/JS minifiés + assets)
```

`dist/` est généré et ignoré par git. Modifier les sources dans `front/` puis rebuilder.

## Configuration

- `front/config.js` : `apiBase` (URL Vercel), `owner`/`repo`, `eventCode` (optionnel).
- **GitHub App** (recommandée, permissions fines limitées à un seul dépôt) :
  - Callback URL : `https://hackaton-ia4impact-team-app.vercel.app/api/auth/callback`
  - Permissions : *Repository → Contents: Read and write*, *Pull requests: Read and write*,
    *Metadata: Read* (auto), *Account → Email addresses: Read*.
  - Installer l'app sur le seul dépôt des travaux (accès « Only select repositories »).
  - Décocher *Expire user authorization tokens* (tokens non expirants : pas de refresh à gérer).
- Variables d'environnement Vercel :
  - `GH_OWNER`, `GH_REPO`, `GH_ADMIN_TOKEN`
  - `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` (ceux de la GitHub App)
  - `GH_REPO_ID` (id numérique du dépôt ; restreint le token utilisateur à ce seul dépôt)
  - `FRONT_URL` (optionnel ; défaut : `https://nneilime.github.io/Hackaton-IA4Impact`)
  - `EMAIL_SECRET_KEY` (clé de chiffrement des emails)
  - `ALLOWED_ORIGIN`, `EVENT_CODE` (optionnel)
  - `STATE_SECRET` (optionnel ; sinon `GH_ADMIN_TOKEN` est utilisé pour signer le state OAuth)
- L'URL de callback OAuth est **calculée depuis l'hôte de la requête** (`/api/auth/callback`) : elle
  doit donc simplement être enregistrée telle quelle dans la GitHub App
  (`https://hackaton-ia4impact-team-app.vercel.app/api/auth/callback`). Aucune variable
  `OAUTH_REDIRECT_URI` n'est nécessaire, et aucun `scope` n'est demandé (les permissions d'une
  GitHub App sont définies dans l'app elle-même).
- Le dépôt de `.zip` s'appuie sur la permission **Contents: Read and write** de la GitHub App
  (accès limité au dépôt installé) et sur le fait que le membre ait **accepté l'invitation**.
  Le front charge **JSZip** depuis cdnjs.
