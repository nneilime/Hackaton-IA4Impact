# Protocoles de mesure : utilisabilité et gain de temps

**État au 10/10/2026 : ces deux protocoles sont prêts, mais ils n'ont pas encore été réalisés avec de vrais utilisateurs.** Aucun gain de temps ni taux de réussite humain n'est donc annoncé.

Seul un **parcours automatisé** a été mesuré (`scripts/e2e_parcours_simple.py`, voir RAPPORT_V3.md). Il prouve que les cinq tâches sont réalisables et donne leur coût minimal en clics. Il ne mesure pas la facilité d'usage pour un humain.

## 1. Test d'utilisabilité, sans tutoriel

**Participants** : 5 à 8 personnes qui n'ont pas développé l'application, idéalement des agents de contrôle. Cinq participants suffisent à faire apparaître la plupart des problèmes majeurs d'un parcours.

**Consigne unique** : « Contrôlez ce dossier comme vous le feriez habituellement. » Aucune explication n'est donnée pendant l'essai. L'observateur se tait.

| Tâche | Réussie si… |
|---|---|
| T1 Ouvrir un dossier à traiter | l'écran du dossier est affiché |
| T2 Trouver l'écart | la carte de l'écart est ouverte |
| T3 Comparer les deux valeurs | le participant énonce les deux valeurs et la différence |
| T4 Prendre une décision de test | une décision est enregistrée (confirmation, faux positif ou revue) |
| T5 Retrouver un dossier traité | le dossier est retrouvé dans la liste |

**Mesures, par tâche et par participant** :
- réussite (oui, avec aide, non) ;
- temps, en secondes ;
- nombre de clics ;
- erreurs de navigation (écran non pertinent ouvert) ;
- demandes d'aide ;
- compréhension de la conclusion : à la question « que signifie le gris ? », le participant répond correctement ou non.

**Dossiers proposés** : Facture1_04 (montant), Facture1_09 (prestation absente), Facture2_06 (fichier mal formé) et un dossier sans écart (Facture3_13).

**Analyse** : taux de réussite avec effectif (par exemple « 4 / 5 »), médiane des temps, liste des points de blocage. Chaque blocage observé chez au moins deux participants donne lieu à une modification de l'interface, puis à un nouveau test.

## 2. Gain de temps : contrôle manuel contre contrôle assisté

**Plan** : chaque participant contrôle des dossiers dans les deux conditions, selon un plan croisé équilibré (carré latin). Cela évite qu'un participant ou qu'un dossier soit toujours dans la même condition, et limite l'effet d'apprentissage.

- **Condition A, manuelle** : le bordereau JPG et le fichier TXT sont ouverts dans des visionneuses standard, avec le cahier des charges.
- **Condition B, assistée** : iMSA Sentinel en mode simple.
- **Dossiers** : 2 lots de 10 dossiers du corpus autorisé, de difficulté comparable (même répartition par mise en page et même nombre d'écarts connus). La moitié des participants commence par la condition A, l'autre moitié par la condition B. Les lots sont échangés.
- **Référence** : pour chaque dossier, la liste des écarts réels issue du **référentiel de validation humaine** (écran « Qualité et validation »), et non la sortie du moteur.

**Mesures, par dossier** :
- temps total de contrôle ;
- temps jusqu'à la localisation du premier écart ;
- temps de décision ;
- écarts correctement identifiés (vrais positifs), faux positifs retenus, écarts manqués ;
- clics ou opérations ;
- demandes d'aide.

**Analyse** :
- différence de temps par paire (même participant, même lot) : médiane et intervalle, avec l'effectif ;
- exactitude (précision, rappel) dans chaque condition.

**Aucune conversion en ETP ni en économies** n'est faite sans un modèle de charge validé par la caisse, aux hypothèses explicites.

**Éthique et confidentialité** : participants volontaires, consentement écrit, données du corpus autorisé uniquement, résultats anonymisés.

## 3. Où les mesures seront visibles

- **Temps de revue actif** : déjà mesuré par l'application (une pause n'est pas comptée). Écran « Supervision », section « Activité et productivité ».
- **Exactitude des alertes** : écran « Qualité et validation », à partir des validations humaines seulement.
