import type { ScoreBlock } from '../lib/api'
import { clampScore, SCORE_LABELS, scoreTone } from '../lib/reports'

export default function ScoreRow({ scores }: { scores: ScoreBlock }) {
  return (
    <ul className="score-list" aria-label="Scores">
      {SCORE_LABELS.map(({ key, label }) => {
        const item = scores[key]
        const value = clampScore(item.score)
        return (
          <li key={key} className={`score-row tone-${scoreTone(value)}${key === 'overall' ? ' is-overall' : ''}`}>
            <div className="score-head">
              <span className="score-label">{label}</span>
              <span className="score-value">
                {value}
                <small>/100</small>
              </span>
            </div>
            <div
              className="score-bar"
              role="meter"
              aria-label={label}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={value}
            >
              <span style={{ width: `${value}%` }} />
            </div>
            {item.rationale && <p className="score-why">{item.rationale}</p>}
          </li>
        )
      })}
    </ul>
  )
}
