import { LoadingOverlay } from '@/components/LoadingOverlay'
import { Label } from '@/components/ui/label'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  REGENERATION_STRATEGIES,
  type InterviewConfigurationSnapshot,
  type RegenerationStrategy,
} from '@/types/interviewPlan'

interface RegeneratePlanDialogProps {
  open: boolean
  loading?: boolean
  regenerationsRemaining: number
  configuration: InterviewConfigurationSnapshot
  onConfirm: (payload: {
    regeneration_strategy: RegenerationStrategy
    additional_instruction: string
  }) => void
  onCancel: () => void
}

export function RegeneratePlanDialog({
  open,
  loading = false,
  regenerationsRemaining,
  configuration,
  onConfirm,
  onCancel,
}: RegeneratePlanDialogProps) {
  const hasJd = Boolean(configuration.jd_text?.trim())
  const strategyOptions = useMemo(
    () => REGENERATION_STRATEGIES.filter((item) => !('requiresJd' in item && item.requiresJd) || hasJd),
    [hasJd],
  )
  const [strategy, setStrategy] = useState<RegenerationStrategy>('align_resume')
  const [additionalInstruction, setAdditionalInstruction] = useState('')

  useEffect(() => {
    if (!open) return
    setStrategy(strategyOptions[0]?.value ?? 'align_resume')
    setAdditionalInstruction('')
  }, [open, strategyOptions])

  useEffect(() => {
    if (strategy !== 'different_plan') {
      setAdditionalInstruction('')
    }
  }, [strategy])

  useEffect(() => {
    if (!open) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !loading) {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [loading, onCancel, open])

  useBodyScrollLock(open)

  if (!open) {
    return null
  }

  if (loading) {
    return <LoadingOverlay open message="正在重新生成面试计划，请耐心等待" />
  }

  const remainingHint =
    regenerationsRemaining <= 1
      ? '这是最后一次重新生成机会，确认计划后将无法再调整。'
      : `本次重新生成后，还可调整 ${regenerationsRemaining - 1} 次（当前剩余 ${regenerationsRemaining} 次）。`

  function handleConfirm() {
    onConfirm({
      regeneration_strategy: strategy,
      additional_instruction: strategy === 'different_plan' ? additionalInstruction.trim() : '',
    })
  }

  return createPortal(
    <div className="confirm-dialog-root" role="presentation">
      <button type="button" className="confirm-dialog-backdrop" aria-label="关闭" disabled={loading} onClick={onCancel} />
      <div className="v2-regenerate-dialog" role="dialog" aria-modal="true" aria-labelledby="regenerate-dialog-title">
        <h3 id="regenerate-dialog-title">重新生成面试计划</h3>
        <p className="v2-regenerate-remaining-hint">{remainingHint}</p>

        <div className="v2-regenerate-section">
          <Label>调整策略（必选）</Label>
          <div className="v2-regenerate-strategies">
            {strategyOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={strategy === option.value ? 'active' : ''}
                disabled={loading}
                onClick={() => setStrategy(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {strategy === 'different_plan' ? (
          <div className="v2-regenerate-section">
            <Label htmlFor="regenerate-instruction">补充说明（可选，最多 200 字）</Label>
            <textarea
              id="regenerate-instruction"
              className="v2-jd-textarea"
              maxLength={200}
              value={additionalInstruction}
              disabled={loading}
              placeholder="例如：希望更偏分布式经验，少问管理类问题"
              onChange={(event) => setAdditionalInstruction(event.target.value)}
            />
          </div>
        ) : null}

        <div className="confirm-dialog-actions">
          <button type="button" className="ghost" disabled={loading} onClick={onCancel}>
            取消
          </button>
          <button type="button" className="primary" disabled={loading} onClick={handleConfirm}>
            确定
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
