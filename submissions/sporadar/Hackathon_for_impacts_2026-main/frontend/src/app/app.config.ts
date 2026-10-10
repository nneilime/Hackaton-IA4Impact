import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { provideIcons } from '@ng-icons/core';
import {
  lucideArrowRight,
  lucideBan,
  lucideCheck,
  lucideCircleAlert,
  lucideCircleDashed,
  lucideCircleHelp,
  lucideClock,
  lucideCloudOff,
  lucideDatabase,
  lucideDownload,
  lucideExternalLink,
  lucideFileText,
  lucideInfo,
  lucideMinus,
  lucideRefreshCw,
  lucideSearch,
  lucideSparkles,
  lucideTriangleAlert,
  lucideX,
} from '@ng-icons/lucide';
import { mockExampleInterceptor } from './core/api/mock-example.interceptor';
import { mockLatencyInterceptor } from './core/api/mock-latency.interceptor';
import { offlineDemoInterceptor } from './core/api/offline-demo.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Chaque question passe par l'URL (?q=…) : les View Transitions animent le passage accueil ↔ résultats
    // (la barre de question glisse du hero vers le haut de page, voir styles.css). Ignoré si le navigateur ne sait pas faire.
    provideRouter(routes, withViewTransitions({ skipInitialTransition: true })),
    // Ordre : la latence simulée enveloppe tout (y compris la démo hors ligne) ; la démo hors ligne répond avant
    // tout appel réseau ; le mock ne fait qu'ajouter l'en-tête Prefer.
    provideHttpClient(withInterceptors([mockLatencyInterceptor, offlineDemoInterceptor, mockExampleInterceptor])),
    provideIcons({
      lucideArrowRight,
      lucideBan,
      lucideCheck,
      lucideCircleAlert,
      lucideCircleDashed,
      lucideCircleHelp,
      lucideClock,
      lucideCloudOff,
      lucideDatabase,
      lucideDownload,
      lucideExternalLink,
      lucideFileText,
      lucideInfo,
      lucideMinus,
      lucideRefreshCw,
      lucideSearch,
      lucideSparkles,
      lucideTriangleAlert,
      lucideX,
    }),
  ],
};
