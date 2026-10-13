import { describe, expect, it } from 'vitest'
import {
  canContinue,
  hasExistingSource,
  jdValid,
  MIN_JD_CHARS,
  sourceAttached,
  sourceNeedsIngest,
} from './setup'

const jd = 'x'.repeat(MIN_JD_CHARS)

describe('setup validation', () => {
  it('requires JD of at least 40 trimmed chars', () => {
    expect(jdValid('x'.repeat(39))).toBe(false)
    expect(jdValid(`  ${'x'.repeat(39)}  `)).toBe(false)
    expect(jdValid(jd)).toBe(true)
  })

  it('checks source attachment per type', () => {
    expect(sourceAttached({ source: null, file: null, paste: '' })).toBe(false)
    expect(sourceAttached({ source: 'sample_video', file: null, paste: '' })).toBe(true)
    expect(sourceAttached({ source: 'upload', file: null, paste: '' })).toBe(false)
    expect(sourceAttached({ source: 'paste', file: null, paste: '  ' })).toBe(false)
    expect(sourceAttached({ source: 'paste', file: null, paste: 'hi' })).toBe(true)
  })

  it('canContinue needs both', () => {
    expect(canContinue({ jd, source: null, file: null, paste: '' })).toBe(false)
    expect(canContinue({ jd: 'short', source: 'sample_video', file: null, paste: '' })).toBe(false)
    expect(canContinue({ jd, source: 'sample_video', file: null, paste: '' })).toBe(true)
  })

  it('reopen setup: existing source skips re-ingest', () => {
    const ex = { sourceType: 'paste' as const, hasMedia: false, hasSegments: true }
    expect(hasExistingSource(ex)).toBe(true)
    const draft = { jd, source: 'paste' as const, file: null, paste: '' }
    expect(sourceNeedsIngest(draft, ex)).toBe(false)
    expect(canContinue(draft, ex)).toBe(true)
  })

  it('reopen setup: new paste text triggers ingest', () => {
    const ex = { sourceType: 'paste' as const, hasMedia: false, hasSegments: true }
    const draft = { jd, source: 'paste' as const, file: null, paste: 'Candidate: new lines' }
    expect(sourceNeedsIngest(draft, ex)).toBe(true)
  })
})
