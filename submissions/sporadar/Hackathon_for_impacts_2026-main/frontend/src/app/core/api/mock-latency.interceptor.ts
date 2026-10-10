import type { HttpInterceptorFn } from '@angular/common/http';
import { delay } from 'rxjs';
import { usesMockData } from './runtime';

/**
 * Temps de réponse simulé pour POST /ask, en millisecondes. Le vrai back (agent LLM) met plusieurs secondes ;
 * sans ce délai, le mock répond instantanément et l'écran « l'IA réfléchit » ne se voit jamais.
 */
export const MOCK_ASK_LATENCY_MS = 6000;

/**
 * Mock (Prism) et démo hors ligne uniquement : retarde la réponse de POST /ask pour une démo réaliste.
 * Avec le vrai back, cet intercepteur ne touche à rien.
 */
export const mockLatencyInterceptor: HttpInterceptorFn = (req, next) => {
  if (!usesMockData || req.method !== 'POST' || !req.url.split('?')[0].endsWith('/ask')) {
    return next(req);
  }
  return next(req).pipe(delay(MOCK_ASK_LATENCY_MS));
};
