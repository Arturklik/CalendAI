import type { EventType } from '../types'

export const eventTypeStyles: Record<
  EventType,
  { label: string; badge: string; dot: string; border: string; soft: string }
> = {
  lecture: {
    label: 'Lecture',
    badge: 'bg-blue-50 text-blue-700 ring-blue-600/10',
    dot: 'bg-blue-500',
    border: 'border-blue-500',
    soft: 'bg-blue-50/80',
  },
  lab: {
    label: 'Lab',
    badge: 'bg-amber-50 text-amber-700 ring-amber-600/10',
    dot: 'bg-amber-500',
    border: 'border-amber-500',
    soft: 'bg-amber-50/80',
  },
  practice: {
    label: 'Practice',
    badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/10',
    dot: 'bg-emerald-500',
    border: 'border-emerald-500',
    soft: 'bg-emerald-50/80',
  },
  exam: {
    label: 'Exam',
    badge: 'bg-rose-50 text-rose-700 ring-rose-600/10',
    dot: 'bg-rose-500',
    border: 'border-rose-500',
    soft: 'bg-rose-50/80',
  },
  other: {
    label: 'Other',
    badge: 'bg-purple-50 text-purple-700 ring-purple-600/10',
    dot: 'bg-purple-500',
    border: 'border-purple-500',
    soft: 'bg-purple-50/80',
  },
}

export const eventTypes: EventType[] = [
  'lecture',
  'practice',
  'lab',
  'exam',
  'other',
]

const pad = (value: number) => String(value).padStart(2, '0')

export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function dateFromKey(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function localDateTimeValue(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value
  return `${dateKey(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function toUtcIso(value: string): string {
  return new Date(value).toISOString()
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export function formatLongDate(value: Date | string): string {
  const date = typeof value === 'string' ? dateFromKey(value) : value
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function formatMonth(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    year: 'numeric',
  }).format(value)
}

export function browserTimezoneOffset(): string {
  const minutes = -new Date().getTimezoneOffset()
  const sign = minutes >= 0 ? '+' : '-'
  const absolute = Math.abs(minutes)
  return `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
}

export function sortByStart<T extends { start_time: string }>(events: T[]): T[] {
  return [...events].sort(
    (left, right) =>
      new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
  )
}

export function startOfWeek(date: Date): Date {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const offset = (start.getDay() + 6) % 7
  start.setDate(start.getDate() - offset)
  return start
}

export function addDays(date: Date, amount: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + amount)
  return result
}
