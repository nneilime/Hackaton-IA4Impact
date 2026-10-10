import { motion } from "motion/react"
import { BanIcon, LockIcon, NfcIcon } from "lucide-react"
import type { Card } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Card visual. Only the masked number is ever displayed. */
export function BankCardVisual({ card, compact }: { card: Card; compact?: boolean }) {
  const opposed = card.status === "OPPOSED"
  const locked = card.status === "LOCKED"
  const virtual = card.kind === "VIRTUAL"
  return (
    <div
      role="img"
      aria-label={`${card.label} ${card.maskedNumber}, ${STATUS[card.status]}`}
      className={cn(
        "relative aspect-[1.586/1] w-full overflow-hidden rounded-[22px] p-5 text-white shadow-[0_18px_30px_-14px_rgba(8,13,52,0.55)]",
        virtual ? "bg-[linear-gradient(135deg,#051b71_0%,#000c3c_100%)]" : "bg-[linear-gradient(135deg,#3954c0_0%,#062499_100%)]",
        compact && "rounded-2xl p-3.5",
      )}
    >
      <svg aria-hidden className="absolute -right-10 -top-12 size-56 opacity-[0.14]" viewBox="0 0 200 200">
        <circle cx="100" cy="100" r="90" fill="none" stroke="white" strokeWidth="18" />
        <circle cx="100" cy="100" r="50" fill="none" stroke="white" strokeWidth="10" />
      </svg>
      <div className="relative flex h-full flex-col justify-between">
        <div className="flex items-start justify-between">
          <span className={cn("font-bold", compact ? "text-xs" : "text-sm")}>{card.label}</span>
          <span className={cn("font-extrabold italic tracking-tight", compact ? "text-sm" : "text-lg")}>{card.network === "VISA" ? "VISA" : "mastercard"}</span>
        </div>
        {!compact && (
          <div className="flex items-center gap-2">
            {!virtual && <div className="h-7 w-10 rounded-md bg-[linear-gradient(135deg,#e5bd77,#bd8a00)] opacity-90" />}
            {card.contactless && <NfcIcon className="size-5 opacity-70" aria-hidden />}
          </div>
        )}
        <div className="flex items-end justify-between">
          <div>
            <p className={cn("tabular font-semibold tracking-[0.18em]", compact ? "text-xs" : "text-[17px]")}>•••• •••• {card.maskedNumber}</p>
            {!compact && <p className="mt-1 text-[11px] font-semibold uppercase opacity-80">{card.holder}</p>}
          </div>
          {!compact && <p className="text-xs font-semibold opacity-80">{card.expiry}</p>}
        </div>
      </div>
      {opposed && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#454545]/55 text-navy backdrop-blur-[3px]"
        >
          <span className={cn("flex items-center justify-center rounded-full bg-white text-brand shadow-md", compact ? "size-8" : "size-12")}>
            <BanIcon className={compact ? "size-4" : "size-6"} aria-hidden />
          </span>
          {!compact && <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-extrabold">Carte en opposition</span>}
        </motion.div>
      )}
      {locked && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#080d34]/45 text-navy backdrop-blur-[2px]">
          <span className={cn("flex items-center justify-center rounded-full bg-white text-navy shadow-md", compact ? "size-8" : "size-12")}>
            <LockIcon className={compact ? "size-4" : "size-6"} aria-hidden />
          </span>
          {!compact && <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-extrabold">Verrouillée temporairement</span>}
        </motion.div>
      )}
    </div>
  )
}

const STATUS: Record<Card["status"], string> = { ACTIVE: "active", LOCKED: "verrouillée temporairement", OPPOSED: "en opposition" }

export function CardStatusPill({ status }: { status: Card["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold",
        status === "ACTIVE" ? "bg-ok-soft text-ok" : status === "LOCKED" ? "bg-info-soft text-navy" : "bg-brand-soft text-brand",
      )}
    >
      {status === "LOCKED" ? <LockIcon className="size-3" aria-hidden /> : <span className={cn("size-1.5 rounded-full", status === "ACTIVE" ? "bg-ok" : "bg-brand")} aria-hidden />}
      {status === "ACTIVE" ? "Active" : status === "LOCKED" ? "Verrouillée" : "En opposition"}
    </span>
  )
}
