import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { MOCK_EXAMPLE } from './api-context';
import type { Product, SisterCandidatesResponse } from './models';
import { apiUrl, usesMockData } from './runtime';

export interface ProductSearch {
  q?: string;
  activeEntity?: string;
  crop?: string;
  target?: string;
  country?: string;
  includeCompetitors?: boolean;
}

/** GET /products et routes dépendantes d'un produit. */
@Injectable({ providedIn: 'root' })
export class ProductsService {
  private readonly http = inject(HttpClient);

  search(filters: ProductSearch): Observable<{ items: Product[] }> {
    let params = new HttpParams();
    for (const [name, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params = params.set(name, String(value));
    }
    // Mock : l'exemple « ingredient_search » dès qu'un filtre substance, culture ou cible est présent.
    const byIngredient = !!(filters.activeEntity || filters.crop || filters.target);
    const context = usesMockData
      ? new HttpContext().set(MOCK_EXAMPLE, byIngredient ? 'ingredient_search' : null)
      : undefined;
    return this.http.get<{ items: Product[] }>(`${apiUrl}/products`, { params, context });
  }

  sisters(productId: string): Observable<SisterCandidatesResponse> {
    return this.http.get<SisterCandidatesResponse>(`${apiUrl}/products/${encodeURIComponent(productId)}/sisters`);
  }
}
