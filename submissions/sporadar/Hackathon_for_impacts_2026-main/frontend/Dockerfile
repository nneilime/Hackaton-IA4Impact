# syntax=docker/dockerfile:1
# Build en 2 étapes : on compile avec Node, puis on ne garde que les fichiers
# statiques servis par nginx (image finale légère, sans Node ni sources).

# --- Étape 1 : build Angular -------------------------------------------------
FROM node:24-alpine AS build
WORKDIR /app
RUN corepack enable

# On copie d'abord les manifests : tant qu'ils ne changent pas, Docker réutilise
# le cache des dépendances (rebuilds beaucoup plus rapides).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# Valeurs venant du .env racine, transmises par docker-compose (build args)
ARG FRONT_API_URL=/api
ENV FRONT_API_URL=$FRONT_API_URL
# BACK_URL renseigné = le navigateur appelle le back en direct (BACK_URL/api), sans passer par le proxy nginx
ARG BACK_URL=""
ENV BACK_URL=$BACK_URL
RUN node scripts/generate-env.mjs && pnpm exec ng build

# --- Étape 2 : serveur nginx -------------------------------------------------
FROM nginx:alpine
# Valeur par défaut vide : sans elle, nginx lirait ${API_KEY} comme une variable inconnue et ne démarrerait pas.
# En Docker Compose, le .env racine (env_file) la remplace.
ENV API_KEY=""
# Back vers lequel nginx transmet /api/ (sans /api). Compose le remplace par BACK_URL du .env, ou par http://backend:BACK_PORT.
ENV BACK_URL="http://backend:3000"
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
# Les fichiers de /etc/nginx/templates sont passés à envsubst au démarrage
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
