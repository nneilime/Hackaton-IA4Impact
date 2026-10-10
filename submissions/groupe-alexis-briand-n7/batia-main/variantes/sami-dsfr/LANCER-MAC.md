# Lancer BâtIA sur un Mac

Tout tient dans un serveur Node sans dépendance. Le seul morceau qui n'est pas dans le dépôt est le fond de carte, environ 140 Mo, téléchargé une seule fois au premier lancement.

## Le plus court : le fichier à double-cliquer

Le fichier `voir-batia.command` à côté de cette note fait tout : il récupère le dépôt dans `~/batia`, le met à jour s'il existe déjà, télécharge le fond de carte la première fois et ouvre http://localhost:4860 dans le navigateur.

1. Télécharger `voir-batia.command` depuis GitHub, bouton « Download raw file » sur la page du fichier.
2. Dans le Finder, clic droit sur le fichier, « Ouvrir ». La première fois, macOS refuse : aller dans Réglages Système, Confidentialité et sécurité, puis « Ouvrir quand même ». Si le Finder a enlevé le droit d'exécution, dans Terminal : `chmod +x ~/Downloads/voir-batia.command`.
3. Une fenêtre Terminal s'ouvre et reste ouverte pendant que le site tourne. La fermer ou faire Ctrl+C pour arrêter.

Il faut git, Node 20 ou plus, et un accès au dépôt privé : être membre de l'organisation GitHub et avoir une clé SSH, sinon le fichier bascule en HTTPS et GitHub demande un identifiant et un jeton. Si git manque, macOS propose de l'installer avec les outils Xcode, il suffit d'accepter puis de relancer le fichier.

## À la main, dans Terminal

Vérifier Node :

    node --version

Si la commande échoue ou affiche moins de 20 :

    brew install node

Sans Homebrew, prendre l'installeur macOS sur https://nodejs.org, version LTS.

Récupérer le dépôt et lancer :

    git clone git@github.com:ai-for-impact-team/ai-for-impact-2026.git ~/batia
    cd ~/batia/variantes/sami-dsfr
    ./lancer.sh

Le script vérifie Node, télécharge le fond de carte avec l'outil pmtiles de la bonne architecture, Apple Silicon ou Intel, puis ouvre http://localhost:4860. Au premier lancement de l'outil pmtiles, macOS peut demander une autorisation dans Confidentialité et sécurité, comme pour le fichier à double-cliquer.

Pour mettre à jour plus tard :

    cd ~/batia && git pull --ff-only && cd variantes/sami-dsfr && ./lancer.sh

## Options

- Autre port si 4860 est pris : `PORT=4871 ./lancer.sh`.
- Depuis un téléphone sur le même Wi-Fi : `./lancer.sh --reseau`, puis l'adresse IP locale du Mac à la place de localhost, par exemple http://192.168.1.20:4860. L'adresse se lit dans Réglages Système, Wi-Fi, Détails.
- Sans le script : `node serveur.mjs` depuis `variantes/sami-dsfr`, à condition que `carte/fond/` contienne déjà les trois fichiers pmtiles.

## Si ça coince

- « Node.js manque » : Terminal ne voit pas Node. Fermer et rouvrir Terminal après l'installation, ou installer depuis nodejs.org.
- Le téléchargement du fond échoue : relancer, le script ne reprend que ce qui manque. Le serveur démarre quand même sans fond, la carte reste grise mais les listes et les fiches fonctionnent.
- La page reste blanche : vérifier que l'adresse est bien http://localhost:4860 et pas https.
- Pour voir les écrans sans rien installer, les captures sont dans `apercu/`.

## Toujours la dernière version

Le script `derniere-version.sh` fait la mise à jour et le lancement en une fois : il met de côté les fichiers modifiés, se place sur `main`, tire la dernière version, arrête un serveur déjà ouvert sur le port, puis lance `lancer.sh`.

    cd ~/batia/variantes/sami-dsfr && ./derniere-version.sh

Le fichier `voir-batia.command` fait déjà la même chose sur Mac à chaque double-clic.

## Importer un classeur Excel

L'import d'un fichier CSV marche avec Node seul. L'import d'un classeur Excel et le recalcul des scores passent par Python 3 et la bibliothèque openpyxl :

    python3 -m pip install openpyxl

Sans Python, l'application reste entière, l'import Excel répond simplement qu'il faut Python ou un export CSV.

## Taille sur le disque

Le dépôt complet pèse 822 Mo une fois cloné, dont 529 Mo pour les copies successives de `chantiers/`. Le fichier `voir-batia.command` fait maintenant un clone partiel : seulement `variantes/sami-dsfr`, `donnees` et `docs`, et l'historique sans les anciens fichiers. Mesuré : 79 Mo et 24 secondes au lieu de 822 Mo, plus les 134 Mo du fond de carte téléchargés une fois. L'outil de téléchargement, 72 Mo, est effacé après usage.

Pour obtenir la même chose à la main :

    git clone --filter=blob:none --no-checkout git@github.com:ai-for-impact-team/ai-for-impact-2026.git ~/batia
    cd ~/batia && git sparse-checkout set variantes/sami-dsfr donnees docs && git checkout main
