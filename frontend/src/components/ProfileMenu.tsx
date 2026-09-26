import { useState, type FormEvent } from 'react'
import { Check, ChevronDown, Copy, KeyRound, Link2, LogOut, UserRound } from 'lucide-react'
import { api, getApiError } from '../api/client'
import type { TelegramLinkTokenResponse, User } from '../types'

interface ProfileMenuProps {
  user: User
  onLogout: () => void
}

export default function ProfileMenu({ user, onLogout }: ProfileMenuProps) {
  const [open, setOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramExpiry, setTelegramExpiry] = useState<number | null>(null)
  const [telegramMessage, setTelegramMessage] = useState('')
  const [telegramError, setTelegramError] = useState('')
  const [requestingToken, setRequestingToken] = useState(false)

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordError('')
    setPasswordMessage('')
    if (newPassword !== confirmPassword) {
      setPasswordError('The new passwords do not match.')
      return
    }

    setSavingPassword(true)
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      setPasswordMessage('Password changed successfully.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (error) {
      setPasswordError(getApiError(error, 'Could not change your password.'))
    } finally {
      setSavingPassword(false)
    }
  }

  async function requestTelegramToken() {
    setTelegramError('')
    setTelegramMessage('')
    setRequestingToken(true)
    try {
      const response = await api.post<TelegramLinkTokenResponse>('/auth/telegram-link-token')
      setTelegramToken(response.data.link_token)
      setTelegramExpiry(response.data.expires_in_seconds)
    } catch (error) {
      setTelegramError(getApiError(error, 'Could not create a Telegram link token.'))
    } finally {
      setRequestingToken(false)
    }
  }

  async function copyTelegramCommand() {
    try {
      await navigator.clipboard.writeText(`/start ${telegramToken}`)
      setTelegramMessage('Command copied to clipboard.')
      setTelegramError('')
    } catch {
      setTelegramError('Clipboard access is unavailable in this browser.')
    }
  }

  return (
    <div className="relative">
      <button
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white py-1.5 pl-2 pr-3 text-left shadow-sm transition hover:border-slate-300"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-sm font-extrabold text-blue-700">
          {user.email.slice(0, 1).toUpperCase()}
        </span>
        <span className="hidden max-w-40 sm:block">
          <span className="block truncate text-xs font-bold text-slate-800">{user.email}</span>
          <span className="mt-0.5 block text-[11px] capitalize text-slate-400">
            {user.subscription_tier} account
          </span>
        </span>
        <ChevronDown className="text-slate-400" size={15} />
      </button>

      {open && (
        <>
          <button
            aria-label="Close profile menu"
            className="fixed inset-0 z-30 cursor-default"
            onClick={() => setOpen(false)}
            type="button"
          />
          <section
            aria-label="Account settings"
            className="absolute right-0 top-[calc(100%+0.75rem)] z-40 max-h-[calc(100vh-6rem)] w-[min(24rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-soft"
            role="dialog"
          >
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                <UserRound size={19} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Signed in as</p>
                <p className="truncate text-sm font-bold text-slate-800">{user.email}</p>
              </div>
            </div>

            <form className="space-y-3 border-b border-slate-100 py-4" onSubmit={changePassword}>
              <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <KeyRound size={15} className="text-blue-600" /> Change password
              </h3>
              <input
                autoComplete="current-password"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                minLength={1}
                onChange={(event) => setCurrentPassword(event.target.value)}
                placeholder="Current password"
                required
                type="password"
                value={currentPassword}
              />
              <input
                autoComplete="new-password"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                minLength={8}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="New password (8+ characters)"
                required
                type="password"
                value={newPassword}
              />
              <input
                autoComplete="new-password"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Confirm new password"
                required
                type="password"
                value={confirmPassword}
              />
              {(passwordError || passwordMessage) && (
                <p className={`text-xs ${passwordError ? 'text-rose-600' : 'text-emerald-700'}`} role="status">
                  {passwordError || passwordMessage}
                </p>
              )}
              <button
                className="w-full rounded-lg bg-slate-900 px-3 py-2.5 text-xs font-bold text-white transition hover:bg-slate-700 disabled:opacity-60"
                disabled={savingPassword}
                type="submit"
              >
                {savingPassword ? 'Updating…' : 'Update password'}
              </button>
            </form>

            <div className="space-y-3 border-b border-slate-100 py-4">
              <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
                <Link2 size={15} className="text-blue-600" /> Connect Telegram
              </h3>
              <p className="text-xs leading-5 text-slate-500">
                Create a one-time command, then send it to the CalendAI bot.
              </p>
              {telegramToken ? (
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Send this command to the bot
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="min-w-0 flex-1 break-all rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs font-semibold text-slate-700">
                      /start {telegramToken}
                    </code>
                    <button
                      aria-label="Copy Telegram command"
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white transition hover:bg-blue-700"
                      onClick={copyTelegramCommand}
                      type="button"
                    >
                      {telegramMessage ? <Check size={15} /> : <Copy size={15} />}
                    </button>
                  </div>
                  {telegramExpiry !== null && (
                    <p className="mt-2 text-[11px] text-slate-400">
                      Expires in {Math.ceil(telegramExpiry / 60)} minutes.
                    </p>
                  )}
                </div>
              ) : (
                <button
                  className="w-full rounded-lg border border-blue-200 bg-blue-50 px-3 py-2.5 text-xs font-bold text-blue-700 transition hover:bg-blue-100 disabled:opacity-60"
                  disabled={requestingToken}
                  onClick={requestTelegramToken}
                  type="button"
                >
                  {requestingToken ? 'Generating command…' : 'Generate link command'}
                </button>
              )}
              {(telegramError || telegramMessage) && (
                <p className={`text-xs ${telegramError ? 'text-rose-600' : 'text-emerald-700'}`} role="status">
                  {telegramError || telegramMessage}
                </p>
              )}
            </div>

            <button
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-bold text-rose-600 transition hover:bg-rose-50"
              onClick={onLogout}
              type="button"
            >
              <LogOut size={16} /> Sign out
            </button>
          </section>
        </>
      )}
    </div>
  )
}
