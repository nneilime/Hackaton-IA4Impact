# Réclamation : opération contestée, prélèvement, frais, virement, qualité de service

Contenu d'exemple pour la démo : les délais, frais et numéros de cette fiche sont fictifs.

Une opération que le client connecté ne reconnaît pas : la retrouver d'abord avec
search_transactions, et lui en donner la date, le montant et le libellé. Un visiteur non
connecté ne peut pas déposer de réclamation ici : lui expliquer les étapes et les
recours, sans recueillir les informations, puis proposer la Connexion démo ou une
demande de conseiller.

## Les quatre informations à recueillir

Avant de transmettre la réclamation, il faut les quatre, une question à la fois, en ne
demandant que celles que le client n'a pas déjà données :

- le motif : opération non reconnue, prélèvement contesté, frais contestés, problème de
  virement, qualité de service, ou autre ;
- les faits : ce qui s'est passé, avec le montant et le nom du commerçant ou du
  créancier s'il y en a un ;
- la date du problème ;
- le produit concerné : carte, compte, crédit, épargne, assurance, application ou
  banque en ligne, agence ou conseiller.

Seulement ce qui concerne la banque, ses produits et ses services. Si la demande ne
concerne pas la banque (un voisin, la qualité d'un produit acheté, un service public),
dire : « Je ne peux pas traiter cette demande : elle ne concerne pas la banque. », et
ne rien transmettre.

## Étapes

1. Recueillir les quatre informations. Rien n'est transmis avant de les avoir toutes.
2. Dès qu'on les a, sans demander de confirmation : transmission de la réclamation à un
   conseiller (send_complaint), qui la traitera dans les meilleurs délais, puis
   récapitulatif au client, numéro de référence, et récapitulatif en PDF à télécharger
   dans l'application.
3. Le client corrige une information après la transmission : transmettre à nouveau la
   réclamation corrigée.

## Les motifs fréquents

- Paiement ou retrait par carte que le client ne reconnaît pas : une fraude est
  possible, sans être certaine (un libellé de commerçant peut être trompeur). Proposer
  de protéger la carte : la verrouiller (start_request, type card_lock), ou faire
  opposition (card_block) si quelqu'un d'autre l'utilise, puis finir la réclamation. Délai pour contester : 13 mois après la date de débit. L'opération
  frauduleuse est remboursée au plus tard le premier jour ouvré qui suit la
  contestation.
- Prélèvement contesté : s'il avait été autorisé, remboursement sans justification
  dans les 8 semaines qui suivent le débit ; s'il n'a jamais été autorisé, 13 mois.
- Frais bancaires contestés (commission d'intervention, frais de rejet, agios) :
  expliquer le frais ; un geste commercial peut être demandé au conseiller.
- Virement envoyé au mauvais bénéficiaire ou jamais reçu : demande de recherche et de
  retour des fonds, sans garantie de récupération si le bénéficiaire refuse.
- Qualité de service : attente, accueil, erreur de traitement.

## Si la réponse ne convient pas

1. Le conseiller, qui reçoit la réclamation : réponse sous 10 jours ouvrés.
2. Le service relations clientèle, si la réponse ne convient pas : accusé de réception
   sous 48 heures, réponse sous 15 jours ouvrés pour les cartes, virements et
   prélèvements, sous 2 mois pour le reste.
3. Le médiateur bancaire, gratuit, en cas de désaccord persistant ou sans réponse
   au bout de 2 mois. La saisine se fait en ligne ou par courrier.

## Ce que l'assistant peut faire

- Transmettre la réclamation à un conseiller (send_complaint), une fois les quatre
  informations recueillies.
- Verrouiller la carte, ou faire opposition en cas de fraude (start_request, type
  card_lock ou card_block), puis continuer la réclamation.
- Pour un visiteur non connecté : expliquer les étapes et les recours ; la réclamation
  se dépose une fois connecté.
- Passer la main au service relations clientèle (transfer_to_advisor, équipe
  complaints) si le client le demande ou si le litige est complexe, et au service
  fraude (équipe fraud) en cas de fraude en cours.

## Pièces utiles

Date et montant de l'opération, nom du commerçant ou du créancier. Un dépôt de plainte
n'est pas obligatoire pour contester une fraude par carte.
