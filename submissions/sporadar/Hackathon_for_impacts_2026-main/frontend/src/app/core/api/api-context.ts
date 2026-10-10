import { HttpContextToken } from '@angular/common/http';

/**
 * Nom de l'exemple Prism à demander (en-tête `Prefer: example=<nom>`).
 * Utilisé UNIQUEMENT en mode mock ou démo hors ligne ; hors mock, l'en-tête n'est jamais envoyé.
 */
export const MOCK_EXAMPLE = new HttpContextToken<string | null>(() => null);

/** Code d'erreur à forcer chez Prism (`Prefer: code=401`), pour développer les états d'erreur. Mock uniquement. */
export const MOCK_CODE = new HttpContextToken<number | null>(() => null);
