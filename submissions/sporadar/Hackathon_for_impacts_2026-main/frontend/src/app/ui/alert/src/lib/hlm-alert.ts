import { Directive, input } from '@angular/core';
import { classes } from '@spartan-ng/helm/utils';
import { cva, type VariantProps } from 'class-variance-authority';

const alertVariants = cva(
  "grid gap-0.5 rounded-lg border px-4 py-3 text-start text-sm has-data-[slot=alert-action]:relative has-data-[slot=alert-action]:pr-18 has-[>ng-icon]:grid-cols-[auto_1fr] has-[>ng-icon]:gap-x-2.5 *:[ng-icon]:row-span-2 *:[ng-icon]:translate-y-0.5 *:[ng-icon]:text-current *:[ng-icon:not([class*='text-'])]:text-[length:--spacing(4)] group/alert relative w-full",
  {
    variants: {
      variant: {
        // Style « Disclaimer » Atlas : bandeau gris Lallemand.
        default: 'border-transparent bg-surface-muted text-ink',
        // Avertissement : ambre (le texte reste en `status-review`, contour décoratif).
        warning: 'border-status-review-line bg-status-review-soft text-status-review',
        destructive: 'border-status-rejected bg-surface text-status-rejected',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export type AlertVariants = VariantProps<typeof alertVariants>;

@Directive({
  selector: 'hlm-alert,[hlmAlert]',
  host: {
    'data-slot': 'alert',
    role: 'alert',
  },
})
export class HlmAlert {
  public readonly variant = input<AlertVariants['variant']>('default');

  constructor() {
    classes(() => alertVariants({ variant: this.variant() }));
  }
}
