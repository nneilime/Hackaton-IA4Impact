import { useState } from "react"
import { Header, Icon, StatusBadge } from "../App"
import { useClinics, type Clinic } from "../data/clinics"
import { useRegionStats } from "../lib/regionStats"
import { riskLabel, riskTone, type RiskTone } from "../lib/risk"
import { FranceMap } from "./FranceMap"

const toneStyles: Record<RiskTone, { text: string; bg: string }> = {
  rose: { text: "text-rose-700", bg: "bg-rose-50" },
  amber: { text: "text-amber-700", bg: "bg-amber-50" },
  emerald: { text: "text-emerald-700", bg: "bg-emerald-50" },
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-4 text-[11px] font-medium text-slate-500">
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-emerald-300" /> Faible (≤ 10
        %)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-amber-300" /> Modéré (10–15
        %)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-rose-300" /> Élevé (&gt; 15
        %)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-slate-200" /> Aucune clinique
      </span>
    </div>
  )
}

function ClinicPreview({
  clinic,
  onClose,
  onOpenFile,
}: {
  clinic: Clinic
  onClose: () => void
  onOpenFile: () => void
}) {
  const tone = riskTone(clinic.errorRate)
  const styles = toneStyles[tone]
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/30 p-6 backdrop-blur-[2px]">
      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`grid h-11 w-11 place-items-center rounded-xl ${styles.bg} ${styles.text}`}
            >
              <Icon name="building" size={20} />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                {clinic.name}
              </h3>
              <p className="text-[11px] text-slate-400">
                {clinic.city} · FINESS {clinic.finess}
              </p>
              <p className="text-[11px] text-slate-400">{clinic.caisse}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
            aria-label="Fermer"
          >
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="mt-4">
          <StatusBadge flagged={clinic.errorRate > 15} />
        </div>
        <p className={`mt-2 text-xs font-medium ${styles.text}`}>
          {riskLabel(clinic.errorRate)}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Taux d’erreur
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {clinic.errorRate.toFixed(1).replace(".", ",")} %
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Montant non conforme
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {clinic.financialLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Factures contrôlées
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {clinic.invoices}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Factures non conformes
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {clinic.issues}
            </p>
          </div>
        </div>
        <button
          onClick={onOpenFile}
          className="mt-5 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-slate-900 text-xs font-semibold text-white hover:bg-slate-800"
        >
          <Icon name="eye" size={15} /> Ouvrir le dossier complet
        </button>
      </div>
    </div>
  )
}

export default function MapPage({
  openClinic,
}: {
  openClinic: (id: number) => void
}) {
  const { clinics, error } = useClinics()
  const regionStats = useRegionStats(clinics)
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [previewClinicId, setPreviewClinicId] = useState<number | null>(null)

  const selectedStats = selectedRegion
    ? (regionStats.find((r) => r.feature.properties.nom === selectedRegion) ??
      null)
    : null
  const previewClinic = previewClinicId
    ? (clinics.find((c) => c.id === previewClinicId) ?? null)
    : null

  return (
    <>
      <Header
        title="Carte des cliniques"
        subtitle="Repérez en un coup d’œil les régions et cliniques à risque"
      />

      {error && (
        <p className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">{error}</p>
      )}
      <div className="mb-4 flex items-center gap-2 text-sm">
        <button
          onClick={() => setSelectedRegion(null)}
          className={`font-medium ${
            selectedRegion
              ? "text-blue-600 hover:underline"
              : "cursor-default text-slate-800"
          }`}
        >
          France
        </button>
        {selectedRegion && (
          <>
            <Icon name="chevron" size={14} />
            <span className="font-semibold text-slate-800">
              {selectedRegion}
            </span>
            <button
              onClick={() => setSelectedRegion(null)}
              className="ml-3 flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              <span className="inline-flex rotate-180">
                <Icon name="arrow" size={13} strokeWidth={2.2} />
              </span>
              Retour à la carte de France
            </button>
          </>
        )}
      </div>

      <div className="grid grid-cols-[1fr_360px] gap-5">
        <section className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900">
                {selectedRegion ?? "France métropolitaine"}
              </h2>
              <p className="mt-0.5 text-xs text-slate-400">
                {selectedRegion
                  ? "Cliquez sur une clinique pour afficher son aperçu"
                  : "Survolez puis cliquez sur une région pour l’explorer"}
              </p>
            </div>
            {!selectedRegion && <Legend />}
          </div>
          <div className="relative z-0 h-[560px] w-full overflow-hidden rounded-xl">
            <FranceMap
              regionStats={regionStats}
              selectedRegion={selectedRegion}
              hoveredRegion={hoveredRegion}
              onHoverRegion={setHoveredRegion}
              onSelectRegion={setSelectedRegion}
              onSelectClinic={setPreviewClinicId}
            />
          </div>
        </section>

        <section className="flex flex-col gap-4">
          {selectedStats ? (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Cliniques · {selectedStats.feature.properties.nom}
                </h3>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  {selectedStats.regionClinics.length} clinique(s) ·{" "}
                  {selectedStats.flaggedCount} signalée(s)
                </p>
              </div>
              <div className="max-h-[480px] divide-y divide-slate-100 overflow-y-auto">
                {selectedStats.regionClinics.length === 0 && (
                  <p className="px-4 py-6 text-center text-xs text-slate-400">
                    Aucune clinique dans cette région.
                  </p>
                )}
                {selectedStats.regionClinics.map((clinic) => (
                  <button
                    key={clinic.id}
                    onClick={() => setPreviewClinicId(clinic.id)}
                    className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-slate-50"
                  >
                    <div>
                      <p className="text-[12px] font-semibold text-slate-800">
                        {clinic.name}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {clinic.city} ·{" "}
                        {clinic.financialLoss.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} €
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[12px] font-semibold ${
                          riskTone(clinic.errorRate) === "rose"
                            ? "text-rose-600"
                            : riskTone(clinic.errorRate) === "amber"
                              ? "text-amber-600"
                              : "text-emerald-600"
                        }`}
                      >
                        {clinic.errorRate.toFixed(1).replace(".", ",")} %
                      </span>
                      <StatusBadge flagged={clinic.errorRate > 15} />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900">
                Vue nationale
              </h3>
              <p className="mt-2 text-xs text-slate-400">
                Survolez une région pour voir ses indicateurs, ou cliquez pour
                l’explorer en détail.
              </p>
              <div className="mt-4 space-y-2">
                {[...regionStats]
                  .filter((r) => r.regionClinics.length > 0)
                  .sort((a, b) => b.avgErrorRate - a.avgErrorRate)
                  .slice(0, 5)
                  .map((stats) => (
                    <button
                      key={stats.feature.properties.code}
                      onClick={() =>
                        setSelectedRegion(stats.feature.properties.nom)
                      }
                      className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition-colors hover:bg-slate-50"
                    >
                      <span className="font-medium text-slate-700">
                        {stats.feature.properties.nom}
                      </span>
                      <span
                        className={`font-semibold ${
                          stats.tone === "rose"
                            ? "text-rose-600"
                            : stats.tone === "amber"
                              ? "text-amber-600"
                              : "text-emerald-600"
                        }`}
                      >
                        {stats.avgErrorRate.toFixed(1).replace(".", ",")} %
                      </span>
                    </button>
                  ))}
              </div>
            </div>
          )}
        </section>
      </div>

      {previewClinic && (
        <ClinicPreview
          clinic={previewClinic}
          onClose={() => setPreviewClinicId(null)}
          onOpenFile={() => openClinic(previewClinic.id)}
        />
      )}
    </>
  )
}
