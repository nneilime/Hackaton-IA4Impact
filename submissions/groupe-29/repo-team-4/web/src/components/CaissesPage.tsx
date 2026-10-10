import { useMemo, useState } from "react"
import { Header, Icon, StatusBadge } from "../App"
import { useClinics } from "../data/clinics"
import { useRegionStats } from "../lib/regionStats"
import { riskTone } from "../lib/risk"

const toneText: Record<"rose" | "amber" | "emerald", string> = {
  rose: "text-rose-600",
  amber: "text-amber-600",
  emerald: "text-emerald-600",
}
const toneIcon: Record<"rose" | "amber" | "emerald", string> = {
  rose: "bg-rose-50 text-rose-600",
  amber: "bg-amber-50 text-amber-600",
  emerald: "bg-emerald-50 text-emerald-600",
}

export default function CaissesPage({
  openClinic,
}: {
  openClinic: (id: number) => void
}) {
  const { clinics } = useClinics()
  const regionStats = useRegionStats(clinics)
  const [expanded, setExpanded] = useState<string | null>(null)

  const activeRegions = regionStats.filter((r) => r.regionClinics.length > 0)
  const distinctCaisses = useMemo(() => {
    const set = new Set<string>()
    regionStats.forEach((r) =>
      r.regionClinics.forEach((c) => set.add(c.caisse)),
    )
    return set.size
  }, [regionStats])
  const totalLoss = regionStats.reduce((sum, r) => sum + r.totalLoss, 0)

  return (
    <>
      <Header
        title="Caisses régionales"
        subtitle="Vue consolidée des caisses rattachées aux cliniques suivies"
      />
      <section className="grid grid-cols-3 gap-4">
        <article className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-[13px] font-medium text-slate-500">
            Caisses régionales actives
          </p>
          <p className="mt-3 text-[26px] font-semibold tracking-[-0.03em] text-slate-950">
            {activeRegions.length}{" "}
            <span className="text-base font-medium text-slate-400">
              / {regionStats.length}
            </span>
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-[13px] font-medium text-slate-500">
            Caisses départementales distinctes
          </p>
          <p className="mt-3 text-[26px] font-semibold tracking-[-0.03em] text-slate-950">
            {distinctCaisses}
          </p>
        </article>
        <article className="rounded-2xl border border-rose-200 bg-rose-50/50 p-5">
          <p className="text-[13px] font-medium text-rose-600">
            Montant non conforme total
          </p>
          <p className="mt-3 text-[26px] font-semibold tracking-[-0.03em] text-rose-700">
            {totalLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
          </p>
        </article>
      </section>

      <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-6 py-5">
          <h2 className="font-semibold text-slate-900">Caisses par région</h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Cliquez sur une caisse régionale pour voir les cliniques
            rattachées
          </p>
        </div>
        <div className="divide-y divide-slate-100">
          {regionStats.map((stats) => {
            const nom = stats.feature.properties.nom
            const isOpen = expanded === nom
            const hasClinics = stats.regionClinics.length > 0
            return (
              <div key={stats.feature.properties.code}>
                <button
                  onClick={() => setExpanded(isOpen ? null : nom)}
                  disabled={!hasClinics}
                  className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-slate-50/70 disabled:cursor-default disabled:hover:bg-transparent"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`grid h-10 w-10 place-items-center rounded-xl ${
                        stats.tone ? toneIcon[stats.tone] : "bg-slate-100 text-slate-400"
                      }`}
                    >
                      <Icon name="bank" size={18} />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">
                        Caisse régionale · {nom}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        {hasClinics
                          ? `${stats.regionClinics.length} clinique(s) · ${stats.flaggedCount} signalée(s)`
                          : "Aucune clinique rattachée"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    {hasClinics && (
                      <>
                        <div className="text-right">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">
                            Taux moyen
                          </p>
                          <p
                            className={`text-sm font-semibold ${stats.tone ? toneText[stats.tone] : "text-slate-600"}`}
                          >
                            {stats.avgErrorRate.toFixed(1).replace(".", ",")} %
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">
                            Non conforme
                          </p>
                          <p className="text-sm font-semibold text-slate-800">
                            {stats.totalLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
                          </p>
                        </div>
                        <span
                          className={`inline-flex text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                        >
                          <Icon name="chevron" size={16} />
                        </span>
                      </>
                    )}
                  </div>
                </button>
                {isOpen && hasClinics && (
                  <div className="divide-y divide-slate-100 bg-slate-50/60 px-6">
                    {stats.regionClinics.map((clinic) => (
                      <button
                        key={clinic.id}
                        onClick={() => openClinic(clinic.id)}
                        className="flex w-full items-center justify-between py-3 text-left"
                      >
                        <div>
                          <p className="text-[13px] font-medium text-slate-700">
                            {clinic.name}
                          </p>
                          <p className="text-[11px] text-slate-400">
                            {clinic.city} · {clinic.caisse}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span
                            className={`text-[12px] font-semibold ${toneText[riskTone(clinic.errorRate)]}`}
                          >
                            {clinic.errorRate.toFixed(1).replace(".", ",")} %
                          </span>
                          <StatusBadge flagged={clinic.errorRate > 15} />
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>
    </>
  )
}
