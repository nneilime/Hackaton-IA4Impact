# Méthodes voisines : d'où vient notre démarche, et ce qui la distingue

Notre prompt d'extraction n'a pas été écrit d'un trait : il a été **mesuré, corrigé, remesuré** en trois versions. Ce document dit à quelles
méthodes connues cette discipline ressemble, et surtout ce qui nous en sépare. C'est une **comparaison conceptuelle** : aucune de ces
méthodes n'a été exécutée ici, et nous n'avons pas implémenté Arbor.

## Notre boucle, à deux niveaux

| Niveau | Quand | Quoi |
|---|---|---|
| 1. Inférence | à chaque passage | le modèle propose → Pydantic vérifie la forme → le code vérifie la preuve → le motif exact du refus est renvoyé → 3 essais, puis un expert |
| 2. Développement | à chaque version du prompt | mesurer sur les passages → lire les échecs → écrire **une règle par échec observé** → remesurer. Historique dans `data/processed/history/` |

Résultats du niveau 2 (`README.md`) : renvois à l'expert 30 → 14 → 17, réussites du premier coup 162 → 84 → 165, avec un contrôle de preuve de plus en plus strict.

## Arbor (RUC-NLPIR)

[Arbor](https://github.com/RUC-NLPIR/Arbor) (licence Apache-2.0) est un agent de recherche autonome « qui exécute des expériences et optimise de façon
itérative ». Il est décrit dans « Toward Generalist Autonomous Research via Hypothesis-Tree Refinement » (Jin et al., arXiv:2606.11926, 2026).
D'après son README : un *Coordinator* entretient un **arbre d'hypothèses** et des *Executors* testent chaque idée dans un worktree git isolé ; les
résultats et les leçons des échecs sont remontés dans l'arbre ; un gain n'est fusionné que s'il tient sur des données **mises de côté** (*held-out*),
au-delà d'un seuil configurable.

| Arbor | Chez nous |
|---|---|
| Hypothèse = un nœud de l'arbre | Une règle de prompt ou un contrôle (ex. « la citation contient la dose ») |
| Un exécuteur isole et évalue l'idée | `./veille extract` puis `./veille eval` |
| L'arbre garde les leçons des échecs | `data/processed/history/` : prompt, traces et évaluation de chaque version (liste plate, pas un arbre) |
| Jeu dev pour explorer, held-out pour valider | Évaluation e-Phy pour régler ; **`./veille holdout`** pour valider |
| Fusion seulement si le gain tient | v3 retenue : le contrôle plus strict est resté à 100 % de doses exactes |
| Gouvernance : un humain promeut le tronc | Statut jamais au-dessus de `verifie_auto` ; un expert valide |

### Ce qui nous sépare d'Arbor
- **Autonomie** : Arbor boucle seul ; nous avons itéré avec un assistant et un humain qui décidaient.
- **Structure** : Arbor explore un arbre en parallèle ; nous avons procédé en séquence, sans arbre.
- **Objet évolué** : Arbor fait évoluer du code ; nous faisons évoluer un prompt et des contrôles.
- **Rigueur de validation** : nous avons d'abord réglé et rapporté nos chiffres sur **les mêmes 197 passages**. C'était l'écart le plus sérieux
  avec la discipline d'Arbor. Il est comblé en partie par le test hors échantillon ci-dessous.

### Test hors échantillon (`./veille holdout`)
104 passages tirés au hasard (graine 1) dans **40 produits e-Phy absents du périmètre de réglage**, donc jamais regardés pendant la mise au point
du prompt, avec la même vérité terrain structurée :

| | Passages de réglage (197) | Hors échantillon (104) |
|---|---|---|
| Publiés | 180 | 102 |
| Réussis du premier coup | 165 | 98 |
| Doses exactes | 100 % (162 comparées) | 100 % (102 comparées) |
| Valeurs inventées | 0 | 0 |

**Limites du test** : e-Phy est un format homogène et structuré, donc plus facile que les étiquettes PDF américaines, qui n'ont pas de vérité
structurée et restent contrôlées par échantillon. Le test montre que le prompt ne dépend pas des 197 passages ; il ne prouve rien sur la source la
plus difficile.

### Lien avec votre dépôt
`arbor_self_improve.py` (Astroport.ONE) applique déjà la discipline d'Arbor pour BRO : hypothèses indépendantes, évaluation sur un jeu dev, rejet si le
gain ne se confirme pas sur le jeu held-out, matérialisation dans un worktree git sans fusion automatique. Notre jeu d'évaluation (e-Phy, 197 passages)
et le test hors échantillon pourraient servir de jeux dev et held-out pour optimiser `prompts/extractor.system.md` de la même façon. Ce n'est pas fait.

## Autres méthodes voisines

| Méthode | Idée | Lien avec notre travail |
|---|---|---|
| [Self-Refine](https://arxiv.org/abs/2303.17651) (Madaan et al., 2023) | le modèle critique puis révise sa propre sortie | même boucle de correction, mais notre vérificateur est **externe et déterministe** (Pydantic, preuve), pas le modèle lui-même |
| [Reflexion](https://arxiv.org/abs/2303.11366) (Shinn et al., 2023) | retour verbal gardé en mémoire pour les essais suivants | notre retour d'erreur vaut pour un seul passage ; pas de mémoire entre passages |
| [DSPy](https://arxiv.org/abs/2310.03714) (Khattab et al., 2023) | programmes déclaratifs, prompts optimisés automatiquement | le contrat Pydantic joue le rôle de signature ; nos prompts sont réglés à la main |
| OPRO (Yang et al., ICLR 2024) | un modèle propose de nouveaux prompts d'après les scores passés | ce que nous avons fait à la main de v1 à v3 (référence non rouverte ici) |
| [TextGrad](https://arxiv.org/abs/2406.07496) (Yuksekgonul et al., 2024) | retours en langage naturel utilisés comme des gradients | nos motifs de refus jouent ce rôle à l'échelle d'un passage |
| Validation + nouvel essai (ex. bibliothèque Instructor) | sortie structurée validée, erreur renvoyée au modèle | c'est notre niveau 1, avec un contrôle de preuve en plus |

## Pistes pour aller plus loin
1. **Automatiser le niveau 2** (Arbor, OPRO, DSPy) : un agent propose des règles à partir des traces refusées, évalue sur un jeu dev, valide sur un held-out, et
   laisse un humain promouvoir la version. Garde-fous : seuil de gain minimal, jamais de fusion automatique.
2. **Mémoire entre passages** (Reflexion) : garder les motifs de refus fréquents et les proposer au modèle en entrée.
3. **Arbre d'hypothèses** au lieu d'une liste, pour ne pas reperdre une leçon.
4. **Un held-out sur les PDF américains**, avec une vérité terrain constituée par un expert.
