import { Directive, input } from '@angular/core';
import { classes } from '@spartan-ng/helm/utils';
import { type VariantProps, cva } from 'class-variance-authority';

/**
 * Badges Atlas. Les variantes de statut portent toujours une icône ET un mot (jamais la couleur seule) :
 * c'est à l'appelant de fournir l'icône et le libellé (voir `atlasStatus` ci-dessous).
 */
const badgeVariants = cva(
  'gap-1 rounded-sm border border-transparent px-2 py-0.5 text-[13px] leading-[18px] font-semibold transition-colors has-data-[icon=inline-end]:pe-1.5 has-data-[icon=inline-start]:ps-1.5 [&>ng-icon]:text-[length:--spacing(3.5)] group/badge aria-invalid:border-destructive inline-flex w-fit shrink-0 items-center justify-center overflow-hidden whitespace-nowrap [&>ng-icon]:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground',
        secondary: 'bg-surface-muted text-ink-strong',
        outline: 'border-line-strong bg-surface text-ink-strong',
        ghost: 'text-ink-strong hover:bg-surface-muted',
        link: 'text-link underline underline-offset-2',
        // Statuts réglementaires Atlas (voir README du design system › StatusBadge).
        validated: 'bg-status-validated-soft text-status-validated',
        review: 'border-status-review-line bg-status-review-soft text-status-review',
        auto: 'bg-status-auto-soft text-status-auto',
        // « Rejeté » est le seul aplat foncé : il se distingue de « Validé » par la clarté.
        rejected: 'bg-status-rejected text-on-status-rejected',
        obsolete: 'bg-status-obsolete-soft text-status-obsolete',
        unavailable: 'border-dashed border-line-strong bg-surface text-ink-muted',
      },
      size: {
        default: '',
        sm: 'px-1.5 py-px text-xs leading-4',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
);

export type BadgeVariants = VariantProps<typeof badgeVariants>;

export type AtlasStatusVariant =
  | 'validated'
  | 'review'
  | 'auto'
  | 'rejected'
  | 'obsolete'
  | 'unavailable';

/**
 * Valeurs d'énumération de `schema/openapi.yaml` : `validation_status` (6 états)
 * et `status_normalized` d'une homologation (5 états).
 */
export type AtlasStatus =
  | 'automatically_extracted'
  | 'to_verify'
  | 'validated'
  | 'rejected'
  | 'obsolete'
  | 'source_unavailable'
  | 'active'
  | 'expired'
  | 'withdrawn'
  | 'pending'
  | 'unknown';

/** Variante + libellé français fixe pour chaque valeur d'API (mots de statut imposés par le design system). */
export const atlasStatus: Record<AtlasStatus, { variant: AtlasStatusVariant; label: string }> = {
  validated: { variant: 'validated', label: 'Validé' },
  active: { variant: 'validated', label: 'Autorisé' },
  to_verify: { variant: 'review', label: 'À vérifier' },
  pending: { variant: 'review', label: 'En instruction' },
  automatically_extracted: { variant: 'auto', label: 'Extraction auto' },
  rejected: { variant: 'rejected', label: 'Rejeté' },
  withdrawn: { variant: 'rejected', label: 'Retiré' },
  obsolete: { variant: 'obsolete', label: 'Obsolète' },
  expired: { variant: 'obsolete', label: 'Expiré' },
  source_unavailable: { variant: 'unavailable', label: 'Source indisponible' },
  unknown: { variant: 'unavailable', label: 'Inconnu' },
};

@Directive({
  selector: '[hlmBadge],hlm-badge',
  host: {
    'data-slot': 'badge',
    '[attr.data-variant]': 'variant()',
  },
})
export class HlmBadge {
  public readonly variant = input<BadgeVariants['variant']>('default');
  public readonly size = input<BadgeVariants['size']>('default');

  constructor() {
    classes(() => badgeVariants({ variant: this.variant(), size: this.size() }));
  }
}
