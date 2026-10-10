import { HttpResponse, type HttpInterceptorFn } from '@angular/common/http';
import { delay, from, map } from 'rxjs';
import { MOCK_EXAMPLE } from './api-context';
import { apiUrl, isOfflineDemo } from './runtime';

/**
 * Démo hors ligne (FRONT_OFFLINE_DEMO=true) : rejoue les exemples fictifs de mocks/examples.yaml,
 * sans aucun serveur. Filet de sécurité pour le pitch si le back tombe ; jamais actif par défaut.
 */
export const offlineDemoInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isOfflineDemo) {
    return next(req);
  }
  const path = (req.url.startsWith(apiUrl) ? req.url.slice(apiUrl.length) : req.url).split('?')[0];
  const key = exampleKey(req.method, path, req.context.get(MOCK_EXAMPLE), req.params.get('format'));
  if (!key) {
    return next(req);
  }
  const status = req.method === 'POST' && path === '/reviews' ? 201 : 200;
  // Chargé à la demande : le JSON d'exemples n'alourdit pas le bundle principal.
  return from(import('../mock/examples.json')).pipe(
    map((module) => new HttpResponse({ status, body: (module.default as Record<string, unknown>)[key] })),
    delay(350),
  );
};

function exampleKey(method: string, path: string, hint: string | null, format: string | null): string | null {
  if (method === 'POST' && path === '/ask') return `ask_${hint ?? 'registration_lookup'}`;
  if (method === 'POST' && path === '/reviews') return 'review_alias_validated';
  if (method !== 'GET') return null;
  if (path === '/products') return hint === 'ingredient_search' ? 'products_ingredient_search' : 'products_name_search';
  if (/^\/products\/[^/]+\/registrations$/.test(path)) return 'registrations_m52';
  if (/^\/products\/[^/]+\/sisters$/.test(path)) return 'sisters_m52';
  if (path === '/compare') return format === 'csv' ? 'compare_m52_fr_ca_csv' : 'compare_m52_fr_ca';
  if (path === '/issues') return 'issues_m52';
  if (path === '/expirations') return 'expirations_12_months';
  if (path === '/sources') return 'sources_all';
  return null;
}
