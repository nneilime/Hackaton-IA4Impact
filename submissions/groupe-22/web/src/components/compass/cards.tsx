import {
  BanIcon, CalculatorIcon, CalendarClockIcon, CheckIcon, ChevronRightIcon, CircleAlertIcon, CircleCheckIcon, CircleSlashIcon, ClockIcon, CreditCardIcon,
  DownloadIcon, KeyRoundIcon, LoaderCircleIcon, LockIcon, LogInIcon, MessageSquareWarningIcon, TriangleAlertIcon, UnlockIcon, UserRoundIcon, WalletIcon,
} from "lucide-react"
import { openLogin } from "@/lib/auth"
import { useChatOpen } from "@/lib/chat"
import { answerAction } from "@/lib/compass"
import { STATUS_LABEL } from "@/lib/demarches"
import { duration, euros, percent } from "@/lib/format"
import { navigate } from "@/lib/router"
import { useCompass, type UIMessage } from "@/lib/store"
import type { AssistantCard, Demarche, FoundTransaction, Loan, PendingAction } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useVoice } from "@/lib/voice"

const box = "hc-outline rounded-2xl bg-white p-3 ring-1 ring-line"

export const DEMARCHE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  card_block: BanIcon,
  card_lock: LockIcon,
  card_unlock: UnlockIcon,
  pin_reissue: KeyRoundIcon,
  password_reset: LockIcon,
  appointment: CalendarClockIcon,
  loan: CalculatorIcon,
  complaint: MessageSquareWarningIcon,
  transfer: UserRoundIcon,
}

/** A chip per tool call: running, done, waiting for the customer's yes, or not done. */
export function ToolChips({ m, dark = false }: { m: UIMessage; dark?: boolean }) {
  if (!m.tools.length) return null
  return (
    <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="Actions de Compass">
      {m.tools.map((t) => (
        <li
          key={t.id}
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-bold",
            t.status === "running" && (dark ? "bg-white/10 text-white/70" : "bg-surface text-muted-ink"),
            t.status === "ok" && "bg-ok-soft text-ok",
            t.status === "waiting" && "bg-info-soft text-navy",
            t.status === "error" && "bg-warn-soft text-warn",
            t.status === "cancelled" && (dark ? "bg-white/10 text-white/80" : "bg-surface text-navy"),
          )}
        >
          {t.status === "running" ? (
            <LoaderCircleIcon className="size-3 animate-spin" aria-hidden />
          ) : t.status === "ok" ? (
            <CheckIcon className="size-3" aria-hidden />
          ) : t.status === "waiting" ? (
            <ClockIcon className="size-3" aria-hidden />
          ) : t.status === "cancelled" ? (
            <CircleSlashIcon className="size-3" aria-hidden />
          ) : (
            <CircleAlertIcon className="size-3" aria-hidden />
          )}
          {t.label}
          {t.status === "error" && <span className="sr-only"> : pas abouti</span>}
        </li>
      ))}
    </ul>
  )
}

export function AssistantCardView({ card }: { card: AssistantCard }) {
  switch (card.kind) {
    case "loan":
      return <LoanCard loan={card.loan} />
    case "demarche":
      return <DemarcheCard demarche={card.demarche} />
    case "confirm":
      return <ConfirmCard action={card.action} />
    case "login":
      return <LoginCard />
    case "accounts":
      return <AccountsCard accounts={card.accounts} />
    case "transactions":
      return <TransactionsCard transactions={card.transactions} count={card.count} />
  }
}

/** An action Compass prepared: nothing happens until the customer's yes, said, typed,
 * or given here (which says it in the conversation). */
function ConfirmCard({ action }: { action: PendingAction }) {
  const state = useCompass((s) => s.actions[action.id] ?? "pending")
  const busy = useCompass((s) => s.busy)
  const chatOpen = useChatOpen()
  const callLive = useVoice((s) => s.status !== "idle" && s.status !== "error" && s.status !== "connecting")
  const live = action.via === "voice" ? callLive : chatOpen
  const Icon = DEMARCHE_ICONS[action.kind] ?? ClockIcon
  const outcome = {
    done: { icon: CircleCheckIcon, text: "Confirmé : c'est fait.", className: "bg-ok-soft text-ok" },
    cancelled: { icon: CircleSlashIcon, text: "Annulé : rien n'a été fait.", className: "bg-surface text-navy" },
    failed: { icon: CircleAlertIcon, text: "Pas fait : voir la réponse de Compass.", className: "bg-warn-soft text-warn" },
  }
  const end = state === "pending" ? null : outcome[state]
  return (
    <article className={cn(box, "flex flex-col gap-2.5", state === "pending" && "ring-2 ring-navy/20")} aria-label={`Action à confirmer : ${action.title}`}>
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted-ink">
        <Icon className="size-3.5" aria-hidden /> {state === "pending" ? "À confirmer" : "Action"}
      </p>
      <p className="text-sm font-extrabold text-navy">{action.title}</p>
      <ul className="flex flex-col gap-1 rounded-xl bg-surface p-2.5 text-xs leading-snug text-navy">
        {action.details.map((d) => (
          <li key={d}>{d}</li>
        ))}
      </ul>
      {end ? (
        <p role="status" className={cn("flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold", end.className)}>
          <end.icon className="size-4 shrink-0" aria-hidden /> {end.text}
        </p>
      ) : live ? (
        <div className="grid grid-cols-2 gap-2">
          <button type="button" disabled={busy && action.via === "text"} onClick={() => answerAction(action.via, false)} className="min-h-11 rounded-xl text-sm font-bold text-navy ring-1 ring-line hover:bg-surface disabled:opacity-50">
            Annuler
          </button>
          <button type="button" disabled={busy && action.via === "text"} onClick={() => answerAction(action.via, true)} className="min-h-11 rounded-xl bg-navy text-sm font-bold text-white hover:bg-navy-2 disabled:opacity-50">
            Confirmer
          </button>
        </div>
      ) : (
        <p className="text-xs text-muted-ink">Conversation terminée : rien n&apos;a été fait.</p>
      )}
    </article>
  )
}

/** The visitor asked for something only a logged-in customer can do. */
function LoginCard() {
  return (
    <article className={cn(box, "flex flex-col gap-2")} aria-label="Connexion requise">
      <p className="flex items-center gap-1.5 text-sm font-extrabold text-navy">
        <LockIcon className="size-4 text-brand" aria-hidden /> Connexion requise
      </p>
      <p className="text-xs leading-snug text-navy">Vos comptes, opérations et cartes ne sont accessibles qu&apos;une fois connecté·e. Ici, avec un profil fictif.</p>
      <button
        type="button"
        onClick={() => {
          useCompass.getState().setSheet("peek")
          openLogin()
        }}
        className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand text-sm font-bold text-white hover:bg-brand-strong"
      >
        <LogInIcon className="size-4" aria-hidden /> Connexion démo
      </button>
    </article>
  )
}

/** The balances get_accounts read: the same figures as the Comptes screen. */
function AccountsCard({ accounts }: { accounts: { label: string; balance_eur: number; iban_end: string }[] }) {
  return (
    <article className={cn(box, "flex flex-col gap-1.5")} aria-label="Vos soldes">
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted-ink">
        <WalletIcon className="size-3.5" aria-hidden /> Vos soldes
      </p>
      {accounts.map((a) => (
        <p key={a.iban_end} className="flex items-baseline justify-between gap-2 text-sm">
          <span className="font-bold text-navy">
            {a.label} <span className="tabular text-xs font-semibold text-muted-ink">•••• {a.iban_end}</span>
          </span>
          <span className="tabular font-extrabold text-navy">{euros(a.balance_eur)}</span>
        </p>
      ))}
      <button
        type="button"
        onClick={() => {
          navigate("/comptes")
          useCompass.getState().setSheet("peek")
        }}
        className="mt-1 flex items-center justify-center gap-1 rounded-xl py-1.5 text-xs font-bold text-brand hover:bg-brand-soft"
      >
        Voir mes comptes <ChevronRightIcon className="size-3.5" aria-hidden />
      </button>
    </article>
  )
}

/** The operations search_transactions found: tap one to open its detail. */
function TransactionsCard({ transactions, count }: { transactions: FoundTransaction[]; count: number }) {
  return (
    <article className={cn(box, "flex flex-col gap-1")} aria-label="Opérations trouvées">
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted-ink">
        <CreditCardIcon className="size-3.5" aria-hidden /> {count > 1 ? `${count} opérations trouvées` : "Opération trouvée"}
      </p>
      <ul className="flex flex-col">
        {transactions.slice(0, 5).map((t) => (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => {
                navigate(`/operations?tx=${encodeURIComponent(t.id)}`)
                useCompass.getState().setSheet("peek")
              }}
              className="flex w-full items-center gap-2 rounded-xl px-1.5 py-2 text-left hover:bg-surface"
              aria-label={`${t.merchant}, ${t.amount}, le ${t.date} : ouvrir le détail`}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-bold text-navy">{t.merchant}</span>
                <span className="block truncate text-[11px] text-muted-ink">
                  {t.date} · {t.label}
                </span>
              </span>
              <span className={cn("tabular whitespace-nowrap text-sm font-extrabold", t.amount_eur > 0 ? "text-ok" : "text-navy")}>{euros(t.amount_eur)}</span>
            </button>
          </li>
        ))}
      </ul>
    </article>
  )
}

function LoanCard({ loan }: { loan: Loan }) {
  const consumer = loan.purpose !== "prêt immobilier"
  // under_35_percent: false when the payment is over the bank's limit (MAX_DEBT_RATIO)
  const tooHigh = Object.entries(loan).some(([key, value]) => /^under_\d+_percent$/.test(key) && value === false)
  const purpose = loan.purpose.charAt(0).toUpperCase() + loan.purpose.slice(1)
  const rows: [string, string][] = [
    ["Montant", euros(loan.amount_eur)],
    ["Durée", duration(loan.months)],
    [consumer ? "TAEG fixe" : "Taux indicatif hors assurance", percent(loan.annual_rate_percent)],
    ["Coût des intérêts", euros(loan.total_interest_eur)],
  ]
  return (
    <article className={cn(box, "flex flex-col gap-2.5")} aria-label={`Simulation : ${purpose}`}>
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted-ink">
        <CalculatorIcon className="size-3.5" aria-hidden /> Simulation · {purpose}
      </p>
      <p className="text-navy">
        <span className="tabular text-2xl font-extrabold">{euros(loan.monthly_payment_eur)}</span> <span className="text-sm font-semibold text-muted-ink">par mois</span>
      </p>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 rounded-xl bg-surface p-2.5 text-xs">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-muted-ink">{label}</dt>
            <dd className="tabular font-bold text-navy">{value}</dd>
          </div>
        ))}
        <div className={tooHigh ? "text-warn" : undefined}>
          <dt className={tooHigh ? undefined : "text-muted-ink"}>Part de vos revenus</dt>
          <dd className={cn("tabular flex items-center gap-1 font-bold", !tooHigh && "text-navy")}>
            {tooHigh && <TriangleAlertIcon className="size-3.5" aria-hidden />}
            {percent(loan.debt_ratio_percent)}
          </dd>
        </div>
      </dl>
      {consumer && (
        <p className="text-[11px] font-semibold text-navy">
          Un crédit vous engage et doit être remboursé. Vérifiez vos capacités de remboursement avant de vous engager.
        </p>
      )}
      <p className="text-[11px] text-muted-ink">Simulation indicative et sans engagement, taux de démonstration.</p>
    </article>
  )
}

/** The recap PDF to download: kept 24 hours on the server, like the démarche here. */
export function RecapButton({ pdf, className }: { pdf: NonNullable<Demarche["pdf"]>; className?: string }) {
  return (
    <a href={pdf.url} download={pdf.name} className={cn("flex min-h-11 items-center justify-center gap-2 rounded-xl bg-navy px-3 py-2 text-sm font-bold text-white hover:bg-navy-2", className)}>
      <DownloadIcon className="size-4 shrink-0" aria-hidden />
      <span className="text-left leading-tight">
        Récapitulatif PDF
        <span className="block text-[10.5px] font-semibold opacity-75">Accessible, disponible 24 heures</span>
      </span>
    </a>
  )
}

function DemarcheCard({ demarche }: { demarche: Demarche }) {
  const Icon = DEMARCHE_ICONS[demarche.kind] ?? CircleCheckIcon
  return (
    <article className={cn(box, "flex flex-col gap-2.5 ring-2 ring-ok/25")} aria-label={`${demarche.title}, référence ${demarche.reference}`}>
      <p className="flex items-center gap-2 text-sm font-extrabold text-navy">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ok-soft text-ok">
          <Icon className="size-4" aria-hidden />
        </span>
        {demarche.title}
      </p>
      <p className="flex items-baseline justify-between gap-2 rounded-xl bg-surface px-3 py-2">
        <span className="text-[11px] font-bold uppercase tracking-wide text-muted-ink">Référence</span>
        <span className="tabular text-base font-extrabold tracking-wide text-navy">{demarche.reference}</span>
      </p>
      <p className="text-xs leading-snug text-navy">{demarche.detail}</p>
      <p className="text-[11px] font-bold text-ok">{STATUS_LABEL[demarche.status] ?? demarche.status}</p>
      {demarche.pdf && <RecapButton pdf={demarche.pdf} />}
      {demarche.status !== "demo_request" && (
      <button
        type="button"
        onClick={() => {
          navigate(`/demarches?ref=${encodeURIComponent(demarche.reference)}`)
          useCompass.getState().setSheet("peek")
        }}
        className="flex items-center justify-center gap-1 rounded-xl py-1.5 text-xs font-bold text-brand hover:bg-brand-soft"
      >
        Voir dans mes démarches <ChevronRightIcon className="size-3.5" aria-hidden />
      </button>
      )}
    </article>
  )
}
