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
    <div className="v2-loading-overlay" role="status" aria-live="polite" aria-busy="true">
      <div className="v2-loading-overlay-card">
        <Loader2 className="v2-loading-overlay-spinner" size={28} aria-hidden="true" />
        {hideLabel ? null : <p className="v2-loading-overlay-label">Loading</p>}
        <p className="v2-loading-overlay-message">{message}</p>
      </div>
    </div>,
    document.body,
  )
}
