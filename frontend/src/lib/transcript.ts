import type { Segment, SegmentIn, Speaker } from './api'

const CYCLE: Speaker[] = ['interviewer', 'candidate', 'unknown']

/** interviewer → candidate → unknown → interviewer */
export function nextSpeaker(s: Speaker): Speaker {
  return CYCLE[(CYCLE.indexOf(s) + 1) % CYCLE.length]
}

export function toSegmentIn(segments: Segment[]): SegmentIn[] {
  return segments.map((s, i) => ({
    idx: i,
    start_ms: s.start_ms,
    end_ms: s.end_ms,
    speaker: s.speaker,
    text: s.text,
  }))
}

export function formatMs(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function canAnalyze(jd: string, segments: Segment[]): boolean {
  return jd.trim().length > 0 && segments.some((s) => s.text.trim().length > 0)
}
