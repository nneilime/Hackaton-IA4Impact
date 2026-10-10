import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgIcon } from '@ng-icons/core';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmTableImports } from '@spartan-ng/helm/table';
import { IssuesService } from '../../../core/api/issues.service';
import type { Answer, DataIssue, IssueType } from '../../../core/api/models';
import { I18n } from '../../../core/i18n/i18n';
import type { EvidenceView } from '../../../core/state/evidence-view';
import { ConfidenceMeter } from '../../../shared/confidence-meter';
import { EvidenceLink } from '../../../shared/evidence-link';
import { StatusBadge } from '../../../shared/status-badge';

const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

/**
 * T03 · `data_quality` : une file de travail, pas un paragraphe.
 * Compteurs par type de problème (qui servent de filtres), puis tableau trié par la priorité calculée par le back.
 * Confiance IA et statut de validation sont deux colonnes distinctes.
 */
@Component({
  selector: 'app-data-quality',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmBadgeImports, HlmTableImports, StatusBadge, ConfidenceMeter, EvidenceLink],
  template: `
    @if (types().length > 0) {
      <div class="mb-3 flex flex-wrap items-center gap-2" role="group" [attr.aria-label]="i18n.t('dq.filters')">
        <button
          type="button"
          class="border-line-strong text-ink-strong hover:bg-surface-muted aria-pressed:bg-primary aria-pressed:text-primary-foreground rounded-pill border px-3 py-1 text-sm font-semibold"
          [attr.aria-pressed]="selected() === null"
          (click)="select(null)"
        >
          {{ i18n.t('dq.all') }} <span class="type-code-sm">{{ total() }}</span>
        </button>
        @for (type of types(); track type) {
          <button
            type="button"
            class="border-line-strong text-ink-strong hover:bg-surface-muted aria-pressed:bg-primary aria-pressed:text-primary-foreground rounded-pill border px-3 py-1 text-sm font-semibold"
            [attr.aria-pressed]="selected() === type"
            [attr.data-issue-type]="type"
            (click)="select(type)"
          >
            <span class="type-code-sm">{{ counts()[type] }}</span> {{ i18n.issueType(type) }}
          </button>
        }
      </div>
    }

    @if (visible().length === 0) {
      <p class="border-line-strong rounded-md border border-dashed p-4 text-sm">{{ i18n.t('dq.empty') }}</p>
    } @else {
      <div hlmTableContainer [attr.aria-busy]="loading()">
        <table hlmTable>
          <caption class="sr-only">
            {{ i18n.t('dq.caption') }}
          </caption>
          <thead hlmTHead>
            <tr hlmTr>
              <th hlmTh scope="col">{{ i18n.t('dq.priority') }}</th>
              <th hlmTh scope="col">{{ i18n.t('dq.country') }}</th>
              <th hlmTh scope="col">{{ i18n.t('dq.field') }}</th>
              <th hlmTh scope="col">{{ i18n.t('dq.problem') }}</th>
              <th hlmTh scope="col">{{ i18n.t('confidence.label') }}</th>
              <th hlmTh scope="col">{{ i18n.t('dq.validation') }}</th>
              <th hlmTh scope="col">{{ i18n.t('dq.check') }}</th>
            </tr>
          </thead>
          <tbody hlmTBody>
            @for (issue of visible(); track issue.issueId) {
              <tr hlmTr>
                <td hlmTd>
                  @switch (issue.priority) {
                    @case ('high') {
                      <span hlmBadge variant="rejected" size="sm"><ng-icon name="lucideTriangleAlert" aria-hidden="true" />{{ i18n.t('dq.high') }}</span>
                    }
                    @case ('medium') {
                      <span hlmBadge variant="review" size="sm"><ng-icon name="lucideCircleAlert" aria-hidden="true" />{{ i18n.t('dq.medium') }}</span>
                    }
                    @case ('low') {
                      <span hlmBadge variant="secondary" size="sm"><ng-icon name="lucideMinus" aria-hidden="true" />{{ i18n.t('dq.low') }}</span>
                    }
                    @default {
                      <span class="text-ink-muted">—</span>
                    }
                  }
                </td>
                <td hlmTd class="type-label">{{ issue.countryCode ?? '—' }}</td>
                <td hlmTd class="type-code">{{ issue.field }}</td>
                <td hlmTd class="whitespace-normal">
                  <span class="font-semibold">{{ i18n.issueType(issue.issueType) }}</span>
                  @if (issue.detail) {
                    <span class="text-ink-muted block text-xs">{{ issue.detail }}</span>
                  }
                </td>
                <td hlmTd>
                  @if (issue.confidence !== null && issue.confidence !== undefined) {
                    <app-confidence-meter [value]="issue.confidence" [compact]="true" />
                  } @else {
                    <span class="text-ink-muted">–</span>
                  }
                </td>
                <td hlmTd>
                  @if (issue.validationStatus) {
                    <app-status-badge [state]="issue.validationStatus" />
                  } @else {
                    <span class="text-ink-muted">—</span>
                  }
                </td>
                <td hlmTd>
                  @if (view(issue); as v) {
                    <app-evidence-link [view]="v">{{ i18n.t('dq.verify') }}</app-evidence-link>
                  } @else {
                    <span class="text-ink-muted text-xs">{{ i18n.t('dq.noEvidence') }}</span>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
  `,
})
export class DataQuality implements OnInit {
  protected readonly i18n = inject(I18n);
  private readonly issuesService = inject(IssuesService);
  private readonly destroyRef = inject(DestroyRef);

  readonly answer = input.required<Answer>();

  protected readonly selected = signal<IssueType | null>(null);
  protected readonly loading = signal(false);
  /** Compteurs fournis par GET /issues ; à défaut, simple décompte des problèmes reçus avec la réponse. */
  private readonly remoteCounts = signal<Record<string, number> | null>(null);
  /** Résultat de GET /issues?issueType=… pour le filtre sélectionné. */
  private readonly remoteFiltered = signal<DataIssue[] | null>(null);

  private readonly received = computed(() => this.answer().issues ?? []);

  protected readonly counts = computed<Record<string, number>>(() => {
    const remote = this.remoteCounts();
    if (remote) return remote;
    const counted: Record<string, number> = {};
    for (const issue of this.received()) {
      counted[issue.issueType] = (counted[issue.issueType] ?? 0) + 1;
    }
    return counted;
  });

  protected readonly types = computed(() =>
    (Object.keys(this.counts()) as IssueType[]).filter((type) => (this.counts()[type] ?? 0) > 0),
  );
  protected readonly total = computed(() => this.types().reduce((sum, type) => sum + (this.counts()[type] ?? 0), 0));

  /** Problèmes affichés, rangés par la priorité envoyée par le back (le front ne calcule aucune priorité). */
  protected readonly visible = computed(() => {
    const type = this.selected();
    const source = type ? (this.remoteFiltered() ?? this.received()) : this.received();
    return source
      .filter((issue) => !type || issue.issueType === type)
      .sort((a, b) => (PRIORITY_RANK[a.priority ?? ''] ?? 3) - (PRIORITY_RANK[b.priority ?? ''] ?? 3));
  });

  ngOnInit(): void {
    this.issuesService
      .list({ productId: this.answer().parameters?.productIds?.[0] })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => this.remoteCounts.set(response.countsByType ?? null),
        error: () => this.remoteCounts.set(null),
      });
  }

  protected select(type: IssueType | null): void {
    this.selected.set(type);
    this.remoteFiltered.set(null);
    if (!type) return;
    this.loading.set(true);
    this.issuesService
      .list({ productId: this.answer().parameters?.productIds?.[0], issueType: type })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.remoteFiltered.set(response.items);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  protected view(issue: DataIssue): EvidenceView | null {
    const evidence = issue.evidence?.[0];
    if (!evidence) return null;
    return {
      title: this.i18n.t('dq.evidenceTitle', { field: issue.field, country: issue.countryCode ?? '—' }),
      evidence,
      valueNormalized: issue.detail,
      confidence: issue.confidence,
    };
  }
}
