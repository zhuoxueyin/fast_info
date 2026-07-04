import sys, os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

import httpx
import json

# 端口走 env(FASTINFO_API_PORT,默认 8000)
base = f"http://127.0.0.1:{os.environ.get('FASTINFO_API_PORT', '8000')}"

print('=== 健康检查 ===')
r = httpx.get(f'{base}/healthz')
print(r.json())

print('\n=== Hot AI分类 (limit=3) ===')
r = httpx.get(f'{base}/api/hot', params={'category': 'AI', 'limit': 3})
data = r.json()
print(f'返回 {len(data.get("items", []))} 条')
for it in data.get('items', []):
    print(f'  - [{it.get("category_l1")}/{it.get("category")}] {it.get("title")[:40]}')
    print(f'    summary: {(it.get("summary") or "")[:60]}')

print('\n=== Hot 科技分类 (limit=3) ===')
r = httpx.get(f'{base}/api/hot', params={'category': '科技', 'limit': 3})
data = r.json()
print(f'返回 {len(data.get("items", []))} 条')
for it in data.get('items', []):
    print(f'  - [{it.get("category_l1")}/{it.get("category")}] {it.get("title")[:40]}')

print('\n=== Stats 统计 ===')
r = httpx.get(f'{base}/api/stats')
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:500])
