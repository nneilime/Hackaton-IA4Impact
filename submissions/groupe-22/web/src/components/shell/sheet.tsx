import { useEffect, useId, useRef, useSyncExternalStore } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "motion/react"
import { XIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Bottom sheet rendered INSIDE the phone viewport (not portalled to <body>),
 * so it stays within the device frame on desktop. Escape closes, focus moves
 * into the sheet and returns to the opener on close.
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  className,
  z = "z-[60]",
}: {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: React.ReactNode
  className?: string
  z?: string
}) {
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  const opener = useRef<Element | null>(null)

  useEffect(() => {
    if (!open) return
    opener.current = document.activeElement
    const t = setTimeout(() => {
      // Focus an explicit target if any, otherwise the dialog itself (screen
      // readers announce its title; no misleading focus ring on "Fermer").
      const target = panel.current?.querySelector<HTMLElement>("[data-autofocus]") ?? panel.current
      target?.focus()
    }, 60)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
      if (e.key === "Tab" && panel.current) {
        const f = [...panel.current.querySelectorAll<HTMLElement>("button:not(:disabled), [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
        if (!f.length) return
        if (e.shiftKey && document.activeElement === f[0]) {
          e.preventDefault()
          f[f.length - 1].focus()
        } else if (!e.shiftKey && document.activeElement === f[f.length - 1]) {
          e.preventDefault()
          f[0].focus()
        }
      }
    }
    document.addEventListener("keydown", onKey)
    return () => {
      clearTimeout(t)
      document.removeEventListener("keydown", onKey)
      ;(opener.current as HTMLElement | null)?.focus?.()
    }
  }, [open, onClose])

  // Portalled to the phone viewport (not <body>) so it covers the whole device,
  // navigation included, without escaping the frame on desktop.
  const host = useSyncExternalStore(
    () => () => {},
    () => document.getElementById("app-viewport"),
    () => null,
  )
  if (!host) return null
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className={cn("absolute inset-0 flex flex-col justify-end", z)}>
          <motion.div
            className="absolute inset-0 bg-navy/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${id}-t`}
            aria-describedby={description ? `${id}-d` : undefined}
            tabIndex={-1}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 340 }}
            className={cn("relative max-h-[88%] overflow-y-auto rounded-t-[28px] bg-white px-5 pb-8 pt-3 shadow-2xl outline-none no-scrollbar", className)}
          >
            <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-line" aria-hidden />
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 id={`${id}-t`} className="text-lg font-extrabold tracking-tight text-navy">
                  {title}
                </h2>
                {description && (
                  <p id={`${id}-d`} className="mt-0.5 text-sm text-muted-ink">
                    {description}
                  </p>
                )}
              </div>
              <button type="button" onClick={onClose} aria-label="Fermer" className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface text-navy hover:bg-line">
                <XIcon className="size-5" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    host,
  )
}
