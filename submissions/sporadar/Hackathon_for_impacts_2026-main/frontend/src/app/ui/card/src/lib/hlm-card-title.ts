import { Directive } from '@angular/core';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmCardTitle]',
  host: { 'data-slot': 'card-title' },
})
export class HlmCardTitle {
  constructor() {
    // Titre de carte Atlas : Bebas Neue en capitales, 24/26,4 (type-display-m).
    classes(() => 'type-display-m');
  }
}
