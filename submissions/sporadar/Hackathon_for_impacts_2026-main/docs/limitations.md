# Limites connues du prototype

Ce document dit honnêtement **ce que le prototype ne sait pas faire**, avec des chiffres vérifiés sur la base partagée
(lecture seule, 10 octobre 2026). C'est une preuve de concept, pas un système réglementaire officiel : **aucun résultat
ne remplace la lecture de la source officielle ni la décision de Regulatory Affairs.**

> Règle à retenir : **une absence de résultat n'est jamais une preuve d'absence d'homologation.**

## En un coup d'œil

| # | Limite | Pays / zone | Gravité pour LPC |
|---|---|---|---|
| 1 | Aucune dose | Canada | Moyenne |
| 2 | Aucun usage avec culture **et** cible sur la même ligne | Canada | **Forte** (bloque la comparaison fine) |
| 3 | Produits retirés sans usages ni date | France | Moyenne |
| 4 | Statut d'origine vide ; seuls les produits autorisés sont publiés | Allemagne | Moyenne |
| 5 | Culture / cible : 87 % / 83 % reconnues, traductions IA non validées | Tous | Moyenne |
| 6 | Biologique / chimique deviné par une règle | Tous | Moyenne |
| 7 | Produits sœurs = hypothèses | Tous | Moyenne |
| 8 | Seulement 3 pays couverts | Autres pays | **Forte** (périmètre) |
| 9 | API ouverte, identifiants à changer | Technique | À traiter avant tout usage réel |

---

## 1. Canada : aucune dose
- **Constat** : 0 dose renseignée sur les 125 431 usages canadiens (actifs, retirés, statut inconnu). C'est une limite de la
  source (Santé Canada PPID), pas un oubli de notre chargement. À titre de comparaison : 17 902 usages français sur 18 023 ont
  une dose, 52 350 usages allemands sur 82 239.
- **Impact LPC** : on ne peut pas comparer les doses autorisées entre le Canada et la France ou l'Allemagne. Pour le
  Canada la dose reste vide : elle n'est jamais remplacée par une valeur inventée.
- **Piste** : lire les doses dans les étiquettes officielles (PDF) avec extraction assistée par IA, puis validation par un
  expert (traçable dans `field_evidence`).

## 2. Canada : aucune ligne d'usage avec culture ET cible
- **Constat** : sur les 125 431 usages canadiens, 60 437 ont une culture, 64 994 ont une cible, **0 ont les deux**. Cause
  confirmée par Dyland : dans le PPID, les cultures (« Sites of Use ») et les ravageurs (« Pests ») sont **deux listes
  séparées par produit**, sans lien entre elles. Le lien culture × cible n'existe donc pas dans la source canadienne. Les usages retirés (37 126)
  sont dans le même cas (16 025 avec culture, 21 101 avec cible, 0 les deux).
- **Impact LPC** : impossible de dire « sur la tomate contre les acariens, tel produit est autorisé au Canada ». L'écran
  « Opportunités » (`/opportunities`) renvoie donc une liste vide pour le Canada, et la comparaison par couple
  culture × cible ne marche que pour la France et l'Allemagne. Relier une culture à une cible serait inventer un lien :
  nous ne le faisons pas.
- **Piste** : au Canada, travailler par culture seule ou par cible seule (jamais en reliant les deux), ou lire les
  étiquettes officielles (PDF) où le lien figure en texte, avec validation par un expert. Le code qui exploite les usages
  retirés du Canada est déjà prêt et servira si la source change.

## 3. France : produits retirés sans usages ni date
- **Constat** : 11 882 homologations retirées sur 13 569, **toutes sans usage**, et **aucune** homologation française
  (retirée ou active) n'a de date d'expiration. 7 homologations actives sur 1 687 n'ont pas non plus d'usage.
- **Impact LPC** : pas d'historique « ce produit était autorisé sur cette culture » ; pas d'alerte d'échéance pour la
  France. Les indicateurs « retirés » se limitent à « produits retirés de même substance », sans lien avec une culture.
- **Piste** : ajouter les fichiers historiques d'E-Phy s'ils existent, ou lire les dates de retrait dans les décisions
  publiées par l'ANSES.

## 4. Allemagne : statut d'origine vide, seulement des produits autorisés
- **Constat** : `status_original` est vide pour les 2 165 homologations allemandes. Les 2 165 sont classées « active » **par
  déduction** : l'API du BVL ne publie que les produits autorisés (et chaque ligne a une date d'expiration). Aucun produit
  retiré allemand n'existe dans nos données.
- **Impact LPC** : « pas de produit allemand retiré » ne veut rien dire : c'est la source qui ne les publie pas. Le statut
  allemand est une hypothèse raisonnable, pas une donnée copiée de la source.
- **Piste** : compléter `status_original` avec le libellé exact de l'API quand il existe, et chercher une source
  d'historique des retraits (BVL ou archives).

## 5. Normalisation des cultures et cibles
- **Constat** : chaque pays nomme les cultures et les cibles dans sa langue ; nous les ramenons à un nom anglais commun
  (colonnes `*_normalized`, les colonnes `*_original` ne sont jamais modifiées). Parmi les usages qui ont une culture,
  **87 %** sont reconnus (140 415 sur 160 699) ; parmi ceux qui ont une cible, **83 %** (134 788 sur 161 958). Par pays :

  | Pays | Cultures reconnues | Cibles reconnues |
  |---|---|---|
  | France | 99,5 % | 94,5 % |
  | Allemagne | 99,1 % | 97,3 % |
  | Canada | 67,8 % | 62,9 % |

  Rapporté à **tous** les usages (même ceux sans culture ou sans cible), la part est plus basse : 62 % pour les cultures et
  60 % pour les cibles, surtout à cause du Canada.
- Les traductions viennent de deux sources : 50 correspondances LPC (25 cultures, 25 cibles, prioritaires) et un dictionnaire
  suggéré par IA (`data/ai_term_mapping.csv`, 1 849 lignes, **toutes en `to_verify`**, 395 avec un code EPPO proposé).
  Aucun expert n'en a encore validé une seule.
- **Impact LPC** : un usage non reconnu n'apparaît pas dans les comparaisons et classements ; une mauvaise traduction
  pourrait rapprocher deux cibles différentes. Les comparaisons entre pays reposent donc en partie sur des hypothèses.
- **Piste** : faire relire par Regulatory Affairs le dictionnaire (d'abord les lignes à faible confiance), puis fournir les
  codes EPPO officiels. Voir `docs/regulatory_validation.md` et `docs/ai_term_mapping.md`.

## 6. Biologique / chimique : une règle, pas une donnée
- **Constat** : aucune source ne dit si un produit est biologique. Nous le déduisons par une règle sur la substance active
  (présence d'un nom de micro-organisme : *Bacillus*, *Trichoderma*, *Metarhizium*…). Tout le reste est classé
  « chemical », c'est-à-dire « non identifié comme micro-organisme » : le cuivre, le soufre ou les pyréthrines y figurent aussi.
- **Impact LPC** : le score d'« espace pour le biocontrôle » (`/opportunities`) peut être faussé dans les deux sens. Un
  nombre de produits biologiques à 0 ne prouve pas qu'il n'y en a pas (les usages non normalisés sont exclus). C'est une
  aide à l'analyse, pas une décision.
- **Piste** : remplacer la règle par une classification officielle (listes de substances approuvées en biocontrôle) validée
  par un expert.

## 7. Produits sœurs = hypothèses
- **Constat** : en base, 14 liens « candidat sœur » sont en `to_verify` et 3 012 noms alternatifs en `to_verify` ;
  1 seul lien est marqué `validated`. Le rapprochement par ingrédient actif et par nom est une aide à la recherche.
- **Impact LPC** : PRESTOP (candidat sœur de LALSTOP G46) apparaît dans les démonstrations **à titre d'hypothèse**. Aucune
  réponse ne doit présenter un produit sœur comme un fait réglementaire.
- **Piste** : Regulatory Affairs confirme ou rejette chaque candidat ; le statut passe alors de `to_verify` à `validated`.

## 8. Trois pays seulement
- **Constat** : France (FR-EPHY), Allemagne (DE-BVL), Canada (CA-PPID). Le registre des sources connaît d'autres sources
  (Belgique, Brésil, Mexique, États-Unis, Uruguay, EPPO) mais **aucune donnée n'a été collectée** pour elles.
- **Impact LPC** : pour tout autre pays, l'application répond `not_covered` (« pays pas encore couvert »), ce qui ne veut
  pas dire « pas homologué ». Aucune conclusion n'est possible.
- **Piste** : ajouter un pays = écrire un adaptateur (modèle : les adaptateurs existants). Plan B déjà prévu : EPA des
  États-Unis. Pour chaque source, vérifier la licence et les conditions d'accès (déjà notées dans le registre des sources).

## 9. Sécurité et exploitation
- **Constat** : l'API de démonstration est **ouverte** (aucune clé d'accès, `API_KEY` vide) et en HTTP simple, sans
  chiffrement. Elle lit la base partagée en lecture seule. Le mot de passe de la base a déjà été changé une fois pendant le
  hackathon. Aucun secret n'est dans git ni dans les images.
- **Impact LPC** : acceptable pour une démonstration avec des données publiques ; **pas acceptable** pour des données
  internes LPC ou un usage réel.
- **À faire après le hackathon** : changer tous les identifiants utilisés pendant l'événement (mot de passe de la base,
  clé du fournisseur d'IA, accès au serveur), activer la clé d'API (`API_KEY`), passer en HTTPS, et restreindre l'accès à la
  base. Le fonctionnement sans clé IA (mode dégradé) reste possible.

---

## Ce qui reste fiable malgré ces limites
- Chaque donnée affichée porte sa source (`source_id`), le lien vers la fiche officielle (`source_record_url`), la date de
  collecte et un statut de validation. Aucune donnée n'est inventée : l'inconnu reste vide ou « unknown ».
- Les réponses de l'agent sont vérifiées par le code : preuves citées existantes, chiffres présents dans les faits, jamais
  « non homologué » sur un résultat vide.
- Les 18 771 homologations sont toutes au statut `automatically_extracted` : **aucune n'a encore été validée par un
  expert**. Voir `docs/regulatory_validation.md` pour la marche à suivre.
