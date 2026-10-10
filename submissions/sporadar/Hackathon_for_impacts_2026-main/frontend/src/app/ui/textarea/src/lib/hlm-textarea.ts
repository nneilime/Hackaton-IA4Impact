import { Directive } from '@angular/core';
import { BrnFieldControlDescribedBy } from '@spartan-ng/brain/field';
import { BrnTextarea } from '@spartan-ng/brain/textarea';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmTextarea]',
  hostDirectives: [
    { directive: BrnTextarea, inputs: ['id', 'forceInvalid'] },
    BrnFieldControlDescribedBy,
  ],
  host: { 'data-slot': 'textarea' },
})
export class HlmTextarea {
  constructor() {
    classes(
      () =>
        'border-input bg-surface text-foreground data-[matches-spartan-invalid=true]:border-destructive rounded-md border px-3 py-2 text-sm leading-[21px] transition-colors placeholder:text-muted-foreground flex field-sizing-content min-h-16 w-full disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-muted disabled:text-ink-muted',
    );
  }
}
