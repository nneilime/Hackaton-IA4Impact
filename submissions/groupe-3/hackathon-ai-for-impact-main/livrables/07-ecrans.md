# Écrans clés

Les 5 écrans de la fiche (§10, p. 6-7), plus l'écran de retour d'expérience. Charte liO à récupérer sur lio-occitanie.fr. Règle commune : **chaque pastille porte une icône et un texte**, jamais une couleur seule.

## Écran 1 : « Mon projet »

- **Objectif :** décrire la sortie en une phrase, comme on parlerait à un collègue.
- **Contenu :** grande zone de texte avec le micro, puis le formulaire prérempli par l'IA (classe, thème, élèves, accompagnateurs, date, horaires, lieu de départ, gare facultative). La gare trouvée s'affiche avec sa distance.
- **Composants :** zone de texte, bouton micro, formulaire éditable, bouton principal.
- **Message rassurant :** « Vous pourrez tout modifier avant de chercher. »

```text
┌──────────────────────────────────────────────────────────┐
│ liO  Copilote du voyage scolaire                         │
├──────────────────────────────────────────────────────────┤
│ Que souhaitez-vous faire découvrir à vos élèves ?        │
│ ┌──────────────────────────────────────────────────┐ 🎙 │
│ │ Classe de 5e, Moyen Âge, 42 élèves et 4 adultes… │    │
│ └──────────────────────────────────────────────────┘    │
│ Ce que j'ai compris :                                    │
│  Classe [5e]   Thème [Moyen Âge]   Élèves [42]  Adultes [4]
│  Date [12/11/2026]   Départ après [08:00]  Retour avant [19:00]
│  Départ [Collège de Foix]  → 🚉 Gare de Foix (900 m)     │
│ Vous pourrez tout modifier avant de chercher.            │
│                          [ Trouver des destinations → ]  │
└──────────────────────────────────────────────────────────┘
```

## Écran 2 : « Où aller ? »

- **Objectif :** choisir parmi 3 idées de sorties adaptées au programme.
- **Contenu :** une carte par destination avec l'intérêt pédagogique, les activités, le temps de trajet, l'accès gare → site et l'indice de confiance.
- **Composants :** cartes de destination, pastilles, bouton « Voir les trains ».
- **Message rassurant :** « Ces 3 destinations sont accessibles en train liO depuis Foix. »

```text
┌─────────────────┬─────────────────┬─────────────────┐
│ Toulouse        │ Carcassonne     │ [3e site]       │
│ Saint-Sernin    │ Cité médiévale  │                 │
│ Art roman,      │ Ville fortifiée │                 │
│ pèlerinages     │                 │                 │
│ 🚆 1h15 direct  │ 🚆 2h, 1 corresp│                 │
│ 📍 18 min à pied│ 🚌 bus urbain   │                 │
│ 🟢 84/100       │ 🟠 71/100       │                 │
│ [Voir trains →] │ [Voir trains →] │ [Voir trains →] │
└─────────────────┴─────────────────┴─────────────────┘
```

## Écran 3 : « Comment y aller ? »

- **Objectif :** vérifier que le groupe peut partir et revenir, et comprendre pourquoi.
- **Contenu :** trains aller et retour, jauge, temps gare → site avec la marge, les contrôles en pastilles, l'indice détaillé et l'explication de l'IA. Si l'indice est rouge, l'alternative apparaît juste en dessous.
- **Composants :** frise du trajet, jauge, liste de pastilles, indice dépliable, encadré « alternative ».
- **Message rassurant :** « Chaque point est vérifié sur les données SNCF. Ce qui n'est pas garanti est signalé. »

```text
┌──────────────────────────────────────────────────────────┐
│ Foix → Toulouse Matabiau → Saint-Sernin  · jeu. 12 nov.  │
│ Aller  🚆 09:12 → 10:27  train 871234  · 📍 18 min à pied │
│ Retour 🚆 15:40 → 16:55  train 871251                     │
│                                                          │
│ Places groupe : 50 · 10 sous option · 40 disponibles     │
│ 1 groupe positionné                                      │
│ 🔴 Capacité insuffisante : 40 places pour 46 voyageurs   │
│                                                          │
│ ┌ Cette proposition n'est pas adaptée à votre groupe : ┐ │
│ │ il manque 6 places sur le train de 09:12.            │ │
│ │ Alternative : train 871238 à 10:12, 50 places        │ │
│ │ disponibles, arrivée 35 min avant la visite.         │ │
│ │ 🔐 Confiance 84/100 🟢   [ Voir le détail ▾ ]         │ │
│ └──────────────────────────────────────────────────────┘ │
│ ✅ Train autorisé aux groupes   ✅ Retour avant 19h       │
│ ⚠️ Retour hors plage 9h-16h : étude au cas par cas       │
│              [ Comparer ]  [ Choisir l'alternative → ]   │
└──────────────────────────────────────────────────────────┘
```

## Écran 4 : « Comparer »

- **Objectif :** choisir entre 2 ou 3 propositions sans tout relire.
- **Contenu :** tableau sur les 6 critères de la fiche (intérêt pédagogique, simplicité du trajet, accessibilité, fiabilité, disponibilité, satisfaction des enseignants).
- **Composants :** tableau comparatif, meilleure valeur surlignée par ligne, bouton de choix par colonne.
- **Message rassurant :** « La meilleure option sur chaque critère est surlignée. »

```text
┌─────────────────────┬──────────────┬──────────────┐
│                     │ Saint-Sernin │ Carcassonne  │
├─────────────────────┼──────────────┼──────────────┤
│ Intérêt pédagogique │ ★★★          │ ★★★          │
│ Simplicité trajet   │ direct  ✦    │ 1 corresp.   │
│ Accessibilité       │ 18 min ✦     │ bus urbain   │
│ Fiabilité           │ 95 % ✦       │ 91 %         │
│ Disponibilité       │ 50/50 ✦      │ 50/50 ✦      │
│ Satisfaction        │ pas de retour│ ❤️ 92 %  ✦   │
├─────────────────────┼──────────────┼──────────────┤
│                     │ [Choisir]    │ [Choisir]    │
└─────────────────────┴──────────────┴──────────────┘
```

## Écran 5 : « Pré-réserver »

- **Objectif :** envoyer la demande et savoir exactement où elle en est.
- **Contenu :** récapitulatif, e-mail de contact, frise des 4 statuts avec l'étape actuelle, référence de dossier, bouton pour télécharger la fiche récapitulative.
- **Composants :** récapitulatif, champ e-mail, frise de statuts, bouton.
- **Message rassurant :** le texte exact de la fiche, « Demande de pré-réservation transmise — confirmation en attente ». Le mot « confirmé » n'apparaît jamais avant la vraie confirmation.

```text
┌──────────────────────────────────────────────────────────┐
│ Dossier LIO-2026-000123                                  │
│ Proposition ✔ ─ Option ✔ ─ ● Pré-réservation ─ Confirmation
│                                                          │
│ Demande de pré-réservation transmise —                   │
│ confirmation en attente                                  │
│ Un chargé de clientèle SNCF vous répond par e-mail.      │
│                                                          │
│ [ Télécharger la fiche récapitulative ]                  │
└──────────────────────────────────────────────────────────┘
```

## Écran 6 : « Votre retour »

- **Objectif :** en moins d'une minute, dire comment s'est passée la sortie.
- **Contenu :** 5 critères (satisfaction globale, adaptation du train au groupe, accès gare → site, sentiment de confiance, recommandation) et un commentaire libre.
- **Composants :** échelles de 1 à 5, bouton ❤️ « je recommande », zone de commentaire.
- **Message rassurant :** « Votre avis aide les prochains enseignants : il entre dans l'indice de confiance de cette sortie. »

```text
┌──────────────────────────────────────────────────────────┐
│ Comment s'est passée votre sortie à Saint-Sernin ?       │
│ Satisfaction globale        ☆☆☆☆☆                        │
│ Train adapté au groupe      ☆☆☆☆☆                        │
│ Accès gare → site           ☆☆☆☆☆                        │
│ Sentiment de confiance      ☆☆☆☆☆                        │
│ Recommanderiez-vous ?       [ ❤️ Oui ]  [ Non ]          │
│ Un commentaire ? ______________________________________  │
│                                       [ Envoyer → ]      │
└──────────────────────────────────────────────────────────┘
```
