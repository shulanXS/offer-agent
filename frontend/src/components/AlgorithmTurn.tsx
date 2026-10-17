/** v2.2 算法回合组件：题目展示 + 手写代码 textarea + 提交判题。 */
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Code2, Loader2 } from 'lucide-react'
import { getAlgorithmProblem, submitAlgorithm, type AlgorithmProblem, type JudgeResponse } from '@/services/algorithm'

interface AlgorithmTurnProps {
  token: string
  problemId?: string
  onResult?: (result: JudgeResponse & { problem_id: string }) => void
  disabled?: boolean
}

type JudgeState = 'idle' | 'loading_problem' | 'ready' | 'judging' | 'done' | 'error'

const SAMPLE_PYTHON = `# 在这里手写你的解答
def solution():
    pass
`

export function AlgorithmTurn({ token, problemId, onResult, disabled = false }: AlgorithmTurnProps) {
  const { t } = useTranslation('interview')
  const [problem, setProblem] = useState<AlgorithmProblem | null>(null)
  const [code, setCode] = useState<string>(SAMPLE_PYTHON)
  const [state, setState] = useState<JudgeState>('idle')
  const [error, setError] = useState<string>('')
  const [result, setResult] = useState<JudgeResponse | null>(null)

  useEffect(() => {
    if (!problemId) return
    setState('loading_problem')
    setError('')
    setResult(null)
    getAlgorithmProblem(problemId, token)
      .then((p) => {
        setProblem(p)
        setCode((prev) => (prev !== SAMPLE_PYTHON ? prev : SAMPLE_PYTHON))
        setState('ready')
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : t('algo_load_error'))
        setState('error')
      })
  }, [problemId, token, t])

  async function handleSubmit() {
    if (!problem) return
    setState('judging')
    setError('')
    try {
      const r = await submitAlgorithm(problem.id, code, token)
      setResult(r)
      setState('done')
      onResult?.({ ...r, problem_id: problem.id })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('algo_judge_error'))
      setState('error')
    }
  }

  if (state === 'loading_problem') {
    return (
      <Card className="app-algo-turn">
        <div className="app-algo-loading">
          <Loader2 className="animate-spin" /> {t('algo_loading')}
        </div>
      </Card>
    )
  }

  if (state === 'error' && !problem) {
    return (
      <Card className="app-algo-turn app-algo-turn-error">
        <p>{error}</p>
      </Card>
    )
  }

  if (!problem) return null

  return (
    <Card className="app-algo-turn">
      <header className="app-algo-head">
        <span className="app-algo-icon" aria-hidden="true">
          <Code2 size={18} />
        </span>
        <h3>
          {t('algo_title')} · <span className="app-algo-diff">{problem.difficulty}</span>
        </h3>
        <div className="app-algo-tags">
          {problem.tags.map((tag) => (
            <span key={tag} className="app-algo-tag">
              {tag}
            </span>
          ))}
        </div>
      </header>
      <pre className="app-algo-prompt">{problem.prompt}</pre>
      <details className="app-algo-signature">
        <summary>{t('algo_signature')}</summary>
        <pre>{problem.function_signature}</pre>
      </details>
      <textarea
        className="app-algo-code"
        value={code}
        disabled={disabled || state === 'judging' || state === 'done'}
        onChange={(e) => setCode(e.target.value)}
        spellCheck={false}
      />
      <div className="app-algo-actions">
        <Button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={disabled || state === 'judging' || !code.trim()}
        >
          {state === 'judging' ? (
            <>
              <Loader2 className="animate-spin" size={14} /> {t('algo_judging')}
            </>
          ) : state === 'done' ? (
            <>
              <CheckCircle2 size={14} /> {t('algo_submitted')}
            </>
          ) : (
            <>{t('algo_submit')}</>
          )}
        </Button>
        {state === 'done' ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setState('ready')
              setCode(SAMPLE_PYTHON)
              setResult(null)
            }}
          >
            {t('algo_retry')}
          </Button>
        ) : null}
      </div>
      {result ? (
        <div className="app-algo-result" data-testid="algo-result">
          <strong>{t('algo_result_overall', { score: result.overall.toFixed(1) })}</strong>
          {result.feedback ? <p>{result.feedback}</p> : null}
          <div className="app-algo-scores">
            {Object.entries(result.scores).map(([k, v]) => (
              <span key={k} className="app-algo-score-chip">
                {k}: {Number(v).toFixed(1)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {error ? <p className="app-error">{error}</p> : null}
    </Card>
  )
}
