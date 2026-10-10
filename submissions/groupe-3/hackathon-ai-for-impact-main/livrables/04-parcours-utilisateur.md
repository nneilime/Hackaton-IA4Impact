# Parcours utilisateur

Le schéma de parcours de l'équipe n'était pas joint. Ce document part donc du parcours en 10 étapes de la fiche (§14, p. 9). Si votre schéma est différent, comparez-le aux problèmes listés ci-dessous.

## Les trous du parcours en 10 étapes

| # | Problème | Étape concernée | Correction |
|---|---|---|---|
| 1 | Rien n'est prévu quand la demande est incomplète | 1 → 2 | L'IA pose **une** question de relance, puis continue |
| 2 | Rien n'est prévu quand les règles d'entrée échouent : moins de 6 ou plus de 50 voyageurs, établissement hors Occitanie, date à moins de 21 jours | 2 | Message clair et piste de sortie (diviser le groupe, changer de date) |
| 3 | Rien n'est prévu quand aucune destination n'est faisable | 3 | L'IA élargit la recherche (thème voisin, autre gare de départ proche) et le dit |
| 4 | Rien n'est prévu quand la jauge est insuffisante ou le train peu fiable | 5 → 6 | « Pas assez fiable, voici pourquoi, voici une alternative » : train suivant, autre jour, autre site |
| 5 | La comparaison arrive après le choix de la destination, sans retour en arrière | 4 → 8 | L'enseignant peut revenir aux destinations depuis l'écran de comparaison |
| 6 | Le parcours s'arrête à « il pré-réserve » : la sortie de l'utilisateur n'est pas définie | 9 → 10 | Référence de dossier, fiche récapitulative, statut suivi, réponse SNCF (confirmation ou contre-proposition) |
| 7 | Le passage de OPTION à PRÉ-RÉSERVATION n'apparaît pas | 9 | Choisir une proposition pose une OPTION (la jauge des autres groupes en tient compte). Envoyer la demande la fait passer en PRÉ-RÉSERVATION |

## Parcours corrigé

```mermaid
flowchart TD
    A(["Entrée : l'enseignant ouvre l'app"]) --> B["Écran 1 : décrit son projet<br/>texte libre ou voix"]
    B --> C{"Brique IA 1 :<br/>tous les champs ?"}
    C -->|"non"| C1["Une question de relance"] --> B
    C -->|"oui"| D["Gare de départ trouvée<br/>depuis le lieu réel"]
    D --> E{"Règles d'entrée<br/>6-50 voyageurs, Occitanie, J+21"}
    E -->|"bloquant"| E1["Message clair et piste :<br/>diviser le groupe, autre date"] --> B
    E -->|"vigilance J+21"| E2["Pastille orange,<br/>on continue"] --> F
    E -->|"ok"| F["Brique IA 2 : 3 destinations<br/>issues du catalogue"]
    F --> G{"Au moins une<br/>destination faisable ?"}
    G -->|"non"| G1["L'IA élargit la recherche<br/>et le dit"] --> F
    G -->|"oui"| H["Écran 2 : Où aller ?<br/>l'enseignant choisit"]
    H --> I["Moteur : trains liO groupes<br/>aller et retour"]
    I --> J["Contrôles R1 à R10, jauge,<br/>indice de confiance"]
    J --> K{"Indice"}
    K -->|"rouge"| K1["Brique IA 3 : pas assez fiable,<br/>voici pourquoi, voici une alternative"] --> I
    K -->|"vert ou orange"| L["Écran 3 : Comment y aller ?"]
    L --> M["Écran 4 : Comparer"]
    M -->|"autre destination"| H
    M --> N["Choix d'une proposition<br/>statut OPTION, jauge mise à jour"]
    N --> O["Écran 5 : Pré-réserver<br/>référence de dossier"]
    O --> P["Statut PRÉ-RÉSERVATION :<br/>confirmation en attente"]
    P --> Q{"Réponse SNCF<br/>simulée"}
    Q -->|"confirmée"| R["Statut CONFIRMATION<br/>fiche récapitulative"]
    Q -->|"contre-proposition"| L
    R --> S["Après le voyage :<br/>écran 6, retour d'expérience"]
    S --> T[("Indice mis à jour<br/>coup de cœur")]
    T --> U(["Sortie : voyage fait,<br/>la donnée sert au suivant"])
```

## Ce qu'on montre en démo

Le chemin du [scénario](README.md#le-scénario-de-démo) passe par ces branches : la relance (si on retire les accompagnateurs de la phrase), la vigilance orange, la jauge rouge avec alternative, puis la pré-réservation et le retour d'expérience. Les autres branches (aucune destination faisable, contre-proposition SNCF) sont codées si le temps le permet, sinon expliquées à l'oral avec ce schéma.
