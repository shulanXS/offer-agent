import { Loader2 } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'

type LoadingOverlayProps = {
  open: boolean
  message: string
  hideLabel?: boolean
}

export function LoadingOverlay({ open, message, hideLabel = false }: LoadingOverlayProps) {
  useBodyScrollLock(open)

  if (!open) {
    return null
  }

  return createPortal(
    <div className="app-loading-overlay" role="status" aria-live="polite" aria-busy="true">
      <div className="app-loading-overlay-card">
        <Loader2 className="app-loading-overlay-spinner" size={28} aria-hidden="true" />
        {hideLabel ? null : <p className="app-loading-overlay-label">Loading</p>}
        <p className="app-loading-overlay-message">{message}</p>
      </div>
    </div>,
    document.body,
  )
}
