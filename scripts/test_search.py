import sys
sys.path.insert(0, "src")
from storage.mongo_writer import ensure_indexes, search_text, count_items

ensure_indexes()
print()
print(f"items 总数: {count_items()}")
print()
print("--- 搜索测试: 'AI 推理' ---")
results = search_text("AI 推理", limit=5)
for r in results:
    title = r.get("title", "")
    score = r.get("score", 0)
    summary = r.get("summary", "")[:60]
    print(f"  [{score:.2f}] {title[:40]}")
    print(f"           {summary}...")
print()
print("--- 搜索测试: 关键词 '推理' ---")
results = search_text("推理", limit=5)
for r in results:
    print(f"  [{r.get('score', 0):.2f}] {r.get('title', '')[:40]}")
print()
print("--- 搜索测试: '大模型' 限 ifanr ---")
results = search_text("大模型", source="ifanr", limit=3)
for r in results:
    print(f"  [{r.get('score', 0):.2f}] {r.get('title', '')[:40]}")
print()
print("--- 搜索测试: 'OpenAI' ---")
results = search_text("OpenAI", limit=5)
for r in results:
    print(f"  [{r.get('score', 0):.2f}] {r.get('title', '')[:40]}")