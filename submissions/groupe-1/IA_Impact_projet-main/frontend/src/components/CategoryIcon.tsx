import type { Category } from "../data/discoveries";

// Pictogramme de chaque thème (trait 2 px, 24×24, couleur héritée) : château, musée, feuille, pont, note de
// musique, coupe, fiole, marteau
export const CATEGORY_PATHS: Record<Category, string> = {
  heritage: "M4 21V9h3V6h2v3h2V4h2v5h2V6h2v3h3v12h-6v-5a2 2 0 0 0-4 0v5H4Z",
  museum: "M3 9 12 4l9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18",
  nature: "M5 19c0-8 6-14 15-14 0 9-6 15-14 15M5 19c3-4 6-7 10-9",
  engineering: "M2 8h20M2 8v12M22 8v12M2 20h4a6 6 0 0 1 12 0h4M7 8v6M12 8v4M17 8v6",
  music: "M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  sport: "M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4ZM17 5h3a3 3 0 0 1-3 4M7 5H4a3 3 0 0 0 3 4",
  science: "M9 3h6M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3M7 15h10",
  craft: "M3 21l9-9M12.5 4.5l7 7-3 3-7-7 3-3ZM15 2l7 7",
};

export function CategoryIcon({ category, className }: { category: Category; className?: string }) {
  return (
    <svg className={`cat-icon ${className ?? ""}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={CATEGORY_PATHS[category]} />
    </svg>
  );
}
