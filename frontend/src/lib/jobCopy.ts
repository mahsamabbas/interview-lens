export function jobStatusMessage(status: string): string {
  switch (status) {
    case 'queued':
      return 'Waiting to start…'
    case 'transcribing':
      return 'Transcribing audio…'
    case 'diarizing':
      return 'Separating speakers…'
    case 'analyzing':
      return 'Writing both reports…'
    case 'ready':
      return 'Transcript ready — review speakers, then analyze.'
    case 'done':
      return 'Done.'
    case 'error':
      return 'Something went wrong.'
    default:
      return 'Working…'
  }
}
