"""将 working_memory 证据投影为候选人可读的问答依据。"""
from __future__ import annotations

from typing import Any


def build_evidence_references(
    evidence: list[dict[str, Any]],
    messages: list[dict[str, Any]] | None = None,
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    rounds = build_answer_rounds(messages or [])
    references: list[dict[str, Any]] = []

    for item in evidence:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue

        matched_round = find_round_for_quote(quote, rounds) if rounds else None
        if rounds and not matched_round:
            continue

        try:
            strength = float(item.get("strength", 0) or 0)
        except (TypeError, ValueError):
            strength = 0.0

        reference: dict[str, Any] = {
            "quote": quote,
            "matched_signal": str(item.get("matched_signal", "")).strip(),
            "polarity": str(item.get("polarity", "neutral")).strip() or "neutral",
            "strength": round(strength, 2),
        }
        if matched_round:
            reference["question"] = matched_round["question"]
            reference["answer"] = matched_round["answer"]
            reference["sequence"] = matched_round["sequence"]
        references.append(reference)

    if rounds:
        references.sort(key=lambda item: (int(item.get("sequence", 0)), str(item.get("matched_signal", ""))))
    return references[:limit]


def build_answer_rounds(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    pending_question = ""

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if role == "assistant" and content:
            pending_question = content
            continue
        if role != "user" or not content:
            continue
        rounds.append(
            {
                "sequence": index,
                "question": pending_question,
                "answer": content,
            }
        )

    return rounds


def find_round_for_quote(quote: str, rounds: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [round_item for round_item in rounds if quote_in_answer(quote, str(round_item.get("answer", "")))]
    if not matches:
        return None
    return min(matches, key=lambda round_item: len(str(round_item.get("answer", ""))))


def find_latest_round_for_quote(quote: str, rounds: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [round_item for round_item in rounds if quote_in_answer(quote, str(round_item.get("answer", "")))]
    if not matches:
        return None
    return max(matches, key=lambda round_item: int(round_item.get("sequence", 0)))


def build_competency_answer_rounds(
    evidence: list[dict[str, Any]],
    messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """返回主题下全部 Q&A 轮次，并将证据标签挂到对应轮次。"""
    rounds = build_answer_rounds(messages or [])
    if not rounds:
        return []

    references = build_evidence_references(evidence, messages)
    evidence_items_by_sequence: dict[int, list[dict[str, Any]]] = {
        int(round_item["sequence"]): [] for round_item in rounds
    }

    for reference in references:
        quote = str(reference.get("quote", "")).strip()
        if not quote:
            continue
        matched_round = find_latest_round_for_quote(quote, rounds)
        if not matched_round:
            continue
        sequence = int(matched_round["sequence"])
        evidence_items_by_sequence.setdefault(sequence, []).append(
            {
                "quote": quote,
                "matched_signal": str(reference.get("matched_signal", "")).strip(),
                "polarity": str(reference.get("polarity", "neutral")).strip() or "neutral",
                "strength": reference.get("strength", 0.0),
            }
        )

    return [
        {
            "sequence": int(round_item["sequence"]),
            "question": str(round_item.get("question", "")),
            "answer": str(round_item.get("answer", "")),
            "evidence_items": evidence_items_by_sequence.get(int(round_item["sequence"]), []),
        }
        for round_item in rounds
    ]


def quote_in_answer(quote: str, answer: str) -> bool:
    normalized_quote = normalize_text(quote)
    normalized_answer = normalize_text(answer)
    if not normalized_quote or not normalized_answer:
        return False
    return normalized_quote in normalized_answer


def normalize_text(text: str) -> str:
    return " ".join(str(text).split())
