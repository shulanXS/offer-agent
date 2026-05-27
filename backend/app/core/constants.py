from enum import Enum


DEFAULT_JOB_TITLE = "后端开发工程师"
DEFAULT_LANGUAGE = "Java"
DEFAULT_DIFFICULTY_LEVEL = "入门"


class InterviewSessionStatus(str, Enum):
    PREPARING = "preparing"
    ACTIVE = "active"
    COMPLETED = "completed"
