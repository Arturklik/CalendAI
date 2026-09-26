import { useEffect, useState, type FormEvent } from 'react'
import { CalendarClock, MapPin, Trash2, X } from 'lucide-react'
import type { Event, EventInput, EventType } from '../types'
import { eventTypes, localDateTimeValue } from '../utils/date'

interface EventModalProps {
  event: Event | null
  initialDate: string
  onClose: () => void
  onSave: (values: EventInput) => Promise<void>
  onDelete: (eventId: string) => Promise<void>
}

interface EventFormValues {
  title: string
  event_type: EventType
  start_time: string
  end_time: string
  location: string
  teacher: string
  description: string
  recurrence_rule: string
}

function emptyValues(initialDate: string): EventFormValues {
  return {
    title: '',
    event_type: 'lecture',
    start_time: `${initialDate}T09:00`,
    end_time: `${initialDate}T10:35`,
    location: '',
    teacher: '',
    description: '',
    recurrence_rule: '',
  }
}

function toFormValues(event: Event | null, initialDate: string): EventFormValues {
  if (!event) return emptyValues(initialDate)
  return {
    title: event.title,
    event_type: event.event_type,
    start_time: localDateTimeValue(event.start_time),
    end_time: localDateTimeValue(event.end_time),
    location: event.location ?? '',
    teacher: event.teacher ?? '',
    description: event.description ?? '',
    recurrence_rule: event.recurrence_rule ?? '',
  }
}

export default function EventModal({
  event,
  initialDate,
  onClose,
  onSave,
  onDelete,
}: EventModalProps) {
  const [values, setValues] = useState(() => toFormValues(event, initialDate))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setValues(toFormValues(event, initialDate))
    setError('')
  }, [event, initialDate])

  function update<K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault()
    setError('')
    if (new Date(values.end_time).getTime() <= new Date(values.start_time).getTime()) {
      setError('End time must be later than start time.')
      return
    }

    setBusy(true)
    try {
      await onSave({
        title: values.title.trim(),
        event_type: values.event_type,
        start_time: new Date(values.start_time).toISOString(),
        end_time: new Date(values.end_time).toISOString(),
        location: values.location.trim() || null,
        teacher: values.teacher.trim() || null,
        description: values.description.trim() || null,
        recurrence_rule: values.recurrence_rule.trim() || null,
      })
      onClose()
    } catch {
      setError('Could not save this class. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteEvent() {
    if (!event || !window.confirm(`Delete “${event.title}” from your calendar?`)) return
    setError('')
    setBusy(true)
    try {
      await onDelete(event.id)
      onClose()
    } catch {
      setError('Could not delete this class. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      aria-label={event ? 'Edit class' : 'Add class'}
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/45 p-4 backdrop-blur-[2px]"
      onMouseDown={(mouseEvent) => {
        if (mouseEvent.target === mouseEvent.currentTarget && !busy) onClose()
      }}
      role="dialog"
    >
      <section className="my-auto w-full max-w-2xl overflow-hidden rounded-2xl bg-white shadow-2xl shadow-slate-950/20">
        <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5 sm:px-7">
          <div>
            <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.12em] text-blue-600">
              <CalendarClock size={14} /> Calendar event
            </div>
            <h2 className="font-display text-xl font-extrabold text-slate-900">
              {event ? 'Edit class' : 'Add a class'}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Add the details you want to keep close at hand.
            </p>
          </div>
          <button
            aria-label="Close dialog"
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            onClick={onClose}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <form className="space-y-5 px-6 py-6 sm:px-7" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-[1fr_190px]">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Class title</span>
              <input
                autoFocus
                className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                maxLength={200}
                onChange={(inputEvent) => update('title', inputEvent.target.value)}
                placeholder="e.g. Linear algebra"
                required
                value={values.title}
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Event type</span>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                onChange={(inputEvent) => update('event_type', inputEvent.target.value as EventType)}
                value={values.event_type}
              >
                {eventTypes.map((type) => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Starts</span>
              <input
                className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                onChange={(inputEvent) => update('start_time', inputEvent.target.value)}
                required
                type="datetime-local"
                value={values.start_time}
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Ends</span>
              <input
                className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                onChange={(inputEvent) => update('end_time', inputEvent.target.value)}
                required
                type="datetime-local"
                value={values.end_time}
              />
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
                <MapPin size={14} className="text-slate-400" /> Classroom / location
              </span>
              <input
                className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                maxLength={255}
                onChange={(inputEvent) => update('location', inputEvent.target.value)}
                placeholder="Building, room, or link"
                value={values.location}
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Teacher</span>
              <input
                className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                maxLength={255}
                onChange={(inputEvent) => update('teacher', inputEvent.target.value)}
                placeholder="Instructor name"
                value={values.teacher}
              />
            </label>
          </div>

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-slate-700">Description</span>
            <textarea
              className="min-h-20 w-full resize-y rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
              onChange={(inputEvent) => update('description', inputEvent.target.value)}
              placeholder="Notes, materials, or reminders"
              rows={2}
              value={values.description}
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-slate-700">Recurrence rule</span>
            <input
              className="w-full rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
              maxLength={255}
              onChange={(inputEvent) => update('recurrence_rule', inputEvent.target.value)}
              placeholder="Optional RFC 5545 rule, e.g. FREQ=WEEKLY"
              value={values.recurrence_rule}
            />
          </label>

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2.5 text-sm text-rose-700" role="alert">
              {error}
            </p>
          )}

          <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
            {event ? (
              <button
                className="inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-bold text-rose-600 transition hover:bg-rose-50 disabled:opacity-50"
                disabled={busy}
                onClick={deleteEvent}
                type="button"
              >
                <Trash2 size={16} /> Delete class
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2.5">
              <button
                className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50 sm:flex-none"
                disabled={busy}
                onClick={onClose}
                type="button"
              >
                Cancel
              </button>
              <button
                className="flex-1 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-bold text-white shadow-md shadow-blue-600/15 transition hover:bg-blue-700 disabled:cursor-wait disabled:opacity-60 sm:flex-none"
                disabled={busy}
                type="submit"
              >
                {busy ? 'Saving…' : event ? 'Save changes' : 'Create class'}
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  )
}
