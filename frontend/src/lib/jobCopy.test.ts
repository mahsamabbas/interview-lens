import { describe, it, expect } from 'vitest'
import { jobStatusMessage } from './jobCopy'

describe('jobStatusMessage', () => {
  it('explains diarizing', () => {
    expect(jobStatusMessage('diarizing')).toMatch(/speakers/i)
  })

  it('covers each known status', () => {
    expect(jobStatusMessage('queued')).toMatch(/waiting/i)
    expect(jobStatusMessage('transcribing')).toMatch(/transcribing/i)
    expect(jobStatusMessage('analyzing')).toMatch(/reports/i)
    expect(jobStatusMessage('ready')).toMatch(/review speakers/i)
    expect(jobStatusMessage('done')).toBe('Done.')
    expect(jobStatusMessage('error')).toMatch(/wrong/i)
  })

  it('falls back for unknown status', () => {
    expect(jobStatusMessage('mystery')).toBe('Working…')
  })
})
