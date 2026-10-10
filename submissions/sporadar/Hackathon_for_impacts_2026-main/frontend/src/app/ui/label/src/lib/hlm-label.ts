import { Directive } from '@angular/core';
import { BrnLabel } from '@spartan-ng/brain/label';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmLabel]',
  hostDirectives: [{ directive: BrnLabel, inputs: ['id', 'for'] }],
  host: { 'data-slot': 'label' },
})
export class HlmLabel {
  constructor() {
    classes(
      () =>
        'gap-2 text-[13px] leading-[18px] font-semibold text-ink-strong group-data-[disabled=true]:text-ink-muted peer-disabled:text-ink-muted flex items-center select-none group-data-[disabled=true]:pointer-events-none peer-disabled:cursor-not-allowed',
    );
  }
}
