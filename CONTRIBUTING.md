# Contribuer — déposer son travail

Merci de participer au **Hackathon IA for Impact** ! Ce document explique comment déposer votre
travail dans ce dépôt.

## Règles

- Chaque participant ou équipe travaille **uniquement** dans son propre dossier :
  - en solo : `submissions/<votre-pseudo-github>/`
  - en équipe : `submissions/<nom-de-votre-equipe>/`
- Il est **interdit de modifier** :
  - le travail des autres participants ;
  - les dossiers [`challenges/`](challenges/) (les énoncés sont en lecture seule) ;
  - les fichiers de configuration (`.github/`, `teams.json`…).
- Tout dépôt passe par une **Pull Request** vers `main` ; une vérification automatique s'assure que
  vous ne modifiez que votre dossier.

## Former votre équipe

Le plus simple est d'utiliser l'[application des équipes](https://nneilime.github.io/Hackaton-IA4Impact/) :
connexion GitHub, choix du défi, emails des membres. Elle crée le dossier
`submissions/<nom-de-votre-equipe>/` et vous invite comme collaborateur du dépôt.

## Créer votre dossier et déposer votre travail

```bash
# 1. Récupérer le dépôt
git clone https://github.com/nneilime/Hackaton-IA4Impact.git
cd Hackaton-IA4Impact

# 2. Créer votre branche de travail
git checkout -b depot/<votre-nom>

# 3. Créer votre dossier (solo) ou celui de votre équipe
mkdir -p submissions/<votre-pseudo-github>

# 4. Ajouter vos fichiers (code, notebook, README, slides…)
cp -r /chemin/vers/votre/projet/* submissions/<votre-pseudo-github>/

# 5. Composer et pousser
git add submissions/<votre-pseudo-github>
git commit -m "Dépôt <votre-pseudo-github>"
git push origin depot/<votre-nom>
```

Ouvrez ensuite une **Pull Request** vers `main`. La vérification `validate-submission` doit passer
avant la fusion.

## Bonnes pratiques

- Ajoutez un **`README.md`** à la racine de votre dossier : nom du projet, défi choisi, membres de
  l'équipe, description de la solution, technologies utilisées, lien vers une démo/slides.
- Un modèle est disponible dans [`submissions/_template/README.md`](submissions/_template/README.md).
- Ne commitez pas de secrets (clés d'API, tokens, `.env`).
- Les gros fichiers de données personnels ne sont pas nécessaires : référencez-les si possible.

## Besoin d'aide ?

Ouvrez une *issue* si vous rencontrez un problème, ou contactez l'équipe organisatrice sur place.
