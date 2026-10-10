# Crédit : prêt personnel, auto, travaux, immobilier, simulation

Contenu d'exemple pour la démo : les taux, montants, âges et délais de cette fiche sont
fictifs.

## Les cinq informations à recueillir

Avant toute simulation, il faut les cinq. Les demander une à une, sans les annoncer ni
dire combien il en reste :

- le motif : voiture, travaux, rénovation énergétique, achat immobilier, ou autre
  projet personnel. Il fixe le type de prêt et son taux : le client n'a pas à le
  donner ;
- le montant à emprunter ;
- l'étalement : la durée du remboursement, en mois ou en années ;
- les ressources : les revenus nets du client chaque mois (salaire, pension,
  allocations) ;
- l'âge du client.

Pourquoi ces questions : uniquement pour faire le calcul. L'âge, parce qu'il faut être
majeur et que le crédit doit être remboursé avant 80 ans ; les revenus, pour vérifier
que la mensualité reste supportable (pas plus de 35 % des revenus). Rien n'est transmis
sans l'accord du client.

## Les options

- Prêt personnel : de 1 000 à 75 000 euros, sur 12 à 84 mois, TAEG fixe de 5,9 %.
- Prêt auto, véhicule neuf ou d'occasion : de 3 000 à 75 000 euros, sur 12 à 84 mois,
  TAEG fixe de 4,9 %.
- Prêt travaux : de 1 500 à 75 000 euros, sur 12 à 120 mois, TAEG fixe de 4,5 %.
  Pour la rénovation énergétique : TAEG de 3,9 %, et éco-prêt à taux zéro possible
  jusqu'à 50 000 euros sous conditions.
- Prêt immobilier : de 50 000 à 1 000 000 d'euros, sur 7 à 25 ans, taux indicatif de
  3,4 % hors assurance. Apport conseillé : 10 % du prix. Les mensualités de tous les
  crédits ne doivent pas dépasser 35 % des revenus. Étudié avec un conseiller.
- L'assistant ne propose pas de crédit renouvelable.

## Étapes

1. Recueillir les cinq informations. Aucun calcul avant de les avoir toutes.
2. Simulation immédiate et sans engagement (simulate_loan) : mensualité, taux, coût
   des intérêts.
3. Le client change la durée ou le montant : nouvelle simulation tout de suite, avec
   les mêmes autres réponses, sans rien redemander.
4. Quand le client le demande : transmission de la simulation à un conseiller
   (send_loan_to_advisor), puis récapitulatif au client, numéro de référence, et
   récapitulatif en PDF à télécharger dans l'application.
   - Prêt personnel, auto ou travaux : un conseiller crédit rappelle le client sous
     48 heures. Si le crédit est accordé : contrat lisible avec un lecteur d'écran,
     signature électronique, délai de rétractation de 14 jours.
   - Prêt immobilier : un conseiller crédit immobilier rappelle sous 24 heures. Pièces
     à préparer : 3 derniers bulletins de salaire, dernier avis d'imposition, 3 mois de
     relevés de compte, compromis de vente. Délai de réflexion de 10 jours après
     réception de l'offre.

## Les mots à expliquer

- Mensualité : la somme remboursée chaque mois.
- Étalement, ou durée : le temps sur lequel on rembourse, par exemple 48 mois, soit
  4 ans.
- TAEG, taux annuel effectif global : le coût total du crédit par an, frais compris,
  en pourcentage du montant emprunté. C'est le chiffre qui permet de comparer deux
  crédits.
- Coût des intérêts : ce que le crédit coûte en plus du montant emprunté.
- Taux d'endettement : la part des revenus qui part chaque mois dans les crédits.
- Apport : l'argent personnel mis dans un achat immobilier, en plus du prêt.
- Délai de rétractation : le temps pendant lequel on peut annuler le crédit après
  l'avoir signé, sans frais.

## Mention obligatoire

Après toute simulation ou proposition de crédit à la consommation, dire : « Un crédit
vous engage et doit être remboursé. Vérifiez vos capacités de remboursement avant de
vous engager. »

## Difficultés de remboursement

Report ou baisse d'échéances possibles : passer la main à un conseiller
(transfer_to_advisor, équipe advisor).
