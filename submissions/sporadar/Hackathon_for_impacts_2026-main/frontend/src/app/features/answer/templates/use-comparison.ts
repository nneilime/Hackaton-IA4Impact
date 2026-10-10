import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgIcon } from '@ng-icons/core';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmInputImports } from '@spartan-ng/helm/input';
import { HlmTableImports } from '@spartan-ng/helm/table';
import { CompareService, type CompareQuery } from '../../../core/api/compare.service';
import { errorKindOf, type ErrorKind } from '../../../core/api/http-error';
import type {
  AuthorizedUse,
  ComparisonCell,
  ComparisonResponse,
  ComparisonRow,
  MappingStatus,
} from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { DataBadges } from '../../../shared/data-badges';
import { EmptyCellReason } from '../../../shared/empty-cell-reason';
import { EvidenceLink } from '../../../shared/evidence-link';
import { StatusBadge } from '../../../shared/status-badge';

/**
 * T02 · `use_comparison` : une ligne par culture × cible (alignées par code EPPO), une colonne par pays.
 * Les colonnes ne sont JAMAIS fusionnées : aucune moyenne, aucune conversion, aucun regroupement de valeurs.
 * Le composant accepte un `ComparisonResponse`, qu'il vienne de `POST /ask` ou de `GET /compare` (même forme).
 */
@Component({
  selector: 'app-use-comparison',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgIcon,
    HlmBadgeImports,
    HlmButtonImports,
    HlmInputImports,
    HlmTableImports,
    StatusBadge,
    EvidenceLink,
    DataBadges,
    EmptyCellReason,
  ],
  template: `
    <form class="mb-3 flex flex-wrap items-end gap-3" (submit)="$event.preventDefault(); applyFilters()">
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-ink-muted">{{ i18n.t('cmp.filterCrop') }}</span>
        <input hlmInput class="w-48" name="crop" [value]="crop()" (input)="crop.set($any($event.target).value)" />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-ink-muted">{{ i18n.t('cmp.filterTarget') }}</span>
        <input hlmInput class="w-48" name="target" [value]="target()" (input)="target.set($any($event.target).value)" />
      </label>
      <button hlmBtn variant="secondary" size="sm" type="submit" [disabled]="loading()">
        <ng-icon name="lucideSearch" aria-hidden="true" />{{ i18n.t('cmp.filter') }}
      </button>
      @if (override()) {
        <button hlmBtn variant="ghost" size="sm" type="button" (click)="resetFilters()">{{ i18n.t('cmp.reset') }}</button>
      }
      <button hlmBtn variant="ghost" size="sm" type="button" class="md:ml-auto" [disabled]="exporting()" (click)="exportCsv()">
        <ng-icon name="lucideDownload" aria-hidden="true" />{{ i18n.t('cmp.exportCsv') }}
      </button>
    </form>

    @if (error(); as kind) {
      <p class="border-status-rejected text-status-rejected mb-3 rounded-sm border px-3 py-2 text-sm" role="alert">
        {{ i18n.t(kind === 'unauthorized' ? 'error.unauthorized' : kind === 'notFound' ? 'error.notFound' : 'error.network') }}
      </p>
    }

    @if (rows().length === 0) {
      <p class="border-line-strong rounded-md border border-dashed p-4 text-sm">{{ i18n.t('cmp.noRows') }}</p>
    } @else {
      <div hlmTableContainer [attr.aria-busy]="loading()">
        <table hlmTable>
          <caption class="sr-only">
            {{ i18n.t('cmp.caption') }}
          </caption>
          <thead hlmTHead>
            <tr hlmTr>
              <th hlmTh scope="col" class="bg-surface-muted sticky left-0 min-w-56">{{ i18n.t('cmp.cropTarget') }}</th>
              @for (code of data().countries; track code) {
                <th hlmTh scope="col" class="min-w-52">
                  <span class="flex flex-col gap-1 tracking-normal normal-case">
                    <span class="border-line-strong bg-surface inline-flex w-fit overflow-hidden rounded-sm border text-[13px] leading-[18px]">
                      <span class="type-code bg-primary text-primary-foreground px-1.5 py-0.5">{{ code }}</span>
                      <span class="text-ink-strong px-2 py-0.5 font-semibold">{{ authority(code) }}</span>
                    </span>
                    <span class="type-code-sm text-ink-muted">{{ sourceLine(code) }}</span>
                  </span>
                </th>
              }
            </tr>
          </thead>
          <tbody hlmTBody>
            @for (row of rows(); track row.rowId) {
              <tr hlmTr [attr.data-differs]="row.differsAcrossCountries ? 'true' : null">
                <th
                  scope="row"
                  class="bg-surface border-line sticky left-0 border-r border-b px-3 py-2 text-start align-top font-normal"
                >
                  <div class="text-ink-strong font-semibold">{{ row.cropNormalized ?? originals(row, 'crop')[0]?.text ?? '—' }}</div>
                  @for (o of originals(row, 'crop'); track o.country) {
                    <div class="text-ink-muted text-xs leading-4">« {{ o.text }} » ({{ o.country }})</div>
                  }
                  <div class="mt-1 flex flex-wrap items-center gap-1">
                    <span class="type-code-sm bg-surface-muted text-ink-strong rounded-sm px-1.5">{{ row.eppoCropCode ?? '—' }}</span>
                    @if (mapping(row, 'crop'); as status) {
                      <app-status-badge [state]="status === 'unmapped' ? 'unknown' : 'to_verify'" [text]="mappingLabel(status)" />
                    }
                  </div>

                  <div class="text-ink mt-2">{{ row.targetNormalized ?? originals(row, 'target')[0]?.text ?? '—' }}</div>
                  @for (o of originals(row, 'target'); track o.country) {
                    <div class="text-ink-muted text-xs leading-4">« {{ o.text }} » ({{ o.country }})</div>
                  }
                  <div class="mt-1 flex flex-wrap items-center gap-1">
                    <span class="type-code-sm bg-surface-muted text-ink-strong rounded-sm px-1.5">{{ row.eppoTargetCode ?? '—' }}</span>
                    @if (mapping(row, 'target'); as status) {
                      <app-status-badge [state]="status === 'unmapped' ? 'unknown' : 'to_verify'" [text]="mappingLabel(status)" />
                    }
                  </div>

                  @if (row.differsAcrossCountries) {
                    <span hlmBadge variant="review" size="sm" class="mt-2">
                      <ng-icon name="lucideTriangleAlert" aria-hidden="true" />{{ i18n.t('cmp.differs') }}
                    </span>
                  }
                </th>

                @for (code of data().countries; track code) {
                  @let cell = cellFor(row, code);
                  <td
                    hlmTd
                    class="align-top whitespace-normal"
                    [class]="row.differsAcrossCountries ? 'shadow-[inset_3px_0_0_var(--status-review-line)]' : ''"
                    [attr.data-country]="code"
                  >
                    @if (cell && cell.state === 'present') {
                      <div class="flex flex-col gap-3">
                        @for (use of cell.uses ?? []; track use.useId) {
                          <div class="flex flex-col items-start gap-1" data-use>
                            <app-evidence-link [view]="useView(use, row, cell)">
                              <span class="text-ink font-semibold">{{ dose(use) }}</span>
                            </app-evidence-link>
                            @if (use.doseUnitOriginal) {
                              <span class="text-ink-muted text-xs">« {{ use.doseUnitOriginal }} »</span>
                            }
                            @if (conditions(use); as text) {
                              <span class="text-ink-muted text-xs">{{ text }}</span>
                            }
                            <app-status-badge [state]="use.evidence.validationStatus" />
                            <app-data-badges [synthetic]="use.isSynthetic || use.evidence.isSynthetic" [frozen]="use.evidence.isFrozenExtract" />
                          </div>
                        }
                      </div>
                    } @else if (cell && cell.state !== 'present') {
                      <app-empty-cell-reason [state]="cell.state" />
                    } @else {
                      <span class="text-ink-muted text-xs">{{ i18n.t('cmp.noCell') }}</span>
                    }
                  </td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>
      <p class="type-caption text-ink-muted mt-2">{{ i18n.t('cmp.footnote') }}</p>
    }
  `,
})
export class UseComparison {
  protected readonly i18n = inject(I18n);
  private readonly compareService = inject(CompareService);
  private readonly destroyRef = inject(DestroyRef);

  readonly comparison = input.required<ComparisonResponse>();

  protected readonly crop = signal('');
  protected readonly target = signal('');
  /** Résultat d'un filtre appliqué via GET /compare ; remplace la réponse reçue de /ask tant qu'il existe. */
  protected readonly override = signal<ComparisonResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly exporting = signal(false);
  protected readonly error = signal<ErrorKind | null>(null);

  protected readonly data = computed(() => this.override() ?? this.comparison());
  protected readonly rows = computed(() => this.data().rows ?? []);

  protected applyFilters(): void {
    this.loading.set(true);
    this.error.set(null);
    this.compareService
      .compare(this.query())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.override.set(response);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(errorKindOf(err));
          this.loading.set(false);
        },
      });
  }

  protected resetFilters(): void {
    this.crop.set('');
    this.target.set('');
    this.override.set(null);
    this.error.set(null);
  }

  protected exportCsv(): void {
    this.exporting.set(true);
    this.error.set(null);
    this.compareService
      .csv(this.query())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (csv) => {
          download(csv, `comparison-${this.data().productId}.csv`);
          this.exporting.set(false);
        },
        error: (err: unknown) => {
          this.error.set(errorKindOf(err));
          this.exporting.set(false);
        },
      });
  }

  protected cellFor(row: ComparisonRow, countryCode: string): ComparisonCell | undefined {
    return row.cells.find((cell) => cell.countryCode === countryCode);
  }

  protected authority(countryCode: string): string {
    return this.data().registrations.find((r) => r.countryCode === countryCode)?.authorityName ?? '';
  }

  /** Source et date de collecte de la colonne : la preuve de l'homologation, à défaut la couverture. */
  protected sourceLine(countryCode: string): string {
    const evidence = this.data().registrations.find((r) => r.countryCode === countryCode)?.evidence;
    if (evidence) {
      return `${evidence.sourceId} · ${this.i18n.date(evidence.collectedAt)}`;
    }
    const coverage = this.data().coverage?.find((c) => c.countryCode === countryCode);
    return coverage ? `${coverage.sourceIds?.join(', ') || '—'} · ${this.i18n.date(coverage.lastCollectedAt)}` : '—';
  }

  /** Noms d'origine de la culture ou de la cible, un par pays, dans la langue de la source. */
  protected originals(row: ComparisonRow, kind: 'crop' | 'target'): { country: string; text: string }[] {
    const seen: { country: string; text: string }[] = [];
    for (const cell of row.cells) {
      const original = (cell.uses ?? []).map((u) => (kind === 'crop' ? u.cropOriginal : u.targetOriginal)).find(Boolean);
      if (original) seen.push({ country: cell.countryCode, text: original });
    }
    return seen;
  }

  /** Statut du mapping EPPO à signaler : le moins bon des usages de la ligne (rien si tout est validé). */
  protected mapping(row: ComparisonRow, kind: 'crop' | 'target'): Exclude<MappingStatus, 'validated'> | null {
    const statuses = row.cells.flatMap((cell) =>
      (cell.uses ?? []).map((u) => (kind === 'crop' ? u.cropMappingStatus : u.targetMappingStatus)),
    );
    if (statuses.includes('unmapped')) return 'unmapped';
    if (statuses.includes('to_verify')) return 'to_verify';
    return null;
  }

  protected mappingLabel(status: Exclude<MappingStatus, 'validated'>): string {
    return this.i18n.t(status === 'unmapped' ? 'mapping.unmapped' : 'mapping.to_verify');
  }

  /** Dose telle que stockée, avec son unité normalisée : jamais convertie. */
  protected dose(use: AuthorizedUse): string {
    if (use.doseValue === null || use.doseValue === undefined) {
      return this.i18n.t('cmp.noDose');
    }
    return `${this.i18n.number(use.doseValue)} ${use.doseUnitNormalized ?? use.doseUnitOriginal ?? ''}`.trim();
  }

  protected conditions(use: AuthorizedUse): string {
    const parts: string[] = [];
    if (use.applicationMethod) parts.push(use.applicationMethod);
    if (use.maxApplications != null) parts.push(this.i18n.t('cmp.max', { n: use.maxApplications }));
    if (use.applicationIntervalDays != null) parts.push(this.i18n.t('cmp.interval', { n: use.applicationIntervalDays }));
    if (use.phiDays != null) parts.push(this.i18n.t('cmp.phi', { n: use.phiDays }));
    if (use.reiHours != null) parts.push(this.i18n.t('cmp.rei', { n: use.reiHours }));
    if (use.restrictionsOriginal) parts.push(`« ${use.restrictionsOriginal} »`);
    return parts.join(' · ');
  }

  protected useView(use: AuthorizedUse, row: ComparisonRow, cell: ComparisonCell): EvidenceView {
    const registration = this.data().registrations.find((r) => r.registrationId === cell.registrationId);
    const unit = use.doseUnitOriginal ?? '';
    return {
      title: this.i18n.t('cmp.evidenceTitle', {
        crop: row.cropNormalized ?? use.cropOriginal ?? '—',
        target: row.targetNormalized ?? use.targetOriginal ?? '—',
        country: cell.countryCode,
      }),
      evidence: use.evidence,
      valueNormalized: this.dose(use),
      valueOriginal: use.doseValue == null ? null : `${this.i18n.number(use.doseValue)} ${unit}`.trim(),
      matchedVia: registration?.matchedVia?.matchedName,
    };
  }

  private query(): CompareQuery {
    return {
      productId: this.data().productId,
      countries: this.data().countries,
      crop: this.crop().trim() || undefined,
      target: this.target().trim() || undefined,
    };
  }
}

/** Télécharge un texte sous forme de fichier (le CSV vient du back, il n'est pas fabriqué ici). */
function download(content: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
