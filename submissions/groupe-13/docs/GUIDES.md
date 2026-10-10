# Guides d'utilisation (version 3.0)

## Mode simple (affiché par défaut depuis la version 3.0)

Le parcours tient en quatre étapes : **dossier → écart → preuve → décision**. Le guide d'une page (`docs/GUIDE_1_PAGE.md` et `.pdf`) suffit pour l'utiliser.

1. **Mes dossiers** : cliquez sur **Contrôler le dossier suivant**, ou sur une ligne du tableau « À traiter ».
2. **Le dossier** : une phrase donne le résultat (« 1 écart à examiner »). Sur le bordereau, seules les zones en écart (rouge) et à vérifier (gris) sont marquées ; les zones conformes restent discrètes.
   - Selon le cas, un bandeau signale un **fichier B2 mal formé** (lecture réalignée), un **rapprochement à confirmer** ou un **bordereau qui porte les identifiants d'un autre dossier**.
3. **L'écart** : deux encadrés côte à côte.
   - *Ce que dit le bordereau* : la valeur lue et l'**agrandissement réel** de la case.
   - *Ce que dit le fichier de facturation* : la valeur, et la ligne du fichier avec les caractères concernés surlignés.

   Selon le type d'écart, le dossier affiche aussi :
   - **Différence**, pour un écart de montant ;
   - **Montant concerné**, pour une prestation absente ;
   - un avertissement quand les deux valeurs ne diffèrent que par un chiffre souvent confondu (0/8, 1/7…).
4. **La décision** : **Confirmer l'écart**, **Faux positif** (motif et cause à choisir) ou **À revoir**. Le logiciel passe tout seul à l'écart suivant ; **Terminer le contrôle** puis **Dossier suivant**.

**Détails techniques** (repliés sous chaque écart) : règle et texte du cahier des charges, convention (lecture littérale et convention pour R01), positions, coordonnées, lectures de chaque moteur OCR, versions, historique.

**Mode expert** : **Autres actions → Mode expert**. On y retrouve tout le poste de contrôle de la version 2.0 : 15 zones, 22 contrôles, lectures OCR, fichier complet, simulation. Le choix est mémorisé sur le poste. Le guide ci-dessous décrit ce mode.

**Navigation** : trois espaces.
- **Mes contrôles** : mes dossiers, écarts à traiter, retrouver un dossier.
- **Pilotage** : supervision, qualité et validation, règles et conventions, rapports.
- **Outils avancés** : revue rapide, investigations, imports, simulation, administration. Ils sont repliés.

## Référentiel de validation humaine (« Qualité et validation » → onglet « Référentiel »)

Un validateur, qui peut être un agent ou un gestionnaire, examine un résultat :
- il voit l'agrandissement de la case, la ligne du fichier et les deux valeurs ;
- il choisit un verdict : **écart réel**, **faux positif**, **conforme confirmé**, **écart manqué** ou **indéterminé** ;
- pour un faux positif, il indique la cause (lecture, géométrie, tableau, fichier, appariement, normalisation, règle, convention, cache, affichage).

Deux validateurs peuvent revoir le même résultat, et les désaccords sont listés. La matrice de confusion, la précision et le rappel sont calculés **uniquement** sur ces validations humaines. La revue assistée par IA du diagnostic 3.0 est visible, marquée « à confirmer », et n'entre dans aucune mesure.

## Décision sur une convention (« Règles et conventions »)

Pour AMB-01 (R01) et AMB-02, un gestionnaire peut enregistrer la décision de la MSA : validée, rejetée ou proposée, avec la référence du document qui la fonde. La décision est journalisée, puis le corpus est réanalysé avec la règle choisie. Sans décision enregistrée, chaque résultat R01 montre les deux interprétations.

# Mode expert (poste de contrôle complet)


## Guide de l'agent de contrôle (mode expert)

1. **Se connecter** avec son compte. La vue d'ensemble affiche :
   - les dossiers à contrôler ;
   - l'ordre de traitement proposé (score paramétrable, pas une norme MSA) ;
   - le bouton **Démarrer la revue rapide**.
2. **Ouvrir un dossier** depuis la file, la liste « Dossiers » ou la revue rapide. Un agent voit les dossiers non affectés et les siens. Les dossiers importés ou simulés par un autre agent restent privés.
3. **Contrôler les 15 zones** (onglet affiché par défaut) :
   - **Sur le bordereau**, chaque zone est encadrée selon son statut : vert = conforme, rouge = anomalie, gris = non vérifiable, gris clair en pointillés = non applicable, orange = erreur technique. Une légende reste affichée sous l'image.
   - **Sélectionner une zone** : cliquez une zone de l'image ou sa pastille Z1 à Z15. Elle est cadrée et mise en évidence, et sa fiche s'ouvre. Pour naviguer : **Précédente / Suivante**, touches `[` et `]`, Échap pour revenir à la vue d'ensemble.
   - **Contenu de la fiche** :
     - la raison de la couleur et les contrôles concernés, avec les valeurs du bordereau et du TXT ;
     - les lectures OCR, et les positions du TXT surlignées à droite ;
     - pour les tableaux (Z6, Z7, Z10), chaque ligne avec sa ligne du TXT ;
     - pour les signatures (Z11, Z14), chaque case avec sa présence détectée ;
     - l'action recommandée et la traçabilité.
   - **Lire les indicateurs** :
     - « Contrôles également incertains » : une zone rouge contient aussi un contrôle non vérifiable ;
     - « Résultats mixtes » : les règles de la zone n'ont pas toutes le même statut.
4. **Vue des 22 contrôles** (onglet « Contrôles ») : la liste par catégorie A à F. Un clic sur un contrôle localise l'élément dans l'image **et** dans le fichier.
5. **Décider**, depuis la fiche de zone ou le contrôle :
   - Confirmer l'écart ;
   - Faux positif (motif obligatoire) ;
   - Revue complémentaire ;
   - Commenter ;
   - Marquer examiné.

   Chaque décision est horodatée et signée, et une décision peut être annulée (motif obligatoire). Une décision ne change jamais le statut calculé d'une règle ou d'une zone.
6. **Corriger ou valider une lecture** (« Corriger / valider » dans la fiche, ou onglet « Lectures OCR ») :
   - La valeur est contrôlée par le serveur (format, cible autorisée). Une saisie invalide est refusée avec un message explicite.
   - Saisir la valeur déjà lue la **valide**, ce qui lève l'incertitude.
   - La lecture d'origine est conservée. Les 22 contrôles et les 15 zones sont recalculés, puis le message indique les zones dont la couleur a changé. Une correction peut être annulée.
7. **Revue rapide** (menu « Revue rapide ») :
   - Les anomalies, et à défaut les contrôles non vérifiables, défilent une par une, par priorité.
   - La bannière indique « Vous vérifiez la zone Z8 — Sous-total des prestations… ». La zone est cadrée et les positions du TXT sont surlignées.
   - **Raccourcis** (configurables) : `C` confirmer, `F` faux positif, `R` revue, `L` corriger la lecture, `M` commenter, `N`/`→` suivante, `P`/`←` précédente. Ils sont ignorés pendant une saisie.
   - Une décision n'est présentée comme enregistrée qu'après confirmation par le serveur.
8. **Simuler une modification** (bouton du dossier) : une **copie** du dossier est créée avec une valeur du TXT modifiée, et l'original n'est jamais touché. La copie est analysée par le moteur réel, privée, marquée « Simulation » et exclue des statistiques.
9. **Conclure** : statut « Écart confirmé », « Faux positif reconnu » ou « Contrôle terminé », ou bouton **Transmettre** au superviseur (motif obligatoire). Le rapport PDF du dossier (avec le tableau des 15 zones et le bordereau encadré) est disponible à tout moment.
10. **Assistant** : résumé, ordre de traitement, explication d'une règle. Il répond à partir du dossier seulement et ne conclut jamais à une fraude.

## Guide du gestionnaire de caisse

- **Supervision de caisse** :
  - indicateurs avec leurs dénominateurs, dont la revue humaine requise, les contrôles confirmés, les faux positifs et les dossiers clôturés ;
  - **matrice des 15 zones** : pour chaque zone, le nombre de dossiers par statut, le pourcentage et un lien vers la liste filtrée ;
  - résultats par règle, par établissement et par agent, priorités et motifs.
- **Volet financier** (niveaux jamais assimilés) :
  - montant facturé ;
  - montant en anomalie (dédoublonné) ;
  - montant facturé des dossiers en alerte ;
  - **écarts confirmés**, règle par règle, selon la dernière décision non annulée, sans double comptage ;
  - indu établi et montants récupérés : « non calculables ».
- **Activité et productivité** : temps mesurés de lecture OCR et d'analyse, temps de revue **actif** (une pause n'est pas comptée), délais jusqu'à la première décision et jusqu'à la clôture, décisions par jour. Sans mesure, « indisponible ». Aucun gain n'est extrapolé.
- **Qualité et validation** (onglet « Mesures ») :
  - exactitude de l'OCR d'après les lectures validées ou corrigées ;
  - désaccords entre moteurs par zone ;
  - précision et rappel des alertes sur les cas annotés ;
  - taux de non vérifiables et de faux positifs.

  Chaque taux affiche son effectif.
- **Investigations** : dossiers par statut et **regroupements d'alertes**, c'est-à-dire des hypothèses formulées au conditionnel (même numéro GHS, identifiants du dossier, code différent entre les deux documents, écart de total expliqué par une ligne, lectures incertaines, fichier décalé).
- **Instruction** : affecter, passer en priorité haute, enregistrer une décision motivée, clôturer (réservé au gestionnaire).
- **Règles et conventions** : table zone ↔ règles et centre des conventions AMB-01 à AMB-08. Pour chacune : texte d'origine, convention, version, dossiers concernés, effet calculé d'un changement de convention.
- **Rapports** : rapports PDF et JSON par dossier, export CSV, journal d'audit, liste des traitements.
- **Administration** (rôle administrateur) :
  - synchronisation du corpus, recalcul forcé ;
  - sauvegarde vérifiée ;
  - purge des métadonnées (précédée d'une sauvegarde automatique).

## Parcours de démonstration pour le jury (version 3.0, 7 à 10 minutes)

Tous les cas ci-dessous sont des dossiers réels du corpus, vérifiés avec la version 3.0 (`docs/RESULTATS.md`, `docs/DIAGNOSTIC_V3.md`).

1. **Ouverture** (30 s) — *Mes dossiers* : 55 dossiers, dont 50 avec au moins un écart. Rappeler qu'un écart n'est pas une fraude.
2. **Le parcours simple** (2 min) — `Facture1_04`. Le dossier s'ouvre sur « 1 écart à examiner » ; cliquer **Examiner les écarts**.
   - À gauche, l'agrandissement réel de la case : 818,97 €.
   - À droite, la ligne du fichier, positions 42 à 49 surlignées : 818,98 €.
   - Une note indique que le fichier est lui-même incohérent : ses lignes totalisent 818,97 €.
   - Cliquer **Confirmer l'écart** : le logiciel indique que tout est décidé.
3. **Une prestation absente** (45 s) — `Facture1_09` : PH7 est facturée mais n'apparaît pas sur le bordereau. Le dossier affiche « Montant concerné », pas une « différence ».
4. **Le fichier mal formé** (1 min 30) — `Facture2_06`.
   - Le bandeau explique qu'un blanc a été inséré en position 11 et que la lecture a été réalignée. Le réalignement est démontré par 4 vérifications internes au fichier, sans jamais utiliser le bordereau.
   - Il reste 1 écart réel (n° FINESS 490002137 contre 490002037), au lieu de 11 fausses anomalies en version 2.0.
   - La ligne d'origine du fichier est conservée et surlignée.
5. **Le bordereau d'un autre dossier** (45 s) — `Facture2_04` : le signal « Bordereau d'un autre dossier ? » indique que le n° de facture lu sur le bordereau est celui de `Facture2_03`.
6. **R01 et la convention** (45 s) — dans **Détails techniques** d'un R01 : la lecture littérale (12278*0) et la convention (12278*01) sont présentées. Puis, dans *Règles et conventions*, montrer qu'une décision de la MSA peut être enregistrée avec sa référence.
7. **Le mode expert** (1 min) — **Autres actions → Mode expert** : les 15 zones, les 22 contrôles et les lectures OCR, inchangés par rapport à la version 2.0.
8. **Pilotage** (1 min 30) — compte superviseur, *Qualité et validation*.
   - La matrice de confusion affiche « indisponible » : aucune validation humaine n'a encore été saisie. C'est volontaire, aucun taux n'est inventé.
   - Saisir une validation, puis montrer que la mesure se calcule avec son effectif.
   - Rappeler que le n° d'assuré est masqué dans la liste des écarts et dans les exports.

Message de clôture :
- **Pour l'agent** : un parcours en quatre étapes, avec la preuve dans les deux documents.
- **Pour la caisse** : des alertes dont la cause est démontrée, des incertitudes explicites, un référentiel de validation humaine pour mesurer, et des décisions tracées.
