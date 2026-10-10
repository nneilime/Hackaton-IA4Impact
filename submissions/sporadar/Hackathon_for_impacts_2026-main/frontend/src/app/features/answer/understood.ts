import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmInputImports } from '@spartan-ng/helm/input';
import type { Answer } from '../../core/api/models';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';

interface Chip {
  label: string;
  value: string;
}

/**
 * Bloc 3 : « Ce que l'IA a compris » (`parameters`, `intent`), affiché et corrigeable.
 * Changer le produit ou les pays renvoie la même question à /ask avec `productId` et `countries` renseignés.
 */
@Component({
  selector: 'app-understood',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmButtonImports, HlmInputImports],
  template: `
    <section class="flex flex-col gap-2" [attr.aria-label]="i18n.t('understood.heading')">
      <div class="flex flex-wrap items-center gap-2">
        <span class="type-caption text-ink-muted">{{ i18n.t('understood.heading') }}</span>
        <ul class="flex flex-wrap items-center gap-2">
          @for (chip of chips(); track chip.label) {
            <li class="type-code-sm border-line-strong text-ink-strong rounded-sm border border-dashed px-2 py-0.5">
              {{ chip.label }} = {{ chip.value }}
            </li>
          }
        </ul>
        <button hlmBtn variant="ghost" size="sm" type="button" [attr.aria-expanded]="editing()" (click)="toggle()">
          <ng-icon name="lucideSearch" aria-hidden="true" />{{ i18n.t('understood.edit') }}
        </button>
      </div>

      @if (editing()) {
        <form class="bg-surface-muted flex flex-wrap items-end gap-3 rounded-md p-3" (submit)="$event.preventDefault(); apply()">
          <label class="flex flex-col gap-1 text-sm">
            <span class="text-ink-muted">{{ i18n.t('understood.product') }}</span>
            <input hlmInput class="w-52" name="product" [value]="product()" (input)="product.set($any($event.target).value)" />
          </label>
          <label class="flex flex-col gap-1 text-sm">
            <span class="text-ink-muted">{{ i18n.t('understood.countries') }}</span>
            <input
              hlmInput
              class="w-52"
              name="countries"
              placeholder="FR, CA, DE"
              [value]="countries()"
              (input)="countries.set($any($event.target).value)"
            />
          </label>
          <button hlmBtn size="sm" type="submit">{{ i18n.t('understood.apply') }}</button>
        </form>
      }
    </section>
  `,
})
export class Understood {
  protected readonly i18n = inject(I18n);
  private readonly store = inject(AnswerStore);

  readonly answer = input.required<Answer>();

  protected readonly editing = signal(false);
  protected readonly product = signal('');
  protected readonly countries = signal('');

  protected readonly chips = computed<Chip[]>(() => {
    const answer = this.answer();
    const p = answer.parameters;
    const all = this.i18n.t('understood.all');
    const chips: Chip[] = [
      { label: this.i18n.t('understood.product'), value: p?.productIds?.join(', ') || all },
      { label: this.i18n.t('understood.countries'), value: p?.countries?.length ? p.countries.join(', ') : all },
    ];
    if (p?.activeEntity) chips.push({ label: this.i18n.t('understood.activeEntity'), value: p.activeEntity });
    if (p?.crop) chips.push({ label: this.i18n.t('understood.crop'), value: p.crop });
    if (p?.target) chips.push({ label: this.i18n.t('understood.target'), value: p.target });
    if (p?.referenceDate) chips.push({ label: this.i18n.t('understood.referenceDate'), value: p.referenceDate });
    chips.push({ label: this.i18n.t('understood.intent'), value: answer.intent ?? '—' });
    return chips;
  });

  protected toggle(): void {
    if (!this.editing()) {
      const p = this.answer().parameters;
      this.product.set(p?.productIds?.[0] ?? '');
      this.countries.set(p?.countries?.join(', ') ?? '');
    }
    this.editing.update((value) => !value);
  }

  protected apply(): void {
    const countries = this.countries()
      .split(/[,\s]+/)
      .map((code) => code.trim().toUpperCase())
      .filter((code) => /^[A-Z]{2}$/.test(code));
    this.store.submit(this.store.question(), {
      productId: this.product().trim() || undefined,
      countries,
      intent: this.store.context().intent,
    });
    this.editing.set(false);
  }
}
