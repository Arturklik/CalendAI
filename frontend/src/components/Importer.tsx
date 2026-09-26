import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AudioLines,
  CalendarDays,
  Check,
  ImagePlus,
  LoaderCircle,
  Mic,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { api, getApiError } from '../api/client'
import type {
  Event,
  EventInput,
  EventType,
  ParsedCalendarEvent,
  ScheduleParseResponse,
} from '../types'
import {
  browserTimezoneOffset,
  dateKey,
  eventTypeStyles,
  eventTypes,
  formatLongDate,
  localDateTimeValue,
  toUtcIso,
} from '../utils/date'

interface ImporterProps {
  onSaved: (events: Event[]) => void
}

interface StagedEvent {
  draftId: string
  title: string
  event_type: EventType
  start_time: string
  end_time: string
  location: string
  teacher: string
  description: string
}

const audioExtensions = ['.mp3', '.wav', '.ogg', '.m4a', '.webm']
const commonTimezones = [
  '-08:00',
  '-05:00',
  '-04:00',
  '+00:00',
  '+01:00',
  '+02:00',
  '+03:00',
  '+05:30',
  '+07:00',
  '+08:00',
  '+09:00',
]

function draftFromParsed(event: ParsedCalendarEvent, index: number): StagedEvent {
  return {
    draftId: `${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
    title: event.title,
    event_type: event.event_type,
    start_time: localDateTimeValue(event.start_time),
    end_time: localDateTimeValue(event.end_time),
    location: event.location ?? '',
    teacher: event.teacher ?? '',
    description: event.description ?? '',
  }
}

function audioExtension(file: File): string {
  const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
  return audioExtensions.includes(extension) ? extension : ''
}

export default function Importer({ onSaved }: ImporterProps) {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioPreview, setAudioPreview] = useState('')
  const [recording, setRecording] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [baseDate, setBaseDate] = useState(() => dateKey(new Date()))
  const [timezone, setTimezone] = useState(browserTimezoneOffset)
  const [drafts, setDrafts] = useState<StagedEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const imageInputRef = useRef<HTMLInputElement>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const timezoneOptions = useMemo(
    () => Array.from(new Set([timezone, ...commonTimezones])).sort(),
    [timezone],
  )

  const groupedDrafts = useMemo(() => {
    const groups = new Map<string, StagedEvent[]>()
    for (const draft of [...drafts].sort((left, right) => left.start_time.localeCompare(right.start_time))) {
      const key = draft.start_time.slice(0, 10)
      groups.set(key, [...(groups.get(key) ?? []), draft])
    }
    return [...groups.entries()]
  }, [drafts])

  useEffect(() => {
    if (!imageFile) {
      setImagePreview('')
      return
    }
    const url = URL.createObjectURL(imageFile)
    setImagePreview(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFile])

  useEffect(() => {
    if (!audioFile) {
      setAudioPreview('')
      return
    }
    const url = URL.createObjectURL(audioFile)
    setAudioPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [audioFile])

  useEffect(
    () => () => {
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop())
      streamRef.current?.getTracks().forEach((track) => track.stop())
    },
    [],
  )

  function acceptImage(file: File | undefined) {
    if (!file) return
    const extensionIsImage = /\.(png|jpe?g|webp)$/i.test(file.name)
    const mimeIsImage = ['image/png', 'image/jpeg', 'image/webp'].includes(file.type)
    if (!extensionIsImage && !mimeIsImage) {
      setError('Choose a PNG, JPG, or WEBP image.')
      return
    }
    setError('')
    setNotice('')
    setImageFile(file)
  }

  function acceptAudio(file: File | undefined) {
    if (!file) return
    if (!audioExtension(file)) {
      setError('Choose an MP3, WAV, OGG, M4A, or WEBM audio file.')
      return
    }
    setError('')
    setNotice('')
    setAudioFile(file)
  }

  async function startRecording() {
    setError('')
    setNotice('')
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Audio recording is not available in this browser. Upload an audio file instead.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      )
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (recordEvent) => {
        if (recordEvent.data.size > 0) chunksRef.current.push(recordEvent.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const extension = recorder.mimeType.toLowerCase().includes('mp4') ? '.m4a' : '.webm'
        if (blob.size > 0) {
          setAudioFile(new File([blob], `calendai-voice-${Date.now()}${extension}`, { type: blob.type }))
        }
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        setRecording(false)
      }
      recorder.start()
      setAudioFile(null)
      setRecording(true)
    } catch {
      setError('Microphone access was not granted. You can upload an audio file instead.')
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  async function parseFile(file: File, endpoint: 'image' | 'voice') {
    setError('')
    setNotice('')
    setBusy(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const response = await api.post<ScheduleParseResponse>(`/ai/parse-${endpoint}`, formData, {
        params: { base_date: baseDate, tz: timezone },
      })
      setDrafts(response.data.events.map(draftFromParsed))
      setNotice(
        response.data.events.length
          ? `Found ${response.data.events.length} ${response.data.events.length === 1 ? 'class' : 'classes'}. Review the details before saving.`
          : 'No classes were detected. Try a clearer image or recording.',
      )
    } catch (requestError) {
      setError(getApiError(requestError, 'Could not recognize this schedule. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  function updateDraft<K extends keyof Omit<StagedEvent, 'draftId'>>(
    draftId: string,
    key: K,
    value: StagedEvent[K],
  ) {
    setDrafts((current) =>
      current.map((draft) => (draft.draftId === draftId ? { ...draft, [key]: value } : draft)),
    )
  }

  async function saveDrafts() {
    if (!drafts.length) return
    if (
      drafts.some(
        (draft) =>
          !draft.title.trim() ||
          !draft.start_time ||
          !draft.end_time ||
          new Date(draft.end_time).getTime() <= new Date(draft.start_time).getTime(),
      )
    ) {
      setError('Every class needs a title and an end time later than its start time.')
      return
    }
    setError('')
    setNotice('')
    setSaving(true)
    const payload: EventInput[] = drafts.map((draft) => ({
      title: draft.title.trim(),
      event_type: draft.event_type,
      start_time: toUtcIso(draft.start_time),
      end_time: toUtcIso(draft.end_time),
      location: draft.location.trim() || null,
      teacher: draft.teacher.trim() || null,
      description: draft.description.trim() || null,
      recurrence_rule: null,
    }))
    try {
      const response = await api.post<Event[]>('/events/batch', payload)
      onSaved(response.data)
      setDrafts([])
      setImageFile(null)
      setAudioFile(null)
      setNotice(`Saved ${response.data.length} ${response.data.length === 1 ? 'class' : 'classes'} to your calendar.`)
    } catch (requestError) {
      setError(getApiError(requestError, 'Could not save these classes. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#162544] via-[#1d3763] to-[#2353a1] px-6 py-7 text-white shadow-sm sm:px-8 sm:py-8">
        <div className="absolute -right-8 -top-20 h-64 w-64 rounded-full border border-white/10" />
        <div className="absolute -right-1 -top-12 h-48 w-48 rounded-full border border-white/10" />
        <div className="relative max-w-2xl">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.13em] text-blue-100">
            <Sparkles size={13} /> Smart schedule importer
          </div>
          <h2 className="font-display text-2xl font-extrabold tracking-tight sm:text-3xl">
            From timetable to calendar.
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100/80">
            Drop in a photo or record a voice note. CalendAI will draft your classes for you to review.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
            <CalendarDays size={18} />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-slate-900">Recognition settings</h3>
            <p className="mt-0.5 text-xs text-slate-500">Used to interpret weekdays and local class times.</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-xs font-bold text-slate-600">Base date</span>
            <input
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
              onChange={(event) => setBaseDate(event.target.value)}
              required
              type="date"
              value={baseDate}
            />
            <span className="mt-1.5 block text-[11px] text-slate-400">The date this schedule was sent or received.</span>
          </label>
          <label className="block">
            <span className="mb-2 block text-xs font-bold text-slate-600">Timezone offset</span>
            <select
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
              onChange={(event) => setTimezone(event.target.value)}
              value={timezone}
            >
              {timezoneOptions.map((offset) => (
                <option key={offset} value={offset}>
                  UTC{offset}{offset === browserTimezoneOffset() ? ' · browser local' : ''}
                </option>
              ))}
            </select>
            <span className="mt-1.5 block text-[11px] text-slate-400">Defaults to this browser’s timezone.</span>
          </label>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <ImagePlus size={19} />
              </div>
              <div>
                <h3 className="text-sm font-extrabold text-slate-900">Import from an image</h3>
                <p className="mt-0.5 text-xs text-slate-500">PNG, JPG, or WEBP up to 20 MB</p>
              </div>
            </div>
          </div>

          {imageFile ? (
            <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
              <img alt="Selected timetable preview" className="max-h-72 w-full object-contain" src={imagePreview} />
              <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-white px-3 py-2.5">
                <span className="min-w-0 truncate text-xs font-semibold text-slate-600">{imageFile.name}</span>
                <span className="flex shrink-0 items-center gap-1">
                  <button
                    className="rounded-lg px-2.5 py-2 text-xs font-bold text-blue-600 transition hover:bg-blue-50"
                    onClick={() => imageInputRef.current?.click()}
                    type="button"
                  >
                    Replace
                  </button>
                  <button
                    aria-label="Remove image"
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                    onClick={() => setImageFile(null)}
                    type="button"
                  >
                    <X size={16} />
                  </button>
                </span>
              </div>
            </div>
          ) : (
            <button
              className={`flex min-h-52 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-5 py-7 text-center transition ${dragging ? 'border-blue-400 bg-blue-50' : 'border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/50'}`}
              onClick={() => imageInputRef.current?.click()}
              onDragEnter={(event) => {
                event.preventDefault()
                setDragging(true)
              }}
              onDragLeave={(event) => {
                event.preventDefault()
                setDragging(false)
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                setDragging(false)
              acceptImage(event.dataTransfer.files[0])
              }}
              type="button"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                <Upload size={21} />
              </span>
              <span className="mt-3 text-sm font-bold text-slate-800">Drop your timetable here</span>
              <span className="mt-1 text-xs text-slate-500">or click to browse your files</span>
            </button>
          )}
          <input
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(event) => {
              acceptImage(event.target.files?.[0])
              event.target.value = ''
            }}
            ref={imageInputRef}
            type="file"
          />
          <button
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!imageFile || busy || recording}
            onClick={() => imageFile && void parseFile(imageFile, 'image')}
            type="button"
          >
            {busy ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={16} />}
            {busy ? 'Reading timetable…' : 'Recognize image'}
          </button>
        </section>

        <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                <AudioLines size={19} />
              </div>
              <div>
                <h3 className="text-sm font-extrabold text-slate-900">Import from voice</h3>
                <p className="mt-0.5 text-xs text-slate-500">Record now or choose an audio file</p>
              </div>
            </div>
          </div>

          <div className="flex min-h-52 flex-col items-center justify-center rounded-xl border border-slate-100 bg-slate-50/70 px-5 py-6 text-center">
            <div className={`relative flex h-16 w-16 items-center justify-center rounded-full ${recording ? 'bg-rose-100 text-rose-600' : 'bg-white text-violet-600 shadow-sm'}`}>
              {recording && <span className="absolute inset-0 animate-ping rounded-full bg-rose-300/40" />}
              {recording ? <AudioLines className="relative" size={24} /> : <Mic size={24} />}
            </div>
            <p className={`mt-3 text-sm font-bold ${recording ? 'text-rose-700' : 'text-slate-800'}`}>
              {recording ? 'Recording your voice…' : audioFile ? 'Audio ready to transcribe' : 'Describe your timetable'}
            </p>
            <p className="mt-1 max-w-xs text-xs leading-5 text-slate-500">
              {recording
                ? 'Speak clearly, then stop when you are finished.'
                : audioFile
                  ? audioFile.name
                  : 'Mention class days, times, and room numbers.'}
            </p>
            {audioPreview && !recording && (
              <audio className="mt-4 h-9 w-full max-w-sm" controls src={audioPreview} />
            )}
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {recording ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-rose-700"
                  onClick={stopRecording}
                  type="button"
                >
                  <span className="h-2 w-2 rounded-sm bg-white" /> Stop recording
                </button>
              ) : (
                <>
                  <button
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-slate-700"
                    onClick={() => void startRecording()}
                    type="button"
                  >
                    <Mic size={14} /> Record voice
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 transition hover:bg-slate-50"
                    onClick={() => audioInputRef.current?.click()}
                    type="button"
                  >
                    <Upload size={14} /> Choose audio
                  </button>
                </>
              )}
            </div>
          </div>
          <input
            accept=".mp3,.wav,.ogg,.m4a,.webm,audio/*"
            className="hidden"
            onChange={(event) => {
              acceptAudio(event.target.files?.[0])
              event.target.value = ''
            }}
            ref={audioInputRef}
            type="file"
          />
          {audioFile && !recording && (
            <button
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 transition hover:text-rose-600"
              onClick={() => setAudioFile(null)}
              type="button"
            >
              <X size={13} /> Remove audio
            </button>
          )}
          <button
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!audioFile || busy || recording}
            onClick={() => audioFile && void parseFile(audioFile, 'voice')}
            type="button"
          >
            {busy ? <LoaderCircle className="animate-spin" size={17} /> : <AudioLines size={16} />}
            {busy ? 'Transcribing audio…' : 'Recognize voice note'}
          </button>
        </section>
      </div>

      {(error || notice) && (
        <div
          className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}
          role={error ? 'alert' : 'status'}
        >
          {error ? <X className="mt-0.5 shrink-0" size={16} /> : <Check className="mt-0.5 shrink-0" size={16} />}
          <span>{error || notice}</span>
        </div>
      )}

      {drafts.length > 0 && (
        <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
          <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.12em] text-emerald-600">
                <Check size={14} /> Ready for review
              </div>
              <h3 className="font-display mt-1 text-lg font-extrabold text-slate-900">Review detected classes</h3>
              <p className="mt-1 text-xs text-slate-500">Edit any field below. Nothing is saved until you confirm.</p>
            </div>
            <button
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow-md shadow-emerald-600/15 transition hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60"
              disabled={saving}
              onClick={() => void saveDrafts()}
              type="button"
            >
              {saving ? <LoaderCircle className="animate-spin" size={17} /> : <Plus size={16} />}
              {saving ? 'Saving classes…' : `Save ${drafts.length} to calendar`}
            </button>
          </div>

          <div className="space-y-6 p-5 sm:p-6">
            {groupedDrafts.map(([day, dayDrafts]) => (
              <div key={day}>
                <div className="mb-3 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue-500" />
                  <h4 className="text-sm font-extrabold capitalize text-slate-800">{formatLongDate(day)}</h4>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
                    {dayDrafts.length}
                  </span>
                </div>
                <div className="calendar-scrollbar overflow-x-auto rounded-xl border border-slate-100">
                  <table className="w-full min-w-[1040px] border-collapse text-left">
                    <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <tr>
                        <th className="px-3 py-3">Title</th>
                        <th className="px-3 py-3">Type</th>
                        <th className="px-3 py-3">Starts</th>
                        <th className="px-3 py-3">Ends</th>
                        <th className="px-3 py-3">Classroom</th>
                        <th className="px-3 py-3">Teacher</th>
                        <th className="w-12 px-2 py-3"><span className="sr-only">Remove</span></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {dayDrafts.map((draft) => (
                        <tr className="align-middle" key={draft.draftId}>
                          <td className="min-w-52 px-2 py-2">
                            <input
                              aria-label="Class title"
                              className="w-full rounded-lg border border-transparent px-2.5 py-2 text-xs font-semibold text-slate-800 outline-none transition focus:border-blue-300 focus:bg-blue-50/30"
                              maxLength={200}
                              onChange={(event) => updateDraft(draft.draftId, 'title', event.target.value)}
                              value={draft.title}
                            />
                          </td>
                          <td className="w-32 px-2 py-2">
                            <select
                              aria-label="Event type"
                              className={`w-full rounded-lg border border-transparent px-2 py-2 text-xs font-bold outline-none focus:border-blue-300 ${eventTypeStyles[draft.event_type].soft}`}
                              onChange={(event) => updateDraft(draft.draftId, 'event_type', event.target.value as EventType)}
                              value={draft.event_type}
                            >
                              {eventTypes.map((type) => (
                                <option key={type} value={type}>{type}</option>
                              ))}
                            </select>
                          </td>
                          <td className="w-48 px-2 py-2">
                            <input
                              aria-label="Start time"
                              className="w-full rounded-lg border border-transparent px-2 py-2 text-xs text-slate-700 outline-none transition focus:border-blue-300"
                              onChange={(event) => updateDraft(draft.draftId, 'start_time', event.target.value)}
                              required
                              type="datetime-local"
                              value={draft.start_time}
                            />
                          </td>
                          <td className="w-48 px-2 py-2">
                            <input
                              aria-label="End time"
                              className="w-full rounded-lg border border-transparent px-2 py-2 text-xs text-slate-700 outline-none transition focus:border-blue-300"
                              onChange={(event) => updateDraft(draft.draftId, 'end_time', event.target.value)}
                              required
                              type="datetime-local"
                              value={draft.end_time}
                            />
                          </td>
                          <td className="min-w-40 px-2 py-2">
                            <input
                              aria-label="Classroom"
                              className="w-full rounded-lg border border-transparent px-2.5 py-2 text-xs text-slate-700 outline-none transition focus:border-blue-300"
                              maxLength={255}
                              onChange={(event) => updateDraft(draft.draftId, 'location', event.target.value)}
                              placeholder="Room"
                              value={draft.location}
                            />
                          </td>
                          <td className="min-w-40 px-2 py-2">
                            <input
                              aria-label="Teacher"
                              className="w-full rounded-lg border border-transparent px-2.5 py-2 text-xs text-slate-700 outline-none transition focus:border-blue-300"
                              maxLength={255}
                              onChange={(event) => updateDraft(draft.draftId, 'teacher', event.target.value)}
                              placeholder="Teacher"
                              value={draft.teacher}
                            />
                          </td>
                          <td className="px-2 py-2">
                            <button
                              aria-label={`Remove ${draft.title || 'class'}`}
                              className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                              onClick={() => setDrafts((current) => current.filter((item) => item.draftId !== draft.draftId))}
                              type="button"
                            >
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
