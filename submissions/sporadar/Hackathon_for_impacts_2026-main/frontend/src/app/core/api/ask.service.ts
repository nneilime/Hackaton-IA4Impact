import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { MOCK_CODE, MOCK_EXAMPLE } from './api-context';
import { guessMockExample } from './mock-intent';
import type { Answer, AskRequest } from './models';
import { apiUrl, usesMockData } from './runtime';

/** POST /ask : la question en langage naturel. */
@Injectable({ providedIn: 'root' })
export class AskService {
  private readonly http = inject(HttpClient);

  /**
   * @param mockExample nom de l'exemple à rejouer (intent de la question cliquée). Ignoré hors mock.
   * @param mockCode code d'erreur à forcer (développement des états d'erreur). Ignoré hors mock.
   */
  ask(request: AskRequest, mockExample?: string | null, mockCode?: number | null): Observable<Answer> {
    let context = new HttpContext();
    if (usesMockData) {
      context = context
        .set(MOCK_EXAMPLE, mockExample ?? guessMockExample(request.question))
        .set(MOCK_CODE, mockCode ?? null);
    }
    return this.http.post<Answer>(`${apiUrl}/ask`, request, { context });
  }
}
