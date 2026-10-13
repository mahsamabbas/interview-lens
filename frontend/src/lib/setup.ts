import type { SourceType } from './api'

export const MIN_JD_CHARS = 40

export interface SetupDraft {
  jd: string
  source: SourceType | null
  file: File | null
  paste: string
}

export function jdValid(jd: string): boolean {
  return jd.trim().length >= MIN_JD_CHARS
}

export function sourceAttached(d: Pick<SetupDraft, 'source' | 'file' | 'paste'>): boolean {
  if (d.source === 'sample_video') return true
  if (d.source === 'upload') return d.file !== null
  if (d.source === 'paste') return d.paste.trim().length > 0
  return false
}

export function canContinue(d: SetupDraft): boolean {
  return jdValid(d.jd) && sourceAttached(d)
}

export const STEPS = [
  { key: 'setup', label: 'Setup' },
  { key: 'transcript', label: 'Transcript' },
  { key: 'reports', label: 'Reports' },
] as const

export type StepKey = (typeof STEPS)[number]['key']
export type AppStep = 'home' | StepKey
