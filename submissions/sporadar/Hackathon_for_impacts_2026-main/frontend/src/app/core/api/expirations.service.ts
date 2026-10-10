import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { ExpirationsResponse } from './models';
import { apiUrl } from './runtime';

/** GET /expirations : homologations qui expirent bientôt. */
@Injectable({ providedIn: 'root' })
export class ExpirationsService {
  private readonly http = inject(HttpClient);

  list(withinMonths = 12, country?: string): Observable<ExpirationsResponse> {
    let params = new HttpParams().set('withinMonths', withinMonths);
    if (country) params = params.set('country', country);
    return this.http.get<ExpirationsResponse>(`${apiUrl}/expirations`, { params });
  }
}
