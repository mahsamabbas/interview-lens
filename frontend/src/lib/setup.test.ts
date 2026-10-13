import { describe, expect, it } from 'vitest'
import { canContinue, jdValid, MIN_JD_CHARS, sourceAttached } from './setup'

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
})
