import { HttpErrorResponse } from '@angular/common/http';

/** Familles d'erreurs que l'interface sait expliquer (cahier §7). */
export type ErrorKind = 'network' | 'unauthorized' | 'notFound';

export function errorKindOf(error: unknown): ErrorKind {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 401) return 'unauthorized';
    if (error.status === 404) return 'notFound';
  }
  // Réseau coupé, 5xx, réponse illisible : même message, même bouton « Réessayer ».
  return 'network';
}
