import { Directive } from '@angular/core';
import {
  BrnTooltip,
  BrnTooltipPosition,
  provideBrnTooltipDefaultOptions,
} from '@spartan-ng/brain/tooltip';
import { hlm } from '@spartan-ng/helm/utils';
import { cva } from 'class-variance-authority';

export const DEFAULT_TOOLTIP_SVG_CLASS =
  'bg-primary fill-primary z-50 block size-2.5 translate-y-[calc(-50%-2px)] rotate-45 rounded-[2px]';

export const DEFAULT_TOOLTIP_CONTENT_CLASSES = hlm(
  'rounded-md px-3 py-1.5 text-xs bg-primary text-primary-foreground z-50 w-fit origin-(--radix-tooltip-content-transform-origin) text-balance',
);

export const tooltipPositionVariants = cva('absolute', {
  variants: {
    position: {
      top: 'bottom-0 left-[calc(50%-5px)] translate-y-full',
      bottom: '-top-2.5 left-[calc(50%-5px)] translate-y-0 rotate-180',
      left: '-end-2.5 top-[calc(50%-5px)] translate-y-0 rotate-270 rtl:-rotate-270',
      right: '-start-2.5 top-[calc(50%-5px)] translate-y-0 rotate-90 rtl:-rotate-90',
    },
  },
});

@Directive({
  selector: '[hlmTooltip]',
  providers: [
    provideBrnTooltipDefaultOptions({
      svgClasses: DEFAULT_TOOLTIP_SVG_CLASS,
      tooltipContentClasses: DEFAULT_TOOLTIP_CONTENT_CLASSES,
      arrowClasses: (position: BrnTooltipPosition) => hlm(tooltipPositionVariants({ position })),
    }),
  ],
  hostDirectives: [
    {
      directive: BrnTooltip,
      inputs: ['brnTooltip: hlmTooltip', 'position', 'hideDelay', 'showDelay', 'tooltipDisabled'],
    },
  ],
})
export class HlmTooltip {}
