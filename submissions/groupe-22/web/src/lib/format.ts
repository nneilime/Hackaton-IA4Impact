// Formatting helpers. The customer's amounts are in cents; the tools' (bank_tools.py)
// are in euros.

const eur = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" })

/** 124580 -> "1 245,80 €" (French grouping uses a narrow no-break space). */
export function formatEUR(cents: number): string {
  return eur.format(cents / 100)
}

/** Signed variant for transaction lists: "+1 850,00 €" / "-42,50 €". */
export function formatSignedEUR(cents: number): string {
  const s = formatEUR(Math.abs(cents))
  return cents > 0 ? `+${s}` : cents < 0 ? `-${s}` : s
}

const dateFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" })
const shortDateFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" })

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso))
}

export function formatShortDate(iso: string): string {
  return shortDateFmt.format(new Date(iso))
}

/** "Aujourd'hui", "Hier" or "mercredi 8 octobre": used to group transactions. */
export function formatDayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso)
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((day(now) - day(d)) / 86_400_000)
  if (diff === 0) return "Aujourd'hui"
  if (diff === 1) return "Hier"
  return new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" }).format(d)
}

/** 10000 -> "10 000 €", 229.36 -> "229,36 €". */
export function euros(amount: number): string {
  const cents = Math.round(amount * 100) % 100 !== 0
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  }).format(amount)
}

/** 4.9 -> "4,9 %". */
export function percent(value: number): string {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(value)} %`
}

/** 48 -> "48 mois (4 ans)". */
export function duration(months: number): string {
  if (months % 12) return `${months} mois`
  const years = months / 12
  return `${months} mois (${years} an${years > 1 ? "s" : ""})`
}
