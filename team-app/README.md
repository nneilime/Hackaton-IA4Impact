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
│   ├── config.js             # à renseigner : URL backend + client_id OAuth
│   ├── data/challenges.json  # galerie des défis
│   └── assets/logos/         # logos des partenaires
├── api/                      # fonctions serverless (hébergées sur Vercel)
│   ├── device/{code,token}.js   # relais OAuth device flow
│   ├── me.js                    # profil + emails vérifiés
│   ├── teams/{index,join,leave}.js
│   └── _lib/                    # helpers (GitHub, CORS, auth)
├── vercel.json
└── package.json
```

## Fonctionnement

1. Le participant se connecte avec GitHub (**device flow**) depuis le site Pages.
2. Le backend Vercel lit son **login** et ses **emails vérifiés**.
3. Il crée une équipe (`teams.json`) avec les **emails** des membres choisis, crée le dossier
   `submissions/<équipe>/` et invite le créateur comme collaborateur.
4. Un coéquipier rejoint l'équipe quand son **email GitHub** correspond à un email déclaré ;
   son login est alors enregistré et il est invité comme collaborateur.
5. Un membre confirmé peut **déposer un `.zip`** depuis le site : l'archive est décompressée
   dans le navigateur (JSZip) puis poussée directement sur `main` (API Git Data GitHub, token
   de l'utilisateur) dans `submissions/<équipe>/`. Si `main` est protégée, une Pull Request est
   ouverte automatiquement.

Le backend tient aussi à jour un registre `participants.csv` (email, login, équipe, défi, statut
`joined`/`invited`) qui contient **tous les emails déclarés**, y compris les membres invités qui
n'ont pas encore rejoint l'équipe.

Aucun email n'est envoyé par l'application.

## Configuration

- `front/config.js` : `apiBase` (URL Vercel), `clientId` (OAuth App), `eventCode` (optionnel).
- Variables d'environnement Vercel : `GH_OWNER`, `GH_REPO`, `GH_ADMIN_TOKEN`, `OAUTH_CLIENT_ID`,
  `ALLOWED_ORIGIN`, `EVENT_CODE` (optionnel).
- Le dépôt de `.zip` s'appuie sur le **scope OAuth `repo`** (compris dans `OAUTH_SCOPES` par défaut)
  et sur le fait que le membre ait **accepté l'invitation** au dépôt. Le front charge **JSZip** depuis
  cdnjs.
