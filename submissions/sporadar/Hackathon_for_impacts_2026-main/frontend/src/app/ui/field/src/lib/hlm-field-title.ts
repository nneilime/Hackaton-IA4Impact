import { Directive } from '@angular/core';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmFieldTitle],hlm-field-title',
  host: { 'data-slot': 'field-label' },
})
export class HlmFieldTitle {
  constructor() {
    classes(
      () =>
        'gap-2 text-[13px] leading-[18px] font-semibold text-ink-strong group-data-[disabled=true]/field:text-ink-muted flex w-fit items-center',
    );
  }
}
