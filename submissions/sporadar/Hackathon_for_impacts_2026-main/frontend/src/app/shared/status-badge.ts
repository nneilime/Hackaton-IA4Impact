import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmBadgeImports, type BadgeVariants } from '@spartan-ng/helm/badge';
import type { CoverageOutcome, RegistrationStatus, ReviewStatus, ValidationStatus } from '../core/api/models';
import { I18n } from '../core/i18n/i18n';

/** Tous les états de la légende (cahier §2) : validation, homologation, couverture, revue, hypothèse. */
export type BadgeState =
  | ValidationStatus
  | RegistrationStatus
  | ReviewStatus
  | Exclude<CoverageOutcome, 'found'>
  | 'hypothesis';

interface BadgeConfig {
  variant: BadgeVariants['variant'];
  icon: string;
  /** Classes en plus de la variante (hachures, pointillés). */
  extra?: string;
}

// Gris hachuré : réservé à « pas trouvé ». Jamais de rouge pour ce cas (le rouge vient d'un statut de la source).
const HATCHED = 'bg-[repeating-linear-gradient(135deg,var(--synthetic-hatch)_0_3px,transparent_3px_6px)]';

const CONFIG: Record<BadgeState, BadgeConfig> = {
  validated: { variant: 'validated', icon: 'lucideCheck' },
  confirmed: { variant: 'validated', icon: 'lucideCheck' },
  active: { variant: 'validated', icon: 'lucideCheck' },
  to_verify: { variant: 'review', icon: 'lucideTriangleAlert' },
  pending: { variant: 'review', icon: 'lucideTriangleAlert' },
  automatically_extracted: { variant: 'auto', icon: 'lucideSparkles' },
  rejected: { variant: 'rejected', icon: 'lucideX' },
  // Rouge : uniquement un statut retiré ou expiré donné par la source.
  withdrawn: { variant: 'rejected', icon: 'lucideBan' },
  expired: { variant: 'rejected', icon: 'lucideClock' },
  obsolete: { variant: 'obsolete', icon: 'lucideClock' },
  source_unavailable: { variant: 'unavailable', icon: 'lucideCloudOff' },
  unknown: { variant: 'unavailable', icon: 'lucideMinus' },
  not_found: { variant: 'unavailable', icon: 'lucideCircleHelp', extra: HATCHED },
  not_covered: { variant: 'outline', icon: 'lucideMinus', extra: 'border-dashed text-ink-muted' },
  hypothesis: { variant: 'outline', icon: 'lucideCircleDashed', extra: 'border-dashed' },
};

/** Le badge d'état unique de l'application : une icône ET un mot, jamais la couleur seule. */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmBadgeImports],
  template: `
    <span hlmBadge [variant]="config().variant" [size]="size()" [class]="config().extra ?? ''" [attr.data-state]="state()">
      <ng-icon [name]="config().icon" aria-hidden="true" />{{ label() }}
    </span>
  `,
})
export class StatusBadge {
  private readonly i18n = inject(I18n);

  readonly state = input.required<BadgeState>();
  readonly size = input<BadgeVariants['size']>('sm');
  /** Remplace le libellé par défaut (ex. « Validé » → « Validé · alias »). */
  readonly text = input<string | null>(null);

  protected readonly config = computed(() => CONFIG[this.state()] ?? CONFIG.unknown);
  protected readonly label = computed(() => this.text() ?? this.i18n.status(this.state()));
}
