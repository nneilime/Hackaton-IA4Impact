import { Directive, input, signal } from '@angular/core';
import { BrnButton } from '@spartan-ng/brain/button';
import { classes } from '@spartan-ng/helm/utils';
import { cva, type VariantProps } from 'class-variance-authority';
import type { ClassValue } from 'clsx';
import { injectBrnButtonConfig } from './hlm-button.token';

/**
 * Boutons Atlas : pilule (radius-pill), texte 14/21 semi-gras, focus plein 2 px (outline global),
 * désactivé en surface-muted + ink-muted (jamais une simple opacité).
 * `primary` : une seule fois par vue, pour l'action que l'écran sert.
 */
export const buttonVariants = cva(
  "rounded-pill border border-transparent text-sm leading-[21px] font-semibold group/button inline-flex shrink-0 items-center justify-center whitespace-nowrap transition-colors select-none data-disabled:pointer-events-none data-disabled:cursor-not-allowed data-disabled:border-line data-disabled:bg-surface-muted data-disabled:text-ink-muted [&_ng-icon:not([class*='text-'])]:text-[length:--spacing(4)] [&_ng-icon]:pointer-events-none [&_ng-icon]:shrink-0",
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary-hover',
        secondary:
          'border-line-strong bg-surface text-ink-strong hover:bg-surface-muted aria-expanded:bg-surface-muted',
        outline:
          'border-line-strong bg-surface text-ink-strong hover:bg-surface-muted aria-expanded:bg-surface-muted',
        ghost: 'text-ink-strong hover:bg-surface-muted aria-expanded:bg-surface-muted',
        destructive: 'bg-status-rejected text-on-status-rejected hover:bg-status-rejected',
        link: 'rounded-sm text-link underline underline-offset-2 hover:no-underline',
      },
      size: {
        default: 'gap-2 px-5 py-2.5',
        xs: "gap-1 px-2.5 py-1 text-xs leading-4 [&_ng-icon:not([class*='text-'])]:text-[length:--spacing(3)]",
        sm: 'gap-1.5 px-3.5 py-1.5 text-[13px] leading-[18px]',
        lg: 'gap-2 px-6 py-3',
        icon: 'size-10',
        'icon-xs': "size-6 [&_ng-icon:not([class*='text-'])]:text-[length:--spacing(3)]",
        'icon-sm': 'size-8',
        'icon-lg': 'size-12',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
);

export type ButtonVariants = VariantProps<typeof buttonVariants>;

@Directive({
  selector: 'button[hlmBtn], a[hlmBtn]',
  exportAs: 'hlmBtn',
  hostDirectives: [{ directive: BrnButton, inputs: ['disabled'] }],
  host: { 'data-slot': 'button' },
})
export class HlmButton {
  private readonly _config = injectBrnButtonConfig();

  private readonly _additionalClasses = signal<ClassValue>('');

  public readonly variant = input<ButtonVariants['variant']>(this._config.variant);

  public readonly size = input<ButtonVariants['size']>(this._config.size);

  constructor() {
    classes(() => [
      buttonVariants({ variant: this.variant(), size: this.size() }),
      this._additionalClasses(),
    ]);
  }

  setClass(classes: string): void {
    this._additionalClasses.set(classes);
  }
}
