import sys, os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

import httpx
import json

base = 'http://127.0.0.1:8000'

# 登录
r = httpx.post(f'{base}/api/auth/login', json={"username": "admin", "password": "admin@2026"})
token = r.json()['token']
headers = {'Authorization': f'Bearer {token}'}
print(f'登录成功, user.id={r.json()["user"]["id"]!r}')

# 测试 inbox
print('\n=== Inbox 测试 ===')
r = httpx.get(f'{base}/api/inbox', headers=headers, params={'page_size': 5})
print(f'状态: {r.status_code}')
data = r.json()
print(f'total: {data.get("total")}')
for item in data.get('items', [])[:3]:
    it = item.get('item', {})
    print(f'  - [{it.get("category_l1", it.get("category"))}] {it.get("title", "?")[:40]}')

# 测试获取订阅列表
print('\n=== 订阅列表 ===')
r = httpx.get(f'{base}/api/subs', headers=headers)
data = r.json()
print(f'总数: {data.get("total")}')
for s in data.get('items', []):
    print(f'  - id={s["id"]} title={s["title"]!r} user_id={s["user_id"]!r}')

# 测试删除第一条订阅
if data.get('items'):
    first_id = data['items'][0]['id']
    print(f'\n=== 删除订阅 {first_id} ===')
    r = httpx.delete(f'{base}/api/subs/{first_id}', headers=headers)
    print(f'状态: {r.status_code}')
    print(f'响应: {r.json()}')

    # 验证删除后列表
    r2 = httpx.get(f'{base}/api/subs', headers=headers)
    print(f'删除后订阅数: {r2.json().get("total")}')
