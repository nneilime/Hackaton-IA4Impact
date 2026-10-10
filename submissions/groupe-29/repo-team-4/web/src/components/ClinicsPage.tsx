import { useEffect, useMemo, useState } from "react"
import { ActionModal, Header, Icon, StatusBadge, useToast } from "../App"
import { api } from "../api/client"
import type { ClinicDetail } from "../api/types"
import { useClinics } from "../data/clinics"
import { franceRegions } from "../data/franceRegions"
import { CATEGORY_LABEL } from "../lib/checks"
import { euros, frDate, frDateTime, percent } from "../lib/format"
import { FLAG_THRESHOLD } from "../lib/risk"
import { useApi } from "../lib/useApi"

const STATUS_LABEL = { open: "En attente", assigned: "En cours", resolved: "Clôturé" } as const

function EditClinicModal({ clinic, onClose, onSaved }: { clinic: ClinicDetail; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: clinic.name ?? "",
    city: clinic.city ?? "",
    postal_code: clinic.postal_code ?? "",
    region: clinic.region ?? "",
    caisse: clinic.caisse ?? "",
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const field = (key: keyof typeof form, label: string) => (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <input
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="mt-1.5 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm font-normal text-slate-700 outline-none focus:border-blue-400"
      />
    </label>
  )
  const save = async () => {
    setBusy(true)
    setError("")
    try {
      await api.updateClinic(clinic.id, Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null])))
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/30 p-6 backdrop-blur-[2px]">
      <div className="w-full max-w-[500px] rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Gérer la clinique</h2>
            <p className="mt-1 text-sm text-slate-500">FINESS {clinic.finess} · corrigez les informations lues sur les documents.</p>
          </div>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100" aria-label="Fermer">
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-4">
          <div className="col-span-2">{field("name", "Nom")}</div>
          {field("postal_code", "Code postal")}
          {field("city", "Ville")}
          <label className="block text-xs font-semibold text-slate-700">
            Région
            <select
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
              className="mt-1.5 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-normal text-slate-700 outline-none focus:border-blue-400"
            >
              <option value="">—</option>
              {franceRegions.features.map((f) => (
                <option key={f.properties.code}>{f.properties.nom}</option>
              ))}
            </select>
          </label>
          {field("caisse", "Caisse de rattachement")}
        </div>
        {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="h-10 rounded-lg border border-slate-200 px-4 text-xs font-semibold text-slate-600 hover:bg-slate-50">
            Annuler
          </button>
          <button
            disabled={busy}
            onClick={save}
            className="h-10 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
          >
            {busy ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ClinicsPage({
  selectedId,
  setSelectedId,
  openTicket,
}: {
  selectedId: number | null
  setSelectedId: (id: number) => void
  openTicket: (id: number) => void
}) {
  const { clinics, reload: reloadClinics, error } = useClinics()
  const [search, setSearch] = useState("")
  const [tab, setTab] = useState<"all" | "ok" | "not-ok">("all")
  const [reportOpen, setReportOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [toastNode, toast] = useToast()

  const selectedIdOrFirst = selectedId ?? clinics[0]?.id ?? null
  useEffect(() => {
    if (selectedId === null && clinics[0]) setSelectedId(clinics[0].id)
  }, [selectedId, clinics, setSelectedId])

  const detail = useApi(() => (selectedIdOrFirst ? api.clinic(selectedIdOrFirst) : Promise.resolve(null)), [selectedIdOrFirst])
  const invoicesState = useApi(
    () => (selectedIdOrFirst ? api.clinicInvoices(selectedIdOrFirst) : Promise.resolve([])),
    [selectedIdOrFirst],
  )
  const selected = detail.data
  const invoices = (invoicesState.data ?? []).filter(
    (row) => tab === "all" || (tab === "ok" ? row.verdict === "CORRECT" : row.verdict === "ISSUES"),
  )
  const listed = useMemo(
    () => clinics.filter((c) => `${c.name} ${c.city} ${c.finess}`.toLowerCase().includes(search.toLowerCase())),
    [clinics, search],
  )

  const reportFraud = async (reason: { value: string } | null, comment: string) => {
    if (!selected) return
    await api.reportClinic(selected.id, reason?.value ?? "Autre comportement suspect", comment)
    setReportOpen(false)
    toast(`Signalement transmis pour ${selected.name}`)
    detail.reload()
    reloadClinics()
  }

  return (
    <>
      <Header title="Cliniques" subtitle="Consultez les performances et l’historique de facturation" />
      {error && <p className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">{error}</p>}
      <div className="grid h-[calc(100vh-145px)] min-h-[590px] grid-cols-[290px_1fr] overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <aside className="flex min-h-0 flex-col border-r border-slate-200">
          <div className="border-b border-slate-200 p-4">
            <label className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-slate-400 focus-within:border-blue-400">
              <Icon name="search" size={15} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher une clinique"
                className="w-full bg-transparent text-xs text-slate-700 outline-none"
              />
            </label>
          </div>
          <div className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto">
            {listed.map((clinic) => (
              <button
                key={clinic.id}
                onClick={() => setSelectedId(clinic.id)}
                className={`w-full border-l-2 px-4 py-3.5 text-left transition-colors ${
                  selectedIdOrFirst === clinic.id ? "border-blue-600 bg-blue-50/60" : "border-transparent hover:bg-slate-50"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className={`text-[13px] font-semibold ${selectedIdOrFirst === clinic.id ? "text-blue-900" : "text-slate-700"}`}>
                      {clinic.name}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-400">
                      {clinic.city} · {clinic.invoices} factures
                    </p>
                  </div>
                  {clinic.errorRate > FLAG_THRESHOLD && (
                    <span className="mt-0.5 text-rose-500">
                      <Icon name="flag" size={14} />
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </aside>
        <main className="min-w-0 overflow-y-auto p-6">
          {!selected ? (
            <p className="text-xs text-slate-400">{detail.loading ? "Chargement…" : "Aucune clinique."}</p>
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <span className="grid h-12 w-12 place-items-center rounded-xl bg-blue-50 text-blue-600">
                    <Icon name="building" size={23} />
                  </span>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-xl font-semibold tracking-tight text-slate-900">{selected.name}</h2>
                      {selected.flagged && <StatusBadge flagged />}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">
                      {selected.postal_code} {selected.city} · FINESS {selected.finess} · {selected.caisse ?? "caisse inconnue"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Montant non conforme</p>
                    <p className="mt-1 text-base font-semibold text-rose-600">{euros(selected.at_risk)}</p>
                  </div>
                  <button
                    onClick={() => setReportOpen(true)}
                    className="flex h-9 items-center gap-2 rounded-lg bg-rose-600 px-3 text-xs font-semibold text-white shadow-sm hover:bg-rose-700"
                  >
                    <Icon name="flag" size={15} /> Signaler
                  </button>
                  <button
                    onClick={() => setEditOpen(true)}
                    className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50"
                  >
                    <Icon name="settings" size={15} /> Gérer
                  </button>
                </div>
              </div>
              <div className="my-6 grid grid-cols-4 gap-3">
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Taux de non-conformité</p>
                  <p className={`mt-2 text-2xl font-semibold ${selected.flagged ? "text-rose-600" : "text-emerald-600"}`}>
                    {percent(selected.error_rate)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Factures contrôlées</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{selected.invoices}</p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Non conformes</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{selected.issues}</p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Signalements</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{selected.reports}</p>
                </div>
              </div>
              {selected.reports_list.length > 0 && (
                <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50/50 px-4 py-3">
                  <p className="text-xs font-semibold text-rose-800">Derniers signalements au contrôle de fraude</p>
                  <ul className="mt-2 space-y-1">
                    {selected.reports_list.slice(0, 3).map((r) => (
                      <li key={r.id} className="text-[11px] text-rose-700">
                        {frDateTime(r.at)} · {r.reason} · {r.user_name ?? r.user}
                        {r.comment ? ` — ${r.comment}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mb-4 flex items-center justify-between">
                <div className="flex rounded-lg bg-slate-100 p-1">
                  {[
                    { key: "all", label: "Toutes" },
                    { key: "ok", label: "Conformes" },
                    { key: "not-ok", label: "Non conformes" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      onClick={() => setTab(item.key as typeof tab)}
                      className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                        tab === item.key ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-400">{invoices.length} factures affichées</p>
              </div>
              <div className="overflow-hidden rounded-xl border border-slate-200">
                <table className="w-full table-fixed">
                  <thead>
                    <tr className="bg-slate-50/70 text-left text-[10px] font-semibold uppercase tracking-[0.06em] text-slate-400">
                      <th className="w-[17%] px-4 py-3">N° facture</th>
                      <th className="w-[13%] px-4 py-3">Date</th>
                      <th className="w-[14%] px-4 py-3">Montant</th>
                      <th className="w-[9%] px-4 py-3">Écarts</th>
                      <th className="w-[14%] px-4 py-3">Montant en écart</th>
                      <th className="w-[15%] px-4 py-3">Dossier</th>
                      <th className="px-4 py-3">Statut</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {invoices.map((invoice) => (
                      <tr
                        key={invoice.pair_id}
                        onClick={() => openTicket(invoice.ticket_id)}
                        className="cursor-pointer text-xs transition-colors hover:bg-blue-50/40"
                      >
                        <td className="px-4 py-3.5">
                          <p className="font-semibold text-blue-600">{invoice.numero_facture ?? "—"}</p>
                          <p className="text-[10px] text-slate-400">{invoice.name}</p>
                        </td>
                        <td className="px-4 py-3.5 text-slate-500">{frDate(invoice.date_fichier)}</td>
                        <td className="px-4 py-3.5 font-medium text-slate-700">{euros(invoice.amount)}</td>
                        <td className={`px-4 py-3.5 font-medium ${invoice.failed_checks ? "text-rose-600" : "text-slate-400"}`}>
                          {invoice.failed_checks}
                        </td>
                        <td className={`px-4 py-3.5 font-semibold ${invoice.discrepancy ? "text-rose-600" : "text-slate-400"}`}>
                          {euros(invoice.discrepancy)}
                        </td>
                        <td className="px-4 py-3.5 text-slate-500">
                          {STATUS_LABEL[invoice.ticket_status]}
                          {invoice.final_category && invoice.final_category !== "none" && (
                            <p className="text-[10px] text-slate-400">{CATEGORY_LABEL[invoice.final_category]}</p>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusBadge ok={invoice.verdict === "CORRECT"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </main>
      </div>
      {reportOpen && <ActionModal type="fraud" onClose={() => setReportOpen(false)} onConfirm={reportFraud} />}
      {editOpen && selected && (
        <EditClinicModal
          clinic={selected}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false)
            toast("Clinique mise à jour")
            detail.reload()
            reloadClinics()
          }}
        />
      )}
      {toastNode}
    </>
  )
}
