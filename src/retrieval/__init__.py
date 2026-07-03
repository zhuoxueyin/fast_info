"""
fastInfo · 检索层
==================

v1 实现:**MongoDB 原生 text index**(BM25-like,中文按 unicode token)
v2 计划:BGE-M3 embedding + 向量检索(用户机器装上 torch 后无缝升级)

接口:
    search(query, limit, source, category) -> list[dict]
"""
from __future__ import annotations
from typing import Optional

from storage.mongo_writer import search_text as _mongo_text_search


def search(
    query: str,
    limit: int = 10,
    source: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """
    检索资讯。

    Args:
        query: 关键词或短语(空格分隔 = OR,双引号包 = phrase)
        limit: 返回前 N 条
        source: 限定数据源(如 "ifanr" / "qbitai")
        category: 限定分类(如 "AI" / "科技")

    Returns:
        按 score 排序的 Item 列表,每条带 "score" 字段(textScore)

    Example:
        >>> search("AI 推理", limit=5)
        >>> search("\"推理模型\" 论文", source="ifanr")
    """
    return _mongo_text_search(query, limit=limit, source=source, category=category)


def hybrid_search(
    query: str,
    limit: int = 10,
    *,
    source: Optional[str] = None,
    category: Optional[str] = None,
    use_embedding: bool = False,    # v1 忽略,等 BGE-M3 接好后启用
) -> list[dict]:
    """
    混合检索(text + vector,v1 仅 text)。

    Args:
        use_embedding: True 时叠加向量检索(等 BGE-M3 接好后 work)
    """
    # TODO v2:如果 use_embedding,叠加 LanceDB / Qdrant 向量检索
    return search(query, limit=limit, source=source, category=category)


if __name__ == "__main__":
    print("=" * 60)
    print("  fastInfo 检索层(v1 = MongoDB text search)")
    print("=" * 60)
    print()
    print("搜索: 'AI 推理' (limit=3)")
    print("-" * 60)
    for r in hybrid_search("AI 推理", limit=3):
        print(f"  [{r.get('score', 0):.2f}] {r.get('title', '')[:50]}")
        print(f"           {r.get('summary', '')[:80]}")
        print()