import { useEffect, useMemo, useState } from "react"
import { ActionModal, ActionModalType, Header, Icon, useToast } from "../App"
import { api, ApiError } from "../api/client"
import type { Check, TicketDetail, TicketSummary } from "../api/types"
import { useAuth } from "../auth"
import { CATEGORY_LABEL, checkField, checkZone, EVENT_LABEL, RISK_LABEL, SOURCE_LABEL, STATUS_ORDER } from "../lib/checks"
import { euros, frDate, frDateTime, plural } from "../lib/format"
import { useApi } from "../lib/useApi"
import DocumentPanel from "./DocumentPanel"

function Loading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="grid min-h-[calc(100vh-56px)] place-items-center">
      <div className="text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-blue-50 text-blue-600">
          <Icon name="compare" size={25} />
        </span>
        <div className="mx-auto mt-5 h-1 w-44 overflow-hidden rounded-full bg-slate-200">
          <span className="loading-bar block h-full rounded-full bg-blue-600" />
        </div>
        <p className="mt-4 text-sm font-semibold text-slate-800">{title}</p>
        <p className="mt-1 text-xs text-slate-400">{subtitle}</p>
      </div>
    </div>
  )
}

function VerdictPill({ verdict, size = "sm" }: { verdict: "CORRECT" | "ISSUES"; size?: "sm" | "lg" }) {
  const ok = verdict === "CORRECT"
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${
        size === "lg" ? "px-2.5 py-1 text-[10px] uppercase tracking-[0.08em]" : "px-2.5 py-1 text-xs"
      } ${
        size === "lg"
          ? ok
            ? "bg-emerald-600 text-white"
            : "bg-rose-600 text-white"
          : ok
            ? "bg-emerald-50 text-emerald-700"
            : "bg-rose-50 text-rose-700"
      }`}
    >
      {size === "sm" && <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />}
      {ok ? "Conforme" : "Non conforme"}
    </span>
  )
}

function RiskBar({ score }: { score: number }) {
  const width = Math.min(100, (score / 12) * 100)
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
        <span
          className={`block h-full rounded-full ${score >= 6 ? "bg-rose-500" : score >= 2 ? "bg-amber-400" : "bg-emerald-500"}`}
          style={{ width: `${Math.max(width, 4)}%` }}
        />
      </span>
      <span className="text-[11px] font-medium text-slate-500">{score.toFixed(1).replace(".", ",")}</span>
    </span>
  )
}

// ---- queue ---------------------------------------------------------------------------------------------

function TicketTable({ tickets, onOpen, empty }: { tickets: TicketSummary[]; onOpen: (id: number) => void; empty: string }) {
  if (tickets.length === 0) return <p className="px-6 py-8 text-center text-xs text-slate-400">{empty}</p>
  return (
    <table className="w-full table-fixed">
      <thead>
        <tr className="bg-slate-50/70 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-400">
          <th className="w-[16%] px-6 py-3">Dossier</th>
          <th className="w-[20%] px-4 py-3">Clinique</th>
          <th className="w-[13%] px-4 py-3">N° facture</th>
          <th className="w-[12%] px-4 py-3">Montant</th>
          <th className="w-[9%] px-4 py-3">Écarts</th>
          <th className="w-[14%] px-4 py-3">Analyse</th>
          <th className="w-[10%] px-4 py-3">Risque</th>
          <th className="px-4 py-3"></th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {tickets.map((t) => (
          <tr key={t.id} onClick={() => onOpen(t.id)} className="cursor-pointer text-sm transition-colors hover:bg-blue-50/40">
            <td className="px-6 py-3.5">
              <p className="font-semibold text-slate-800">{t.pair_name}</p>
              {t.escalated ? (
                <p className="mt-0.5 truncate text-[11px] font-medium text-amber-600" title={t.escalation_comment ?? ""}>
                  Avis demandé · {t.escalation_comment}
                </p>
              ) : (
                <p className="mt-0.5 text-[11px] text-slate-400">n° {t.id}</p>
              )}
            </td>
            <td className="truncate px-4 py-3.5 text-slate-600">{t.clinic_name ?? "—"}</td>
            <td className="px-4 py-3.5 font-mono text-[12px] text-slate-600">{t.numero_facture ?? "—"}</td>
            <td className="px-4 py-3.5 font-medium text-slate-700">{euros(t.amount)}</td>
            <td className={`px-4 py-3.5 font-semibold ${t.failed_checks ? "text-rose-600" : "text-slate-400"}`}>{t.failed_checks}</td>
            <td className="px-4 py-3.5">
              <VerdictPill verdict={t.final_verdict ?? t.algo_verdict} />
            </td>
            <td className="px-4 py-3.5">
              {t.algo_verdict === "CORRECT" && !t.escalated ? (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                  Priorité basse
                </span>
              ) : (
                <RiskBar score={t.risk_score} />
              )}
            </td>
            <td className="px-4 py-3.5 text-right text-slate-300">
              <Icon name="chevron" size={16} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function QueueView({ onOpen, onClaim, claiming }: { onOpen: (id: number) => void; onClaim: () => void; claiming: boolean }) {
  const { user, refresh } = useAuth()
  const isManager = user?.role === "admin"
  const mine = useApi(() => api.tickets({ mine: true, status: "assigned" }), [])
  const queue = useApi(() => api.tickets({ status: "open", escalated: isManager ? undefined : false, limit: 500 }), [isManager])
  const escalated = (queue.data ?? []).filter((t) => t.escalated)
  const regular = (queue.data ?? []).filter((t) => !t.escalated)

  useEffect(() => {
    refresh()
  }, [refresh])

  const counts = user?.queue
  const waiting = isManager ? (counts?.open ?? 0) + (counts?.escalated ?? 0) : (counts?.open ?? 0)

  return (
    <>
      <Header
        title="Comparaison"
        subtitle="Contrôlez chaque facture B2 face à son bordereau scanné"
        actions={
          <button
            onClick={() => {
              mine.reload()
              queue.reload()
              refresh()
            }}
            className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            <Icon name="refresh" size={15} /> Actualiser
          </button>
        }
      />
      <section className="mb-6 flex items-center justify-between rounded-2xl border border-blue-200 bg-blue-50/60 px-6 py-5">
        <div className="flex items-center gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-blue-100 text-blue-600">
            <Icon name="file" size={22} />
          </span>
          <div>
            <p className="text-lg font-semibold text-slate-900">{plural(waiting, "dossier en attente", "dossiers en attente")}</p>
            <p className="mt-0.5 text-sm text-slate-500">
              {isManager && counts?.escalated
                ? `${plural(counts.escalated, "demande d’avis", "demandes d’avis")} vous attendent en priorité · `
                : ""}
              {plural(counts?.resolved_by_me ?? 0, "dossier clôturé", "dossiers clôturés")} par vous
            </p>
          </div>
        </div>
        <button
          onClick={onClaim}
          disabled={claiming || waiting === 0}
          className="flex h-11 items-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {claiming ? "Attribution..." : "Prendre le dossier suivant"} <Icon name="arrow" size={16} />
        </button>
      </section>

      {(mine.data?.length ?? 0) > 0 && (
        <section className="mb-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-sm font-semibold text-slate-900">Mes dossiers en cours</h2>
            <p className="mt-0.5 text-xs text-slate-400">
              {plural(mine.data!.length, "dossier attribué", "dossiers attribués")} sur {user?.max_active} au maximum
            </p>
          </div>
          <TicketTable tickets={mine.data!} onOpen={onOpen} empty="" />
        </section>
      )}

      {isManager && escalated.length > 0 && (
        <section className="mb-6 overflow-hidden rounded-2xl border border-amber-200 bg-white">
          <div className="border-b border-amber-200 bg-amber-50/60 px-6 py-4">
            <h2 className="text-sm font-semibold text-amber-900">Demandes d’avis des agents</h2>
            <p className="mt-0.5 text-xs text-amber-700">Dossiers transmis par un agent qui attendent votre décision</p>
          </div>
          <TicketTable tickets={escalated} onOpen={onOpen} empty="" />
        </section>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-sm font-semibold text-slate-900">File d’attente</h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Les dossiers les plus risqués en premier · sans anomalie détectée en dernier
          </p>
        </div>
        {queue.error ? (
          <p className="px-6 py-6 text-xs text-rose-600">{queue.error}</p>
        ) : queue.loading && !queue.data ? (
          <p className="px-6 py-8 text-center text-xs text-slate-400">Chargement…</p>
        ) : (
          <TicketTable tickets={regular} onOpen={onOpen} empty="Aucun dossier en attente. Bon travail !" />
        )}
      </section>
    </>
  )
}

// ---- one ticket ----------------------------------------------------------------------------------------

function discrepancy(t: TicketDetail): number | null {
  const f = t.pair.facture
  const b = t.pair.bordereau
  // a B2 file whose layout is broken (X1) has no meaningful amounts to compare
  if (!f || !b || t.pair.checks.some((c) => c.code === "X1" && c.status === "FAIL")) return null
  let total = 0
  let known = false
  if (f.total_prestations !== null && b.sous_total_123 !== null) {
    total += Math.abs(f.total_prestations - b.sous_total_123)
    known = true
  }
  if (f.total_honoraires !== null && b.sous_total_4 !== null) {
    total += Math.abs(f.total_honoraires - b.sous_total_4)
    known = true
  }
  return known ? total : null
}

function SourceTag({ source }: { source: Check["expected_source"] }) {
  return (
    <span className="mt-1 block font-sans text-[10px] font-medium uppercase tracking-wide text-slate-400">
      {SOURCE_LABEL[source]}
    </span>
  )
}

function StatusIcon({ status }: { status: Check["status"] }) {
  const style =
    status === "PASS" ? "bg-emerald-50 text-emerald-600" : status === "FAIL" ? "bg-rose-100 text-rose-600" : "bg-amber-50 text-amber-600"
  return (
    <span className={`mx-auto grid h-7 w-7 place-items-center rounded-full ${style}`} title={status}>
      {status === "UNVERIFIABLE" ? (
        <span className="text-sm font-bold">?</span>
      ) : (
        <Icon name={status === "PASS" ? "check" : "x"} size={15} strokeWidth={2.3} />
      )}
    </span>
  )
}

function TicketView({
  ticketId,
  onBack,
  onFinished,
  toast,
}: {
  ticketId: number
  onBack: () => void
  onFinished: (message: string) => void
  toast: (message: string, tone?: "success" | "error") => void
}) {
  const { user, refresh } = useAuth()
  const { data: t, error, loading, reload } = useApi(() => api.ticket(ticketId), [ticketId])
  const [filter, setFilter] = useState<"issues" | "all">("issues")
  const [panel, setPanel] = useState<{ check: Check | null } | null>(null)
  const [modal, setModal] = useState<ActionModalType | null>(null)
  const [busy, setBusy] = useState(false)

  const checks = useMemo(
    () => [...(t?.pair.checks ?? [])].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]),
    [t],
  )

  if (!t) {
    if (error) {
      return (
        <div className="grid min-h-[60vh] place-items-center text-center">
          <div>
            <p className="text-sm font-semibold text-slate-800">Dossier inaccessible</p>
            <p className="mt-1 text-xs text-slate-500">{error}</p>
            <button onClick={onBack} className="mt-4 h-9 rounded-lg border border-slate-200 px-4 text-xs font-semibold text-slate-600">
              Retour à la file
            </button>
          </div>
        </div>
      )
    }
    return <Loading title="Analyse de la facture en cours" subtitle="Lecture du bordereau et du flux B2..." />
  }

  const isManager = user?.role === "admin"
  const mine = t.status === "assigned" && t.assignee_id === user?.id
  const canAct = t.status === "assigned" && (mine || isManager)
  const canTake = t.status === "open" && (!t.escalated || isManager)
  // agents only (managers are the ones asked), on a case they hold or can take, not already waiting for a manager
  const canAskManager = !isManager && !t.escalated && (canAct ? mine : canTake)
  const failed = checks.filter((c) => c.status === "FAIL")
  const unverifiable = checks.filter((c) => c.status === "UNVERIFIABLE")
  const passed = checks.filter((c) => c.status === "PASS")
  const shown = filter === "issues" ? checks.filter((c) => c.status !== "PASS") : checks
  const reviews = new Map(t.check_reviews.map((r) => [r.check_code, r]))
  const gap = discrepancy(t)
  const algoOk = t.algo_verdict === "CORRECT"
  const facture = t.pair.facture

  const run = async (action: () => Promise<unknown>, after?: () => void) => {
    setBusy(true)
    try {
      await action()
      after?.()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error")
      if (e instanceof ApiError && e.status === 409) reload()
    } finally {
      setBusy(false)
    }
  }

  const take = () => run(() => api.requestTicket(t.id), () => {
    reload()
    refresh()
    toast("Dossier attribué")
  })
  const release = () => run(() => api.releaseTicket(t.id), () => {
    refresh()
    onBack()
    toast("Dossier remis dans la file")
  })
  const validate = () => {
    if (!algoOk) return setModal("validate")
    run(() => api.resolveTicket(t.id, "CORRECT", "none", ""), () => onFinished("Facture validée conforme"))
  }
  const reopen = () => run(() => api.reopenTicket(t.id, "réouverture par un manager"), () => {
    reload()
    toast("Dossier rouvert")
  })
  const reviewCheck = async (code: string, outcome: "confirmed" | "dismissed") => {
    try {
      await api.reviewCheck(t.id, code, outcome)
      await reload()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error")
    }
  }

  const confirmModal = async (reason: { label: string; value: string } | null, comment: string) => {
    if (modal === "manager") {
      if (!canAct) await api.requestTicket(t.id) // an open case is taken first: only its holder can escalate it
      await api.escalateTicket(t.id, comment)
      setModal(null)
      onFinished("Demande envoyée aux managers")
    } else if (modal === "validate") {
      await api.resolveTicket(t.id, "CORRECT", (reason?.value ?? "none") as "none" | "ocr_error", comment)
      setModal(null)
      onFinished("Facture validée, écarts expliqués")
    } else if (modal === "problem") {
      const category = (reason?.value ?? "billing_error") as "billing_error" | "suspected_fraud"
      const text = [reason?.label, comment].filter(Boolean).join(" — ")
      await api.resolveTicket(t.id, "ISSUES", category, text)
      setModal(null)
      onFinished(category === "suspected_fraud" ? "Suspicion de fraude enregistrée" : "Erreur confirmée, facture transmise")
    }
  }

  return (
    <>
      <div className="pb-28">
        <div className="mb-7 flex items-end justify-between">
          <div>
            <button onClick={onBack} className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-700">
              <span className="inline-flex rotate-180">
                <Icon name="arrow" size={13} />
              </span>
              File d’attente
            </button>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-400">
              <span className={`h-2 w-2 rounded-full ${t.status === "resolved" ? "bg-slate-400" : "bg-blue-500"}`} />
              {t.status === "resolved"
                ? `DOSSIER CLÔTURÉ · ${frDateTime(t.resolved_at)}`
                : t.status === "assigned"
                  ? mine
                    ? "FACTURE À CONTRÔLER · attribuée à vous"
                    : `ATTRIBUÉE À ${(t.assignee_name ?? t.assignee ?? "").toUpperCase()}`
                  : t.escalated
                    ? "EN ATTENTE D’UN AVIS MANAGER"
                    : "EN ATTENTE D’ATTRIBUTION"}
            </div>
            <h1 className="text-[27px] font-semibold tracking-[-0.035em] text-slate-950">
              Facture {facture?.numero_facture ?? t.pair_name}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {t.pair_name} · fichier du {frDate(facture?.date_fichier)} · comparaison automatique du {frDateTime(t.pair.updated_at)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {canAskManager && (
              <button
                disabled={busy}
                onClick={() => setModal("manager")}
                className="flex h-9 items-center gap-2 whitespace-nowrap rounded-lg border border-blue-200 bg-blue-50 px-3 text-xs font-semibold text-blue-700 hover:bg-blue-100"
              >
                <Icon name="message" size={15} /> Demander à un manager
              </button>
            )}
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500">
              Dossier n° {t.id}
            </span>
          </div>
        </div>

        {t.escalated && t.escalation_comment && t.status !== "resolved" ? (
          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            <Icon name="message" size={18} />
            <div>
              <p className="font-semibold">Avis demandé par un agent</p>
              <p className="mt-0.5 text-amber-800">{t.escalation_comment}</p>
            </div>
          </div>
        ) : null}

        {t.status === "resolved" && (
          <div className="mb-5 flex items-start justify-between rounded-2xl border border-slate-200 bg-white px-6 py-4">
            <div className="flex items-start gap-3">
              <Icon name={t.final_verdict === "CORRECT" ? "check" : "flag"} size={18} />
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  Décision finale : {t.final_verdict === "CORRECT" ? "conforme" : "non conforme"} ·{" "}
                  {CATEGORY_LABEL[t.final_category ?? "none"]}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  par {t.resolved_by_name ?? "—"} · {frDateTime(t.resolved_at)}
                  {t.final_comment ? ` · « ${t.final_comment} »` : ""}
                </p>
              </div>
            </div>
            {isManager && (
              <button
                disabled={busy}
                onClick={reopen}
                className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                Rouvrir
              </button>
            )}
          </div>
        )}

        <section
          className={`mb-5 flex items-center justify-between rounded-2xl border px-6 py-5 ${
            algoOk ? "border-emerald-200 bg-emerald-50/60" : "border-rose-200 bg-rose-50/60"
          }`}
        >
          <div className="flex items-center gap-4">
            <span
              className={`grid h-12 w-12 place-items-center rounded-full ${algoOk ? "bg-emerald-100 text-emerald-600" : "bg-rose-100 text-rose-600"}`}
            >
              <Icon name={algoOk ? "check" : "x"} size={24} strokeWidth={2.2} />
            </span>
            <div>
              <VerdictPill verdict={t.algo_verdict} size="lg" />
              <p className="mt-2 text-sm text-slate-600">
                {failed.length
                  ? `${plural(failed.length, "écart nécessite", "écarts nécessitent")} votre attention avant décision.`
                  : "Aucun écart détecté par l’analyse automatique."}
                {unverifiable.length ? ` ${plural(unverifiable.length, "contrôle est", "contrôles sont")} à vérifier sur le scan.` : ""}
              </p>
            </div>
          </div>
          <div className={`flex divide-x ${algoOk ? "divide-emerald-200" : "divide-rose-200"}`}>
            <div className="px-8">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Clinique</p>
              <p className="mt-1 max-w-[220px] truncate text-sm font-semibold text-slate-800">{t.clinic_name ?? "—"}</p>
            </div>
            <div className="px-8">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Montant facturé</p>
              <p className="mt-1 text-sm font-semibold text-slate-800">{euros(t.amount)}</p>
            </div>
            <div className="pl-8">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Montant en écart</p>
              <p className={`mt-1 text-sm font-semibold ${gap ? "text-rose-600" : "text-slate-800"}`}>{euros(gap)}</p>
            </div>
          </div>
        </section>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Détail de la comparaison</h2>
              <p className="mt-0.5 text-xs text-slate-400">{checks.length} contrôles réalisés</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex gap-4 text-[11px]">
                <span className="flex items-center gap-1.5 text-emerald-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" /> {passed.length} conformes
                </span>
                <span className="flex items-center gap-1.5 text-rose-600">
                  <span className="h-2 w-2 rounded-full bg-rose-500" /> {failed.length} écarts
                </span>
                <span className="flex items-center gap-1.5 text-amber-600">
                  <span className="h-2 w-2 rounded-full bg-amber-400" /> {unverifiable.length} à vérifier
                </span>
              </div>
              <div className="flex rounded-lg bg-slate-100 p-1">
                {(
                  [
                    ["issues", "Écarts"],
                    ["all", "Tous"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setFilter(key)}
                    className={`rounded-md px-3 py-1 text-xs font-medium ${filter === key ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setPanel({ check: null })}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
              >
                <Icon name="file" size={14} /> Documents
              </button>
            </div>
          </div>
          {shown.length === 0 ? (
            <p className="px-6 py-8 text-center text-xs text-slate-400">Aucun écart : tous les contrôles sont conformes.</p>
          ) : (
            <table className="w-full table-fixed">
              <thead>
                <tr className="bg-slate-50/70 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-400">
                  <th className="w-[28%] px-6 py-3">Champ contrôlé</th>
                  <th className="w-[24%] px-4 py-3">Valeur lue</th>
                  <th className="w-[24%] px-4 py-3">Référence</th>
                  <th className="w-[10%] px-4 py-3 text-center">Résultat</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((check) => {
                  const bad = check.status === "FAIL"
                  const review = reviews.get(check.code)
                  return (
                    <tr key={check.code} className={bad ? "bg-rose-50/70" : check.status === "UNVERIFIABLE" ? "bg-amber-50/40" : ""}>
                      <td className="px-6 py-4 align-top">
                        <p className="text-sm font-medium text-slate-700">{checkField(check)}</p>
                        <p className="mt-0.5 text-[11px] text-slate-400">
                          {check.code} · {checkZone(check)}
                          {bad && ` · ${RISK_LABEL[check.risk]}`}
                        </p>
                        {check.status !== "PASS" && check.detail && (
                          <p className="mt-1 text-[11px] leading-snug text-slate-500">{check.detail}</p>
                        )}
                        <div className="mt-1 flex flex-wrap gap-1">
                          {check.ocr_suspect && (
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">Lecture OCR douteuse</span>
                          )}
                          {review && (
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                review.outcome === "confirmed" ? "bg-rose-100 text-rose-700" : "bg-slate-200 text-slate-600"
                              }`}
                            >
                              {review.outcome === "confirmed" ? "Écart confirmé" : "Écart écarté"}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className={`break-words px-4 py-4 align-top font-mono text-[12px] ${bad ? "font-semibold text-rose-700" : "text-slate-600"}`}>
                        {check.found ?? "—"}
                        <SourceTag source={check.found_source} />
                      </td>
                      <td className={`break-words px-4 py-4 align-top font-mono text-[12px] ${bad ? "font-semibold text-rose-700" : "text-slate-600"}`}>
                        {check.expected ?? "—"}
                        <SourceTag source={check.expected_source} />
                      </td>
                      <td className="px-4 py-4 align-top">
                        <StatusIcon status={check.status} />
                      </td>
                      <td className="px-4 py-4 text-right align-top">
                        <button
                          onClick={() => setPanel({ check })}
                          className={`inline-flex h-8 items-center gap-1.5 rounded-lg border bg-white px-3 text-[11px] font-semibold shadow-sm ${
                            bad ? "border-rose-200 text-rose-700 hover:bg-rose-50" : "border-slate-200 text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <Icon name="eye" size={14} /> Visualiser
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>

        <section className="mt-5 rounded-2xl border border-slate-200 bg-white px-6 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Historique du dossier</h2>
          <ol className="mt-3 space-y-2">
            {t.events.map((e, index) => (
              <li key={index} className="flex items-start gap-3 text-xs">
                <span className="mt-0.5 text-slate-300">
                  <Icon name="clock" size={14} />
                </span>
                <span className="w-32 shrink-0 text-slate-400">{frDateTime(e.at)}</span>
                <span className="font-medium text-slate-700">{EVENT_LABEL[e.action] ?? e.action}</span>
                <span className="text-slate-500">
                  {e.user_name ?? e.user ?? "Analyse automatique"}
                  {e.detail ? ` · ${e.detail}` : ""}
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <div className="fixed bottom-0 left-16 right-0 z-30 border-t border-slate-200 bg-white/95 px-9 py-4 shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between">
          {canAct ? (
            <>
              <div>
                <p className="text-xs font-semibold text-slate-700">
                  {algoOk ? "La facture semble conforme : confirmez-vous ?" : "Confirmez-vous l’erreur détectée ?"}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-400">La décision sera enregistrée dans l’historique.</p>
              </div>
              <div className="flex items-center gap-2.5">
                <button
                  disabled={busy}
                  onClick={release}
                  className="h-10 rounded-lg px-3 text-xs font-semibold text-slate-500 hover:bg-slate-50"
                >
                  Libérer
                </button>
                {!isManager && (
                  <button
                    disabled={busy}
                    onClick={() => setModal("manager")}
                    className="flex h-10 items-center gap-2 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-4 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    <Icon name="message" size={16} /> Demander à un manager
                  </button>
                )}
                <button
                  disabled={busy}
                  onClick={() => setModal("problem")}
                  className="flex h-10 items-center gap-2 rounded-lg bg-rose-600 px-4 text-xs font-semibold text-white shadow-sm hover:bg-rose-700"
                >
                  <Icon name="flag" size={16} /> Contester
                </button>
                <button
                  disabled={busy}
                  onClick={validate}
                  className="flex h-10 items-center gap-2 rounded-lg bg-emerald-600 px-5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
                >
                  <Icon name="check" size={16} /> Valider
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-xs text-slate-500">
                {t.status === "resolved"
                  ? "Ce dossier est clôturé."
                  : t.status === "assigned"
                    ? `Ce dossier est en cours de traitement par ${t.assignee_name ?? t.assignee}.`
                    : canTake
                      ? "Prenez ce dossier pour le traiter."
                      : "Ce dossier attend l’avis d’un manager."}
              </p>
              {canTake && (
                <button
                  disabled={busy || loading}
                  onClick={take}
                  className="flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
                >
                  Prendre ce dossier <Icon name="arrow" size={15} />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {panel && (
        <DocumentPanel
          pair={t.pair}
          check={panel.check}
          review={panel.check ? reviews.get(panel.check.code) : undefined}
          canReview={canAct}
          onReview={reviewCheck}
          onClose={() => setPanel(null)}
        />
      )}
      {modal && (
        <ActionModal
          type={modal}
          onClose={() => setModal(null)}
          onConfirm={confirmModal}
          commentRequired={modal === "problem" ? algoOk : undefined}
          note={
            modal === "problem" && algoOk
              ? "L’analyse automatique n’a relevé aucun écart : expliquez ce que vous avez constaté."
              : undefined
          }
        />
      )}
    </>
  )
}

// ---- page ----------------------------------------------------------------------------------------------

export default function ComparePage({ focusTicketId, onLeaveFocus }: { focusTicketId: number | null; onLeaveFocus: () => void }) {
  const { refresh } = useAuth()
  const [current, setCurrent] = useState<number | null>(focusTicketId)
  const [booting, setBooting] = useState(focusTicketId === null)
  const [claiming, setClaiming] = useState(false)
  const [toastNode, toast] = useToast()

  // an agent coming back to the page resumes the ticket they are working on
  useEffect(() => {
    if (focusTicketId !== null) return
    api
      .tickets({ mine: true, status: "assigned", limit: 1 })
      .then((mine) => mine[0] && setCurrent(mine[0].id))
      .catch(() => undefined)
      .finally(() => setBooting(false))
  }, [focusTicketId])

  const claimNext = async (message?: string) => {
    if (message) toast(message)
    setClaiming(true)
    try {
      const ticket = await api.claimNext()
      setCurrent(ticket.id)
    } catch (e) {
      setCurrent(null)
      if (!(e instanceof ApiError && e.status === 404)) toast(e instanceof Error ? e.message : String(e), "error")
      else if (!message) toast("Aucun dossier en attente")
    } finally {
      setClaiming(false)
      refresh()
    }
  }

  const back = () => {
    setCurrent(null)
    onLeaveFocus()
  }

  if (booting) return <Loading title="Chargement de votre file" subtitle="Recherche de vos dossiers en cours..." />

  return (
    <>
      {current !== null ? (
        <TicketView key={current} ticketId={current} onBack={back} onFinished={(message) => claimNext(message)} toast={toast} />
      ) : claiming ? (
        <Loading title="Attribution du dossier suivant" subtitle="Sélection du dossier le plus prioritaire..." />
      ) : (
        <QueueView onOpen={setCurrent} onClaim={() => claimNext()} claiming={claiming} />
      )}
      {toastNode}
    </>
  )
}
