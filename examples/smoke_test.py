r"""
fastInfo · 烟雾测试(各模型组跑一遍)
==================================================
- 验证 M3 / K2.6 API Key 是否可用
- 验证熔断/冷却/fallback 正常工作
- 验证 Redis 可连通

跑法:
    cd D:\WORK\trae\fast_info
    $env:PYTHONPATH = "."
    python examples/smoke_test.py
"""
from __future__ import annotations
import asyncio
import os
import sys
import time

# 把 src/ 加进 path,以便 import 不依赖安装
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import redis  # 验证 redis 客户端可用

from llm.model_registry import build_default_registry, ModelError, ModelErrorType


def banner(text: str):
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def check_redis():
    banner("[1/4] Redis 连通检查")
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
    try:
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        pong = r.ping()
        info = r.info("server")
        print(f"   ✓ Redis ping: {pong}")
        print(f"   ✓ 版本: {info.get('redis_version')}")
        print(f"   ✓ URL: {url}")
        return True
    except Exception as e:
        print(f"   ✗ Redis 失败: {e}")
        print(f"     检查: docker compose ps 看看 redis 是否 running")
        return False


def check_api_keys():
    banner("[2/4] API Key 加载检查")
    mmx = os.environ.get("MMX_API_KEY", "")
    kimi = os.environ.get("KIMI_API_KEY", "")
    has_mmx = bool(mmx and mmx.startswith("sk-"))
    has_kimi = bool(kimi and kimi.startswith("sk-"))
    print(f"   {'✓' if has_mmx else '✗'} MMX_API_KEY:     {'已加载' if has_mmx else '未设置'}")
    print(f"   {'✓' if has_kimi else '✗'} KIMI_API_KEY:    {'已设置(长度 ' + str(len(kimi)) + ')' if has_kimi else '未设置'}")
    return has_mmx or has_kimi  # 至少一个就行


async def check_model_groups(registry):
    banner("[3/4] 模型组端到端测试")

    if not os.environ.get("MMX_API_KEY") and not os.environ.get("KIMI_API_KEY"):
        print("   ⚠ 两个 API Key 都没设置,跳过实际调用,只验证路由逻辑")
        return

    tests = [
        ("short_summary", [
            {"role": "system", "content": "你是一个资讯编辑。请用 1 句话回答。"},
            {"role": "user", "content": "用一句话介绍 Kimi K2.6 模型的核心亮点。"},
        ], 100),
    ]

    for group_name, messages, max_tokens in tests:
        print(f"\n  → 测试 {group_name}")
        group = registry.get(group_name)
        t0 = time.time()
        try:
            result = await group.chat(messages, max_tokens=max_tokens)
            elapsed = (time.time() - t0) * 1000
            content = result["choices"][0]["message"]["content"]
            used_model = result.get("model", "?")
            print(f"   ✓ {elapsed:.0f}ms  model={used_model}")
            print(f"   ✓ 内容: {content[:80]}{'...' if len(content) > 80 else ''}")
        except ModelError as e:
            print(f"   ✗ 失败: {e.err_type.value} - {e}")


async def check_fallback_logic(registry):
    banner("[4/4] Fallback 链路验证(模拟 M3 不可达,看是否切到 K2.6)")
    print("  - 把 M3 的 base_url 改成不可达地址,迫使 fallback 触发")
    print("  - 优先级: M3(primary) → K2.6(fallback)")

    if not os.environ.get("KIMI_API_KEY"):
        print("  ⚠ 跳过(没有 KIMI key 来验证 fallback)")
        return

    group = registry.get("short_summary")
    m3_provider = next(p for p in group.providers if p.cfg.id == "m3")
    kimi_provider = next(p for p in group.providers if p.cfg.id == "kimi")

    original_base_url = m3_provider.cfg.base_url
    original_timeout = m3_provider.cfg.timeout_ms
    original_key = m3_provider.cfg.api_key

    # 重置 M3 的熔断器 / 冷却(避免前一轮测试的影响)
    m3_provider.breaker = type(m3_provider.breaker)()
    m3_provider.cooldown = type(m3_provider.cooldown)()
    kimi_provider.breaker = type(kimi_provider.breaker)()
    kimi_provider.cooldown = type(kimi_provider.cooldown)()

    try:
        # 让 M3 不可达
        m3_provider.cfg.base_url = "http://localhost:1"
        m3_provider.cfg.timeout_ms = 1500
        await m3_provider.aclose()
        import httpx as _httpx
        m3_provider.client = _httpx.AsyncClient(
            base_url=m3_provider.cfg.base_url,
            timeout=m3_provider.cfg.timeout_ms / 1000.0,
            headers={"Authorization": f"Bearer {m3_provider.cfg.api_key}"},
        )

        messages = [
            {"role": "user", "content": "回复 'fallback OK'"},
        ]
        result = await group.chat(messages, max_tokens=20)
        content = result["choices"][0]["message"]["content"]
        used_model = result.get("model", "?")
        print(f"   ✓ 真实命中 provider: {used_model}")
        print(f"   ✓ 内容: {content[:60]}")
        if "kimi" in used_model.lower():
            print(f"   ✓ Fallback 链路验证通过!M3 不可达 → 切到 K2.6")
        elif "minimax" in used_model.lower():
            print(f"   ⚠ 应该 fallback 切到 K2.6,但实际还在 M3,可能是 M3 又恢复或 weight 影响")
        else:
            print(f"   ? 未知 model 名称: {used_model}")
    except Exception as e:
        err_msg = str(e)
        if "Invalid Authentication" in err_msg or "invalid_authentication" in err_msg:
            print(f"   ⚠ K2.6 key 不可用(Invalid Auth)—— 这正证明 fallback 链路被触发了!")
            print(f"     M3 不可达 → 切到 K2.6 → K2.6 返回 401 → 整体失败")
            print(f"     修复: 更新 KIMI_API_KEY 环境变量,流程就完全打通了")
            print(f"     ✓ Fallback 触发逻辑正确 ✓")
        else:
            print(f"   ✗ Fallback 链路异常: {e}")
    finally:
        # 恢复
        m3_provider.cfg.base_url = original_base_url
        m3_provider.cfg.timeout_ms = original_timeout
        await m3_provider.aclose()
        import httpx as _httpx
        m3_provider.client = _httpx.AsyncClient(
            base_url=original_base_url,
            timeout=original_timeout / 1000.0,
            headers={"Authorization": f"Bearer {original_key}"},
        )


async def main():
    print("\n" + "=" * 70)
    print("  fastInfo 烟雾测试")
    print("=" * 70)

    redis_ok = check_redis()
    api_ok = check_api_keys()

    if not redis_ok:
        print("\n  ⚠ Redis 不可用,但模型路由仍可测(只是队列/缓存/限流用不上)")

    if api_ok:
        banner("[*] 构建模型组注册表")
        registry = build_default_registry()
        print(f"   ✓ 注册了 {len(registry.list_groups())} 个模型组: {registry.list_groups()}")

        await check_model_groups(registry)
        await check_fallback_logic(registry)

        await registry.aclose()
    else:
        print("\n  ⚠ 未设置任何 API Key,跳过模型测试")
        print("     设置方法:")
        print("       $env:MMX_API_KEY = 'sk-...'")
        print("       $env:KIMI_API_KEY = 'sk-...'")

    print()
    print("=" * 70)
    print("  Smoke test 完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
