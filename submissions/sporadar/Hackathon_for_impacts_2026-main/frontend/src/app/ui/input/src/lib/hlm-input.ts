import { Directive } from '@angular/core';
import { BrnFieldControlDescribedBy } from '@spartan-ng/brain/field';
import { BrnInput } from '@spartan-ng/brain/input';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: '[hlmInput]',
  hostDirectives: [
    { directive: BrnInput, inputs: ['id', 'forceInvalid'] },
    BrnFieldControlDescribedBy,
  ],
  host: { 'data-slot': 'input' },
})
export class HlmInput {
  constructor() {
    classes(
      () =>
        'border-input bg-surface text-foreground data-[matches-spartan-invalid=true]:border-destructive h-10 rounded-md border px-3 py-1 text-sm leading-[21px] transition-colors file:h-7 file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground w-full min-w-0 file:inline-flex file:border-0 file:bg-transparent disabled:pointer-events-none disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-muted disabled:text-ink-muted',
    );
  }
}
