# Charte UI v2 : dense, large, ludique

Retour du client sur la v1 : tout est trop gros, l'accueil s'empile en hauteur au lieu d'utiliser la largeur, le parcours doit être plus guidé et plus ludique. Ces règles s'appliquent à TOUTES les pages. Elles priment sur les choix de la v1.

## 1. Échelle typographique (maximums)

| Rôle | Classes | Taille max |
|---|---|---|
| Titre de page (h1) | `text-2xl lg:text-3xl font-extrabold tracking-tight` | 30 px |
| Titre de section (h2) | `text-lg lg:text-xl font-bold` | 20 px |
| Titre de carte (h3) | `text-base font-bold` | 16 px |
| Texte courant, bulles de chat | `text-sm lg:text-[15px]` | 15 px |
| Texte d'interface dense (listes, cartes, tableaux) | `text-sm` | 14 px |
| Libellés, métadonnées | `text-xs font-semibold uppercase tracking-wide` | 12 px |
| Chiffre clé (score, heure) | `text-xl lg:text-2xl font-extrabold tabular-nums` | 24 px |

Exception unique : l'écran de projection du vote en classe (`/vote/:code/animer`), pensé pour un vidéoprojecteur, peut aller jusqu'à `text-5xl`.

## 2. Espacement et conteneurs

- Conteneur de page : `mx-auto max-w-7xl px-4 lg:px-6 py-5 lg:py-6`.
- Espace entre blocs : `gap-4 lg:gap-5`. Jamais plus de `gap-8` ou `py-10`.
- Cartes : `p-4` (ou `p-3` pour les listes), coins `rounded-box`, contour `border-2 border-secondary` réservé aux éléments forts ; les autres cartes en `border border-base-300`.
- Ombre dure `shadow-[4px_4px_0_0] shadow-secondary` : seulement sur l'élément principal de l'écran (1 ou 2 par écran maximum), pas sur chaque carte.
- Boutons : `btn-sm` par défaut, `btn-md` uniquement pour l'action principale de l'étape. Jamais `btn-lg`.
- Badges `badge-sm`, champs `input-sm` / `select-sm` dans les zones denses, `input-md` dans le formulaire principal.
- Mascotte : 40 px dans le header, 64 à 96 px dans l'intro d'une page, 32 à 40 px dans les bulles. Jamais plus de 120 px hors projection.
- Décorations Memphis (cercles, demi-cercles, traverses) : 2 par écran au maximum, 48 px de diamètre au maximum.

## 3. Mise en page : la largeur d'abord

- À partir de `lg` (1024 px), jamais une seule colonne étroite et longue. Utiliser des grilles : `lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]`, `lg:grid-cols-3`, ou une grille 12 colonnes.
- Aucune colonne de contenu plus étroite que 320 px.
- L'intro de chaque page tient sur une seule rangée : mascotte (64 px) + titre + une phrase. Elle fait au plus 120 px de haut. Plus de grands héros.
- Sur un écran 1366 × 768, l'action principale de l'étape doit être visible sans défiler. Elle vit dans la barre d'action collante (voir 4).
- Les listes longues défilent dans leur propre zone (`max-h-[…] overflow-y-auto`) plutôt que d'allonger la page (ex. le fil du chat).
- Tableaux et informations comparables : grilles alignées, chiffres en `tabular-nums`, alignements au pixel.

## 4. Guidage et fluidité

- **Barre de guidage** (dans le shell, automatique selon la route) : « Étape 2 sur 6 · Choisissez une destination » + une astuce de Tchouette. Les pages n'ont rien à faire pour l'avoir.
- **Barre d'action collante** en bas de chaque étape : `import BarreAction from '../layout/BarreAction'`. Toujours le même emplacement : retour à gauche, action principale à droite, aide courte au milieu. Une page n'affiche qu'UNE action principale.
- Chaque action donne un retour immédiat : bouton en chargement, `toast` de confirmation (« Ajouté à la comparaison »), animation courte.
- Chargement : squelettes à la forme du contenu + Tchouette `reflexion`. Jamais d'écran vide.
- Textes explicites et courts : un verbe d'action par bouton (« Voir les trains », « Envoyer la demande »), des phrases de 15 mots au plus dans l'interface.
- Ludique sans gêner : micro-animations (`motion-safe:animate-entree`, `motion-safe:animate-pop`), Tchouette qui réagit, petites phrases complices. Rien qui clignote en continu à côté d'un champ de saisie.

## 5. Animations disponibles (définies dans `src/index.css`)

Toujours préfixées de `motion-safe:` pour respecter `prefers-reduced-motion`.

| Classe | Effet | Usage |
|---|---|---|
| `animate-entree` | fondu + montée de 8 px, 280 ms | apparition d'une page, d'une carte, d'un message |
| `animate-pop` | petit rebond d'échelle, 320 ms | vote, ajout, badge qui change |
| `animate-flotte` | flottement vertical lent, 4 s, infini | mascotte au repos uniquement |
| `animate-train-passe` | traversée horizontale de -30 % à 130 %, 11 s, infini avec pause | le train liO du header |

## 6. Rappels de marque et d'accessibilité (inchangés)

- « liO » toujours écrit ainsi. Pas de logo officiel redessiné.
- Couleurs sémantiques daisyUI uniquement (primary rouge pour l'action principale, secondary bleu nuit, accent or avec texte sombre).
- Statuts : couleur + icône + texte, jamais la couleur seule.
- Contraste, labels, focus visible, cibles tactiles d'au moins 40 px sur mobile.
