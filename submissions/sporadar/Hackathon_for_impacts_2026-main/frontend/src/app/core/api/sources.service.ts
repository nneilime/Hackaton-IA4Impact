import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type { SourceInfo } from './models';
import { apiUrl } from './runtime';

/** GET /sources : sources officielles intégrées et fraîcheur de la collecte. */
@Injectable({ providedIn: 'root' })
export class SourcesService {
  private readonly http = inject(HttpClient);

  list(): Observable<{ items: SourceInfo[] }> {
    return this.http.get<{ items: SourceInfo[] }>(`${apiUrl}/sources`);
  }
}
