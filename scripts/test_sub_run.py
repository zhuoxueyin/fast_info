"""直接调 run_subscription 看实际跑通流程"""
import sys
sys.path.insert(0, "src")
from subscription import list_subscriptions

subs = list_subscriptions(user_id=None)
print(f"找到 {len(subs)} 个订阅:")
for s in subs:
    print(f"  - {s['_id']} | title={s.get('title')}")
    print(f"    kws={s.get('keywords', [])}")
    print(f"    sources={s.get('sources', [])}")
    print(f"    max={s.get('max_items')}")
    print()

if subs:
    from subscription import run_subscription_sync
    s = subs[1] if len(subs) > 1 else subs[0]
    print(f"\n跑订阅: {s.get('title')}")
    result = run_subscription_sync(s)
    print(f"结果: {result}")
else:
    print("\n没订阅 — 先 register / subscribe")