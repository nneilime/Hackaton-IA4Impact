import {
  BanknoteIcon, ChevronLeftIcon, CircleHelpIcon, FuelIcon, HeartPulseIcon, HouseIcon, PiggyBankIcon,
  ShoppingBagIcon, ShoppingCartIcon, TrainFrontIcon, TvIcon, UtensilsIcon, ArrowDownLeftIcon, ArrowUpRightIcon,
} from "lucide-react"
import { formatSignedEUR } from "@/lib/format"
import { back as goBack, navigate } from "@/lib/router"
import type { Transaction } from "@/lib/types"
import { cn } from "@/lib/utils"

const CAT: Record<string, { icon: React.ComponentType<{ className?: string }>; bg: string; fg: string }> = {
  Alimentation: { icon: ShoppingCartIcon, bg: "bg-[#f0f9f4]", fg: "text-[#008234]" },
  Restaurants: { icon: UtensilsIcon, bg: "bg-[#fff5e6]", fg: "text-[#af4000]" },
  Transports: { icon: TrainFrontIcon, bg: "bg-[#eaf7ff]", fg: "text-[#003bb2]" },
  Abonnements: { icon: TvIcon, bg: "bg-[#edeaf8]", fg: "text-[#492578]" },
  Logement: { icon: HouseIcon, bg: "bg-[#efefef]", fg: "text-[#454545]" },
  Santé: { icon: HeartPulseIcon, bg: "bg-[#fff3f4]", fg: "text-[#960010]" },
  Shopping: { icon: ShoppingBagIcon, bg: "bg-[#f3efed]", fg: "text-[#8f0e43]" },
  Revenus: { icon: BanknoteIcon, bg: "bg-[#f0f9f4]", fg: "text-[#008234]" },
  "Virements reçus": { icon: ArrowDownLeftIcon, bg: "bg-[#f0f9f4]", fg: "text-[#008234]" },
  "Virements émis": { icon: ArrowUpRightIcon, bg: "bg-[#efefef]", fg: "text-[#454545]" },
  Épargne: { icon: PiggyBankIcon, bg: "bg-[#eaf7ff]", fg: "text-[#003bb2]" },
  "Non catégorisé": { icon: CircleHelpIcon, bg: "bg-[#fff5e6]", fg: "text-[#af4000]" },
}

export function CategoryIcon({ category, merchant, className }: { category: string; merchant?: string; className?: string }) {
  const c = CAT[category] ?? CAT["Non catégorisé"]
  const Icon = merchant === "Station-service" ? FuelIcon : c.icon
  return (
    <span aria-hidden className={cn("flex size-10 shrink-0 items-center justify-center rounded-full", c.bg, c.fg, className)}>
      <Icon className="size-[18px]" />
    </span>
  )
}

export function Amount({ cents, className }: { cents: number; className?: string }) {
  return <span className={cn("tabular whitespace-nowrap font-bold", cents > 0 ? "text-ok" : "text-navy", className)}>{formatSignedEUR(cents)}</span>
}

export function TxRow({ tx, onClick, highlighted }: { tx: Transaction; onClick?: () => void; highlighted?: boolean }) {
  const body = (
    <>
      <CategoryIcon category={tx.category} merchant={tx.merchant} />
      <span className="min-w-0 flex-1 text-left">
        <span className="block truncate text-[15px] font-bold text-navy">{tx.merchant}</span>
        <span className="flex items-center gap-1.5 text-xs text-muted-ink">
          <span className="truncate">{tx.category}</span>
          {tx.status === "PENDING" && <span className="rounded-full bg-warn-soft px-1.5 py-0.5 text-[10px] font-bold text-warn">En attente</span>}
        </span>
      </span>
      <Amount cents={tx.amountCents} className="text-[15px]" />
    </>
  )
  return onClick ? (
    <button
      type="button"
      onClick={onClick}
      data-highlighted={highlighted ? "true" : undefined}
      className="flex w-full items-center gap-3 rounded-2xl px-2 py-2.5 transition-colors hover:bg-surface"
      aria-label={`${tx.merchant}, ${formatSignedEUR(tx.amountCents)}, ${tx.category}${tx.status === "PENDING" ? ", en attente" : ""}`}
    >
      {body}
    </button>
  ) : (
    <div className="flex items-center gap-3 px-2 py-2.5">{body}</div>
  )
}

export function ScreenHeader({ title, back, right, subtitle }: { title: string; back?: string | true; right?: React.ReactNode; subtitle?: string }) {
  return (
    <header className="sticky top-0 z-20 flex items-center gap-2 bg-surface/90 px-4 pb-3 pt-3 backdrop-blur">
      {back && (
        <button
          type="button"
          onClick={() => (back === true ? goBack() : navigate(back))}
          aria-label="Retour"
          className="-ml-1 flex size-10 items-center justify-center rounded-full text-navy hover:bg-white"
        >
          <ChevronLeftIcon className="size-6" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[22px] font-extrabold tracking-tight text-navy">{title}</h1>
        {subtitle && <p className="text-xs font-medium text-muted-ink">{subtitle}</p>}
      </div>
      {right}
    </header>
  )
}

export function DemoBadge({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-ink", className)}>
      <span className="size-1.5 rounded-full bg-brand" aria-hidden />
      Prototype de démonstration
    </span>
  )
}

export function Section({ title, action, children, className, ...rest }: { title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("px-4", className)} {...rest}>
      {(title || action) && (
        <div className="mb-2 flex items-center justify-between">
          {title && <h2 className="text-[15px] font-extrabold tracking-tight text-navy">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Panel({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("hc-outline rounded-3xl bg-white p-4 shadow-[0_1px_2px_rgba(8,13,52,0.04),0_1px_3px_rgba(8,13,52,0.06)]", className)} {...rest}>
      {children}
    </div>
  )
}

export function SkeletonRows({ n = 4 }: { n?: number }) {
  return (
    <div className="flex flex-col gap-3 p-2" aria-busy="true" aria-label="Chargement">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="skeleton size-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3 w-1/2" />
            <div className="skeleton h-2.5 w-1/3" />
          </div>
          <div className="skeleton h-3 w-16" />
        </div>
      ))}
    </div>
  )
}

/** The fictional customer couldn't be loaded (server down): the assistant still works. */
export function LoadError({ retry }: { retry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-8 py-16 text-center" role="alert">
      <p className="text-sm text-muted-ink">Impossible de charger vos comptes pour le moment.</p>
      <button type="button" onClick={retry} className="h-11 rounded-2xl bg-navy px-5 text-sm font-bold text-white">
        Réessayer
      </button>
    </div>
  )
}
