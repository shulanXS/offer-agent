/** v2.2 算法题 API 客户端。 */
import { requestJson } from './client'

export interface AlgorithmProblem {
  id: string
  difficulty: string
  tags: string[]
  prompt: string
  function_signature: string
}

export interface JudgeResponse {
  verdict: string
  scores: Record<string, number>
  overall: number
  feedback: string
  per_test: Array<Record<string, unknown>>
}

export function listAlgorithmProblems(token: string) {
  return requestJson<AlgorithmProblem[]>('/api/algorithm/problems', {}, token)
}

export function getAlgorithmProblem(problemId: string, token: string) {
  return requestJson<AlgorithmProblem>(
    `/api/algorithm/problems/${problemId}`,
    {},
    token,
  )
}

export function submitAlgorithm(
  problemId: string,
  code: string,
  token: string,
  language: 'python' | 'cpp' | 'java' | 'javascript' = 'python',
) {
  return requestJson<JudgeResponse>(
    '/api/algorithm/judge',
    {
      method: 'POST',
      body: JSON.stringify({ problem_id: problemId, code, language }),
    },
    token,
    300_000,
  )
}
