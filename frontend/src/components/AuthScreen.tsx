import { useState, type FormEvent } from 'react'
import { ArrowRight, CalendarDays, Eye, EyeOff, Sparkles } from 'lucide-react'
import { api, ACCESS_TOKEN_KEY, getApiError } from '../api/client'
import type { AccessTokenResponse, User } from '../types'

interface AuthScreenProps {
  onAuthenticated: (user: User) => void
}

export default function AuthScreen({ onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    if (mode === 'register' && password !== confirmPassword) {
      setError('Your passwords do not match.')
      return
    }

    setBusy(true)
    try {
      if (mode === 'register') {
        await api.post('/auth/register', { email: email.trim(), password })
      }
      const tokenResponse = await api.post<AccessTokenResponse>('/auth/login', {
        email: email.trim(),
        password,
      })
      localStorage.setItem(ACCESS_TOKEN_KEY, tokenResponse.data.access_token)
      const userResponse = await api.get<User>('/auth/me')
      onAuthenticated(userResponse.data)
    } catch (requestError) {
      setError(
        getApiError(
          requestError,
          mode === 'register'
            ? 'We could not create your account. Please try again.'
            : 'We could not sign you in. Please check your details.',
        ),
      )
      localStorage.removeItem(ACCESS_TOKEN_KEY)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[1.02fr_0.98fr]">
      <section className="relative hidden overflow-hidden bg-[#14213d] px-12 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-36 -top-36 h-[32rem] w-[32rem] rounded-full border border-white/10" />
        <div className="absolute -right-16 -top-16 h-[24rem] w-[24rem] rounded-full border border-white/10" />
        <div className="absolute -bottom-40 -left-24 h-[30rem] w-[30rem] rounded-full bg-blue-500/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500 shadow-lg shadow-blue-950/20">
            <CalendarDays size={22} strokeWidth={2.2} />
          </div>
          <span className="font-display text-xl font-extrabold tracking-tight">CalendAI</span>
        </div>

        <div className="relative max-w-xl py-16">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-300/10 px-3.5 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-blue-100">
            <Sparkles size={14} /> Your semester, in sync
          </div>
          <h1 className="font-display text-5xl font-extrabold leading-[1.12] tracking-tight xl:text-6xl">
            Make room for
            <span className="mt-2 block text-blue-300">what matters.</span>
          </h1>
          <p className="mt-6 max-w-md text-base leading-7 text-slate-300">
            Turn timetable photos and voice notes into a thoughtful schedule you can
            manage anywhere.
          </p>

          <div className="mt-12 grid max-w-md grid-cols-3 gap-3">
            {[
              ['01', 'Capture'],
              ['02', 'Organize'],
              ['03', 'Get there'],
            ].map(([number, label]) => (
              <div key={number} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <span className="text-xs font-bold tracking-widest text-blue-300">{number}</span>
                <p className="mt-2 text-sm font-semibold text-white">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-slate-400">A calmer way to plan your day.</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white">
              <CalendarDays size={21} />
            </div>
            <span className="font-display text-xl font-extrabold">CalendAI</span>
          </div>

          <div className="mb-8">
            <p className="text-sm font-semibold text-blue-600">
              {mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}
            </p>
            <h2 className="font-display mt-2 text-3xl font-extrabold tracking-tight text-slate-900">
              {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {mode === 'login'
                ? 'Pick up where you left off with your schedule.'
                : 'Your calendar is just a few details away.'}
            </p>
          </div>

          <form className="space-y-5" onSubmit={submit}>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Email address</span>
              <input
                autoComplete="email"
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
                type="email"
                value={email}
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Password</span>
              <span className="relative block">
                <input
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 pr-12 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                  minLength={mode === 'register' ? 8 : 1}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'}
                  required
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                />
                <button
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 flex items-center px-4 text-slate-400 hover:text-slate-700"
                  onClick={() => setShowPassword((visible) => !visible)}
                  type="button"
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
            </label>

            {mode === 'register' && (
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Confirm password</span>
                <input
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Enter your password again"
                  required
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                />
              </label>
            )}

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
                {error}
              </div>
            )}

            <button
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3.5 text-sm font-bold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={busy}
              type="submit"
            >
              {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
              {!busy && <ArrowRight size={17} />}
            </button>
          </form>

          <p className="mt-7 text-center text-sm text-slate-500">
            {mode === 'login' ? 'New to CalendAI?' : 'Already have an account?'}{' '}
            <button
              className="font-bold text-blue-600 hover:text-blue-700"
              onClick={() => {
                setMode((current) => (current === 'login' ? 'register' : 'login'))
                setError('')
              }}
              type="button"
            >
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </div>
      </section>
    </main>
  )
}
