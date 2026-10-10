import { BooleanInput } from '@angular/cdk/coercion';
import {
  booleanAttribute,
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
} from '@angular/core';
import { BrnSelectContent, BrnSelectList } from '@spartan-ng/brain/select';
import { classes, hlm } from '@spartan-ng/helm/utils';
import { HlmSelectScrollDown } from './hlm-select-scroll-down';
import { HlmSelectScrollUp } from './hlm-select-scroll-up';

@Component({
  selector: 'hlm-select-content',
  imports: [HlmSelectScrollUp, HlmSelectScrollDown, BrnSelectList],
  changeDetection: ChangeDetectionStrategy.OnPush,
  hostDirectives: [BrnSelectContent],
  template: `
    @if (showScroll()) {
      <hlm-select-scroll-up />
    }

    <div brnSelectList [class]="_computedListboxClasses()">
      <ng-content />
    </div>

    @if (showScroll()) {
      <hlm-select-scroll-down />
    }
  `,
})
export class HlmSelectContent {
  protected readonly _computedListboxClasses = computed(() => hlm('flex flex-col'));

  public readonly showScroll = input<boolean, BooleanInput>(false, { transform: booleanAttribute });

  constructor() {
    classes(
      () =>
        'bg-popover no-scrollbar text-popover-foreground border-line max-h-72 min-w-36 flex-col rounded-lg border shadow-md relative flex w-(--brn-select-width) overflow-x-hidden overflow-y-auto',
    );
  }
}
