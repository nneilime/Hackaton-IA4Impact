// Calls to our server (server.py). The session is an HttpOnly cookie the page never
// sees: same-origin fetches send it. A 401 means it ended (logout elsewhere, expired):
// the auth store goes back to the visitor (see onUnauthorized in auth.ts).

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

let unauthorized: () => void = () => {}

/** Set by auth.ts: what a 401 does (kept here to avoid an import cycle). */
export function onUnauthorized(handler: () => void) {
  unauthorized = handler
}

export async function api<T>(path: string, { method = "GET", body }: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "Le serveur est injoignable. Vérifiez votre connexion, puis réessayez.")
  }
  if (res.ok) return (await res.json()) as T
  let message = "Une erreur est survenue. Réessayez."
  try {
    const detail = (await res.json()).detail
    if (typeof detail === "string") message = detail
  } catch {
    /* not JSON: keep the generic message */
  }
  if (res.status === 401 && path !== "/api/auth/login") unauthorized()
  throw new ApiError(res.status, message)
}
