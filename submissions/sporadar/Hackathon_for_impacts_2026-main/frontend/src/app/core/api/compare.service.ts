import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { ComparisonResponse } from './models';
import { apiUrl } from './runtime';

export interface CompareQuery {
  productId: string;
  countries: readonly string[];
  crop?: string;
  target?: string;
}

/** GET /compare (JSON ou CSV). */
@Injectable({ providedIn: 'root' })
export class CompareService {
  private readonly http = inject(HttpClient);

  compare(query: CompareQuery): Observable<ComparisonResponse> {
    return this.http.get<ComparisonResponse>(`${apiUrl}/compare`, { params: this.params(query) });
  }

  /** Export pour Excel / Power Automate : le CSV vient du back, le front ne le fabrique pas. */
  csv(query: CompareQuery): Observable<string> {
    return this.http.get(`${apiUrl}/compare`, {
      params: this.params(query).set('format', 'csv'),
      responseType: 'text',
    });
  }

  private params(query: CompareQuery): HttpParams {
    let params = new HttpParams().set('productId', query.productId).set('countries', query.countries.join(','));
    if (query.crop) params = params.set('crop', query.crop);
    if (query.target) params = params.set('target', query.target);
    return params;
  }
}
