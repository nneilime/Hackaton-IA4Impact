# Déployer BâtIA sur Vercel

Le serveur Node devient une fonction (`api/serveur.mjs`), toutes les adresses y sont réécrites par `vercel.json`, et le fond de carte, 134 Mo, est servi en statique depuis `public/carte/fond/`. Le dossier `public/` n'est pas dans git, le script le remplit par des liens durs vers `carte/fond/`.

Comme le site devient joignable par n'importe qui, un mot de passe est demandé avant toute page et toute donnée : variable `BATIA_MDP` sur Vercel. Sans cette variable, en local, rien n'est demandé. Le mot de passe se tape sur la page de connexion, le cookie dure douze heures.

    npx vercel@50 login
    ./deployer-vercel.sh

Le script relie le dossier au projet `batia`, pose le mot de passe, envoie, puis affiche l'adresse et le mot de passe. Pour choisir le mot de passe : `BATIA_MDP=monmot ./deployer-vercel.sh`.

Ce qui change une fois en ligne :

- Les décisions, retours terrain et imports sont écrits dans `/tmp` de la fonction, ils disparaissent à chaque nouvelle instance. C'est une démonstration, pas un stockage.
- Python n'est pas disponible dans la fonction : l'import d'un classeur Excel répond qu'il faut un export CSV, et un CSV importé met à jour les historiques sans recalculer les scores, l'application le dit.
- Sous le capot interroge les services publics depuis la fonction, comme en local.
