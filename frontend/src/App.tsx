import { useEffect, useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { ACCESS_TOKEN_KEY, api } from './api/client'
import AuthScreen from './components/AuthScreen'
import Dashboard from './components/Dashboard'
import type { User } from './types'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    if (!token) {
      setCheckingSession(false)
      return
    }

    let current = true
    api
      .get<User>('/auth/me')
      .then((response) => {
        if (current) setUser(response.data)
      })
      .catch(() => {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        if (current) setUser(null)
      })
      .finally(() => {
        if (current) setCheckingSession(false)
      })

    return () => {
      current = false
    }
  }, [])

  function authenticated(authenticatedUser: User) {
    setUser(authenticatedUser)
    if (window.location.pathname !== '/') window.history.replaceState(null, '', '/')
  }

  function logout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    setUser(null)
    window.history.replaceState(null, '', '/login')
  }

  if (checkingSession) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#f5f7fb] text-sm font-semibold text-slate-500">
        <LoaderCircle className="mr-2 animate-spin text-blue-600" size={19} /> Checking your account…
      </main>
    )
  }

  return user ? (
    <Dashboard onLogout={logout} user={user} />
  ) : (
    <AuthScreen onAuthenticated={authenticated} />
  )
}
