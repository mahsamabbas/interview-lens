import { useState } from 'react'
import Home from './components/Home'
import Reports from './components/Reports'
import Setup from './components/Setup'
import Stepper from './components/Stepper'
import TranscriptStudio from './components/TranscriptStudio'
import { getSession } from './lib/api'
import type { AppStep, StepKey } from './lib/setup'

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [step, setStep] = useState<AppStep>('home')
  const [openError, setOpenError] = useState<string | null>(null)

  const goHome = () => {
    setSessionId(null)
    setStep('home')
  }

  const openSession = async (id: string) => {
    setOpenError(null)
    try {
      const s = await getSession(id)
      setSessionId(id)
      setStep(s.status === 'done' ? 'reports' : s.segments.length > 0 ? 'transcript' : 'setup')
    } catch (e) {
      setOpenError((e as Error).message)
    }
  }

  const inSession = step !== 'home'

  return (
    <main className="app-shell">
      {inSession && (
        <header className="chrome">
          <button type="button" className="brand-link" onClick={goHome} aria-label="InterviewLens home">
            Interview<span>Lens</span>
          </button>
        </header>
      )}

      {inSession && <Stepper current={step as StepKey} onNavigate={setStep} />}
      {openError && (
        <p className="notice" role="alert">
          Couldn’t open that session: {openError}
        </p>
      )}

      {step === 'home' && (
        <Home
          onNew={() => {
            setSessionId(null)
            setStep('setup')
          }}
          onOpen={(id) => void openSession(id)}
        />
      )}
      {step === 'setup' && (
        <Setup
          key={sessionId ?? 'new'}
          sessionId={sessionId}
          onBack={goHome}
          onReady={(id) => {
            setSessionId(id)
            setStep('transcript')
          }}
        />
      )}
      {step === 'transcript' && sessionId && (
        <TranscriptStudio
          key={sessionId}
          sessionId={sessionId}
          onBack={() => setStep('setup')}
          onAnalyzed={() => setStep('reports')}
        />
      )}
      {step === 'reports' && (
        <Reports
          key={sessionId ?? 'none'}
          sessionId={sessionId}
          onBackToTranscript={() => setStep('transcript')}
          onHome={goHome}
        />
      )}
    </main>
  )
}
