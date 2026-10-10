# Méthode de calcul du risque (moteur/risque.py)

1. Pour chaque équipement du périmètre (1 285), le score est une **somme de points** plafonnée à 100 ; chaque point vient d'une raison écrite en clair. Aucun modèle de langage, aucun apprentissage opaque.
2. **Usure** : âge de l'appareil en place à la date de référence divisé par sa durée de vie de référence, porté au cube (forme Weibull : l'usure s'accélère) ; 40 points à 100 % de la durée de vie, jusqu'à 55 au-delà.
3. **Dépannages des 12 derniers mois** : 9 points par arrêt total, 6 par fonctionnement dégradé, 2,5 par gêne mineure (plafond 30).
4. **Notes des techniciens sur 18 mois** : 9 points par note d'usure (« usure avancée », « réparation provisoire », « corrosion », « pièce difficile à obtenir »…), 14 par note de fin de vie (« défaillance majeure », « panne irréparable », « hors service ») (plafond 32).
5. **Anomalies en visite** (« anomalie constatée », « remplacement nécessaire ») sur 18 mois : 5 points chacune (plafond 15).
6. **Entretien manqué** : part des visites sans accès au logement sur 3 ans, jusqu'à 10 points (au-delà d'une visite sur trois).
7. **Demandes des locataires** liées à l'équipement (mots du sujet : chauffage, eau tiède, cumulus, ascenseur, VMC…) sur 12 mois : 6 points chacune (plafond 14), +6 si la demande revient ou a été rouverte.
8. **Grand logement** (≥ 85 m²) : +2 points, l'appareil est plus sollicité.
9. Anti-fuite : seules les données datées au plus tard à la date de référence sont lues, l'historique de l'appareil précédent (avant le dernier remplacement) est ignoré, et le champ « nb_remplacements_2018_2025 » n'est pas utilisé.
10. Les poids ont été réglés sur 2024 (référence 31/12/2023), puis mesurés sans retouche sur 2025 (référence 31/12/2024) : voir `moteur/performance.json`. Niveaux affichés : « alerte » = 10 % des équipements les plus à risque, « vigilance » = 10 à 25 %.
