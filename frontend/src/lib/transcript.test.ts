import { describe, expect, it } from 'vitest'
import type { Segment } from './api'
import { canAnalyze, formatMs, nextSpeaker, toSegmentIn } from './transcript'

const seg = (text: string): Segment => ({
  id: 'x',
  session_id: 's',
  idx: 5,
  start_ms: 0,
  end_ms: 1000,
  speaker: 'candidate',
  text,
})

describe('transcript helpers', () => {
  it('cycles speakers interviewer → candidate → unknown', () => {
    expect(nextSpeaker('interviewer')).toBe('candidate')
    expect(nextSpeaker('candidate')).toBe('unknown')
    expect(nextSpeaker('unknown')).toBe('interviewer')
  })

  it('reindexes segments for PATCH', () => {
    expect(toSegmentIn([seg('a'), seg('b')]).map((s) => s.idx)).toEqual([0, 1])
  })

  it('formats timestamps', () => {
    expect(formatMs(65_000)).toBe('1:05')
  })

  it('requires JD and a non-empty segment to analyze', () => {
    expect(canAnalyze('jd', [seg('hi')])).toBe(true)
    expect(canAnalyze('  ', [seg('hi')])).toBe(false)
    expect(canAnalyze('jd', [])).toBe(false)
    expect(canAnalyze('jd', [seg('  ')])).toBe(false)
  })
})
