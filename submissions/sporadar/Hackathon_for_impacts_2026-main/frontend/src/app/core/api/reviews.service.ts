import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { Review, ReviewRequest } from './models';
import { apiUrl } from './runtime';

/** POST /reviews : décision humaine (valider / rejeter). Route optionnelle côté back. */
@Injectable({ providedIn: 'root' })
export class ReviewsService {
  private readonly http = inject(HttpClient);

  submit(request: ReviewRequest): Observable<Review> {
    return this.http.post<Review>(`${apiUrl}/reviews`, request);
  }
}
