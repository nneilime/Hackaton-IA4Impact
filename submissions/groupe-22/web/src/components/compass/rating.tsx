import { useEffect, useRef, useState } from "react"
import { StarIcon } from "lucide-react"
import { rate } from "@/lib/rating"
import { useCompass } from "@/lib/store"
import { cn } from "@/lib/utils"
import { toast } from "@/components/shell/toast"
import { CompassMark } from "./compass-mark"

const MEANING = ["", "Très déçu·e", "Déçu·e", "Correct", "Satisfait·e", "Très satisfait·e"]

/** « Votre avis » when a conversation ends: 1 to 5 stars, native radios (arrows to
 * choose, read out as « 3 étoiles sur 5 »), then « Envoyer », or « Passer ». */
export function RatingView() {
  const mode = useCompass((s) => s.rating?.mode)
  const [stars, setStars] = useState(0)
  const [hover, setHover] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  const shown = hover || stars

  // Read out first by screen readers: the call just ended, this is what's on screen now.
  useEffect(() => heading.current?.focus({ preventScroll: true }), [])

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!stars) return
        rate(stars)
        toast("Merci pour votre avis.")
      }}
      className="flex h-full flex-col items-center justify-center gap-5 px-6 pb-[max(env(safe-area-inset-bottom),24px)] text-center"
    >
      <span className="flex size-14 items-center justify-center rounded-2xl bg-brand text-white shadow-[0_10px_24px_-10px_rgba(6,36,153,0.7)]" aria-hidden>
        <CompassMark className="size-8" />
      </span>
      <div>
        <h2 ref={heading} tabIndex={-1} className="text-[22px] font-extrabold leading-tight tracking-tight text-navy outline-none">
          Votre avis
        </h2>
        <p className="mt-1 text-[15px] font-semibold text-muted-ink">
          {mode === "voice" ? "Comment s'est passé cet appel avec Compass ?" : "Comment s'est passée cette conversation avec Compass ?"}
        </p>
      </div>
      <fieldset>
        <legend className="sr-only">Votre note, de 1 à 5 étoiles</legend>
        <div className="flex" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className="cursor-pointer" onMouseEnter={() => setHover(n)}>
              <input type="radio" name="stars" value={n} checked={stars === n} onChange={() => setStars(n)} className="peer sr-only" />
              <span className="block rounded-xl p-1 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-1 peer-focus-visible:outline-navy">
                <StarIcon className={cn("size-11 transition-colors", n <= shown ? "fill-navy text-navy" : "text-muted-ink")} strokeWidth={1.75} aria-hidden />
              </span>
              <span className="sr-only">
                {n} étoile{n > 1 ? "s" : ""} sur 5, {MEANING[n]}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="h-5 text-sm font-bold text-navy" aria-hidden>
        {MEANING[shown]}
      </p>
      <div className="flex w-full max-w-72 flex-col gap-2">
        <button type="submit" disabled={!stars} className="h-12 rounded-2xl bg-brand font-bold text-white transition hover:bg-brand-strong disabled:bg-line disabled:text-muted-ink">
          Envoyer
        </button>
        <button type="button" onClick={() => rate(null)} className="h-11 rounded-2xl text-sm font-bold text-navy hover:bg-surface">
          Passer
        </button>
      </div>
    </form>
  )
}
