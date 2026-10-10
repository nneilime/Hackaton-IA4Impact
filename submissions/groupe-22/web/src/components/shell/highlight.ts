import { useEffect, useRef } from "react"
import { useCompass } from "@/lib/store"
import type { Highlight } from "@/lib/types"

/** Marks an element where the assistant's work shows, scrolls it into view, then fades. */
export function useHighlight<T extends HTMLElement = HTMLDivElement>(target: Highlight) {
  const ref = useRef<T>(null)
  const h = useCompass((s) => s.highlight)
  const active = h?.target === target
  useEffect(() => {
    if (!active || !ref.current) return
    const reduce = document.documentElement.dataset.motion === "reduce"
    ref.current.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" })
    const t = setTimeout(() => {
      if (useCompass.getState().highlight?.nonce === h?.nonce) useCompass.getState().setHighlight(null)
    }, 6000)
    return () => clearTimeout(t)
  }, [active, h?.nonce])
  return { ref, "data-highlighted": active ? "true" : undefined } as const
}
