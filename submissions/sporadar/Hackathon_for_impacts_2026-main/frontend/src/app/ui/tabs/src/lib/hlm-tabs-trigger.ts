import { Directive, input } from '@angular/core';
import { BrnTabsTrigger } from '@spartan-ng/brain/tabs';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmTabsTrigger]',
  hostDirectives: [
    { directive: BrnTabsTrigger, inputs: ['brnTabsTrigger: hlmTabsTrigger', 'disabled'] },
  ],
  host: {
    'data-slot': 'tabs-trigger',
  },
})
export class HlmTabsTrigger {
  public readonly triggerFor = input.required<string>({ alias: 'hlmTabsTrigger' });
  constructor() {
    // Onglet Atlas : libellé type-label, onglet actif souligné du rouge de marque (rand, accent rare).
    classes(() => [
      "gap-1.5 border border-transparent px-3 py-2 text-[13px] leading-[18px] font-semibold text-ink-muted hover:text-ink-strong data-active:text-ink-strong relative inline-flex flex-none items-center justify-center whitespace-nowrap transition-colors group-data-[orientation=vertical]/tabs:w-full group-data-[orientation=vertical]/tabs:justify-start disabled:pointer-events-none disabled:text-ink-muted [&_ng-icon:not([class*='text-'])]:text-[length:--spacing(4)] [&_ng-icon]:pointer-events-none [&_ng-icon]:shrink-0",
      'after:bg-brand after:absolute after:opacity-0 after:transition-opacity group-data-[orientation=horizontal]/tabs:after:inset-x-0 group-data-[orientation=horizontal]/tabs:after:-bottom-px group-data-[orientation=horizontal]/tabs:after:h-0.5 group-data-[orientation=vertical]/tabs:after:inset-y-0 group-data-[orientation=vertical]/tabs:after:-right-px group-data-[orientation=vertical]/tabs:after:w-0.5 data-active:after:opacity-100',
    ]);
  }
}
