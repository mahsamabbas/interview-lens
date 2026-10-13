import type { Recommendation, ScoreBlock } from './api'

export const VERDICT: Record<Recommendation, { label: string; tone: 'pass' | 'borderline' | 'no' }> = {
  pass: { label: 'PASS', tone: 'pass' },
  borderline: { label: 'Borderline', tone: 'borderline' },
  no: { label: 'NO', tone: 'no' },
}

export const SCORE_LABELS: { key: keyof ScoreBlock; label: string }[] = [
  { key: 'overall', label: 'Overall' },
  { key: 'jd_match', label: 'Job match' },
  { key: 'answer_depth', label: 'Answer depth' },
  { key: 'communication', label: 'Communication' },
  { key: 'structure', label: 'Structure' },
]

export function clampScore(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

export function scoreTone(n: number): 'high' | 'mid' | 'low' {
  const s = clampScore(n)
  return s >= 70 ? 'high' : s >= 45 ? 'mid' : 'low'
}
