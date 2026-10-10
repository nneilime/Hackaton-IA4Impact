import { create } from "zustand"
import { AnimatePresence, motion } from "motion/react"
import { CircleAlertIcon, CircleCheckIcon, InfoIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type Toast = { id: number; kind: "ok" | "error" | "info"; text: string }
const useToasts = create<{ items: Toast[] }>(() => ({ items: [] }))

export function toast(text: string, kind: Toast["kind"] = "ok") {
  const id = Date.now() + Math.random()
  useToasts.setState((s) => ({ items: [...s.items, { id, kind, text }] }))
  setTimeout(() => useToasts.setState((s) => ({ items: s.items.filter((t) => t.id !== id) })), 4200)
}

export function Toaster() {
  const items = useToasts((s) => s.items)
  return (
    <div aria-live="polite" role="status" className="pointer-events-none absolute inset-x-0 top-14 z-[70] flex flex-col items-center gap-2 px-4">
      <AnimatePresence>
        {items.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8 }}
            className={cn(
              "pointer-events-auto flex max-w-full items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold shadow-lg",
              t.kind === "ok" && "bg-navy text-white",
              t.kind === "error" && "bg-brand text-white",
              t.kind === "info" && "bg-white text-navy ring-1 ring-line",
            )}
          >
            {t.kind === "ok" ? <CircleCheckIcon className="size-4 shrink-0" /> : t.kind === "error" ? <CircleAlertIcon className="size-4 shrink-0" /> : <InfoIcon className="size-4 shrink-0" />}
            <span>{t.text}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
