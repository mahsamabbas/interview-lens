import { describe, it, expect } from 'vitest'
import { clampScore, scoreTone, VERDICT } from './reports'

describe('reports helpers', () => {
  it('clamps scores to 0-100', () => {
    expect(clampScore(120)).toBe(100)
    expect(clampScore(-5)).toBe(0)
    expect(clampScore(NaN)).toBe(0)
    expect(clampScore(72.6)).toBe(73)
  })

  it('buckets score tone', () => {
    expect(scoreTone(85)).toBe('high')
    expect(scoreTone(50)).toBe('mid')
    expect(scoreTone(10)).toBe('low')
  })

  it('maps verdict labels', () => {
    expect(VERDICT.pass.label).toBe('PASS')
    expect(VERDICT.borderline.label).toBe('Borderline')
    expect(VERDICT.no.label).toBe('NO')
  })
})
