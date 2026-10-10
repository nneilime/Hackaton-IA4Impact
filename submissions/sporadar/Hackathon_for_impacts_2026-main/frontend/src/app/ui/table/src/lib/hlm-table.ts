import { Directive } from '@angular/core';
import { classes } from '@spartan-ng/helm/utils';

@Directive({
  selector: 'div[hlmTableContainer]',
  host: { 'data-slot': 'table-container' },
})
export class HlmTableContainer {
  constructor() {
    classes(() => 'border-line bg-surface relative w-full overflow-x-auto rounded-lg border');
  }
}

/**
 * Directive to apply Atlas styling to a <table> element.
 */
@Directive({
  selector: 'table[hlmTable]',
  host: { 'data-slot': 'table' },
})
export class HlmTable {
  constructor() {
    classes(() => 'w-full caption-bottom border-separate border-spacing-0 text-sm leading-[21px]');
  }
}

/**
 * Directive to apply Atlas styling to a <thead> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'thead[hlmTHead],thead[hlmTableHeader]',
  host: { 'data-slot': 'table-header' },
})
export class HlmTHead {
  constructor() {
    classes(() => 'bg-surface-muted');
  }
}

/**
 * Directive to apply Atlas styling to a <tbody> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'tbody[hlmTBody],tbody[hlmTableBody]',
  host: { 'data-slot': 'table-body' },
})
export class HlmTBody {
  constructor() {
    classes(() => '[&_tr:last-child>*]:border-b-0');
  }
}

/**
 * Directive to apply Atlas styling to a <tfoot> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'tfoot[hlmTFoot],tfoot[hlmTableFooter]',
  host: { 'data-slot': 'table-footer' },
})
export class HlmTFoot {
  constructor() {
    classes(() => 'bg-surface-muted border-line border-t font-semibold [&>tr]:last:border-b-0');
  }
}

/**
 * Directive to apply Atlas styling to a <tr> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'tr[hlmTr],tr[hlmTableRow]',
  host: { 'data-slot': 'table-row' },
})
export class HlmTr {
  constructor() {
    classes(
      () =>
        'hover:bg-surface-muted data-[state=selected]:bg-surface-muted transition-colors has-aria-expanded:bg-surface-muted',
    );
  }
}

/**
 * Directive to apply Atlas styling to a <th> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'th[hlmTh],th[hlmTableHead]',
  host: { 'data-slot': 'table-head' },
})
export class HlmTh {
  constructor() {
    classes(
      () =>
        'border-line text-ink-strong h-10 border-b px-3 py-2 text-start align-middle text-xs leading-4 font-semibold tracking-[0.04em] whitespace-nowrap uppercase [&:has([role=checkbox])]:pe-0',
    );
  }
}

/**
 * Directive to apply Atlas styling to a <td> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'td[hlmTd],td[hlmTableCell]',
  host: { 'data-slot': 'table-cell' },
})
export class HlmTd {
  constructor() {
    classes(() => 'border-line border-b px-3 py-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pe-0');
  }
}

/**
 * Directive to apply Atlas styling to a <caption> element
 * within an HlmTable context.
 */
@Directive({
  selector: 'caption[hlmCaption],caption[hlmTableCaption]',
  host: { 'data-slot': 'table-caption' },
})
export class HlmCaption {
  constructor() {
    classes(() => 'text-muted-foreground p-3 text-start text-sm');
  }
}
