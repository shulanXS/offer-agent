"""v2.2/v2.3 算法题路由：题库 + 提交判题 + LLM 限流。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.rate_limit import LLM_LIMIT, limiter
from app.services.algorithm_judge_service import (
    get_problem,
    judge_submission,
    list_problems,
)
from app.schemas.algorithm import AlgorithmProblem, JudgeRequest, JudgeResponse

router = APIRouter(prefix="/algorithm", tags=["algorithm"])


@router.get("/problems", response_model=list[AlgorithmProblem])
def list_algorithm_problems(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return list_problems()


@router.get("/problems/{problem_id}", response_model=AlgorithmProblem)
def get_algorithm_problem(
    problem_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return get_problem(problem_id)


@router.post("/judge", response_model=JudgeResponse)
@limiter.limit(LLM_LIMIT)  # v2.3: 判题走 LLM，必须限流
def judge(
    request: Request,
    body: JudgeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return judge_submission(problem_id=body.problem_id, code=body.code, language=body.language)
