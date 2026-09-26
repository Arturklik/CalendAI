import { useEffect, useState, type ReactNode } from 'react'
import {
  CalendarDays,
  Check,
  Clock3,
  GraduationCap,
  LayoutGrid,
  LoaderCircle,
  Plus,
  Sparkles,
} from 'lucide-react'
import { api, getApiError } from '../api/client'
import type { Event, EventInput, User } from '../types'
import { dateKey, sortByStart } from '../utils/date'
import CalendarView from './CalendarView'
import EventModal from './EventModal'
import Importer from './Importer'
import ProfileMenu from './ProfileMenu'

interface DashboardProps {
  user: User
  onLogout: () => void
}

type DashboardTab = 'calendar' | 'import'

interface EventDialogState {
  event: Event | null
  date: string
}

export default function Dashboard({ user, onLogout }: DashboardProps) {
  const [activeTab, setActiveTab] = useState<DashboardTab>('calendar')
  const [events, setEvents] = useState<Event[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [banner, setBanner] = useState('')
  const [dialog, setDialog] = useState<EventDialogState | null>(null)

  useEffect(() => {
    let current = true
    api
      .get<Event[]>('/events')
      .then((response) => {
        if (current) setEvents(sortByStart(response.data))
      })
      .catch((error: unknown) => {
        if (current) setLoadError(getApiError(error, 'Could not load your calendar.'))
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
  }, [])

  const today = dateKey(new Date())
  const todaysClasses = events.filter((event) => dateKey(new Date(event.start_time)) === today).length
  const upcomingClasses = events.filter((event) => new Date(event.start_time).getTime() >= Date.now()).length

  function openCreate(date: string) {
    setDialog({ event: null, date })
  }

  async function saveEvent(values: EventInput) {
    if (dialog?.event) {
      const response = await api.patch<Event>(`/events/${dialog.event.id}`, values)
      setEvents((current) =>
        sortByStart(current.map((event) => (event.id === response.data.id ? response.data : event))),
      )
      setBanner('Class updated successfully.')
      return
    }

    const response = await api.post<Event>('/events', values)
    setEvents((current) => sortByStart([...current, response.data]))
    setBanner('Class added to your calendar.')
  }

  async function deleteEvent(eventId: string) {
    await api.delete(`/events/${eventId}`)
    setEvents((current) => current.filter((event) => event.id !== eventId))
    setBanner('Class removed from your calendar.')
  }

  function addImportedEvents(imported: Event[]) {
    setEvents((current) => sortByStart([...current, ...imported]))
    setBanner(`${imported.length} ${imported.length === 1 ? 'class was' : 'classes were'} added to your calendar.`)
    setActiveTab('calendar')
  }

  function handleLogout() {
    onLogout()
  }

  return (
    <div className="min-h-screen bg-[#f5f7fb] lg:flex">
      <aside className="hidden w-[248px] shrink-0 flex-col bg-[#14213d] px-5 py-6 text-white lg:flex">
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 shadow-lg shadow-blue-950/20">
            <CalendarDays size={21} strokeWidth={2.2} />
          </div>
          <div>
            <p className="font-display text-lg font-extrabold tracking-tight">CalendAI</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">Your schedule hub</p>
          </div>
        </div>

        <div className="mt-12">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.17em] text-slate-500">Workspace</p>
          <nav aria-label="Main navigation" className="space-y-1">
            <button
              aria-current={activeTab === 'calendar' ? 'page' : undefined}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${activeTab === 'calendar' ? 'bg-blue-500 text-white shadow-md shadow-blue-950/20' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`}
              onClick={() => setActiveTab('calendar')}
              type="button"
            >
              <LayoutGrid size={17} /> Calendar
              <span className="ml-auto rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-bold">{events.length}</span>
            </button>
            <button
              aria-current={activeTab === 'import' ? 'page' : undefined}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${activeTab === 'import' ? 'bg-blue-500 text-white shadow-md shadow-blue-950/20' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`}
              onClick={() => setActiveTab('import')}
              type="button"
            >
              <Sparkles size={17} /> AI importer
              <span className="ml-auto rounded bg-white/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-blue-200">New</span>
            </button>
          </nav>
        </div>

        <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-400/15 text-blue-200">
            <GraduationCap size={18} />
          </div>
          <p className="mt-3 text-xs font-bold text-white">Your classes, in sync</p>
          <p className="mt-1 text-[11px] leading-5 text-slate-400">
            Changes here are ready to sync with your CalendAI mobile app.
          </p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 px-4 py-3 backdrop-blur-xl sm:px-7 lg:px-9">
          <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white lg:hidden">
                <CalendarDays size={19} />
              </div>
              <div className="min-w-0">
                <p className="hidden text-xs font-semibold text-slate-400 sm:block">CalendAI workspace</p>
                <p className="truncate text-sm font-extrabold text-slate-800 lg:text-base">
                  {activeTab === 'calendar' ? 'Schedule overview' : 'Smart schedule importer'}
                </p>
              </div>
              <span className="hidden h-5 w-px bg-slate-200 sm:block" />
              <div className="hidden items-center gap-1.5 text-xs font-medium text-slate-500 sm:flex">
                <Clock3 size={13} className="text-slate-400" />
                {new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date())}
              </div>
            </div>
            <ProfileMenu onLogout={handleLogout} user={user} />
          </div>
        </header>

        <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-7 sm:py-8 lg:px-9">
          <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-blue-600">
                {activeTab === 'calendar' ? 'Your semester at a glance' : 'Plan smarter'}
              </p>
              <h1 className="font-display mt-1 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
                {activeTab === 'calendar' ? 'Your calendar' : 'Build your schedule'}
              </h1>
              <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">
                {activeTab === 'calendar'
                  ? 'Manage classes, keep track of what is coming up, and stay in sync.'
                  : 'Let AI read a timetable image or voice note, then review every class before saving.'}
              </p>
            </div>
            {activeTab === 'calendar' && (
              <button
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-md shadow-blue-600/15 transition hover:bg-blue-700"
                onClick={() => openCreate(today)}
                type="button"
              >
                <Plus size={17} /> Add class
              </button>
            )}
          </div>

          <div className="mb-5 grid gap-3 sm:grid-cols-3">
            <MetricCard label="Classes in calendar" value={loading ? '—' : String(events.length)} icon={<CalendarDays size={17} />} tone="blue" />
            <MetricCard label="Scheduled today" value={loading ? '—' : String(todaysClasses)} icon={<Clock3 size={17} />} tone="violet" />
            <MetricCard label="Coming up" value={loading ? '—' : String(upcomingClasses)} icon={<Sparkles size={17} />} tone="emerald" />
          </div>

          {(loadError || banner) && (
            <div
              className={`mb-5 flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm ${loadError ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}
              role={loadError ? 'alert' : 'status'}
            >
              <span className="flex items-center gap-2">
                {loadError ? <span className="font-semibold">{loadError}</span> : <><Check size={16} />{banner}</>}
              </span>
              <button
                aria-label="Dismiss message"
                className="rounded p-1 opacity-60 hover:opacity-100"
                onClick={() => {
                  setBanner('')
                  setLoadError('')
                }}
                type="button"
              >
                ×
              </button>
            </div>
          )}

          <div className="mb-5 flex gap-2 rounded-xl bg-slate-200/60 p-1 lg:hidden">
            <MobileTab active={activeTab === 'calendar'} icon={<CalendarDays size={15} />} label="Calendar" onClick={() => setActiveTab('calendar')} />
            <MobileTab active={activeTab === 'import'} icon={<Sparkles size={15} />} label="AI Import" onClick={() => setActiveTab('import')} />
          </div>

          {loading && activeTab === 'calendar' ? (
            <div className="flex min-h-80 items-center justify-center rounded-2xl border border-slate-100 bg-white text-sm font-semibold text-slate-500">
              <LoaderCircle className="mr-2 animate-spin text-blue-600" size={18} /> Loading your calendar…
            </div>
          ) : activeTab === 'calendar' ? (
            <CalendarView
              events={events}
              onAdd={openCreate}
              onEdit={(event) => setDialog({ event, date: dateKey(new Date(event.start_time)) })}
            />
          ) : (
            <Importer onSaved={addImportedEvents} />
          )}
        </main>
      </div>

      {dialog && (
        <EventModal
          event={dialog.event}
          initialDate={dialog.date}
          onClose={() => setDialog(null)}
          onDelete={deleteEvent}
          onSave={saveEvent}
        />
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string
  value: string
  icon: ReactNode
  tone: 'blue' | 'violet' | 'emerald'
}) {
  const tones = {
    blue: 'bg-blue-50 text-blue-600',
    violet: 'bg-violet-50 text-violet-600',
    emerald: 'bg-emerald-50 text-emerald-600',
  }
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-100 bg-white px-4 py-3.5 shadow-sm">
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${tones[tone]}`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-slate-500">{label}</p>
        <p className="mt-0.5 text-lg font-extrabold leading-5 text-slate-900">{value}</p>
      </div>
    </div>
  )
}

function MobileTab({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-current={active ? 'page' : undefined}
      className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-bold transition ${active ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
      onClick={onClick}
      type="button"
    >
      {icon}{label}
    </button>
  )
}
