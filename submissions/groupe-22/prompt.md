ok, modifions le calcul de crédits

on va faire le shéma suivant.

on a un nombre d'informations a récolter [age, montant, motif, étalement, ressources]
le taux est un variable interne

si l'user demande à faire un demande de calcul de crédits, on rentre dans la démarche de
récupèrer les infos nécéssaires.
on ne commence pas le calcul tans que toutes les infos nécéssaires ne sont pas récoltées;

Dès que les infos sont récoltées, on rentre dans la démarche de calcul.

dans le system prompt : si l'user ne comprend pas un terme -> expliquer
si l'user demande pourquoi est ce que l'on récolte des ifos sur lui, on le rassure en disant que c'est juste pour le calcul

18 : pilotage 100 % vocal
5 : recalcul direct quand l’utilisateur change la durée

à la fin, on done le récapitulatife à l'utilisateur. et on annonce que c'est transmis au conseiller.

At the beginin, the agent talk and we cant stop it. can we make this introducion stopable ?

on ajoute la séparation des démarches, nouveaux concepts,
si l'agent commence un démarche, il n'en commence pas une autre.
pour en commencer un autre, il expliquer à l'utilisateur qu'il arète la démarche
précédante, pour en commencer un autre.

et aussi, on modif la démarche réclamations.

maintenant, voici la logique.

si l'user demande à faire un réclamations, on rentre en démarche réclamations.
les informations à récolter sont : [modif, fait, date (la date du pb), produit]

on boucle tant qu'on les a pas , tu peux t'inspirer de la démarche crédits.

pendant la démarche, si la démarche ne concerne pas un demande en
rapport avec la banque, on annonce à l'user que on ne peux pas traiter
sa demande

une fois que toutes les informations sont récoltées, on annonce
à l'utilisateur que on transmet sa demande à un agent
et qu'elle sera traitée dans les meilleurs delais.

à la fin, on donne un récapitulatife à l'utilisateur en pdf.
