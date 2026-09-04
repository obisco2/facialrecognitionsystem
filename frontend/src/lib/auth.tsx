import { createContext, useContext, useState, useCallback } from 'react'
import type { User } from './api'
import { clearTokens, setTokens } from './api'

interface AuthContextValue {
  user: User | null
  setUser: (u: User | null) => void
  logout: () => void
  setAuth: (u: User & { access_token: string; refresh_token: string }) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)
const STORAGE_KEY = 'attendiq.user'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  })

  const setUser = useCallback((u: User | null) => {
    setUserState(u)
    if (u) localStorage.setItem(STORAGE_KEY, JSON.stringify(u))
    else localStorage.removeItem(STORAGE_KEY)
  }, [])

  const setAuth = useCallback((u: User & { access_token: string; refresh_token: string }) => {
    const { access_token, refresh_token, ...userOnly } = u as any
    setUser(userOnly as User)
    setTokens(access_token, refresh_token)
  }, [setUser])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [setUser])

  return <AuthContext.Provider value={{ user, setUser, logout, setAuth }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
