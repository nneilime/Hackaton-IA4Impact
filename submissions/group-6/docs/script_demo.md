# Script de Démonstration — Copilote de Crise Enedis

> **Hackathon IA for Impact 2026** — Défi Optimisation et Gestion de Crise Réseau Électrique  
> **Livrable Fiche C** : Script de démonstration live (2 minutes) + Vidéo de secours `demo.mp4`.  
> **Auteur / Responsable Fiche C** : ATAE.  
> **Scénario d'appui** : CRISE_024 sur la page Streamlit *« Salle de crise express »*.

---

## 1. Fiche Synthétique & Consignes de Présentation

- **Durée cible** : **1 minute 45 secondes** à **1 minute 55 secondes** (s'intègre parfaitement dans le pitch global de 5 minutes).
- **Règle d'or** : *« L'outil recommande, le responsable décide. »* Montrer la puissance du moteur mathématique WSPT + Hongrois sans jamais déposséder l'humain de sa responsabilité d'arbitrage.
- **Support principal** : Démonstration en direct sur navigateur (`http://localhost:8501`).
- **Support de secours (Failover)** : Fichier vidéo préenregistré `demo.mp4` (situé à la racine du dépôt / accessible en 1 clic).

### Configuration technique préalable (À vérifier 10 min avant le pitch)
1. Lancer l'application en local :
   ```powershell
   streamlit run app/Accueil.py
   ```
2. Ouvrir le navigateur en plein écran (F11 ou mode présentation), zoom à 100% ou 90% selon la résolution du vidéoprojecteur.
3. Se positionner dans le menu de gauche sur la page **« 1_Salle_de_crise_express »**.
4. S'assurer que le fichier vidéo `demo.mp4` est ouvert en arrière-plan dans le lecteur vidéo prêt à être basculé par `Alt+Tab`.

---

## 2. Déroulé Chronologique & Script Oral (Mot à Mot)

| Timing | Action à l'écran | Script oral (Ce que dit le présentateur) | Données clés à pointer |
|---|---|---|---|
| **00:00 - 00:15** | Afficher le haut de la page « Salle de crise express ». Défilement fluide. | *« Bonjour à tous. Voici notre copilote de crise en action, conçu pour assister le Directeur de Crise Enedis face à 250 incidents simultanés et 63 équipes à mobiliser. »* | Titre et sous-titre de la salle de crise. |
| **00:15 - 00:35** | Dans la barre latérale, sélectionner **CRISE_024**. Montrer les cartes d'indicateurs (KPIs) en haut de page. | *« Nous chargeons la CRISE_024. Observez immédiatement le comparatif entre les règles usuelles et notre stratégie WSPT couplée à l'algorithme hongrois. Par rapport à la règle métier R2 (plus de clients d'abord), nous gagnons 10 263 clients·heures (−4,9 %) et plus de 14 % par rapport à R1. Mais le vrai bond est humain : l'attente maximale d'un client sensible passe de 26,8h à 18,8h, et le délai moyen d'intervention sur les sites prioritaires est divisé par deux (2,7h contre 5,5h). Zéro dépassement de l'amplitude de 12h. »* | `199 005` clients·heures WSPT (−4,9 % vs R2, −14,4 % vs R1). Attente moy. sensible : **2,7h**. Dépassements : **0**. |
| **00:35 - 00:55** | Descendre sur le graphique **« Clients coupés au fil de la crise »**. Pointer l'écart entre les courbes. | *« Regardez cette courbe de rétablissement. L'aire sous la courbe mesure la souffrance électrique globale. Dès la 4e heure, notre stratégie décroche plus vite : 19 % des foyers sont déjà réalimentés, contre seulement 10 % avec R2 et 7 % avec R1. C'est l'effet combiné du ratio de Smith et du couplage optimal par l'algorithme hongrois, qui évite le croisement inefficace des trajets d'équipes. »* | Courbe WSPT systématiquement sous R1 et R2. % rétablis à 4h : **19 %** vs 10 % (R2). |
| **00:55 - 01:15** | Aller sur la **« Carte de la crise à l'instant t »**. Placer le curseur à **H+6**, puis le glisser à **H+20**. | *« Projetons-nous sur le terrain. À H+6, en plein pic de crise : les ronds rouges représentent les incidents en attente, le contour violet signale les clients sensibles sous tension. Les triangles bleus et lignes de déplacement matérialisent nos 63 équipes. Glissons maintenant à H+20 : la bascule vers le vert montre la résorption méthodique des poches de crise et la protection assurée des sites critiques de santé. »* | Carte dynamique interactive. Curseur temporel H+6 → H+20. Contour violet = sensibles. |
| **01:15 - 01:35** | Descendre à la section **« Décisions expliquées »**. Cliquer sur le filtre radio **« seulement les décisions à discuter »**. Cliquer sur **« ❌ Refuser cette affectation »**. | *« Mais dans une crise Enedis, l'algorithme ne doit jamais être une boîte noire. Chaque affectation est justifiée avec ses composantes de score et un indice de confiance. Filtrons sur les décisions 'à discuter'. Ici, une équipe locale est proposée, mais l'arbitrage est serré. En un clic, le responsable peut refuser cette affectation. Le copilote recalcule instantanément le reste de la crise et chiffre l'impact exact : +110 clients·heures, pour 0 minute d'attente supplémentaire sur les sensibles. Le responsable valide en pleine conscience. »* | Filtre « à discuter », bouton « Refuser », bloc métrique d'impact recalculé en temps réel. |
| **01:35 - 01:50** | Dans la barre latérale, cocher la case **« Routes coupées en montagne (vitesse ÷ 3) »**. Montrer la mise à jour des métriques. | *« Enfin, la résilience aux aléas climatiques. Activons un stress test : effondrement de routes en montagne, vitesse divisée par 3. Les indicateurs s'adaptent instantanément : le WSPT conserve sa supériorité avec 207 000 clients·heures contre 239 000 pour R1, et maintient l'attente moyenne des sensibles sous les 3 heures. »* | Checkbox stress test, réactivité temps réel, maintien de l'avantage de la stratégie. |
| **01:50 - 02:00** | Remonter en haut de page ou revenir sur l'accueil. Conclure d'une phrase nette. | *« En synthèse : une solution 100 % CPU, ultra-rapide, mathématiquement rigoureuse, qui divise par deux l'attente des plus fragiles tout en laissant le dernier mot aux femmes et aux hommes d'Enedis. Merci. »* | Clôture percutante et sereine. |

---

## 3. Procédure de Secours (Plan B — Vidéo `demo.mp4`)

Si pendant le pitch en direct :
- La connexion réseau locale pose problème,
- Ou Streamlit met plus de 3 secondes à rafraîchir un calcul en raison d'un freeze du navigateur hôte,

**Bascule immédiate (moins de 3 secondes) :**
1. Enchaîner oralement sans interruption : *« Pour vous faire gagner du temps, passons directement à notre enregistrement de référence. »*
2. Raccourci clavier `Alt + Tab` vers le lecteur vidéo affichant `demo.mp4`.
3. Appuyer sur `Espace` (lecture).
4. Poursuivre le script oral synchronisé sur les images de la vidéo (le minutage du tableau §2 correspond exactement à la vidéo).

---

## 4. Réponses Préparées aux Questions Fréquentes du Jury (Q&A)

### Q1 : Pourquoi la stratégie WSPT est-elle meilleure que la règle métier R2 (plus de clients d'abord) ?
> **Réponse** : *« R2 ne regarde que le volume de clients, quitte à envoyer une équipe sur un chantier de 10 heures alors que trois chantiers de 40 clients pourraient être réglés en 2 heures chacun. WSPT (Weighted Shortest Processing Time) applique la règle de Smith, mathématiquement optimale pour 1 serveur : on priorise le ratio (poids / durée). Avec l'algorithme hongrois en amont, on optimise en plus le matching spatial global des 63 équipes pour réduire les temps morts de route (15,4 % de trajet pour WSPT contre 21,5 % pour R2). »*

### Q2 : Comment garantissez-vous qu'aucune équipe ne dépasse l'amplitude maximale de 12 heures ?
> **Réponse** : *« Le simulateur intègre une fonction stricte de garde-fou `est_faisable` : une équipe ne peut se voir affecter un incident que si `durée trajet aller + durée chantier + durée trajet retour au site d'attache <= amplitude restante`. Si l'amplitude est épuisée, l'équipe rentre obligatoirement à sa base et observe 11 heures de repos incompressible avant toute nouvelle disponibilité. Résultat sur 100 crises : strictement 0 dépassement. »*

### Q3 : Que se passe-t-il techniquement quand le responsable refuse une affectation ?
> **Réponse** : *« La paire (équipe, incident) est ajoutée à la liste des contraintes `interdites`. Le simulateur rejoue la crise à partir de l'état exact de la décision : l'algorithme trouve la meilleure solution sous cette contrainte supplémentaire et compare le score à la solution nominale. Le responsable voit le coût chiffré de son choix en temps réel. »*

### Q4 : Y a-t-il une dépendance à un LLM externe ou à des API propriétaires ?
> **Réponse** : *« Aucune. Notre solution est 100 % souveraine, open-source et CPU. Le moteur repose sur SciPy (Hongrois), NumPy et OR-Tools. Les explications de base sont calculées par règles transparentes déterministes. Le module LLM optionnel tourne en local (Ollama / Qwen) avec un garde-fou anti-hallucination qui retombe automatiquement sur les gabarits certifiés. »*
