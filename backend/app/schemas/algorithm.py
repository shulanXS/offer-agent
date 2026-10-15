"""v2.2 算法题 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AlgorithmProblem(BaseModel):
    id: str
    difficulty: str
    tags: list[str]
    prompt: str
    function_signature: str


class JudgeRequest(BaseModel):
    problem_id: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=20000)
    language: Literal["python", "cpp", "java", "javascript"] = "python"


class JudgePerTest(BaseModel):
    input: dict
    expected: object
    actual: object
    pass_: bool = Field(alias="pass")
    reason: str = ""

    class Config:
        populate_by_name = True


class JudgeResponse(BaseModel):
    verdict: str
    scores: dict[str, float]
    overall: float
    feedback: str
    per_test: list[dict] = Field(default_factory=list)
