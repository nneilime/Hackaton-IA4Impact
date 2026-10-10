import { Component, DOCUMENT, effect, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { I18n } from './core/i18n/i18n';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class App {
  constructor() {
    const document = inject(DOCUMENT);
    const i18n = inject(I18n);
    // La langue de la page suit la bascule FR / EN (lecteurs d'écran, césure).
    effect(() => {
      document.documentElement.lang = i18n.lang();
    });
  }
}
