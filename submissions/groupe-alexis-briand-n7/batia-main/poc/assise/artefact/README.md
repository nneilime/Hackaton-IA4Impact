# Assise en page claude.ai

Copie de la version du port 9011 publiée comme page claude.ai (artefact privé),
pour la montrer sans installer quoi que ce soit.

Ce qui change par rapport à `poc/assise/` :

- le serveur (`serveur.mjs`) est rejoué dans le navigateur par
  `outils/serveur-local.js` : mêmes calculs, à partir des fichiers du kit ;
- les décisions restent dans le navigateur de chaque visiteur ; un import ne
  dure que le temps de la visite ;
- les boutons d'export copient le tableau (la page ne peut pas télécharger) ;
- l'hébergeur refuse les fichiers binaires bruts et les fichiers de plus de
  16 Mo : le fond de carte est redécoupé en 20 morceaux de 11,5 Mo au plus,
  puis, comme les glyphes, écrit en base64 (texte) ; la carte les relit par
  plages quand l'hébergeur le permet, sinon morceau par morceau.

## Refaire la page

```bash
poc/carte/outils/extraire-fond.sh          # si le fond n'existe pas encore
python3 poc/assise/artefact/outils/decouper.py <chemin de pmtiles> poc/carte/fond poc/assise/artefact/fond
poc/assise/artefact/outils/assembler.sh    # écrit poc/assise/artefact/site/
```

`site/` se publie en plusieurs envois de moins de 64 Mo (limite d'un envoi).
Pour l'essayer en local : `node poc/assise/artefact/outils/statique.mjs
poc/assise/artefact/site 4800`, avec une page d'essai qui ajoute l'enveloppe
HTML (la page publiée n'en a pas : l'hébergeur l'ajoute).
