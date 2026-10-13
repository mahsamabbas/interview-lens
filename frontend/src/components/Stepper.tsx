import { STEPS, type StepKey } from '../lib/setup'

interface Props {
  current: StepKey
  /** Steps the user may jump back to. */
  onNavigate?: (step: StepKey) => void
}

export default function Stepper({ current, onNavigate }: Props) {
  const idx = STEPS.findIndex((s) => s.key === current)
  return (
    <nav aria-label="Session progress">
      <ol className="stepper">
        {STEPS.map((s, i) => {
          const cls = i < idx ? 'is-done' : i === idx ? 'is-active' : ''
          const canGo = i < idx && onNavigate
          return (
            <li key={s.key} className={cls} aria-current={i === idx ? 'step' : undefined}>
              {canGo ? (
                <button type="button" className="stepper-link" onClick={() => onNavigate(s.key)}>
                  {s.label}
                </button>
              ) : (
                s.label
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
