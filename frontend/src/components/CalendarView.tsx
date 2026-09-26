import { useMemo, useState } from 'react'
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MapPin,
  Plus,
  UserRound,
} from 'lucide-react'
import type { Event } from '../types'
import {
  addDays,
  dateFromKey,
  dateKey,
  eventTypeStyles,
  formatLongDate,
  formatMonth,
  formatTime,
  sortByStart,
  startOfWeek,
} from '../utils/date'

type CalendarMode = 'month' | 'week' | 'day'

interface CalendarViewProps {
  events: Event[]
  onAdd: (date: string) => void
  onEdit: (event: Event) => void
}

const weekDayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function getMonthDays(date: Date): Date[] {
  const firstDay = new Date(date.getFullYear(), date.getMonth(), 1)
  const offset = (firstDay.getDay() + 6) % 7
  const start = addDays(firstDay, -offset)
  return Array.from({ length: 42 }, (_, index) => addDays(start, index))
}

function EventTypeBadge({ type }: { type: Event['event_type'] }) {
  const style = eventTypeStyles[type]
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold ring-1 ring-inset ${style.badge}`}>
      {style.label}
    </span>
  )
}

function AgendaEvent({ event, onClick }: { event: Event; onClick: () => void }) {
  const style = eventTypeStyles[event.event_type]
  return (
    <button
      className={`group w-full rounded-xl border border-slate-100 border-l-[3px] ${style.border} bg-white p-3.5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-200 hover:shadow-md`}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-slate-900 group-hover:text-blue-700">
            {event.title}
          </p>
          <div className="mt-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
            <Clock3 size={13} className="text-slate-400" />
            {formatTime(event.start_time)} – {formatTime(event.end_time)}
          </div>
        </div>
        <EventTypeBadge type={event.event_type} />
      </div>
      {(event.location || event.teacher) && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-500">
          {event.location && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={13} className="text-slate-400" /> {event.location}
            </span>
          )}
          {event.teacher && (
            <span className="inline-flex items-center gap-1.5">
              <UserRound size={13} className="text-slate-400" /> {event.teacher}
            </span>
          )}
        </div>
      )}
      {event.description && (
        <p className="mt-2.5 line-clamp-2 text-xs leading-5 text-slate-500">
          {event.description}
        </p>
      )}
    </button>
  )
}

export default function CalendarView({ events, onAdd, onEdit }: CalendarViewProps) {
  const [mode, setMode] = useState<CalendarMode>('month')
  const [selectedDate, setSelectedDate] = useState(() => dateKey(new Date()))
  const todayKey = dateKey(new Date())
  const selected = dateFromKey(selectedDate)

  const eventsByDate = useMemo(() => {
    const grouped = new Map<string, Event[]>()
    for (const event of sortByStart(events)) {
      const key = dateKey(new Date(event.start_time))
      grouped.set(key, [...(grouped.get(key) ?? []), event])
    }
    return grouped
  }, [events])

  const selectedEvents = eventsByDate.get(selectedDate) ?? []

  function navigate(direction: number) {
    if (mode === 'month') {
      const month = selected.getMonth() + direction
      const targetMonth = new Date(selected.getFullYear(), month, 1)
      const lastDay = new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0).getDate()
      setSelectedDate(dateKey(new Date(targetMonth.getFullYear(), targetMonth.getMonth(), Math.min(selected.getDate(), lastDay))))
    } else {
      setSelectedDate(dateKey(addDays(selected, direction * (mode === 'week' ? 7 : 1))))
    }
  }

  function title() {
    if (mode === 'month') return formatMonth(selected)
    if (mode === 'day') return formatLongDate(selected)
    const first = startOfWeek(selected)
    const last = addDays(first, 6)
    if (first.getMonth() === last.getMonth()) {
      return `${new Intl.DateTimeFormat(undefined, { month: 'long' }).format(first)} ${first.getDate()}–${last.getDate()}`
    }
    return `${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(first)} – ${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(last)}`
  }

  function renderMonth() {
    const days = getMonthDays(selected)
    return (
      <div className="overflow-hidden rounded-xl border border-slate-100">
        <div className="grid grid-cols-7 border-b border-slate-100 bg-slate-50/80">
          {weekDayNames.map((name) => (
            <div key={name} className="py-3 text-center text-[10px] font-bold uppercase tracking-wider text-slate-400 sm:text-xs">
              {name}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {days.map((day) => {
            const key = dateKey(day)
            const dayEvents = eventsByDate.get(key) ?? []
            const inMonth = day.getMonth() === selected.getMonth()
            const isSelected = key === selectedDate
            const isToday = key === todayKey
            return (
              <div
                className={`min-h-[5.7rem] border-b border-r border-slate-100 p-1.5 text-left transition last:border-r-0 sm:min-h-[7.2rem] sm:p-2.5 ${!inMonth ? 'bg-slate-50/50' : 'bg-white'} ${isSelected ? 'bg-blue-50/80 ring-2 ring-inset ring-blue-400' : ''}`}
                key={key}
              >
                <button
                  aria-label={`Select ${formatLongDate(day)}${dayEvents.length ? `, ${dayEvents.length} classes` : ''}`}
                  aria-pressed={isSelected}
                  className="group w-full text-left"
                  onClick={() => setSelectedDate(key)}
                  type="button"
                >
                  <span className={`mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition group-hover:bg-blue-100 sm:mx-0 sm:h-8 sm:w-8 sm:text-sm ${isToday ? 'bg-blue-600 text-white group-hover:bg-blue-700' : isSelected ? 'text-blue-700' : inMonth ? 'text-slate-700' : 'text-slate-300'}`}>
                    {day.getDate()}
                  </span>
                </button>
                <span className="mt-1.5 hidden space-y-1 sm:block">
                  {dayEvents.slice(0, 2).map((event) => (
                    <button
                      className={`block w-full truncate rounded-md px-1.5 py-1 text-left text-[10px] font-semibold leading-none transition hover:ring-1 hover:ring-slate-300 ${eventTypeStyles[event.event_type].soft} text-slate-700`}
                      key={event.id}
                      onClick={() => onEdit(event)}
                      title={`${formatTime(event.start_time)} ${event.title}`}
                      type="button"
                    >
                      {formatTime(event.start_time)} {event.title}
                    </button>
                  ))}
                  {dayEvents.length > 2 && (
                    <button
                      className="block pl-1 text-[10px] font-semibold text-slate-400 hover:text-blue-600"
                      onClick={() => setSelectedDate(key)}
                      type="button"
                    >
                      +{dayEvents.length - 2} more
                    </button>
                  )}
                </span>
                {dayEvents.length > 0 && (
                  <span className="mt-1 flex justify-center gap-0.5 sm:hidden">
                    {dayEvents.slice(0, 3).map((event) => (
                      <button
                        aria-label={`Edit ${event.title}`}
                        className={`h-2 w-2 rounded-full ${eventTypeStyles[event.event_type].dot}`}
                        key={event.id}
                        onClick={() => onEdit(event)}
                        type="button"
                      />
                    ))}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  function renderWeek() {
    const days = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(selected), index))
    return (
      <div className="calendar-scrollbar overflow-x-auto pb-1">
        <div className="grid min-w-[700px] grid-cols-7 divide-x divide-slate-100 rounded-xl border border-slate-100">
          {days.map((day) => {
            const key = dateKey(day)
            const dayEvents = eventsByDate.get(key) ?? []
            const isSelected = key === selectedDate
            const isToday = key === todayKey
            return (
              <div className={`min-h-[20rem] bg-white ${isSelected ? 'bg-blue-50/30' : ''}`} key={key}>
                <button
                  aria-pressed={isSelected}
                  className="w-full border-b border-slate-100 px-2 py-3 text-center transition hover:bg-blue-50/60"
                  onClick={() => setSelectedDate(key)}
                  type="button"
                >
                  <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {weekDayNames[(day.getDay() + 6) % 7]}
                  </span>
                  <span className={`mx-auto mt-1 flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${isToday ? 'bg-blue-600 text-white' : isSelected ? 'bg-blue-100 text-blue-700' : 'text-slate-700'}`}>
                    {day.getDate()}
                  </span>
                  <span className="mt-1 block text-[10px] text-slate-400">
                    {dayEvents.length ? `${dayEvents.length} ${dayEvents.length === 1 ? 'class' : 'classes'}` : '—'}
                  </span>
                </button>
                <div className="space-y-2 p-1.5 sm:p-2">
                  {dayEvents.slice(0, 4).map((event) => (
                    <button
                      className={`w-full rounded-lg border-l-2 ${eventTypeStyles[event.event_type].border} ${eventTypeStyles[event.event_type].soft} p-2 text-left transition hover:brightness-[0.98]`}
                      key={event.id}
                      onClick={() => onEdit(event)}
                      type="button"
                    >
                      <span className="block text-[10px] font-bold text-slate-500">
                        {formatTime(event.start_time)}
                      </span>
                      <span className="mt-1 block line-clamp-2 text-[11px] font-bold leading-4 text-slate-800">
                        {event.title}
                      </span>
                    </button>
                  ))}
                  {dayEvents.length > 4 && (
                    <button
                      className="px-1 text-[10px] font-bold text-blue-600 hover:text-blue-700"
                      onClick={() => setSelectedDate(key)}
                      type="button"
                    >
                      +{dayEvents.length - 4} more
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  function renderDay() {
    return (
      <div className="rounded-xl border border-slate-100 bg-white p-5 sm:p-7">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-slate-100 pb-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-blue-600">Day list</p>
            <h3 className="font-display mt-1 text-xl font-extrabold text-slate-900">{formatLongDate(selected)}</h3>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-500">
            {selectedEvents.length} {selectedEvents.length === 1 ? 'class' : 'classes'}
          </span>
        </div>
        {selectedEvents.length ? (
          <div className="space-y-3">
            {selectedEvents.map((event) => (
              <button
                className={`flex w-full items-center gap-4 rounded-xl border border-slate-100 border-l-4 ${eventTypeStyles[event.event_type].border} p-4 text-left transition hover:bg-slate-50`}
                key={event.id}
                onClick={() => onEdit(event)}
                type="button"
              >
                <span className="w-24 shrink-0 text-xs font-bold tabular-nums text-slate-500">
                  {formatTime(event.start_time)}
                  <span className="mx-1 text-slate-300">–</span>
                  {formatTime(event.end_time)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold text-slate-900">{event.title}</span>
                  <span className="mt-1 block truncate text-xs text-slate-500">
                    {[event.location, event.teacher].filter(Boolean).join(' · ') || 'No location or teacher added'}
                  </span>
                </span>
                <EventTypeBadge type={event.event_type} />
              </button>
            ))}
          </div>
        ) : (
          <EmptyAgenda onAdd={() => onAdd(selectedDate)} />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1">
              <button
                aria-label="Previous period"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800"
                onClick={() => navigate(-1)}
                type="button"
              >
                <ChevronLeft size={17} />
              </button>
              <button
                aria-label="Next period"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800"
                onClick={() => navigate(1)}
                type="button"
              >
                <ChevronRight size={17} />
              </button>
            </div>
            <h2 className="font-display min-w-40 text-lg font-extrabold capitalize text-slate-900 sm:text-xl">
              {title()}
            </h2>
            <button
              className="rounded-lg px-3 py-2 text-xs font-bold text-blue-600 transition hover:bg-blue-50"
              onClick={() => setSelectedDate(todayKey)}
              type="button"
            >
              Today
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div aria-label="Calendar view" className="flex rounded-lg bg-slate-100 p-1" role="group">
              {(['month', 'week', 'day'] as const).map((value) => (
                <button
                  aria-pressed={mode === value}
                  className={`rounded-md px-3 py-1.5 text-xs font-bold capitalize transition ${mode === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                  key={value}
                  onClick={() => setMode(value)}
                  type="button"
                >
                  {value === 'day' ? 'Day list' : value}
                </button>
              ))}
            </div>
            <button
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2.5 text-xs font-bold text-white shadow-md shadow-blue-600/15 transition hover:bg-blue-700"
              onClick={() => onAdd(selectedDate)}
              type="button"
            >
              <Plus size={15} /> Add class
            </button>
          </div>
        </div>

        {mode === 'month' ? renderMonth() : mode === 'week' ? renderWeek() : renderDay()}

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Event types</span>
          {(Object.keys(eventTypeStyles) as Array<keyof typeof eventTypeStyles>).map((type) => (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-500" key={type}>
              <span className={`h-2 w-2 rounded-full ${eventTypeStyles[type].dot}`} />
              {eventTypeStyles[type].label}
            </span>
          ))}
        </div>
      </section>

      {mode !== 'day' && (
        <section className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-blue-600">
                <CalendarDays size={14} /> Selected day
              </div>
              <h3 className="font-display mt-1 text-lg font-extrabold capitalize text-slate-900">
                {formatLongDate(selected)}
              </h3>
            </div>
            <button
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold text-blue-600 transition hover:bg-blue-50"
              onClick={() => onAdd(selectedDate)}
              type="button"
            >
              <Plus size={15} /> Add class
            </button>
          </div>
          {selectedEvents.length ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {selectedEvents.map((event) => (
                <AgendaEvent event={event} key={event.id} onClick={() => onEdit(event)} />
              ))}
            </div>
          ) : (
            <EmptyAgenda onAdd={() => onAdd(selectedDate)} />
          )}
        </section>
      )}
    </div>
  )
}

function EmptyAgenda({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-5 py-9 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-slate-400 shadow-sm">
        <Clock3 size={19} />
      </div>
      <p className="mt-3 text-sm font-bold text-slate-700">Nothing on the schedule yet</p>
      <p className="mt-1 text-xs text-slate-500">Add a class or import your timetable to get started.</p>
      <button
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-bold text-blue-600 shadow-sm ring-1 ring-slate-200 transition hover:bg-blue-50"
        onClick={onAdd}
        type="button"
      >
        <Plus size={14} /> Add a class
      </button>
    </div>
  )
}
