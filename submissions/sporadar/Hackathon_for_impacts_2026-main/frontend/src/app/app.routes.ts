import { Routes } from '@angular/router';
import { AnswerPage } from './features/answer/answer-page';

// Une seule page : la question, la langue et les paramètres corrigés vivent dans l'URL (?q=…&lang=…).
export const routes: Routes = [
  { path: '', component: AnswerPage },
  { path: '**', redirectTo: '' },
];
