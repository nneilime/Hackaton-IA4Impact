import { useEffect, useMemo, useRef, useState } from "react"
import { Icon } from "../App"
import { api } from "../api/client"
import type { Check, CheckReview, Pair } from "../api/types"
import { checkField, checkHighlights, checkZone, RISK_LABEL, SOURCE_LABEL } from "../lib/checks"
import { euros } from "../lib/format"

type Tab = "scan" | "ocr" | "b2"

function ScanView({ pair, check }: { pair: Pair; check: Check | null }) {
  const highlights = useMemo(() => (check ? checkHighlights(check, pair) : []), [check, pair])
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [failed, setFailed] = useState(false)
  const [zoom, setZoom] = useState(highlights.length ? 2 : 1)
  const scrollRef = useRef<HTMLDivElement>(null)

  const rects = useMemo(
    () =>
      natural
        ? highlights.map((h) => {
            const [x1, y1, x2, y2] =
              h.units === "norm"
                ? h.box.map((v) => v / 1000)
                : [h.box[0] / natural.w, h.box[1] / natural.h, h.box[2] / natural.w, h.box[3] / natural.h]
            return { x1, y1, x2, y2, label: h.label }
          })
        : [],
    [highlights, natural],
  )

  // bring the first highlighted area into view whenever the zoom or the check changes
  useEffect(() => {
    const el = scrollRef.current
    if (!el || rects.length === 0) return
    const first = rects[0]
    const last = rects[rects.length - 1]
    const cx = (first.x1 + last.x2) / 2
    const cy = (first.y1 + last.y2) / 2
    el.scrollTo({
      left: cx * el.scrollWidth - el.clientWidth / 2,
      top: cy * el.scrollHeight - el.clientHeight / 2,
      behavior: "smooth",
    })
  }, [rects, zoom])

  if (failed) {
    return (
      <div className="grid h-[520px] place-items-center rounded-xl border border-dashed border-slate-300 bg-white text-center text-xs text-slate-400">
        <div>
          <Icon name="file" size={28} />
          <p className="mt-2">Scan non disponible pour ce dossier.</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <span className="truncate text-xs font-semibold text-slate-700">{pair.name}.jpg</span>
        <div className="flex items-center gap-1 rounded-lg bg-white p-1 shadow-sm">
          {[1, 2, 3].map((z) => (
            <button
              key={z}
              onClick={() => setZoom(z)}
              className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                zoom === z ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {z * 100} %
            </button>
          ))}
        </div>
      </div>
      <div ref={scrollRef} className="h-[520px] overflow-auto rounded-xl border border-slate-300 bg-slate-200 shadow-inner">
        <div className="relative" style={{ width: `${zoom * 100}%` }}>
          <img
            src={api.imageUrl(pair.id)}
            alt={`Bordereau ${pair.name}`}
            className="block w-full select-none"
            draggable={false}
            onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
            onError={() => setFailed(true)}
          />
          {rects.map((r, index) => (
            <div
              key={index}
              className="pointer-events-none absolute border-2 border-rose-500 bg-rose-500/10 shadow-[0_0_0_3px_rgba(244,63,94,0.15)]"
              style={{
                left: `${r.x1 * 100}%`,
                top: `${r.y1 * 100}%`,
                width: `${(r.x2 - r.x1) * 100}%`,
                height: `${(r.y2 - r.y1) * 100}%`,
              }}
            >
              <span className="absolute -top-5 right-0 whitespace-nowrap rounded bg-rose-600 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                {r.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

function TextView({ pair, kind }: { pair: Pair; kind: "ocr" | "facture" }) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState("")
  useEffect(() => {
    let alive = true
    api
      .documentText(pair.id, kind)
      .then((t) => alive && setText(t))
      .catch((e) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [pair.id, kind])
  if (error) return <p className="rounded-lg bg-white p-4 text-xs text-slate-500">{error}</p>
  if (text === null) return <p className="p-4 text-xs text-slate-400">Chargement…</p>
  return (
    <pre
      className={`h-[560px] overflow-auto rounded-xl border border-slate-200 bg-white p-4 font-mono leading-relaxed text-slate-700 ${
        kind === "facture" ? "whitespace-pre text-[10px]" : "whitespace-pre-wrap text-[10.5px]"
      }`}
    >
      {text}
    </pre>
  )
}

function SignatureBoxes({ pair }: { pair: Pair }) {
  const boxes = pair.bordereau?.signature_boxes ?? []
  if (!boxes.some((b) => b.signed !== null)) {
    return <p className="text-xs text-slate-400">Les cases de signature n’ont pas été analysées (scan absent).</p>
  }
  return (
    <div className="divide-y divide-slate-100">
      {boxes
        .filter((b) => b.signed || b.rows > 0 || b.problems.length > 0)
        .map((b) => (
          <div key={b.box} className="py-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700">
                Case {b.box} · {b.printed_name ?? b.printed_executant ?? "sans texte"}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  b.signed ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                }`}
              >
                {b.signed ? "Signée" : "Vide"}
              </span>
            </div>
            <p className="mt-1 text-slate-500">
              Montant imprimé {euros(b.printed_amount)} · actes {euros(b.computed_amount)} ({b.rows} ligne
              {b.rows > 1 ? "s" : ""})
            </p>
            {b.problems.map((p) => (
              <p key={p} className="mt-1 text-rose-600">
                {p}
              </p>
            ))}
          </div>
        ))}
    </div>
  )
}

export default function DocumentPanel({
  pair,
  check,
  review,
  canReview,
  onReview,
  onClose,
}: {
  pair: Pair
  check: Check | null
  review?: CheckReview
  canReview: boolean
  onReview: (code: string, outcome: "confirmed" | "dismissed") => Promise<void>
  onClose: () => void
}) {
  const [tab, setTab] = useState<Tab>("scan")
  const [busy, setBusy] = useState(false)
  const isSignature = check?.code === "C18" || check?.code === "X3"

  const reviewAs = async (outcome: "confirmed" | "dismissed") => {
    if (!check) return
    setBusy(true)
    try {
      await onReview(check.code, outcome)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-[560px] flex-col border-l border-slate-200 bg-white shadow-[-12px_0_35px_rgba(15,23,42,0.12)]">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-5">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-slate-900">
            {check ? `${checkField(check)} · ${checkZone(check)}` : "Documents du dossier"}
          </h2>
          <p className="mt-0.5 text-[11px] text-slate-400">
            {check ? `${check.code} · ${RISK_LABEL[check.risk]}` : pair.name}
          </p>
        </div>
        <button
          onClick={onClose}
          className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
          aria-label="Fermer le panneau"
        >
          <Icon name="x" size={17} />
        </button>
      </div>
      <div className="flex shrink-0 gap-1 border-b border-slate-200 px-5 py-2">
        {(
          [
            ["scan", "Bordereau scanné"],
            ["ocr", "Lecture OCR"],
            ["b2", "Fichier B2"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === key ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto bg-slate-100 p-5">
        {tab === "scan" && <ScanView key={check?.code ?? "doc"} pair={pair} check={check} />}
        {tab === "ocr" && <TextView pair={pair} kind="ocr" />}
        {tab === "b2" && <TextView pair={pair} kind="facture" />}

        {check && (
          <div className="mt-5 rounded-xl border border-slate-200 bg-white p-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Valeur lue · {SOURCE_LABEL[check.found_source]}
                </p>
                <p className="mt-1 break-words font-mono text-[13px] font-semibold text-slate-800">{check.found ?? "—"}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Référence · {SOURCE_LABEL[check.expected_source]}
                </p>
                <p
                  className={`mt-1 break-words font-mono text-[13px] font-semibold ${
                    check.status === "FAIL" ? "text-rose-700" : "text-slate-800"
                  }`}
                >
                  {check.expected ?? "—"}
                </p>
              </div>
            </div>
            {check.detail && <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">{check.detail}</p>}
            {check.ocr_suspect && (
              <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
                Les deux valeurs ne diffèrent que par des caractères que l’OCR confond souvent : vérifiez sur le scan.
              </p>
            )}
            {isSignature && (
              <div className="mt-3 border-t border-slate-100 pt-3">
                <SignatureBoxes pair={pair} />
              </div>
            )}
            {check.status !== "PASS" && (
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-xs font-semibold text-slate-700">L’écart est-il réel ?</p>
                {review && (
                  <p className="mt-1 text-[11px] text-slate-400">
                    Votre avis : {review.outcome === "confirmed" ? "écart confirmé" : "écart écarté (erreur de lecture)"}
                  </p>
                )}
                {canReview ? (
                  <div className="mt-3 flex gap-2">
                    <button
                      disabled={busy}
                      onClick={() => reviewAs("confirmed")}
                      className={`h-9 flex-1 rounded-lg border text-xs font-semibold ${
                        review?.outcome === "confirmed"
                          ? "border-rose-600 bg-rose-600 text-white"
                          : "border-rose-200 text-rose-700 hover:bg-rose-50"
                      }`}
                    >
                      Oui, l’écart est réel
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => reviewAs("dismissed")}
                      className={`h-9 flex-1 rounded-lg border text-xs font-semibold ${
                        review?.outcome === "dismissed"
                          ? "border-slate-800 bg-slate-800 text-white"
                          : "border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      Non, erreur de lecture
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-[11px] text-slate-400">Prenez le dossier pour donner votre avis.</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
