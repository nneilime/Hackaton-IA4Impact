import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react"
import { api, hasToken, setToken, setUnauthorizedHandler } from "./api/client"
import type { Me } from "./api/types"

type AuthState = {
  user: Me | null
  checking: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [checking, setChecking] = useState(hasToken())

  const refresh = useCallback(async () => {
    if (!hasToken()) {
      setUser(null)
      return
    }
    try {
      setUser(await api.me())
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    refresh().finally(() => setChecking(false))
    return () => setUnauthorizedHandler(null)
  }, [refresh])

  const login = useCallback(
    async (username: string, password: string) => {
      const { token } = await api.login(username, password)
      setToken(token)
      await refresh()
    },
    [refresh],
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setToken(null)
      setUser(null)
    }
  }, [])

  return <AuthContext.Provider value={{ user, checking, login, logout, refresh }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth outside AuthProvider")
  return value
}

export function initials(user: { display_name: string | null; username: string }): string {
  const source = user.display_name || user.username
  const parts = source.split(/[\s._-]+/).filter((p) => p.length > 2 || /^[A-Z]/.test(p))
  const last = parts.length > 1 ? parts[parts.length - 1][0] : (parts[0]?.[1] ?? "")
  return ((parts[0]?.[0] ?? "") + last).toUpperCase()
}
