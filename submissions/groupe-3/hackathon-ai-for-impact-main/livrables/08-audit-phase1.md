# Audit phase 1 : UI, UX, accessibilité et code

Audit en lecture seule du site Tchouette (branche Mohamed-Front, 10 octobre 2026). 8 auditeurs (rendu réel à 1440 et 375 px, accueil, recherche, fin de parcours, shell et vote, duplication et valeurs en dur, accessibilité, back et données) ont relevé 186 constats ; chacun a été contre-vérifié par un relecteur sceptique (185 confirmés, 1 réfutés), puis les doublons ont été fusionnés.

## Synthèse

- **L'indice de confiance, chiffre central du produit, se contredit d'un écran à l'autre.**
  - Une destination affiche « 90 Fiable » grâce à un trajet d'un autre jour que celui demandé.
  - Un trajet refusé affiche 84 en rouge, juste au-dessus d'un 78 en orange.
  - Sur Comparer, « Meilleur » couvre 14 cellules sur 18 et la page annonce « 6 critères sur 6 ».
  - Voir #2, #5 et #6.
- **« Comment y aller ? » s'ouvre sur un refus.** La première carte est rouge. Le trajet présélectionné tombe un autre jour, alors qu'un trajet valable existe à la date demandée, et il est hors de l'écran. Le bouton « Pré-réserver » est pourtant déjà actif, et rien ne dit que la date a changé (#3, #4).
- **Le premier écran ne fait pas comprendre la valeur en 10 s.**
  - Il ne dit ni à qui l'outil s'adresse ni ce qu'il vérifie.
  - La consigne revient 4 fois et jusqu'à 4 mascottes s'animent en même temps.
  - La promesse « sait dire non » est cachée sous la barre d'action.
  - Sur téléphone, le champ de saisie n'est pas visible.
  - Voir #8 à #11 et #16.
- **Des résultats faux sont présentés comme justes.**
  - 4 thèmes suggérés sur 10 donnent des destinations hors sujet, annoncées comme pertinentes.
  - Après modification de la demande, l'app réaffiche les anciens résultats et peut pré-réserver l'ancienne proposition.
  - Une date passée est acceptée.
  - Voir #1, #7 et #17.
- **La fin du parcours brouille l'état réel de la demande.**
  - La ligne des étapes coche « Comparer » sans qu'il y ait eu de comparaison, et « Pré-réserver » rouvre un formulaire vide.
  - Le récapitulatif ressemble à un vrai billet, et le dossier a pour titre une simple référence.
  - La suite de la démo est cachée, et la contre-proposition mène à une erreur 409.
  - Voir #30, #35 à #38, #42 et #43.
- **Une même notion change de nom selon l'écran.** Le niveau d'indice a 4 jeux de libellés. On lit aussi « Meilleure » ou « Recommandé », « liO » ou « SNCF », « Adultes » ou « Accompagnateurs ». L'or sert à la fois de couleur de marque et d'alerte (#25, #33, #49 à #51).
- **Brancher les vraies données réserve des surprises.**
  - Une option de démo est présentée comme réelle.
  - La règle R1 repose sur une hypothèse non signalée, et R8 sur un simple rectangle.
  - Les barèmes, calibrés sur la démo, feraient passer la plupart des trajets en orange.
  - Voir #55 à #58.

## Tableau d'audit

| # | Problème | Écran / composant | Impact | Effort | Catégorie | Référence |
|---|---|---|---|---|---|---|
| 1 | Les thèmes suggérés (4 sur 10 hors catalogue, « Sciences et espace » ramené à « Sciences et nature ») donnent des destinations hors sujet, annoncées comme correspondant au thème. | Accueil · formulaire, champ Thème | Élevé | M | UX | demande.ts:41 ; themes.py:6 |
| 2 | La note d'une destination reprend le meilleur trajet toutes dates confondues : « 90 Fiable » vient du 13 nov., alors que le 12 nov. demandé est rouge ou orange. | Destinations · CarteDestination | Élevé | M | UX | propositions.py:294 ; CarteDestination.tsx:166 |
| 3 | La page s'ouvre sur une carte rouge « Pas adapté ». Le trajet présélectionné (autre jour) est sous la barre, le changement de date n'est jamais dit, et le h2 compte les trajets refusés. | Trajets · liste + barre d'action | Élevé | M | UX | Trajets.tsx:55 ; propositions.py:275 |
| 4 | La présélection « Meilleure » ignore la date demandée : elle retient l'alternative du 13 nov. alors qu'un trajet orange existe le 12. Comparer la recommande sans aucun signal « Autre date ». | Trajets · présélection ; Comparer | Élevé | M | UX | Trajets.tsx:151 ; Comparer.tsx:242 |
| 5 | Un trajet bloqué affiche son score brut (84 rouge au-dessus d'un 78 orange), et Comparer peut lui donner « Meilleur » en fiabilité. | Trajets / Comparer · anneau d'indice | Élevé | S | UX | IndiceConfiance.tsx:23 ; confiance.py:25 |
| 6 | « Meilleur » apparaît sur tous les ex aequo (14 cellules sur 18), et la bulle compte les égalités comme des victoires (« 6 critères sur 6 »). | Comparer · tableau + bulle | Élevé | S | UX | Comparer.tsx:71 ; Comparer.tsx:314 |
| 7 | Modifier la demande ne vide pas le cache : les anciennes destinations et les anciens trajets reviennent, et la pré-réservation part avec l'ancienne proposition et la nouvelle demande. | transverse front · VoyageContext | Élevé | S | Code | VoyageContext.tsx:73 ; Destinations.tsx:101 |
| 8 | Le premier écran ne dit ni le public (« scolaire » n'apparaît que dans un sous-titre pâle) ni ce qui est vérifié (places, accès, droit de dire non). La phrase d'accroche est masquée sur mobile. | Accueil · intro et en-tête | Moyen | S | UX | Accueil.tsx:127 ; HeaderTrain.tsx:99 |
| 9 | Sur téléphone, le champ du chat et « Essayer l'exemple » sont sous la ligne de flottaison et sous la barre collante. Seul un bouton désactivé est visible. | Accueil · chat à 375 × 812 | Moyen | M | UX | ChatTchouette.tsx:136 ; Accueil.tsx:118 |
| 10 | À l'arrivée, « racontez » apparaît 4 fois et la liste de ce qui manque 3 à 4 fois. Ces messages d'état sont écrits à 5 endroits du code. | Accueil · guide, h1, bulle, billet, barre | Moyen | M | UX | etapes.ts:36 ; Accueil.tsx:52 |
| 11 | Jusqu'à 4 Tchouette animées en boucle (l'intro qui salue, la bulle qui « parle » au-dessus du champ), plus le train toutes les 11 s, sans moyen de mettre en pause (WCAG 2.2.2). | Accueil · mascottes ; bandeau | Moyen | S | Visuel | Accueil.tsx:84 ; animation.tsx:28 |
| 12 | Quand la demande est complète, Tchouette la récapitule deux fois (« C'est noté… », « Je récapitule… », environ 85 mots), alors que le billet l'affiche déjà. | Accueil · réponse du chat | Moyen | S | UX | chat.py:201 ; chat.py:225 |
| 13 | Si la gare est introuvable, le front ignore `gare_depart` et affiche « Ajustez l'effectif », « 6/6 compris » ou « il manque encore gare_depart ». | Accueil · barre, billet, formulaire | Moyen | S | UX | demande.ts:84 ; FormulaireProjet.tsx:279 |
| 14 | La puce « Voir les trains » renvoie la phrase au chat et tourne en boucle, car la navigation est déduite du texte. Une gare saisie à la main devient une gare factice avec lat/lon à 0. | Accueil · réponses rapides | Moyen | M | Code | ChatTchouette.tsx:86 ; FormulaireProjet.tsx:131 |
| 15 | En mode formulaire, le billet recopie les valeurs tapées : deux jauges, deux alertes J-21 et trois messages sur l'effectif. | Accueil · formulaire + billet | Moyen | S | UX | FormulaireProjet.tsx:478 ; BilletDemande.tsx:161 |
| 16 | « Une ligne, quatre arrêts » dessine un second parcours qui contredit les 6 étapes de l'en-tête, et ce bloc tombe sous la barre collante. | Accueil · LignePromesse | Moyen | S | UX | LignePromesse.tsx:13 ; Accueil.tsx:203 |
| 17 | L'API accepte une date passée (indice vert, pré-réservation en 200), et le front la laisse passer par l'onglet Chat : le billet affiche à la fois « déjà passée » et « Tout y est ! ». | Accueil → API | Moyen | S | Code | controles.py:186 ; demande.ts:102 |
| 18 | FormulaireProjet fait 685 lignes : le motif de champ est recopié 11 fois, les ids viennent de deux sources, et l'état d'envoi, tenu deux fois, se perd quand on change d'onglet. | Accueil · FormulaireProjet | Moyen | L | Code | FormulaireProjet.tsx:199 ; Accueil.tsx:77 |
| 19 | La durée, le temps gare → site et l'anneau d'indice sont en bas de carte, sous la barre collante en 1366 × 768. | Destinations · CarteDestination | Moyen | S | Visuel | CarteDestination.tsx:118 |
| 20 | « Horaires indicatifs (jeudi type) » n'apparaît qu'à la fin de la bulle repliée, et l'API n'expose aucun champ structuré pour cette information. | Destinations / Trajets · bulle Tchouette | Moyen | M | UX | BulleTchouette.tsx:22 ; trains.py:119 |
| 21 | Avant les cartes : la consigne est répétée 3 fois, la bulle redit l'intro et le bandeau, et « Faire voter » est le seul bouton plein. Sur mobile, la première carte commence à y ≈ 660 sur 812. | Destinations · en-tête de liste | Moyen | M | UX | Destinations.tsx:248 ; Destinations.tsx:271 |
| 22 | L'intérêt pédagogique (3 lignes), les activités, l'aide et l'astuce sont tronqués. Le texte complet n'existe qu'en `title`, invisible au clavier et au toucher. | Destinations · cartes ; barres | Moyen | M | Accessibilité | CarteDestination.tsx:119 ; BarreAction.tsx:51 |
| 23 | Chaque carte montre tout d'emblée (2 frises, 2 plans de 50 sièges, une légende) : environ 430 px sur ordinateur, 1000 px sur mobile. L'orange « tout juste » y côtoie l'anneau vert. | Trajets · CarteProposition | Moyen | M | UX | CarteProposition.tsx:178 ; JaugePlaces.tsx:73 |
| 24 | Jargon visible : « sous option », « manquantes », numéro de train seul et en double, « corresp. ». « Emport » et les codes R sont dans les parties repliées. | Trajets · jauge, frise, contrôles | Moyen | M | UX | JaugePlaces.tsx:85 ; FriseTrajet.tsx:98 |
| 25 | « Meilleure » (Trajets) et « Recommandé » (Comparer) désignent des trajets différents avec le même trophée. « Sélectionnée » a deux styles, et une carte peut porter jusqu'à 5 badges. | Trajets / Comparer · badges | Moyen | S | Visuel | CarteProposition.tsx:119 ; Comparer.tsx:356 |
| 26 | En bas de page, le toast « Ajouté à la comparaison » couvre le bouton « Pré-réserver » pendant 3,5 s. Sur le vote, le toast répète mot pour mot la bulle. | Trajets · barre ; Vote élève | Moyen | S | UX | Trajets.tsx:386 ; VoteEleve.tsx:207 |
| 27 | À 375 px, l'alerte rouge s'écrase en une colonne de 1 ou 2 mots, parce que le lien reste sur la même ligne. Le numéro de train se colle à l'heure. | Trajets · CarteProposition mobile | Moyen | S | Visuel | CarteProposition.tsx:156 ; FriseTrajet.tsx:96 |
| 28 | Les critères de l'indice et les catégories de site sont reconnus par regex sur des libellés français. Un renommage donne « Non évalué » sans erreur, et les icônes du vote sont déjà fausses. | Comparer · contrat CritereIndice | Moyen | M | Code | Comparer.tsx:62 ; schemas.py:110 |
| 29 | À 375 px, le tableau est coupé (la colonne Critère prend environ 47 %), sans indice de défilement, dans une zone qui ne reçoit pas le focus. | Comparer · tableau mobile | Moyen | M | Visuel | Comparer.tsx:342 |
| 30 | Le récapitulatif imite un titre de transport (« Billet récapitulatif », faux code-barres) sans mention « demande non confirmée ». | Pré-réserver / Dossier · BilletRecap | Moyen | S | UX | BilletRecap.tsx:138 ; BilletRecap.tsx:239 |
| 31 | Sur mobile, le champ e-mail commence à 1461 px du haut. Le bouton désactivé demande l'e-mail alors qu'aucun champ n'est visible. | Pré-réserver · mobile | Moyen | S | UX | PreReservation.tsx:132 |
| 32 | La frise « Ce qui va se passer » place « Vous êtes ici » sur Proposition (étape 1 sur 4), alors que la page est l'étape 5 sur 6. | Pré-réserver · FriseStatuts | Moyen | S | UX | PreReservation.tsx:145 ; FriseStatuts.tsx:63 |
| 33 | La promesse est incohérente : « chargé de clientèle liO » ou « SNCF », « option posée » contre « rien n'est réservé », « deux » ou « trois minutes », et un statut nommé de 3 façons. | Pré-réserver / Dossier · textes | Moyen | S | UX | etapes.ts:78 ; PreReservation.tsx:147 |
| 34 | Rien ne dit quand SNCF répondra, combien de temps tient l'option, ni ce qu'il reste à faire une fois la sortie confirmée. | Pré-réserver / Dossier · suites | Moyen | S | UX | PreReservation.tsx:142 ; Dossier.tsx:389 |
| 35 | L'arrivée sur le dossier n'a aucun moment de succès : le h1 est la référence « LIO-2026-… » et la confirmation d'envoi n'est qu'un sous-titre gris. | Dossier · intro | Moyen | S | UX | Dossier.tsx:148 ; Dossier.tsx:181 |
| 36 | Seuls les boutons « Simuler… », en btn-sm sous le billet près de la barre, font avancer la démo. Pendant l'attente, la barre n'a pas d'action principale. | Dossier · encadré Démonstration | Moyen | M | UX | Dossier.tsx:234 ; Dossier.tsx:331 |
| 37 | Après une contre-proposition, l'encadré de démo reste actif : chaque clic renvoie un 409 « statut CONTRE_PROPOSITION », et « Réessayer » rejoue l'échec. | Dossier · encadré Démonstration | Moyen | S | UX | Dossier.tsx:133 ; dossiers.py:135 |
| 38 | La contre-proposition est inexploitable : les trains sont noyés dans une phrase d'environ 50 mots, il n'y a pas de bouton « Accepter », le billet reste sur l'ancien trajet et l'option n'est jamais libérée. | Dossier · contre-proposition | Moyen | L | UX | Dossier.tsx:342 ; dossiers.py:141 |
| 39 | L'état est répété sur 5 surfaces (pastille, intro, frise, encart, historique). Le message du serveur, de 17 à 50 mots, occupe l'intro, et l'historique est toujours déplié. | Dossier · vue générale | Moyen | M | UX | Dossier.tsx:170 ; config.py:67 |
| 40 | Le retour peut être envoyé avant la sortie et hors CONFIRMATION (le serveur ne refuse qu'ANNULE), et il modifie la satisfaction du site. Le commentaire n'est pas borné côté serveur. | Retour · formulaire et API | Moyen | S | Code | retours.py:17 ; etapes.ts:130 |
| 41 | Notation par étoiles : focus clavier invisible, étoiles vides à 1,51:1, cibles de 24 px collées les unes aux autres. | Retour · notation | Moyen | M | Accessibilité | Retour.tsx:118 |
| 42 | La ligne des étapes impose « Comparer » alors que le bouton principal saute cette étape : la gare est alors cochée et « pas encore disponible » à la fois. Les coches ne reflètent pas l'avancement réel, et il n'y a pas de gare « Suivi ». | Shell · LigneEtapes | Moyen | M | UX | LigneEtapes.tsx:62 ; etapes.ts:16 |
| 43 | Après l'envoi, la gare « Pré-réserver » (étape courante sur le dossier) rouvre le formulaire vide. Un nouvel envoi ignore le nouvel e-mail. | Shell · LigneEtapes | Moyen | S | UX | etapes.ts:127 ; PreReservation.tsx:106 |
| 44 | Le cadre collant prend environ 197 px (en-tête de 137 px et barre de 60 px), soit près de 30 % d'un portable en 1366 × 768. | Shell · AppShell, BarreAction | Moyen | M | UX | AppShell.tsx:13 ; BarreAction.tsx:77 |
| 45 | Tchouette parle par 3 canaux non coordonnés (astuce du guide, intro, bulle de la barre). L'astuce devient périmée (« Donnez la classe… » alors que tout est rempli), et « rien n'est réservé » apparaît 3 fois. | Shell · GuideEtape, BarreAction | Moyen | M | UX | GuideEtape.tsx:17 ; etapes.ts:38 |
| 46 | L'app n'offre aucun moyen de retrouver un dossier : la référence ne vit qu'en sessionStorage et il n'y a pas de champ « Suivre une demande ». | Shell · « Mon dossier » | Moyen | S | UX | VoyageContext.tsx:52 ; AppShell.tsx:40 |
| 47 | Le changement d'étape n'est pas annoncé : le titre d'onglet reste figé, le focus retombe sur `<body>` et aucune zone live ne signale la nouvelle page. | Shell · AppShell | Moyen | S | Accessibilité | AppShell.tsx:44 ; index.html:8 |
| 48 | Le bouton d'envoi des 3 formulaires est `disabled` : Entrée ne fait rien, la validation au clic et le focus sur la première erreur ne s'exécutent jamais, et la raison n'est pas lue au Tab. | Shell · BarreAction (Accueil, Pré-réserver, Retour) | Moyen | M | Accessibilité | BarreAction.tsx:108 ; Accueil.tsx:211 |
| 49 | Le niveau d'indice a 4 jeux de libellés (« Vigilance », « Point de vigilance », « Confiance moyenne », « Pas adapté (à votre groupe) »), et l'accès vert en a 2 (« facile », « simple »). | transverse front · niveaux | Moyen | S | UX | niveaux.ts:12 ; dossier/format.ts:89 |
| 50 | La demande change de mots et de format selon l'écran : « Adultes », « acc. » ou « accompagnateurs », « Classe » ou « Niveau », et la date s'affiche en 3 formats. | transverse front · billet, bandeau, récapitulatif | Moyen | S | UX | BilletDemande.tsx:157 ; BandeauDemande.tsx:28 |
| 51 | L'or #ffcd00 sert à la fois de couleur de marque et d'avertissement, et de trait sur fond clair à 1,38 à 1,50:1 (anneau Vigilance, sièges, étape Contre-proposition). | transverse front · thème lio | Moyen | S | Visuel | index.css:33 ; IndiceConfiance.tsx:12 |
| 52 | Trois intros d'écran différentes (mascotte de 64 ou 72 px, disque or qui change de côté, rail), et 11 tailles de mascotte sans échelle commune. | transverse front · intros | Moyen | M | Visuel | IntroEcran.tsx:18 ; IntroEtape.tsx:27 |
| 53 | Des composants et utilitaires existent en double et divergent : PastilleNiveau ×2, format.ts ×3 (fonctions `pluriel` incompatibles), useEcranEtroit ×2, et deux BulleTchouette homonymes. | transverse front · components/voyage et dossier | Moyen | M | Code | dossier/format.ts:80 ; voyage/format.ts:53 |
| 54 | Quand l'API est indisponible, l'enseignant lit « erreur 502 » ou « Vérifiez que l'API tourne sur le port 8000 ». Côté vote, le message mêle vouvoiement et tutoiement. | transverse front · client.ts | Moyen | S | UX | client.ts:36 ; client.ts:41 |
| 55 | L'option fictive de 10 places et les retours simulés sont insérés même en mode SNCF. R9 annonce « un autre groupe est positionné » sans dire qu'il s'agit d'une simulation. | back · build_db, R9 | Moyen | S | Code | build_db.py:249 ; controles.py:211 |
| 56 | openpyxl n'est pas installé : la liste des trains groupes en .xlsx est ignorée, R1 repose sur une hypothèse non signalée, et /api/sante répond quand même « sncf ». | back · ETL | Moyen | S | Code | build_db.py:102 ; requirements.txt:1 |
| 57 | R8 (établissement en Occitanie) se fonde sur un rectangle : Agen, Avignon, Arles et Andorre passent en vert. L'information de l'API Adresse est jetée. | back · geo, R8 | Moyen | S | Code | geo.py:55 ; comprendre.py:364 |
| 58 | Les barèmes de l'indice sont codés en dur et calibrés sur la démo. Avec les vraies données (régularité médiane de 86 %, suppressions autour de 6,6 %), la plupart des trajets passeraient en orange. | back · confiance | Moyen | M | Code | confiance.py:85 ; confiance.py:101 |
| 59 | Le catalogue est codé en dur (24 sites). DATAtourisme (53 228 POI) et lieux_occitanie ne sont branchés sur rien. Il n'y a pas de dictionnaire de données, et le MLD diverge de db.py. | back · ETL, catalogue | Moyen | L | Code | catalogue.py:20 ; commun.py:25 |
| 60 | Les 45 tests ne couvrent ni la date passée, ni R8 en rouge, ni les bornes d'effectif, ni un thème inconnu, ni l'import xlsx. Aucun outil de couverture n'est installé. | back · tests | Moyen | M | Code | conftest.py:15 ; test_regles.py:48 |
| 61 | L'onglet actif, en bleu nuit plein, concurrence la puce « Essayer l'exemple ». « Envoyer » et le micro sont en btn-md. | Accueil · bascule, chat | Faible | S | Visuel | Accueil.tsx:151 ; ChatTchouette.tsx:295 |
| 62 | Le formulaire affiche toujours 5 champs facultatifs, mais seuls 2 portent la mention « (facultatif) ». | Accueil · formulaire | Faible | M | UX | FormulaireProjet.tsx:534 |
| 63 | Les placeholders sont à 3,25:1, et « 42 » ou « 4 » ressemblent à des valeurs déjà saisies. | Accueil · chat, formulaire | Faible | S | Accessibilité | ChatTchouette.tsx:273 ; FormulaireProjet.tsx:439 |
| 64 | Sous 640 px, la pastille d'état du chat ne s'exprime que par la couleur. | Accueil · en-tête du chat | Faible | S | Accessibilité | ChatTchouette.tsx:143 |
| 65 | Le contour de focus des boutons or sur fond blanc (puce d'exemple, « Retirer de la comparaison ») est à 1,50:1. | Accueil · puce d'exemple ; Trajets | Faible | S | Accessibilité | ChatTchouette.tsx:244 ; Trajets.tsx:421 |
| 66 | « Trois sorties » et « 6 critères de la fiche » sont écrits en dur, sans lien avec les données. | Destinations · intro ; Comparer | Faible | S | Code | Destinations.tsx:166 ; Comparer.tsx:314 |
| 67 | Le lien « Modifier » du bandeau fait environ 16 px de haut et n'est souligné qu'au survol. | Destinations / Trajets · bandeau | Faible | S | Accessibilité | Destinations.tsx:180 ; Trajets.tsx:241 |
| 68 | La fin d'une recherche n'est pas annoncée : la zone `role="status"` est détruite au moment où le résultat arrive. | Destinations / Trajets · chargement | Faible | S | Accessibilité | EtatsEcran.tsx:53 ; Destinations.tsx:169 |
| 69 | Au repos, le contour des cartes est à 1,26:1 et le bouton radio est réservé aux lecteurs d'écran. Le rond vide du vote est lui aussi à 1,26:1. | Destinations · cartes ; Vote | Faible | S | Accessibilité | CarteDestination.tsx:22 ; CarteChoix.tsx:101 |
| 70 | L'heure de visite est calculée mais absente du contrat : la carte n'affiche qu'une marge. | Trajets · carte, contrat | Faible | S | UX | propositions.py:100 ; CarteProposition.tsx:183 |
| 71 | Le bouton « Choisir » de la colonne recommandée fait doublon avec « Pré-réserver X » dans la barre, et « Retirer » a le même poids visuel. | Comparer · pied de tableau | Faible | S | UX | Comparer.tsx:400 ; Comparer.tsx:459 |
| 72 | La logique de statut est éparpillée dans 5 fichiers. SUITES.OPTION et le badge OPTION ne servent jamais. | Dossier · statuts | Faible | M | Code | Dossier.tsx:133 ; dossier/format.ts:101 |
| 73 | L'écran Merci annonce l'évolution de l'indice 3 fois et parle d'« indice du site », alors que le back dit « de votre trajet ». | Retour · écran Merci | Faible | S | UX | Retour.tsx:416 ; retours.py:42 |
| 74 | À 375 px, « Comment y aller ? » chevauche « Comparer », rien ne signale les gares hors champ, et le bandeau n'affiche que des icônes. | Shell · LigneEtapes, HeaderTrain mobile | Faible | S | Visuel | LigneEtapes.tsx:58 ; HeaderTrain.tsx:46 |
| 75 | La mention « Étape N sur 6 » (12 px) est à 4,42:1, juste sous le seuil de 4,5:1. | Shell · GuideEtape | Faible | S | Accessibilité | GuideEtape.tsx:34 |
| 76 | Le pied de page affiche « API non joignable » et « IA en mode démo » sous le titre « État du service ». | Shell · PiedDePage | Faible | S | UX | PiedDePage.tsx:24 |
| 77 | `scroll-smooth` n'est pas conditionné : le retour en haut à chaque changement de page reste animé, même avec « réduire les animations ». | Shell · index.html, AppShell | Faible | S | Accessibilité | index.html:2 ; AppShell.tsx:45 |
| 78 | Sur mobile, 37 boutons btn-sm et le champ e-mail en input-sm font 32 px, sous les 40 px fixés par DESIGN.md. | Shell · BarreAction et pages | Faible | S | Accessibilité | Trajets.tsx:436 ; PreReservation.tsx:162 |
| 79 | Les erreurs de champ, la raison du bouton désactivé et les alertes sont en 12 px, et le badge « Vous êtes ici » en 10 px. | Shell · textes d'interface | Faible | S | Accessibilité | FormulaireProjet.tsx:186 ; BarreAction.tsx:95 |
| 80 | États vides et d'erreur : 3 à 4 mises en page différentes, « Réessayer » proposé même sur des 404 ou 409 définitifs, barre d'action incohérente pendant l'erreur, bloc recopié une dizaine de fois. | Shell · états d'écran | Faible | M | UX | EtatsEcran.tsx:34 ; Trajets.tsx:249 |
| 81 | Sur l'écran projeté, en attente du premier vote, la page fait 919 px pour 900 : bulle sur 4 lignes, « ! » seul sur sa ligne, phrase qui répète la carte. | Vote · projection | Faible | S | Visuel | VoteAnimer.tsx:226 ; commentaires.ts:38 |
| 82 | Après la clôture, les opacités cumulées font tomber « N votes » à 3,78:1 et la commune à 2,3 à 3,55:1. « 100 % » passe sur deux lignes. | Vote · course, cartes | Faible | S | Accessibilité | CourseTrains.tsx:12 ; CarteChoix.tsx:29 |
| 83 | « Voir les trains » sur l'écran projeté dépend du sessionStorage de l'onglet, avec une destination factice comme repli. | Vote · projection | Faible | M | Code | VoteAnimer.tsx:176 ; vote.ts:94 |
| 84 | Sur l'écran projeté, un h2 précède le h1, et les écrans de chargement n'ont aucun h1. | Vote · titres | Faible | S | Accessibilité | CarteRejoindre.tsx:15 ; VoteAnimer.tsx:122 |
| 85 | Les deux dialogues de confirmation sont recopiés à la main, et `aria-labelledby` pointe vers un id défini dans un autre composant. | Vote · dialogues ; HeaderTrain | Faible | S | Code | VoteAnimer.tsx:183 ; HeaderTrain.tsx:141 |
| 86 | Les décorations Memphis dépassent 2 par écran (5 sur l'Accueil, rail de Destinations, étoiles et code-barres du Dossier, 15 confettis), et la mascotte flotte deux fois sur l'écran projeté. | transverse front · décor | Faible | S | Visuel | Accueil.tsx:121 ; Destinations.tsx:32 |
| 87 | Aucun token pour l'ombre dure (19 occurrences), le texte à 15 px, les animations en cascade et les rails (9 espacements). La palette est recopiée en hexadécimal dans 5 fichiers. | transverse front · thème | Faible | M | Code | index.css:48 ; Tchouette.tsx:24 |
| 88 | L'échelle typographique n'est pas tenue : h2 en 5 styles, chiffre clé sans palier lg, référence du dossier forcée à 24 px. | transverse front · titres | Faible | S | Visuel | Dossier.tsx:149 ; LignePromesse.tsx:53 |
| 89 | Les règles métier sont recopiées entre front et back (6 à 50 voyageurs, J-21, 08:00/18:00, champs obligatoires, meilleure proposition), et « 50 » ou « 21 jours » sont écrits en dur dans les textes. | transverse front · règles | Faible | M | Code | demande.ts:7 ; config.py:42 |
| 90 | Le code de chargement de l'API est recopié entre Destinations et Trajets, et la classe de conteneur l'est 9 fois. | transverse front · pages | Faible | M | Code | Destinations.tsx:70 ; Trajets.tsx:106 |
| 91 | Les pages font de 460 à 485 lignes (Dossier, Comparer, Retour, Trajets) et mêlent données, logique et rendu. | transverse front · pages | Faible | M | Code | Comparer.tsx:78 ; Dossier.tsx:84 |
| 92 | `--hauteur-header` n'est jamais lue, si bien que le récapitulatif collant est décalé de 23 à 64 px. Des exports, props et variantes ne servent à rien. | transverse front · code mort | Faible | S | Code | AppShell.tsx:21 ; Accueil.tsx:198 |
| 93 | Si l'on clique « Nouvelle sortie » pendant que Tchouette réfléchit, sa réponse réécrit l'ancienne demande. La session restaurée n'est pas validée. | transverse front · état | Faible | S | Code | useConversation.ts:68 ; VoyageContext.tsx:54 |
| 94 | rangAstuce écrit dans une Map de module pendant le rendu, à partir d'un tirage aléatoire. | transverse front · GuideEtape | Faible | S | Code | etapes.ts:141 |
| 95 | Le code n'est pas découpé : un élève qui vote charge toute l'application (536 Ko). | transverse front · App.tsx | Faible | S | Code | App.tsx:3 |
| 96 | L'API accepte un effectif négatif ou démesuré et une heure comme « 25:99 ». | back · schémas | Faible | S | Code | schemas.py:33 ; comprendre.py:349 |
| 97 | `_taux('0,80%')` renvoie 80 : tout taux de 1 % ou moins écrit en pourcentage serait multiplié par 100. | back · ETL | Faible | S | Code | build_db.py:65 |
| 98 | resoudre_gare parcourt tout le référentiel pour chaque arrêt, ce qui bloque le premier démarrage environ 1 min pendant la construction de la base. | back · ETL, démarrage | Faible | S | Code | build_db.py:139 ; main.py:28 |
| 99 | Il n'y a pas de couche d'accès aux données (41 requêtes SQL réparties dans 9 services), et la jauge est calculée deux fois. | back · services | Faible | L | Code | controles.py:47 ; dossiers.py:89 |
| 100 | Les services lèvent eux-mêmes des HTTPException, et le cas « même gare » renvoie une destination verte notée 0/100. | back · main.py, services | Faible | M | Code | main.py:133 ; dossiers.py:54 |
| 101 | Le contrat est laxiste : /destinations et /trajets n'exigent ni niveau ni thème, et la pré-réservation accepte une demande absente ou différente. Les types sont recopiés à la main. | back · contrat | Faible | M | Code | main.py:92 ; schemas.py:206 |
| 102 | Code mort côté back : fonctions de geo, colonnes jamais lues, `demande_id` toujours NULL, statut ANNULE inatteignable, positionnement jamais libéré. | back · services, schéma | Faible | M | Code | geo.py:85 ; dossiers.py:27 |
| 103 | Des valeurs sont écrites en dur dans les services : puces de sites, « grille 2026 », « 18:00 », et « 9h-16h » à 6 endroits. | back · services | Faible | S | Code | chat.py:192 ; controles.py:23 |
| 104 | Des utilitaires sont recopiés (distance, mois, heures), et il existe une dépendance circulaire entre app et etl. | back · utilitaires | Faible | S | Code | geo.py:68 ; db.py:295 |

## Données attendues pour remplacer les données fictives

Pour les 4 sources SNCF, une partie est déjà en place :
- `build_db.py` lit déjà ces fichiers, et `test_build_db.py` vérifie leur format.
- `db.py` passe tout seul sur ces données dès qu'elles sont présentes dans `data/`.

Les sites, les options des autres groupes, les retours et les communes n'ont encore aucune source réelle.

- **Trains autorisés aux groupes** (« Liste des trains groupes », xlsx, vers la table `train`)
  - Champs : numero (texte, sans « .0 »), autorise_groupe à 1 pour chaque train listé, capacite_groupe (50 par défaut aujourd'hui), axe, origine, destination.
  - Utiles si disponibles : période de validité, jours de circulation, plage horaire ouverte aux groupes.
  - Remplace l'hypothèse actuelle « tous les trains de Data_Hackathon.csv sont autorisés » (R1).
  - Prérequis : openpyxl.
- **Desserte** (« Détail desserte », xlsx, vers la table `desserte`)
  - Champs : date (AAAA-MM-JJ), train, ordre (rang de l'arrêt), code UIC (7-8 chiffres ou « StopPoint:OCETrain TER-8761xxxx »), stop, arr (HH:MM, vide à l'origine), dep (HH:MM, vide au terminus). jour_semaine est calculé.
  - Le vrai fichier va du 2026-02-01 au 2026-06-30 et couvre 309 arrêts.
  - Remplace la grille de `reseau_demo.py`. Hors de cette période, les horaires restent des horaires « jour type ».
- **Indicateurs mensuels** (Data_Hackathon.csv, séparateur « ; », vers `indicateur_mensuel` puis `fiabilite_train`)
  - Champs : Mois (en lettres), Année, N° Train, Axe, Origine / Destination, Frequentation, Taux régularité du train (« 63,20% »), Nombre de suppressions, Minutes perdues.
  - Manquent pour l'indice :
    - le taux de respect de l'emport, qui vaut 8 points (aujourd'hui fixé à 4 sur 8) ;
    - les circulations théoriques et réalisées (sinon recomptées depuis la desserte) ;
    - un taux de suppression explicite.
  - Les barèmes de `confiance.py` sont à recalibrer sur ces distributions.
- **Gares** (gares.json, open data SNCF, vers la table `gare`)
  - Champs : codes_uic (séparés par « ; », 8 chiffres), nom, position_geographique.lat et .lon.
  - À ajouter : commune et code département, nécessaires pour R8 et pour trouver la gare la plus proche.
- **Sites culturels** (DATAtourisme, vers `site_culturel`, remplace `catalogue.SITES`)
  - Correspondances :
    - id ← URI_ID_du_POI (qui sert aussi de source_url) ;
    - nom ← Nom_du_POI ;
    - commune ← Code_postal_et_commune (partie après « # ») ;
    - lat/lon ← Latitude/Longitude ;
    - interet_pedagogique ← résumé de Description ;
    - catégories ← Categories_de_POI : garder CulturalSite, Museum, Castle, ReligiousSite…, exclure EntertainmentAndEvent (9 537 lignes sur 53 228).
  - À calculer :
    - gare_uic (gare groupe la plus proche) ;
    - minutes_pied et minutes_pied_groupe (distance / 80 m par min × 1,3 + 5) ;
    - thèmes ramenés au vocabulaire canonique de `themes.py`, niveaux (CP à Tle), activités, richesse (1 à 3) ;
    - une catégorie stable pour les icônes du vote.
  - Absents de DATAtourisme, donc à marquer « à vérifier » : heure_ouverture, heure_fermeture, duree_visite_min, capacite_accueil (R10), acces_urbain, minutes_urbain, correspondances_urbain (R3).
- **Options des autres groupes** (table `positionnement`, remplace `POSITIONNEMENTS_SIMULES` et `_option_scenario`)
  - Champs : train_numero, date_sortie, nb_places, dossier_reference (null si le groupe est externe), est_simule. Jamais d'identité de groupe.
  - Source réelle : outil de réservation ou chargé de clientèle SNCF.
- **Retours d'expérience** (table `retour_experience`, remplace `RETOURS_SIMULES`)
  - Champs : dossier_reference, site_id, satisfaction, adaptation_train, acces_gare_site, confiance (de 1 à 5), recommande (0 ou 1), commentaire, cree_le, est_simule.
- **Communes** (remplace la table de repli `geo.COMMUNES`, 72 entrées)
  - Champs : nom, code INSEE, code département, lat/lon. Sources : COG ou API Geo.
- **Référentiels** (thèmes, niveaux, règles R2 et R7)
  - À exposer par l'API pour que le front cesse de recopier ses propres listes (10 thèmes au front contre 8 au back).
- **Tarifs** (information seulement, hors périmètre)
  - Grille groupe de 10 € (6 à 10 voyageurs) à 50 € (41 à 50 voyageurs) par train.

## Angles morts

- **Vérification en direct partielle.** Les serveurs de développement (5173 et 8000) ne répondaient pas pendant une bonne partie de l'audit. Beaucoup de constats reposent donc sur :
  - la lecture du code ;
  - des appels via TestClient ;
  - des captures faites sur une instance isolée (front sur 5187, back sur 8047) avec une copie de lio.db.

  Les scores dépendent aussi de l'état de la base : Saint-Sernin affiche 90 ou 85 selon qu'une pré-réservation existe déjà.
- **Mode LLM non testé.** Tout a tourné en mode démo, sans clé Anthropic. Ni la qualité des réponses de Tchouette, ni le reclassement des destinations par le modèle, ni la latence (jusqu'à environ 50 s avec relance) n'ont été évalués.
- **Pas de vraies données SNCF.** Le dossier data/ ne contient que DATAtourisme. L'effet des barèmes a été estimé à partir de visualisation/carte/data.js, pas mesuré dans l'application.
- **Appareils et conditions réelles.**
  - Le mobile n'a été testé qu'en émulation (375, 390 et 768 px), sans vrai téléphone iOS ou Android.
  - L'écran de vote n'a pas été vu sur un vidéoprojecteur en 1366 × 768 ou 1280 × 720.
  - La charge n'a pas été testée : 30 téléphones qui interrogent le serveur toutes les 2 s sur le Wi-Fi d'une école.
- **Accessibilité sans outils réels.** Aucun passage au lecteur d'écran (NVDA, VoiceOver), aucun test de zoom à 200 % ou d'affichage en 320 px, aucun test en contraste forcé. Les verdicts viennent du code et de calculs de contraste.
- **Compréhension en 10 s non mesurée.** Il n'y a eu ni test avec des enseignants ni chronométrage avec un jury fictif. Le scénario réel de la démo (script, ordre des écrans, appareil utilisé) n'a pas été audité.
- **Hors périmètre.**
  - Performance (Lighthouse, temps de chargement).
  - Sécurité et données personnelles : e-mail stocké, absence d'authentification, dossier accessible par simple référence séquentielle.
  - Concurrence : deux classes qui posent une option sur le même train.
  - Impression de la fiche.
  - Exactitude du contenu des 24 fiches de sites.
  - Les dossiers livrables/ et visualisation/.
- **Constat réfuté.** L'idée que toutes les animations et décorations sont inutiles a été réfutée, car DESIGN.md les prévoit. Seuls les écarts mesurables ont été retenus (#11 et #86).
