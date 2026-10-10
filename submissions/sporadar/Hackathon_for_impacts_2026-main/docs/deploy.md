# Déployer le backend (image Docker via ttl.sh)

L'image contient l'API et les fichiers `data/` (mappings), **aucun secret**. `ttl.sh` est un registre PUBLIC et anonyme :
ne jamais y mettre de `.env` ni de clé. Le tag complet (`ttl.sh/lpc-api-<uuid>:12h`) est donné par la personne qui a construit l'image.

## Lancer sur le serveur de la base (Nhan)

1. Créer à la main un fichier `.env` sur le serveur (il n'est ni dans l'image ni dans git), à partir de `.env.example` :
   `DATABASE_URL=...` (obligatoire), et si besoin `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `API_KEY`.
   Sans clé IA, `/ask` marche en mode dégradé (mots-clés).
2. Lancer :

```bash
docker pull <tag>
docker run -d --name lpc-api --env-file .env -p 3000:3000 --restart unless-stopped <tag>
curl http://localhost:3000/api/health      # -> {"status":"ok"}
```

Mise à jour : `docker rm -f lpc-api`, puis `pull` et `run` avec le nouveau tag. Logs : `docker logs lpc-api`.

## Expiration

Sur ttl.sh, l'image disparaît **12 h** après la publication (suffixe `:12h`). Passé ce délai, `docker pull` échoue : il faut reconstruire.

## Reconstruire et republier (depuis la racine du dépôt)

```bash
docker build --platform linux/amd64 -f backend/Dockerfile -t lpc-api:local .
# Contrôle de sécurité : ces commandes ne doivent RIEN afficher
docker run --rm --entrypoint sh lpc-api:local -c "find / -name '.env' -not -path '/proc/*' 2>/dev/null; grep -rIl 'gsk_' /srv 2>/dev/null"
TAG=ttl.sh/lpc-api-$(python -c "import uuid;print(uuid.uuid4().hex[:12])"):12h
docker tag lpc-api:local $TAG && docker push $TAG && echo $TAG
```

Le `.dockerignore` exclut `.env`, `.git`, `.venv`, `frontend/`, `data/raw/`, `data/merged/` et les logs. Le dossier de travail dans l'image est `/srv`.
