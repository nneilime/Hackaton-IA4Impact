import { useMemo, useState } from "react"
import { Header, Icon, IconName, StatusBadge } from "../App"
import { api } from "../api/client"
import { useClinics } from "../data/clinics"
import { CHECK_INFO } from "../lib/checks"
import { euros, percent, plural } from "../lib/format"
import { FLAG_THRESHOLD } from "../lib/risk"
import { useApi } from "../lib/useApi"

export default function DashboardPage({
  openClinic,
  openTicket,
}: {
  openClinic: (id: number) => void
  openTicket: (id: number) => void
}) {
  const { data: overview, error } = useApi(() => api.overview(), [])
  const escalated = useApi(() => api.tickets({ status: "open", escalated: true, limit: 6 }), [])
  const { clinics } = useClinics()
  const [search, setSearch] = useState("")
  const [descending, setDescending] = useState(true)
  const [sortKey, setSortKey] = useState<"errorRate" | "financialLoss">("errorRate")

  const visibleClinics = useMemo(
    () =>
      clinics
        .filter((clinic) => `${clinic.name} ${clinic.city} ${clinic.finess}`.toLowerCase().includes(search.toLowerCase()))
        .sort((a, b) => (descending ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey])),
    [clinics, search, descending, sortKey],
  )

  const o = overview
  const kpis: { label: string; value: string; note: string; icon: IconName; tone: "blue" | "green" | "red" }[] = [
    {
      label: "Cliniques suivies",
      value: o ? String(o.clinics) : "—",
      note: o ? `${plural(o.flagged_clinics, "signalée", "signalées")} (seuil > ${FLAG_THRESHOLD} %)` : "",
      icon: "building",
      tone: "blue",
    },
    {
      label: "Factures contrôlées",
      value: o ? String(o.invoices) : "—",
      note: o ? `${o.resolved} clôturées · ${o.pending} en attente` : "",
      icon: "file",
      tone: "blue",
    },
    {
      label: "Taux de non-conformité",
      value: o ? percent(o.error_rate) : "—",
      note: o ? `${o.issues} factures non conformes` : "",
      icon: "activity",
      tone: "red",
    },
    {
      label: "Montant non conforme",
      value: o ? euros(o.at_risk, true) : "—",
      note: o ? `sur ${euros(o.billed, true)} facturés` : "",
      icon: "activity",
      tone: "red",
    },
    {
      label: "Fraudes confirmées",
      value: o ? String(o.confirmed_fraud) : "—",
      note: o ? `${euros(o.confirmed_fraud_amount, true)} · ${plural(o.reports, "signalement", "signalements")}` : "",
      icon: "flag",
      tone: "red",
    },
    {
      label: "Accord agents / analyse",
      value: o?.agreement_rate === null || !o ? "—" : percent(o.agreement_rate),
      note: o ? (o.escalated ? `${plural(o.escalated, "demande d’avis", "demandes d’avis")} en attente` : "Aucune demande d’avis") : "",
      icon: "check",
      tone: "green",
    },
  ]

  return (
    <>
      <Header title="Tableau de bord" subtitle="Vue d’ensemble des contrôles de facturation" />
      {error && <p className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">{error}</p>}
      <section className="grid grid-cols-3 gap-4">
        {kpis.map((kpi) => (
          <article key={kpi.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.02)]">
            <div className="flex items-start justify-between">
              <p className="text-[13px] font-medium text-slate-500">{kpi.label}</p>
              <span
                className={`grid h-9 w-9 place-items-center rounded-xl ${
                  kpi.tone === "red" ? "bg-rose-50 text-rose-600" : kpi.tone === "green" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"
                }`}
              >
                <Icon name={kpi.icon} size={18} />
              </span>
            </div>
            <p className="mt-4 text-[28px] font-semibold tracking-[-0.04em] text-slate-950">{kpi.value}</p>
            <p className={`mt-1 text-xs ${kpi.tone === "green" ? "font-medium text-emerald-600" : "text-slate-400"}`}>{kpi.note}</p>
          </article>
        ))}
      </section>

      <section className="mt-6 grid grid-cols-2 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-sm font-semibold text-slate-900">Demandes d’avis des agents</h2>
            <p className="mt-0.5 text-xs text-slate-400">Dossiers transmis aux managers</p>
          </div>
          {(escalated.data ?? []).length === 0 ? (
            <p className="px-6 py-6 text-center text-xs text-slate-400">Aucune demande en attente.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {escalated.data!.map((t) => (
                <li key={t.id}>
                  <button onClick={() => openTicket(t.id)} className="flex w-full items-center justify-between px-6 py-3 text-left hover:bg-slate-50">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-slate-800">
                        {t.pair_name} · {t.clinic_name}
                      </p>
                      <p className="truncate text-[11px] text-amber-700">{t.escalation_comment}</p>
                    </div>
                    <Icon name="chevron" size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-sm font-semibold text-slate-900">Anomalies les plus fréquentes</h2>
            <p className="mt-0.5 text-xs text-slate-400">Contrôles en échec sur l’ensemble des factures</p>
          </div>
          <ul className="space-y-2.5 px-6 py-4">
            {(o?.top_failed_checks ?? []).map((c) => {
              const max = o!.top_failed_checks[0]?.count || 1
              return (
                <li key={c.code} className="text-xs">
                  <div className="flex justify-between">
                    <span className="font-medium text-slate-700">
                      {CHECK_INFO[c.code]?.field ?? c.label} <span className="text-slate-400">· {c.code}</span>
                    </span>
                    <span className="font-semibold text-slate-600">{c.count}</span>
                  </div>
                  <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <span className="block h-full rounded-full bg-rose-400" style={{ width: `${(c.count / max) * 100}%` }} />
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      </section>

      <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="font-semibold text-slate-900">Suivi des cliniques</h2>
            <p className="mt-0.5 text-xs text-slate-400">Taux de non-conformité : décision de l’agent, sinon analyse automatique</p>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex h-9 w-56 items-center gap-2 rounded-lg border border-slate-200 px-3 text-slate-400 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-50">
              <Icon name="search" size={16} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher..."
                className="w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
              />
            </label>
            {(
              [
                ["errorRate", "Taux"],
                ["financialLoss", "Montant"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => {
                  if (sortKey === key) setDescending(!descending)
                  else {
                    setSortKey(key)
                    setDescending(true)
                  }
                }}
                className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-medium hover:bg-slate-50 ${
                  sortKey === key ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600"
                }`}
              >
                <Icon name="sort" size={16} />
                {label}
              </button>
            ))}
          </div>
        </div>
        <table className="w-full table-fixed">
          <thead>
            <tr className="bg-slate-50/70 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-400">
              <th className="w-[27%] px-6 py-3">Clinique</th>
              <th className="w-[13%] px-4 py-3">Ville</th>
              <th className="w-[10%] px-4 py-3">Factures</th>
              <th className="w-[10%] px-4 py-3">En attente</th>
              <th className="w-[15%] px-4 py-3">Montant non conforme</th>
              <th className="w-[15%] px-4 py-3">Taux</th>
              <th className="px-4 py-3">Statut</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visibleClinics.map((clinic) => (
              <tr key={clinic.id} onClick={() => openClinic(clinic.id)} className="group cursor-pointer text-sm transition-colors hover:bg-blue-50/40">
                <td className="px-6 py-3.5 font-medium text-slate-800">
                  <div className="flex items-center gap-3">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-500">
                      <Icon name="building" size={15} />
                    </span>
                    <span className="truncate">{clinic.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-slate-500">{clinic.city}</td>
                <td className="px-4 py-3.5 text-slate-600">{clinic.invoices}</td>
                <td className="px-4 py-3.5 text-slate-600">{clinic.pending}</td>
                <td className="px-4 py-3.5 font-semibold text-slate-700">
                  {clinic.financialLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <span className={`w-14 font-semibold ${clinic.errorRate > FLAG_THRESHOLD ? "text-rose-600" : "text-slate-700"}`}>
                      {percent(clinic.errorRate)}
                    </span>
                    <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                      <span
                        className={`block h-full rounded-full ${
                          clinic.errorRate > FLAG_THRESHOLD ? "bg-rose-500" : clinic.errorRate > 10 ? "bg-amber-400" : "bg-emerald-500"
                        }`}
                        style={{ width: `${Math.min(clinic.errorRate, 100)}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <StatusBadge flagged={clinic.errorRate > FLAG_THRESHOLD} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
