import { Injectable, inject, signal } from '@angular/core';
import type { ParamMap } from '@angular/router';
import { Router } from '@angular/router';
import type { Subscription } from 'rxjs';
import { AskService } from '../api/ask.service';
import { errorKindOf, type ErrorKind } from '../api/http-error';
import type { Answer, SourceInfo } from '../api/models';
import { isMock } from '../api/runtime';
import { SourcesService } from '../api/sources.service';
import { I18n } from '../i18n/i18n';
import type { EvidenceView } from './evidence-view';

export type LoadStatus = 'idle' | 'loading' | 'success' | 'error';

/** Contexte facultatif d'une question : ce que l'interface sait déjà (produit, pays) ou veut forcer. */
export interface AskContext {
  productId?: string;
  countries?: readonly string[];
  /** Intention de la question cliquée : sert uniquement de nom d'exemple en mode mock. */
  intent?: string | null;
}

interface AskState extends AskContext {
  question: string;
  language: string;
  /** Code d'erreur à forcer chez Prism (`?mockCode=401`), mock uniquement. */
  mockCode?: number | null;
}

/**
 * État de la page : question en cours, réponse courante, chargement, erreur, preuve ouverte, sources.
 * L'URL est la source de vérité de la question (q, lang, product, countries) : `syncFromUrl` la lit,
 * `submit` l'écrit. Ainsi un lien copié, précédent et suivant rouvrent la même réponse.
 */
@Injectable({ providedIn: 'root' })
export class AnswerStore {
  private readonly askService = inject(AskService);
  private readonly sourcesService = inject(SourcesService);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18n);

  readonly question = signal('');
  readonly answer = signal<Answer | null>(null);
  readonly status = signal<LoadStatus>('idle');
  readonly errorKind = signal<ErrorKind | null>(null);
  /** Valeur dont la preuve est ouverte dans le panneau latéral (null = panneau fermé). */
  readonly evidence = signal<EvidenceView | null>(null);
  readonly sources = signal<SourceInfo[]>([]);
  /** Contexte de la dernière question envoyée (produit/pays), repris par les relances. */
  readonly context = signal<AskContext>({});

  private last: AskState | null = null;
  private lastKey = '';
  private subscription: Subscription | null = null;
  private sourcesLoaded = false;

  /** Appelé à chaque changement des paramètres d'URL. */
  syncFromUrl(params: ParamMap): void {
    const lang = params.get('lang');
    if (lang === 'fr' || lang === 'en') {
      this.i18n.lang.set(lang);
    }
    const question = params.get('q')?.trim() ?? '';
    if (question.length === 0) {
      this.reset();
      return;
    }
    const countries = params.get('countries')?.split(',').filter(Boolean);
    const mockCode = isMock ? Number(params.get('mockCode')) || null : null;
    const state: AskState = {
      question,
      language: this.i18n.lang(),
      productId: params.get('product') ?? undefined,
      countries: countries?.length ? countries : undefined,
      intent: isMock ? params.get('intent') : null,
      mockCode,
    };
    const key = JSON.stringify(state);
    if (key === this.lastKey && this.status() !== 'error') {
      return;
    }
    this.load(state, key);
  }

  /** Pose une question : écrit l'URL, qui déclenche l'appel (ou le relance si l'URL est déjà identique). */
  submit(question: string, context: AskContext = {}): void {
    const trimmed = question.trim();
    if (trimmed.length < 3) {
      return;
    }
    const queryParams = {
      q: trimmed,
      lang: this.i18n.lang(),
      product: context.productId || undefined,
      countries: context.countries?.length ? context.countries.join(',') : undefined,
      intent: isMock ? (context.intent ?? undefined) : undefined,
      mockCode: isMock ? (this.last?.mockCode ?? undefined) : undefined,
    };
    const target = this.router.serializeUrl(this.router.createUrlTree([], { queryParams }));
    if (target === this.router.url) {
      this.retry(trimmed, context);
      return;
    }
    void this.router.navigate([], { queryParams });
  }

  /** Relance la dernière question telle quelle (bouton « Réessayer », ou même question reposée). */
  retry(question?: string, context?: AskContext): void {
    const base = this.last;
    if (!base && !question) {
      return;
    }
    const state: AskState = {
      ...(base ?? { language: this.i18n.lang(), question: question as string }),
      ...(context ?? {}),
      question: question ?? (base as AskState).question,
      language: this.i18n.lang(),
    };
    this.load(state, JSON.stringify(state));
  }

  /** Change la langue de l'interface (et des réponses) en gardant la question dans l'URL. */
  setLanguage(lang: 'fr' | 'en'): void {
    this.i18n.lang.set(lang);
    void this.router.navigate([], { queryParams: { lang }, queryParamsHandling: 'merge' });
  }

  openEvidence(view: EvidenceView): void {
    this.evidence.set(view);
  }

  closeEvidence(): void {
    this.evidence.set(null);
  }

  /** Fraîcheur des sources pour l'en-tête. Une panne ici n'empêche jamais de poser une question. */
  loadSources(): void {
    if (this.sourcesLoaded) {
      return;
    }
    this.sourcesLoaded = true;
    this.sourcesService.list().subscribe({
      next: (response) => this.sources.set(response.items),
      error: () => this.sources.set([]),
    });
  }

  private reset(): void {
    this.subscription?.unsubscribe();
    this.last = null;
    this.lastKey = '';
    this.question.set('');
    this.answer.set(null);
    this.status.set('idle');
    this.errorKind.set(null);
    this.evidence.set(null);
    this.context.set({});
  }

  private load(state: AskState, key: string): void {
    this.subscription?.unsubscribe();
    this.last = state;
    this.lastKey = key;
    this.question.set(state.question);
    this.context.set({ productId: state.productId, countries: state.countries, intent: state.intent });
    this.status.set('loading');
    this.errorKind.set(null);
    this.evidence.set(null);

    this.subscription = this.askService
      .ask(
        { question: state.question, language: state.language, productId: state.productId, countries: state.countries ? [...state.countries] : undefined },
        state.intent,
        state.mockCode,
      )
      .subscribe({
        next: (answer) => {
          this.answer.set(answer);
          this.status.set('success');
        },
        error: (error: unknown) => {
          // Pas de réponse périmée à côté d'un message d'erreur : on repart d'un cadre propre.
          this.answer.set(null);
          this.errorKind.set(errorKindOf(error));
          this.status.set('error');
        },
      });
  }
}
