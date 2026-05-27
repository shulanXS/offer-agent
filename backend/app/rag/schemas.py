from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RoleProfile:
    slug: str
    display_name: str
    aliases: tuple[str, ...]
    default_focus_points: tuple[str, ...]
    keywords: tuple[str, ...]


ROLE_PROFILES: dict[str, RoleProfile] = {
    "backend_engineer": RoleProfile(
        slug="backend_engineer",
        display_name="后端开发工程师",
        aliases=("后端开发工程师", "后端工程师", "java后端", "后端研发工程师", "服务端开发工程师"),
        default_focus_points=("系统设计", "数据一致性", "性能优化", "故障排查"),
        keywords=("Java", "SQL", "Redis", "接口设计", "微服务"),
    ),
    "frontend_engineer": RoleProfile(
        slug="frontend_engineer",
        display_name="前端开发工程师",
        aliases=("前端开发工程师", "前端工程师", "web前端", "前端研发工程师"),
        default_focus_points=("组件设计", "状态管理", "性能优化", "工程化协作"),
        keywords=("React", "TypeScript", "工程化", "性能优化", "交互体验"),
    ),
    "product_manager": RoleProfile(
        slug="product_manager",
        display_name="产品经理",
        aliases=("产品经理", "高级产品经理", "to b产品经理", "to c产品经理", "产品策划"),
        default_focus_points=("需求分析", "优先级判断", "指标设计", "跨团队协作"),
        keywords=("需求分析", "用户研究", "数据分析", "项目推进", "业务理解"),
    ),
}


DOC_TYPE_LABELS = {
    "jd": "岗位 JD",
    "skills": "必备技能",
    "questions": "常见面试题",
    "rubric": "重点考察维度",
}


@dataclass
class KnowledgeChunk:
    id: str
    role_slug: str
    role_name: str
    doc_type: str
    section_title: str
    content: str
    source_path: str
    embedding: list[float] = field(default_factory=list)


@dataclass
class RetrievedChunk:
    id: str
    role_slug: str
    role_name: str
    doc_type: str
    section_title: str
    content: str
    source_path: str
    score: float = 0.0

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role_slug": self.role_slug,
            "role_name": self.role_name,
            "doc_type": self.doc_type,
            "section_title": self.section_title,
            "source_path": self.source_path,
            "score": self.score,
            "content": self.content,
        }


@dataclass
class PlanningRAGContext:
    role_slug: str = ""
    role_name: str = ""
    query: str = ""
    context: str = ""
    focus_points: list[str] = field(default_factory=list)
    sources: list[RetrievedChunk] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.context.strip()

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "role_slug": self.role_slug,
            "role_name": self.role_name,
            "query": self.query,
            "context": self.context,
            "focus_points": self.focus_points,
            "sources": [item.to_log_dict() for item in self.sources],
        }


def normalize_role(target_role: str = "", job_title: str = "") -> RoleProfile | None:
    raw = f"{target_role} {job_title}".strip().lower()
    if not raw:
        return None
    for profile in ROLE_PROFILES.values():
        if any(alias.lower() in raw for alias in profile.aliases):
            return profile
    return None
