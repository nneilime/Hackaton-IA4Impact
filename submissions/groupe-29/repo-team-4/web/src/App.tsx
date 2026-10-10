import { ReactNode, useEffect, useState } from "react"
import { AuthProvider, initials, useAuth } from "./auth"
import CaissesPage from "./components/CaissesPage"
import ClinicsPage from "./components/ClinicsPage"
import ComparePage from "./components/ComparePage"
import DashboardPage from "./components/DashboardPage"
import LoginPage from "./components/LoginPage"
import MapPage from "./components/MapPage"

export type Page = "dashboard" | "compare" | "clinics" | "map" | "caisses"
export type IconName = "activity" | "arrow" | "bank" | "building" | "calendar" | "check" | "chevron" | "clock" | "compare" | "download" | "eye" | "file" | "flag" | "help" | "home" | "logout" | "map" | "message" | "refresh" | "search" | "settings" | "sort" | "upload" | "x"

const MANAGER_PAGES: Page[] = ["dashboard", "clinics", "map", "caisses"]

export function Icon({
  name,
  size = 20,
  strokeWidth = 1.8,
}: {
  name: IconName
  size?: number
  strokeWidth?: number
}) {
  const paths: Record<IconName, ReactNode> = {
    home: (
      <>
        <path d="m3 10 9-7 9 7" />
        <path d="M5 9v11h14V9M9 20v-6h6v6" />
      </>
    ),
    compare: (
      <>
        <path d="M7 3 3 7l4 4" />
        <path d="M3 7h12a4 4 0 0 1 4 4v1" />
        <path d="m17 21 4-4-4-4" />
        <path d="M21 17H9a4 4 0 0 1-4-4v-1" />
      </>
    ),
    building: (
      <>
        <path d="M4 21V5l8-3 8 3v16" />
        <path d="M9 21v-4h6v4M8 7h.01M12 7h.01M16 7h.01M8 11h.01M12 11h.01M16 11h.01" />
        <path d="M2 21h20" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.09A1.7 1.7 0 0 0 8.95 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.58 15 1.7 1.7 0 0 0 3.02 14H3v-4h.09A1.7 1.7 0 0 0 4.6 8.95a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.58 1.7 1.7 0 0 0 10 3.02V3h4v.09A1.7 1.7 0 0 0 15.05 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.42 9 1.7 1.7 0 0 0 20.98 10H21v4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    sort: (
      <>
        <path d="M8 7h12M8 12h9M8 17h6M4 5v14m0 0-2-2m2 2 2-2" />
      </>
    ),
    flag: (
      <>
        <path d="M5 22V3M5 4h11l-1 4 1 4H5" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V4m0 0L7 9m5-5 5 5" />
        <path d="M4 15v5h16v-5" />
      </>
    ),
    file: (
      <>
        <path d="M6 2h8l4 4v16H6z" />
        <path d="M14 2v5h5M9 13h6M9 17h6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    x: (
      <>
        <path d="m6 6 12 12M18 6 6 18" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v13m0 0 5-5m-5 5-5-5" />
        <path d="M4 20h16" />
      </>
    ),
    eye: (
      <>
        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
        <circle cx="12" cy="12" r="2.5" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    activity: (
      <>
        <path d="M3 12h4l2-7 4 14 2-7h6" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.8 9a2.4 2.4 0 1 1 3.3 2.22c-.74.33-1.1.78-1.1 1.78M12 17h.01" />
      </>
    ),
    message: (
      <>
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z" />
        <path d="M8 9h8M8 13h5" />
      </>
    ),
    map: (
      <>
        <path d="M12 21s7-6.4 7-11.5A7 7 0 0 0 5 9.5C5 14.6 12 21 12 21Z" />
        <circle cx="12" cy="9.5" r="2.4" />
      </>
    ),
    bank: (
      <>
        <path d="M3 21h18M4 21V10h16v11M2 10l10-6 10 6M6 10v7M10 10v7M14 10v7M18 10v7" />
      </>
    ),
    logout: (
      <>
        <path d="M15 4h4v16h-4" />
        <path d="M10 8l-4 4 4 4M6 12h10" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 11a8 8 0 0 0-14.6-4.5L4 8" />
        <path d="M4 3v5h5M4 13a8 8 0 0 0 14.6 4.5L20 16" />
        <path d="M20 21v-5h-5" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}

function Sidebar({ page, setPage }: { page: Page; setPage: (page: Page) => void }) {
  const { user, logout } = useAuth()
  const isManager = user?.role === "admin"
  const nav = [
    { page: "compare" as Page, label: "Comparaison", icon: "compare" as IconName },
    { page: "dashboard" as Page, label: "Tableau de bord · Manager", icon: "home" as IconName },
    { page: "clinics" as Page, label: "Cliniques · Manager", icon: "building" as IconName },
    { page: "map" as Page, label: "Carte · Manager", icon: "map" as IconName },
    { page: "caisses" as Page, label: "Caisses régionales · Manager", icon: "bank" as IconName },
  ].filter((item) => isManager || !MANAGER_PAGES.includes(item.page))

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-16 flex-col items-center border-r border-slate-200 bg-white py-5">
      <button
        onClick={() => setPage("compare")}
        className="mb-7 grid h-9 w-9 place-items-center rounded-xl bg-blue-600 text-white shadow-sm"
        aria-label="Accueil"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3.3 19.5 7.6v8.8L12 20.7l-7.5-4.3V7.6L12 3.3Z" stroke="currentColor" strokeWidth="1.7" />
          <path d="M8.1 12h7.8M12 8.1v7.8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <nav className="flex flex-col items-center gap-2">
        {nav.map((item, index) => (
          <div key={item.page} className="contents">
            {index === 1 && <span className="my-2 h-px w-6 bg-slate-200" />}
            <button
              onClick={() => setPage(item.page)}
              className={`group relative grid h-10 w-10 place-items-center rounded-xl transition-colors ${
                page === item.page ? "bg-blue-50 text-blue-600" : "text-slate-400 hover:bg-slate-50 hover:text-slate-700"
              }`}
              aria-label={item.label}
            >
              <Icon name={item.icon} />
              <span className="tooltip">{item.label}</span>
            </button>
          </div>
        ))}
      </nav>
      <div className="mt-auto flex flex-col items-center gap-2">
        <button
          onClick={() => logout()}
          className="group relative grid h-10 w-10 place-items-center rounded-xl text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-700"
          aria-label="Se déconnecter"
        >
          <Icon name="logout" />
          <span className="tooltip">Se déconnecter</span>
        </button>
        {user && (
          <div
            className="group relative mt-2 grid h-9 w-9 place-items-center rounded-full bg-slate-900 text-[11px] font-semibold text-white"
            aria-label={user.display_name ?? user.username}
          >
            {initials(user)}
            <span className="tooltip">
              {user.display_name ?? user.username} · {isManager ? "Manager" : "Agent"}
            </span>
          </div>
        )}
      </div>
    </aside>
  )
}

export function Header({ title, subtitle, actions }: { title: string; subtitle: string; actions?: ReactNode }) {
  const { user, logout } = useAuth()
  const [menu, setMenu] = useState(false)
  return (
    <header className="mb-8 flex items-center justify-between">
      <div>
        <h1 className="text-[27px] font-semibold tracking-[-0.035em] text-slate-950">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm sm:flex">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Système opérationnel
        </div>
        {user && (
          <div className="relative">
            <button
              onClick={() => setMenu(!menu)}
              className="grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm hover:bg-slate-50"
              aria-label="Compte"
            >
              <span className="text-[11px] font-semibold">{initials(user)}</span>
            </button>
            {menu && (
              <div className="absolute right-0 top-11 z-50 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-xl">
                <div className="border-b border-slate-100 px-3 pb-2 pt-1">
                  <p className="text-sm font-semibold text-slate-800">{user.display_name ?? user.username}</p>
                  <p className="text-[11px] text-slate-400">
                    @{user.username} · {user.role === "admin" ? "Manager" : "Agent de contrôle"}
                  </p>
                </div>
                <button
                  onClick={() => logout()}
                  className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  <Icon name="logout" size={15} /> Se déconnecter
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}

export function StatusBadge({ ok, flagged }: { ok?: boolean; flagged?: boolean }) {
  const isOk = ok ?? !flagged
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
        isOk ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
      }`}
    >
      {isOk ? (
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
      ) : (
        <Icon name={flagged ? "flag" : "x"} size={13} strokeWidth={2.2} />
      )}
      {flagged ? "Signalée" : isOk ? "Conforme" : "Non conforme"}
    </span>
  )
}

export function Toast({ message, tone = "success" }: { message: string; tone?: "success" | "error" }) {
  return (
    <div className="fixed left-1/2 top-6 z-[60] flex max-w-[560px] -translate-x-1/2 items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-xs font-semibold text-white shadow-xl">
      <span
        className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${tone === "error" ? "bg-rose-500" : "bg-emerald-500"}`}
      >
        <Icon name={tone === "error" ? "x" : "check"} size={12} strokeWidth={2.5} />
      </span>
      {message}
    </div>
  )
}

/** A toast that hides itself; show(message) to display one. */
export function useToast(): [ReactNode, (message: string, tone?: "success" | "error") => void] {
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null)
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), toast.tone === "error" ? 4500 : 2500)
    return () => window.clearTimeout(timer)
  }, [toast])
  return [toast ? <Toast message={toast.message} tone={toast.tone} /> : null, (message, tone = "success") => setToast({ message, tone })]
}

export type ActionModalType = "problem" | "validate" | "manager" | "fraud"

export type ActionReason = { label: string; value: string }

const ACTION_MODAL_CONFIG: Record<
  ActionModalType,
  {
    title: string
    subtitle: string
    reasons: ActionReason[] | null
    commentLabel: string
    commentPlaceholder: string
    commentRequired: boolean
    confirmLabel: string
    confirmClasses: string
  }
> = {
  problem: {
    title: "Contester",
    subtitle: "Confirmez l’écart détecté et précisez son motif.",
    reasons: [
      { label: "Écart de montant", value: "billing_error" },
      { label: "Code acte incorrect", value: "billing_error" },
      { label: "Identifiant incohérent (FINESS, lot, facture, assuré)", value: "billing_error" },
      { label: "Signature manquante", value: "billing_error" },
      { label: "Suspicion de fraude", value: "suspected_fraud" },
    ],
    commentLabel: "Commentaire (facultatif)",
    commentPlaceholder: "Ajoutez des précisions pour le suivi...",
    commentRequired: false,
    confirmLabel: "Contester",
    confirmClasses: "bg-rose-600 hover:bg-rose-700",
  },
  validate: {
    title: "Valider malgré les écarts",
    subtitle: "L’analyse automatique a relevé des écarts : indiquez pourquoi la facture est conforme.",
    reasons: [
      { label: "Écart dû à une erreur de lecture (OCR)", value: "ocr_error" },
      { label: "Écart justifié, sans incidence", value: "none" },
    ],
    commentLabel: "Justification",
    commentPlaceholder: "Ce que vous avez vérifié sur le bordereau...",
    commentRequired: true,
    confirmLabel: "Valider la facture",
    confirmClasses: "bg-emerald-600 hover:bg-emerald-700",
  },
  manager: {
    title: "Demander à un manager",
    subtitle: "Le dossier sera transmis aux managers avec votre question.",
    reasons: null,
    commentLabel: "Commentaire",
    commentPlaceholder: "Expliquez votre demande...",
    commentRequired: true,
    confirmLabel: "Envoyer la demande",
    confirmClasses: "bg-blue-600 hover:bg-blue-700",
  },
  fraud: {
    title: "Signaler au contrôle de fraude",
    subtitle: "Transmettez ce dossier au service de contrôle de fraude pour investigation.",
    reasons: [
      { label: "Facturation d’actes fictifs", value: "Facturation d’actes fictifs" },
      { label: "Surfacturation systématique", value: "Surfacturation systématique" },
      { label: "Falsification de documents", value: "Falsification de documents" },
      { label: "Pratique tarifaire anormale", value: "Pratique tarifaire anormale" },
      { label: "Autre comportement suspect", value: "Autre comportement suspect" },
    ],
    commentLabel: "Commentaire (contexte pour l’enquête)",
    commentPlaceholder: "Décrivez les éléments qui motivent ce signalement...",
    commentRequired: true,
    confirmLabel: "Signaler",
    confirmClasses: "bg-rose-700 hover:bg-rose-800",
  },
}

export function ActionModal({
  type,
  onClose,
  onConfirm,
  commentRequired,
  note,
}: {
  type: ActionModalType
  onClose: () => void
  onConfirm: (reason: ActionReason | null, comment: string) => Promise<void> | void
  commentRequired?: boolean
  note?: string
}) {
  const config = ACTION_MODAL_CONFIG[type]
  const [reasonIndex, setReasonIndex] = useState(0)
  const [comment, setComment] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const required = commentRequired ?? config.commentRequired

  const confirm = async () => {
    setBusy(true)
    setError("")
    try {
      await onConfirm(config.reasons?.[reasonIndex] ?? null, comment.trim())
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
            <h2 className="text-lg font-semibold text-slate-900">{config.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{config.subtitle}</p>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
            aria-label="Fermer"
          >
            <Icon name="x" size={17} />
          </button>
        </div>
        {type === "fraud" && (
          <div className="mt-5 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs text-rose-700">
            <Icon name="flag" size={14} strokeWidth={2.2} />
            Cette action transmet immédiatement le dossier au service de contrôle de fraude.
          </div>
        )}
        {note && (
          <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">{note}</div>
        )}
        {config.reasons && (
          <label className="mt-6 block text-xs font-semibold text-slate-700">
            Motif
            <select
              value={reasonIndex}
              onChange={(event) => setReasonIndex(Number(event.target.value))}
              className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-normal text-slate-700 outline-none focus:border-blue-400"
            >
              {config.reasons.map((item, index) => (
                <option key={item.label} value={index}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="mt-5 block text-xs font-semibold text-slate-700">
          {required ? config.commentLabel.replace(" (facultatif)", "") : config.commentLabel}
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            rows={4}
            placeholder={config.commentPlaceholder}
            className="mt-2 w-full resize-none rounded-lg border border-slate-200 p-3 text-sm font-normal text-slate-700 outline-none placeholder:text-slate-400 focus:border-blue-400"
          />
        </label>
        {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="h-10 rounded-lg border border-slate-200 px-4 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            Annuler
          </button>
          <button
            disabled={busy || (required && !comment.trim())}
            onClick={confirm}
            className={`h-10 rounded-lg px-4 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 ${config.confirmClasses}`}
          >
            {busy ? "Envoi..." : config.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

function Shell() {
  const { user } = useAuth()
  const [page, setPage] = useState<Page>("compare")
  const [selectedClinic, setSelectedClinic] = useState<number | null>(null)
  const [focusTicket, setFocusTicket] = useState<number | null>(null)
  const isManager = user?.role === "admin"

  // an agent never lands on a manager page (e.g. after switching accounts)
  useEffect(() => {
    if (!isManager && MANAGER_PAGES.includes(page)) setPage("compare")
  }, [isManager, page])

  const openClinic = (id: number) => {
    setSelectedClinic(id)
    setPage("clinics")
  }
  const openTicket = (id: number) => {
    setFocusTicket(id)
    setPage("compare")
  }
  const navigate = (next: Page) => {
    if (next === "compare") setFocusTicket(null)
    setPage(next)
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <Sidebar page={page} setPage={navigate} />
      <div className="ml-16 min-h-screen">
        <main className="mx-auto max-w-[1320px] px-9 py-7">
          {page === "compare" && (
            <ComparePage key={focusTicket ?? "queue"} focusTicketId={focusTicket} onLeaveFocus={() => setFocusTicket(null)} />
          )}
          {isManager && page === "dashboard" && <DashboardPage openClinic={openClinic} openTicket={openTicket} />}
          {isManager && page === "map" && <MapPage openClinic={openClinic} />}
          {isManager && page === "caisses" && <CaissesPage openClinic={openClinic} />}
          {isManager && page === "clinics" && (
            <ClinicsPage selectedId={selectedClinic} setSelectedId={setSelectedClinic} openTicket={openTicket} />
          )}
        </main>
      </div>
    </div>
  )
}

function Gate() {
  const { user, checking } = useAuth()
  if (checking) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f8fafc]">
        <div className="h-1 w-44 overflow-hidden rounded-full bg-slate-200">
          <span className="loading-bar block h-full rounded-full bg-blue-600" />
        </div>
      </div>
    )
  }
  return user ? <Shell /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
