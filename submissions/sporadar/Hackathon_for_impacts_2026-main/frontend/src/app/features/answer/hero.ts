import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, inject, signal, viewChildren } from '@angular/core';
import { I18n } from '../../core/i18n/i18n';

/** Clips Mixkit (licence gratuite), servis en local depuis public/hero/ : de la graine au champ. */
const CLIPS = [
  'hero/01-sprouts.mp4',
  'hero/02-seedlings.mp4',
  'hero/03-leaves.mp4',
  'hero/04-rain.mp4',
  'hero/05-field.mp4',
];

/** Durée du fondu enchaîné, en secondes (identique à la transition CSS duration-[1500ms]). */
const FADE_S = 1.5;

/**
 * Écran d'accueil (affiché tant qu'aucune question n'est posée) : vidéos décoratives enchaînées en fondu,
 * voile sombre pour la lisibilité, titre et sous-titre centrés.
 *
 * Deux lecteurs <video> superposés : pendant que l'un joue, l'autre précharge le clip suivant.
 * Un peu avant la fin du clip, l'autre lecteur démarre et passe au premier plan (fondu d'opacité),
 * puis l'ancien charge le clip d'après. Pas de `loop` : c'est ce qui évite le saut au retour au début.
 * Avec « réduire les animations », seule l'image fixe (poster) est affichée.
 */
@Component({
  selector: 'app-hero',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="relative isolate overflow-hidden bg-[#0f1f12]" data-section="hero">
      <img src="hero/poster.jpg" alt="" aria-hidden="true" class="absolute inset-0 -z-20 h-full w-full object-cover" />
      @for (src of sources(); track $index) {
        <video
          #player
          class="absolute inset-0 -z-20 h-full w-full object-cover transition-opacity duration-[1500ms] ease-in-out motion-reduce:hidden"
          [class.opacity-0]="front() !== $index"
          [src]="src"
          [autoplay]="$index === 0 && firstClip()"
          [muted]="true"
          playsinline
          preload="auto"
          aria-hidden="true"
          (timeupdate)="onTimeUpdate($index)"
        ></video>
      }
      <div class="absolute inset-0 -z-10 bg-gradient-to-b from-black/45 via-black/35 to-black/70" aria-hidden="true"></div>

      <div class="mx-auto flex max-w-4xl flex-col items-center gap-4 px-6 pt-20 pb-24 text-center sm:pt-24 sm:pb-28">
        <h1 class="type-display-l sm:type-display-xl text-balance text-white! drop-shadow-md">{{ i18n.t('page.title') }}</h1>
        <p class="max-w-2xl text-lg text-balance text-white/85">{{ i18n.t('page.subtitle') }}</p>
      </div>
    </section>
  `,
})
export class Hero {
  protected readonly i18n = inject(I18n);

  private readonly players = viewChildren<ElementRef<HTMLVideoElement>>('player');

  /** Clip chargé dans chacun des deux lecteurs. */
  protected readonly sources = signal<[string, string]>([CLIPS[0], CLIPS[1]]);
  /** Lecteur visible (0 ou 1). */
  protected readonly front = signal(0);
  /** Seul le tout premier clip démarre seul ; ensuite chaque clip attend son tour (préchargé, en pause). */
  protected readonly firstClip = signal(true);

  /** Indice dans CLIPS du clip en cours de lecture. */
  private current = 0;
  private fading = false;
  private fadeTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    // Le hero disparaît dès qu'une question est posée : on n'oublie pas un fondu en cours.
    inject(DestroyRef).onDestroy(() => clearTimeout(this.fadeTimer));
  }

  /** Appelé pendant la lecture : déclenche le fondu vers l'autre lecteur juste avant la fin du clip. */
  protected onTimeUpdate(player: number): void {
    if (this.fading || player !== this.front()) return;
    const active = this.players()[player]?.nativeElement;
    const next = this.players()[1 - player]?.nativeElement;
    if (!active || !next || !active.duration || active.duration - active.currentTime > FADE_S) return;

    this.fading = true;
    this.firstClip.set(false);
    next.currentTime = 0;
    next.play().catch(() => undefined);
    this.front.set(1 - player);
    this.current = (this.current + 1) % CLIPS.length;

    // Fondu terminé : l'ancien lecteur s'arrête et précharge le clip qui suivra.
    this.fadeTimer = setTimeout(() => {
      active.pause();
      const following = CLIPS[(this.current + 1) % CLIPS.length];
      this.sources.update((sources) => {
        const updated: [string, string] = [...sources];
        updated[player] = following;
        return updated;
      });
      this.fading = false;
    }, FADE_S * 1000);
  }
}
