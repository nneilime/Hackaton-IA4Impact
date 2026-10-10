// French formatting of the backend's values (amounts in cents, ISO dates).

const euroFormat = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" })
const euroRound = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 })

export function euros(cents: number | null | undefined, round = false): string {
  if (cents === null || cents === undefined) return "—"
  return (round ? euroRound : euroFormat).format(cents / 100)
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—"
  return `${value.toFixed(digits).replace(".", ",")} %`
}

export function frDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
}

export function frDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
}

export function plural(count: number, one: string, many: string): string {
  return `${count} ${count > 1 ? many : one}`
}
