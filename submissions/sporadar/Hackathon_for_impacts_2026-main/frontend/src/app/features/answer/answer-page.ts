import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { NgIcon } from '@ng-icons/core';
import { HlmAlertImports } from '@spartan-ng/helm/alert';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmSkeletonImports } from '@spartan-ng/helm/skeleton';
import type { SuggestedQuestion } from '../../core/api/models';
import { I18n, type MessageKey } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';
import { EvidencePanel } from '../../shared/evidence-panel';
import { AppFooter } from './app-footer';
import { AppHeader } from './app-header';
import { AnswerToc } from './answer-toc';
import { AskBar } from './ask-bar';
import { Hero } from './hero';
import { ThinkingStatus } from './thinking-status';
import { Conclusion } from './conclusion';
import { SearchScope } from './search-scope';
import { Understood } from './understood';
import { DataQuality } from './templates/data-quality';
import { ExpiryWatch } from './templates/expiry-watch';
import { IngredientSearch } from './templates/ingredient-search';
import { MessageTemplate } from './templates/message-template';
import { RegistrationLookup } from './templates/registration-lookup';
import { SisterProduct } from './templates/sister-product';
import { SourceLookup } from './templates/source-lookup';
import { UseComparison } from './templates/use-comparison';

type TemplateKind =
  | 'registration_lookup'
  | 'use_comparison'
  | 'ingredient_search'
  | 'expiry_watch'
  | 'data_quality'
  | 'sister_product'
  | 'source_lookup';

/**
 * La page unique : un cadre commun (en-tête, question, « ce que l'IA a compris », conclusion, périmètre,
 * avertissements, suite, disclaimer) et, au centre, UN gabarit choisi par `intent` — rien d'autre.
 * Un intent inconnu tombe sur le message « hors périmètre ».
 */
@Component({
  selector: 'app-answer-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgIcon,
    HlmAlertImports,
    HlmButtonImports,
    HlmSkeletonImports,
    AppHeader,
    AppFooter,
    Hero,
    ThinkingStatus,
    AskBar,
    AnswerToc,
    Understood,
    Conclusion,
    SearchScope,
    EvidencePanel,
    RegistrationLookup,
    UseComparison,
    DataQuality,
    SisterProduct,
    SourceLookup,
    IngredientSearch,
    ExpiryWatch,
    MessageTemplate,
  ],
  template: `
    <app-header />

    <!-- Accueil : le hero vidéo n'apparaît que tant qu'aucune question n'est posée -->
    @if (store.status() === 'idle') {
      <app-hero />
    }

    <main
      class="mx-auto flex max-w-6xl flex-col gap-6 px-6 pb-12 xl:grid xl:max-w-[80rem] xl:grid-cols-[13rem_minmax(0,1fr)] xl:gap-x-8"
      [class.pt-8]="store.status() !== 'idle'"
    >
      <div class="relative z-10 w-full xl:col-span-2" [class.-mt-8]="store.status() === 'idle'">
        <app-ask-bar />
      </div>

      @switch (store.status()) {
        @case ('loading') {
          <section
            class="flex flex-col gap-3 xl:col-start-2"
            role="status"
            aria-busy="true"
            data-state="loading"
          >
            <app-thinking-status [sources]="sourceNames()" />
            <div hlmSkeleton class="h-7 w-3/4"></div>
            <div hlmSkeleton class="h-5 w-1/2"></div>
            <div hlmSkeleton class="h-40 w-full"></div>
          </section>
        }
        @case ('error') {
          <div
            hlmAlert
            variant="destructive"
            class="xl:col-span-2"
            data-state="error"
            [attr.data-error]="store.errorKind()"
          >
            <ng-icon name="lucideTriangleAlert" aria-hidden="true" />
            <h2 hlmAlertTitle>{{ i18n.t(errorTitleKey()) }}</h2>
            <p hlmAlertDescription>
              {{ i18n.t(errorBodyKey()) }}
              <button
                hlmBtn
                variant="secondary"
                size="sm"
                type="button"
                class="mt-2"
                (click)="store.retry()"
              >
                <ng-icon name="lucideRefreshCw" aria-hidden="true" />{{ i18n.t('state.retry') }}
              </button>
            </p>
          </div>
        }
        @case ('success') {
          @if (store.answer(); as answer) {
            <!-- Sommaire latéral (desktop) : généré à partir des titres de la réponse -->
            <aside class="hidden xl:block" data-section="toc">
              <div class="sticky top-6">
                <app-answer-toc rootId="answer-content" />
              </div>
            </aside>

            <div id="answer-content" class="flex min-w-0 flex-col gap-6">
              <app-understood [answer]="answer" />
              <app-conclusion [answer]="answer" />
              <app-search-scope [coverage]="answer.coverage" />

              <!-- Bloc 6 : le gabarit propre à l'intent -->
              <section
                class="flex flex-col gap-3"
                [attr.data-template]="template() ?? 'message'"
                [attr.data-toc]="templateLabel()"
              >
                @switch (template()) {
                  @case ('registration_lookup') {
                    <app-registration-lookup [answer]="answer" />
                  }
                  @case ('use_comparison') {
                    @if (answer.comparison; as comparison) {
                      <app-use-comparison [comparison]="comparison" />
                    }
                  }
                  @case ('data_quality') {
                    <app-data-quality [answer]="answer" />
                  }
                  @case ('sister_product') {
                    <app-sister-product [answer]="answer" />
                  }
                  @case ('source_lookup') {
                    <app-source-lookup [answer]="answer" />
                  }
                  @case ('ingredient_search') {
                    <app-ingredient-search [answer]="answer" />
                  }
                  @case ('expiry_watch') {
                    <app-expiry-watch [answer]="answer" />
                  }
                }
                @if (showMessage()) {
                  <app-message-template [answer]="answer" (clarify)="clarify($event)" />
                }
              </section>

              <!-- Bloc 7 : avertissements, jamais repliés -->
              @if (answer.warnings.length > 0) {
                <section
                  class="flex flex-col gap-2"
                  aria-labelledby="warnings-title"
                  data-section="warnings"
                >
                  <h2 id="warnings-title" class="type-caption text-ink-muted">
                    {{ i18n.t('warnings.heading') }}
                  </h2>
                  @for (warning of answer.warnings; track warning) {
                    <div hlmAlert variant="warning">
                      <ng-icon name="lucideTriangleAlert" aria-hidden="true" />
                      <p hlmAlertDescription>{{ warning }}</p>
                    </div>
                  }
                </section>
              }

              <!-- Bloc 8 : la suite -->
              @if (answer.suggestedQuestions?.length) {
                <section
                  class="flex flex-col gap-2"
                  aria-labelledby="follow-title"
                  data-section="follow-up"
                >
                  <h2 id="follow-title" class="type-caption text-ink-muted">
                    {{ i18n.t('follow.heading') }}
                  </h2>
                  <ul class="flex flex-wrap gap-2">
                    @for (suggestion of answer.suggestedQuestions; track suggestion.question) {
                      <li>
                        <button
                          hlmBtn
                          variant="outline"
                          size="sm"
                          type="button"
                          [attr.data-intent]="suggestion.intent"
                          (click)="follow(suggestion)"
                        >
                          {{ suggestion.label }}
                          <ng-icon name="lucideArrowRight" aria-hidden="true" />
                        </button>
                      </li>
                    }
                  </ul>
                </section>
              }
            </div>
          }
        }
      }
    </main>

    <!-- Pied : le disclaimer est toujours présent, avec la fraîcheur des sources -->
    <app-footer />

    <app-evidence-panel />
  `,
})
export class AnswerPage {
  protected readonly store = inject(AnswerStore);
  protected readonly i18n = inject(I18n);

  constructor() {
    inject(ActivatedRoute)
      .queryParamMap.pipe(takeUntilDestroyed())
      .subscribe((params) => this.store.syncFromUrl(params));
    this.store.loadSources();
  }

  /** Sources interrogées, affichées pendant le chargement. */
  protected readonly sourceNames = computed(() =>
    this.store
      .sources()
      .filter((source) => source.lastCollectedAt)
      .map((source) => source.sourceId)
      .join(' · '),
  );

  /** Le gabarit est choisi par `intent` seulement (et reste vide si l'IA demande une précision ou sort du périmètre). */
  protected readonly template = computed<TemplateKind | null>(() => {
    const answer = this.store.answer();
    if (
      !answer ||
      answer.answerStatus === 'needs_clarification' ||
      answer.answerStatus === 'out_of_scope'
    ) {
      return null;
    }
    switch (answer.intent) {
      case 'registration_lookup':
      case 'use_comparison':
      case 'ingredient_search':
      case 'expiry_watch':
      case 'data_quality':
      case 'sister_product':
      case 'source_lookup':
        return answer.intent;
      default:
        return null;
    }
  });

  /** Titre du gabarit dans le sommaire (vide : le gabarit n'est pas listé, son message a son propre titre). */
  protected readonly templateLabel = computed(() => {
    const kind = this.template();
    return kind ? this.i18n.t(`toc.result.${kind}`) : null;
  });

  /** Message clair : hors périmètre, aucune donnée, précision demandée, ou intent inconnu. */
  protected readonly showMessage = computed(() => {
    const answer = this.store.answer();
    return !!answer && (this.template() === null || answer.answerStatus === 'no_data');
  });

  protected readonly errorTitleKey = computed<MessageKey>(() => {
    const kind = this.store.errorKind();
    return kind === 'unauthorized'
      ? 'error.unauthorized'
      : kind === 'notFound'
        ? 'error.notFound'
        : 'error.network';
  });

  protected readonly errorBodyKey = computed<MessageKey>(() => {
    const kind = this.store.errorKind();
    return kind === 'unauthorized'
      ? 'error.unauthorized.body'
      : kind === 'notFound'
        ? 'error.notFound.body'
        : 'error.network.body';
  });

  protected follow(suggestion: SuggestedQuestion): void {
    this.store.submit(suggestion.question, { intent: suggestion.intent });
  }

  /** Une option de précision relance la question avec le choix de l'utilisateur. */
  protected clarify(option: string): void {
    this.store.submit(`${this.store.question()} — ${option}`, { intent: 'registration_lookup' });
  }
}
