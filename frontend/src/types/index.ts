export type EventType = 'lecture' | 'practice' | 'lab' | 'exam' | 'other'

export interface Event {
  id: string
  title: string
  event_type: EventType
  start_time: string
  end_time: string
  location: string | null
  teacher: string | null
  description: string | null
  recurrence_rule: string | null
  updated_at: string
  is_deleted: boolean
}

export interface EventInput {
  title: string
  event_type: EventType
  start_time: string
  end_time: string
  location: string | null
  teacher: string | null
  description: string | null
  recurrence_rule: string | null
}

export interface User {
  id: string
  email: string
  telegram_id: number | null
  subscription_tier: string
  created_at: string
}

export interface ParsedCalendarEvent {
  title: string
  event_type: EventType
  start_time: string
  end_time: string
  location: string | null
  teacher: string | null
  description: string | null
}

export interface ScheduleParseResponse {
  events: ParsedCalendarEvent[]
}

export interface AccessTokenResponse {
  access_token: string
  token_type: 'bearer'
}

export interface TelegramLinkTokenResponse {
  link_token: string
  expires_in_seconds: number
}
