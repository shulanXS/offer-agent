from enum import Enum


DEFAULT_JOB_TITLE = "后端开发工程师"
DEFAULT_LANGUAGE = "Java"
DEFAULT_DIFFICULTY_LEVEL = "入门"


class InterviewPlanSessionStatus(str, Enum):
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    PLAN_CONFIRMED = "plan_confirmed"


V2_SESSION_SCHEMA_VERSION = 2
