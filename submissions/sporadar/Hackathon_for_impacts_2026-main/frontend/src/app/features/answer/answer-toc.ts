import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { I18n } from '../../core/i18n/i18n';

interface TocItem {
  id: string;
  label: string;
  /** 1 = section, 2 = sous-section (indentée). */
  level: 1 | 2;
}

/** Marge au-dessus d'une section atteinte par le sommaire, et seuil de détection de la section courante. */
const SCROLL_OFFSET_PX = 24;

/**
 * Sommaire latéral (desktop) : parcourt le DOM de la réponse, en récupère les titres et permet d'y défiler.
 * Sont retenus, dans l'ordre du document : les `h2`, les `h3` (sous-sections) et tout élément portant `data-toc`
 * (`data-toc="Libellé"`, ou le texte de l'élément si l'attribut est vide ; `data-toc-level="1"` force le niveau).
 * Il se met à jour tout seul quand la réponse change, qu'un gabarit finit de charger ou que la langue bascule.
 */
@Component({
  selector: 'app-answer-toc',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (items().length > 1) {
      <nav [attr.aria-label]="i18n.t('toc.label')" data-toc-nav>
        <p class="type-caption text-ink-muted mb-2 px-3">{{ i18n.t('toc.title') }}</p>
        <ul class="border-line flex flex-col border-l">
          @for (item of items(); track item.id) {
            <li>
              <a
                class="hover:text-ink-strong focus-visible:ring-ring -ml-px block rounded-r-sm border-l-2 py-1 pr-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
                [class]="
                  (item.level === 2 ? 'pl-6 ' : 'pl-3 ') +
                  (item.id === activeId()
                    ? 'border-primary text-ink-strong font-semibold'
                    : 'text-ink-muted border-transparent')
                "
                [href]="'#' + item.id"
                [attr.aria-current]="item.id === activeId() ? 'location' : null"
                (click)="go($event, item)"
              >
                {{ item.label }}
              </a>
            </li>
          }
        </ul>
      </nav>
    }
  `,
})
export class AnswerToc {
  protected readonly i18n = inject(I18n);
  private readonly destroyRef = inject(DestroyRef);

  /** Id de l'élément qui contient la réponse à parcourir. */
  readonly rootId = input.required<string>();

  protected readonly items = signal<TocItem[]>([]);
  protected readonly activeId = signal<string | null>(null);

  private anchors = new Map<string, HTMLElement>();
  private frame = 0;

  constructor() {
    afterNextRender(() => {
      const root = document.getElementById(this.rootId());
      if (!root) return;

      const observer = new MutationObserver(() => this.schedule(root));
      observer.observe(root, { childList: true, subtree: true, characterData: true });
      const onScroll = () => this.updateActive();
      window.addEventListener('scroll', onScroll, { passive: true });

      this.destroyRef.onDestroy(() => {
        observer.disconnect();
        window.removeEventListener('scroll', onScroll);
        cancelAnimationFrame(this.frame);
      });
      this.scan(root);
    });
  }

  protected go(event: Event, item: TocItem): void {
    const anchor = this.anchors.get(item.id);
    if (!anchor) return;
    event.preventDefault();
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    anchor.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    this.activeId.set(item.id);
  }

  /** Regroupe les rafales de mutations du DOM en un seul balayage par image. */
  private schedule(root: HTMLElement): void {
    cancelAnimationFrame(this.frame);
    this.frame = requestAnimationFrame(() => this.scan(root));
  }

  private scan(root: HTMLElement): void {
    const anchors = new Map<string, HTMLElement>();
    const items: TocItem[] = [];

    root.querySelectorAll<HTMLElement>('h2, h3, [data-toc]').forEach((el, index) => {
      const label = (el.dataset['toc'] || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!label) return;

      // Un titre masqué visuellement (sr-only) mène à sa section entière, pour que le défilement tombe au bon endroit.
      const section = el.id ? el.closest<HTMLElement>('section[aria-labelledby]') : null;
      const anchor = section && section.getAttribute('aria-labelledby') === el.id ? section : el;
      if (!anchor.id) anchor.id = `toc-${index}`;
      anchor.style.scrollMarginTop = `${SCROLL_OFFSET_PX}px`;

      const level = el.dataset['tocLevel'] === '1' || el.tagName !== 'H3' ? 1 : 2;
      anchors.set(anchor.id, anchor);
      items.push({ id: anchor.id, label, level });
    });

    this.anchors = anchors;
    const previous = this.items();
    const unchanged =
      previous.length === items.length &&
      previous.every(
        (p, i) => p.id === items[i].id && p.label === items[i].label && p.level === items[i].level,
      );
    if (!unchanged) this.items.set(items);
    this.updateActive();
  }

  /** Section courante : la dernière dont le haut a dépassé le seuil. */
  private updateActive(): void {
    let current: string | null = null;
    for (const item of this.items()) {
      const anchor = this.anchors.get(item.id);
      if (anchor && anchor.getBoundingClientRect().top <= SCROLL_OFFSET_PX + 8) current = item.id;
    }
    const atBottom =
      window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
    if (atBottom && this.items().length > 0) current = this.items()[this.items().length - 1].id;
    this.activeId.set(current ?? this.items()[0]?.id ?? null);
  }
}
