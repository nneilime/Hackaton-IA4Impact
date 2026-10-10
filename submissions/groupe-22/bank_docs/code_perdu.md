# Code perdu : code de carte, mot de passe, identifiant, carte ou téléphone perdu ou volé

Contenu d'exemple pour la démo : les délais, frais et numéros de cette fiche sont fictifs.

## Qualifier la situation, une question à la fois

1. Quel code ? Le code secret de la carte bancaire, le mot de passe de l'application
   ou de la banque en ligne, l'identifiant client, ou la validation des opérations
   sur le téléphone (authentification forte).
2. La carte ou le téléphone est-il perdu ou volé, ou quelqu'un a-t-il pu voir ou
   obtenir le code ? Si oui, c'est urgent : proposer l'opposition tout de suite.

## Règle de sécurité

La banque ne demande jamais un code secret, un mot de passe ou un code reçu par SMS :
ni par téléphone, ni par e-mail, ni par cet assistant. Le client ne doit jamais les
dire à voix haute. Si quelqu'un les lui a demandés, c'est probablement une fraude :
proposer l'opposition et le service fraude.

## Récupération sécurisée

- Code de la carte oublié : après 3 codes faux, la carte est bloquée par sécurité pour
  les paiements avec code. Le code peut être renvoyé par courrier sous 5 à 7 jours
  ouvrés, en braille ou en gros caractères si le client le souhaite. Frais : 10 euros.
  L'assistant peut faire la demande (start_request, type pin_reissue).
- Mot de passe oublié, client connecté : l'assistant envoie par SMS, au numéro
  enregistré, un lien de réinitialisation valable 30 minutes (start_request, type
  password_reset). La page est compatible avec les lecteurs d'écran. Après 3 mots de
  passe faux, l'accès est bloqué 24 heures ; un conseiller peut le débloquer avant.
- Mot de passe oublié, visiteur qui ne peut pas se connecter : sur la page de connexion
  de la banque en ligne ou de l'application, le lien « Mot de passe oublié » demande
  l'identifiant client, puis envoie un lien ou un code au numéro de téléphone
  enregistré. Personne ne doit demander le mot de passe, ni par téléphone, ni par
  e-mail, ni par cet assistant. S'il n'a plus accès à ce numéro, un conseiller vérifie
  son identité (demande de conseiller, transfer_to_advisor).
- Identifiant oublié : il figure sur le contrat d'ouverture de compte ; sinon, un
  conseiller le renvoie par SMS (transfer_to_advisor, équipe advisor).
- Téléphone perdu ou changé (validation des opérations) : un conseiller désactive
  l'ancien appareil et aide à enregistrer le nouveau (transfer_to_advisor).

## Opposition : carte perdue ou volée, code compromis

- 24 heures sur 24 et 7 jours sur 7. L'assistant fait l'opposition lui-même, après
  confirmation du client (start_request, type card_block). Par téléphone : 01 23 45
  67 89 (numéro fictif de démo).
- L'opposition est définitive. Une nouvelle carte, avec un nouveau code, arrive par
  courrier sous 7 jours ouvrés.
- En cas d'opérations frauduleuses, les contester ensuite (fiche Réclamation).
