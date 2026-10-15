"""v2.2 算法题题库（v1 起步：5 道经典 + 隐藏测试）。"""
from __future__ import annotations

from typing import Any

# 每题：id / difficulty / tags / prompt（候选人看到） / hidden_tests（仅服务端用）
# 候选代码 + 隐藏测试由 LLM judge 模拟执行（不出于安全不真跑 exec）。
PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "two_sum",
        "difficulty": "Easy",
        "tags": ["array", "hash-table"],
        "prompt": (
            "给定一个整数数组 nums 和一个目标值 target，请在数组中找出和为目标值的两个整数，"
            "返回它们的下标（0-indexed）。每种输入恰好对应唯一答案。\n\n"
            "示例：\n"
            "输入：nums = [2,7,11,15], target = 9\n"
            "输出：[0,1]\n"
        ),
        "hidden_tests": [
            {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
            {"input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
            {"input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]},
        ],
        "function_signature": "def two_sum(nums: list[int], target: int) -> list[int]:",
    },
    {
        "id": "reverse_linked_list",
        "difficulty": "Easy",
        "tags": ["linked-list"],
        "prompt": (
            "反转一个单链表。\n\n"
            "示例：\n"
            "输入：1 -> 2 -> 3 -> 4 -> 5 -> NULL\n"
            "输出：5 -> 4 -> 3 -> 2 -> 1 -> NULL\n"
        ),
        "hidden_tests": [
            {"input": {"values": [1, 2, 3, 4, 5]}, "expected": [5, 4, 3, 2, 1]},
            {"input": {"values": [1, 2]}, "expected": [2, 1]},
            {"input": {"values": [1]}, "expected": [1]},
        ],
        "function_signature": "def reverse_list(head: ListNode) -> ListNode:",
    },
    {
        "id": "valid_parentheses",
        "difficulty": "Easy",
        "tags": ["string", "stack"],
        "prompt": (
            "给定一个只包含 '(', ')', '{', '}', '[', ']' 的字符串，判断字符串是否有效。\n\n"
            "示例：\n"
            "输入：\"()[]{}\"\n"
            "输出：true\n"
        ),
        "hidden_tests": [
            {"input": {"s": "()[]{}"}, "expected": True},
            {"input": {"s": "(]"}, "expected": False},
            {"input": {"s": "([)]"}, "expected": False},
            {"input": {"s": "{[]}"}, "expected": True},
        ],
        "function_signature": "def is_valid(s: str) -> bool:",
    },
    {
        "id": "max_subarray",
        "difficulty": "Medium",
        "tags": ["array", "dp"],
        "prompt": (
            "给定一个整数数组 nums，找到一个具有最大和的连续子数组（子数组最少包含一个元素），返回其最大和。\n\n"
            "示例：\n"
            "输入：nums = [-2,1,-3,4,-1,2,1,-5,4]\n"
            "输出：6（连续子数组 [4,-1,2,1]）\n"
        ),
        "hidden_tests": [
            {"input": {"nums": [-2, 1, -3, 4, -1, 2, 1, -5, 4]}, "expected": 6},
            {"input": {"nums": [1]}, "expected": 1},
            {"input": {"nums": [5, 4, -1, 7, 8]}, "expected": 23},
        ],
        "function_signature": "def max_sub_array(nums: list[int]) -> int:",
    },
    {
        "id": "lru_cache",
        "difficulty": "Medium",
        "tags": ["design", "hash-table", "linked-list"],
        "prompt": (
            "设计一个 LRU (最近最少使用) 缓存。它应该支持以下操作：\n"
            " - get(key)：如果键存在于缓存中，返回对应的值，否则返回 -1。\n"
            " - put(key, value)：插入 / 更新键值对。如果缓存已满，先淘汰最久未使用的键。\n\n"
            "容量 capacity 在初始化时给定。\n"
            "两个操作的时间复杂度都应为 O(1)。\n"
        ),
        "hidden_tests": [
            {
                "ops": [
                    ["LRUCache", 2],
                    ["put", 1, 1],
                    ["put", 2, 2],
                    ["get", 1],
                    ["put", 3, 3],
                    ["get", 2],
                ],
                "expected_outputs": [None, None, None, 1, None, -1],
            },
        ],
        "function_signature": "class LRUCache:\n    def __init__(self, capacity: int):\n    def get(self, key: int) -> int:\n    def put(self, key: int, value: int) -> None:",
    },
]


def get_problem_by_id(pid: str) -> dict[str, Any] | None:
    for item in PROBLEMS:
        if item["id"] == pid:
            return item
    return None


def list_problem_summaries() -> list[dict[str, Any]]:
    """对外只暴露 id/difficulty/tags/prompt，隐藏测试不出给候选人。"""
    return [
        {
            "id": item["id"],
            "difficulty": item["difficulty"],
            "tags": item["tags"],
            "prompt": item["prompt"],
            "function_signature": item["function_signature"],
        }
        for item in PROBLEMS
    ]
