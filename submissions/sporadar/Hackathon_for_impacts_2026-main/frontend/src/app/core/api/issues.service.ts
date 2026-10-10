import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { IssueType, IssuesResponse } from './models';
import { apiUrl } from './runtime';

export interface IssuesQuery {
  productId?: string;
  country?: string;
  issueType?: IssueType;
}

/** GET /issues : file de travail des champs manquants, incertains ou non validés. */
@Injectable({ providedIn: 'root' })
export class IssuesService {
  private readonly http = inject(HttpClient);

  list(query: IssuesQuery = {}): Observable<IssuesResponse> {
    let params = new HttpParams();
    if (query.productId) params = params.set('productId', query.productId);
    if (query.country) params = params.set('country', query.country);
    if (query.issueType) params = params.set('issueType', query.issueType);
    return this.http.get<IssuesResponse>(`${apiUrl}/issues`, { params });
  }
}
