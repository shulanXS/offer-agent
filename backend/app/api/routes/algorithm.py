"""v2.2 算法题路由：题库 + 提交判题。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
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
def judge(body: JudgeRequest, current_user: dict = Depends(get_current_user)) -> dict:
    return judge_submission(problem_id=body.problem_id, code=body.code, language=body.language)
