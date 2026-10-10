import { environment } from '../../../environments/environment';

// `environment` est généré `as const` : on élargit les types pour pouvoir tester les deux valeurs.
export const apiUrl: string = environment.apiUrl;
export const isMock: boolean = environment.mock;
export const isOfflineDemo: boolean = environment.offlineDemo;
/** Vrai quand les réponses viennent d'exemples fictifs (Prism ou rejeu hors ligne). */
export const usesMockData: boolean = isMock || isOfflineDemo;
