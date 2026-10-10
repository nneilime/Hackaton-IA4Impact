import type { HttpInterceptorFn } from '@angular/common/http';
import { MOCK_CODE, MOCK_EXAMPLE } from './api-context';
import { isMock } from './runtime';

/**
 * Mode mock uniquement : choisit la réponse d'exemple de Prism avec l'en-tête `Prefer`.
 * Hors mock, cet intercepteur ne touche à rien : l'en-tête n'est jamais envoyé.
 */
export const mockExampleInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isMock) {
    return next(req);
  }
  const example = req.context.get(MOCK_EXAMPLE);
  const code = req.context.get(MOCK_CODE);
  const preferences = [code ? `code=${code}` : null, example ? `example=${example}` : null].filter(Boolean);
  if (preferences.length === 0) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { Prefer: preferences.join(', ') } }));
};
