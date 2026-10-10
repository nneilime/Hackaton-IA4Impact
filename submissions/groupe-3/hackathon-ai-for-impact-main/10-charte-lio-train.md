# Spécifications Graphiques & UI — liO Train (Région Occitanie)

Ce document récapitule les règles de marque, la palette chromatique, les choix typographiques et les contraintes techniques d'intégration pour tout développement web, mobile ou applicatif lié au service ferroviaire régional **liO Train**.

---

## 1. Règles d'identité & Bloc-marque

### 1.1 Orthographe et casse
* **Règle absolue :** Le nom de la marque s’écrit obligatoirement **`liO`** :
  * Deux premières lettres en minuscules : `li`
  * Dernière lettre en majuscule : `O`
* **Interdictions strictes :** Ne jamais orthographier `LiO`, `LIO`, `Lio` ou `lio`.

### 1.2 Structure du logotype
* **Typogramme :** Lettrage vectoriel spécifique et exclusif.
* **Accents identitaires :** Les marques distinctives reprennent les couleurs sang et or de la Région Occitanie (point du « i » et motifs d’accompagnement).
* **Baseline institutionnelle :** *« Les transports de Ma Région »* adossée à l'emblème de la Région Occitanie (croix occitane).
* **Zone de protection :** Respecter un espace vide autour du logotype équivalent au minimum à la demi-hauteur du « O ». Aucun texte, bouton ou illustration ne doit pénétrer dans cet espace.
* **Intégrité :** Interdiction de déformer, compresser, réorienter ou séparer les éléments du bloc-marque.

---

## 2. Palette Chromatique (Tokens Design)

| Token / Rôle | Nom de teinte | Pantone / CMJN | Code HEX | Usage recommandé en UI |
| :--- | :--- | :--- | :--- | :--- |
| `lio-blue-dark` | Bleu liO Nuit | Pantone 289 C / 282 C *(C100 M75 Y15 K65)* | `#0B2341` | Barres de navigation, headers, fonds sombres, texte emphase |
| `lio-red` | Rouge Occitanie | Pantone 200 C *(C0 M100 Y65 K15)* | `#C8102E` | Boutons d'action prioritaires (CTA), alertes trafic, retards |
| `lio-yellow` | Jaune / Or Occitanie | Pantone 116 C *(C0 M10 Y100 K0)* | `#FFCD00` | Accents visuels, notifications modérées, puces d'état |
| `lio-bg-light` | Gris neutre liO | *(C5 M3 Y3 K4)* | `#F4F5F7` | Arrière-plan des fiches horaires, cartes, panneaux latéraux |
| `lio-border` | Bordure neutre | *(C10 M8 Y8 K10)* | `#E2E5E9` | Lignes de séparation de trajets, bordures de tableaux |
| `lio-text-main` | Anthracite | *(C0 M0 Y0 K90)* | `#1E1E1E` | Corps de texte principal (lisibilité standard) |
| `lio-white` | Blanc pur | — | `#FFFFFF` | Conteneurs de cartes, fond général, texte sur fond bleu nuit |

---

## 3. Typographie & Règles de texte

* **Typogramme officiel :** Propriétaire et vectoriel (fichiers `.svg` / `.ai` obligatoires ; pas de police système correspondante pour le logo).
* **Polices d'interface (UI) :**
  * La police recommandée pour les services publics territoriaux et régionaux est la famille **Marianne**, avec fallback direct vers **Montserrat** ou **Inter** :
    ```css
    font-family: "Marianne", "Montserrat", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    ```
* **Chiffres et horaires de circulation :**
  * Pour les grilles horaires et les numéros de rames, activer les chiffres tabulaires afin d'assurer un alignement vertical parfait :
    ```css
    font-variant-numeric: tabular-nums;
    ```
* **Hiérarchie :**
  * **Titres de gare / Lignes :** Bold à ExtraBold (`700` - `800`).
  * **Sous-titres & statut de voie :** SemiBold (`600`).
  * **Horaires :** Medium (`500`) ou SemiBold (`600`).
  * **Mentions et conditions tarifaires :** Regular (`400`), taille minimale de 12px / 0.75rem.

---

## 4. Intégration Technique (Tailwind CSS & CSS Custom Properties)

### 4.1 Variables CSS natives
```css
:root {
  --lio-color-blue: #0b2341;
  --lio-color-blue-dark: #071629;
  --lio-color-red: #c8102e;
  --lio-color-red-hover: #a00d24;
  --lio-color-yellow: #ffcd00;
  --lio-color-surface: #f4f5f7;
  --lio-color-border: #e2e5e9;
  --lio-color-text: #1e1e1e;
  --lio-color-white: #ffffff;
}
```

### 4.2 Configuration Tailwind (`tailwind.config.ts`)
```typescript
import type { Config } from 'tailwindcss';

export default {
  theme: {
    extend: {
      colors: {
        lio: {
          blue: {
            DEFAULT: '#0B2341',
            dark: '#071629',
            light: '#1B3B66',
          },
          red: {
            DEFAULT: '#C8102E',
            hover: '#A00D24',
          },
          yellow: {
            DEFAULT: '#FFCD00',
            hover: '#E5B800',
          },
          surface: '#F4F5F7',
          border: '#E2E5E9',
          text: '#1E1E1E',
        },
      },
      fontFamily: {
        lio: ['Marianne', 'Montserrat', 'Inter', 'sans-serif'],
      },
    },
  },
} satisfies Config;
```

---

## 5. Règles d'accessibilité (WCAG 2.1)

1. **Texte sur fond coloré :**
   * `#FFFFFF` sur `lio-blue` (`#0B2341`) : **Ratio > 14:1** (Conforme WCAG AAA).
   * `#FFFFFF` sur `lio-red` (`#C8102E`) : **Ratio ~ 4.6:1** (Conforme WCAG AA pour texte normal, AAA pour grand texte).
   * **Avertissement :** Le jaune `#FFCD00` ne doit jamais servir de couleur de texte sur fond blanc (contraste insuffisant < 1.5:1). Utiliser exclusivement le texte sombre `#1E1E1E` sur les badges jaunes.
2. **Indicateurs de retard et trafic :**
   * Ne jamais coder l'information par la seule couleur rouge/jaune/vert. Associer systématiquement une icône (pictogramme d'alerte, coche) et un libellé textuel explicite (ex. *« À l'heure »*, *« Retard 10 min »*).

---

## 6. Sources officielles & Documentation

* **Région Occitanie :** Document officiel *« Règles d’utilisation du bloc-marque liO »* (Réf. `Regles_utilisation_bloc-marque_072025-compresse.pdf`).
* **Portail liO Occitanie :** Espace partenaires et communication institutionnelle ([lio-occitanie.fr](https://www.lio-occitanie.fr)).
* **Charte Région Occitanie :** Guide des usages graphiques et blason régional ([laregion.fr](https://www.laregion.fr)).