import sys
sys.path.insert(0, "src")
from llm.model_registry import DEFAULT_GROUPS_SPEC, ProviderConfig, LLMProvider

print("=" * 60)
print("  各组 Kimi 配置(应该全部走 anthropic 协议 + kimi.com/coding)")
print("=" * 60)
for g in DEFAULT_GROUPS_SPEC:
    for prov in g["providers"]:
        if prov["id"] == "kimi":
            print(f"  {g['name']:<22} protocol={prov.get('protocol')}  base={prov['base_url']}  env={prov['api_key_env']}")

print()
print("=" * 60)
print("  Provider 实例化测试(Anthropic 协议 header)")
print("=" * 60)
try:
    cfg = ProviderConfig(
        id="kimi-test",
        base_url="https://api.kimi.com/coding/",
        api_key_env="KIMI_CODING_API_KEY",
        model="kimi-k2.6",
        priority=2,
        protocol="anthropic",
    )
    p = LLMProvider(cfg, breaker=None, cooldown=None)
    headers = dict(p.client.headers)
    print(f"  provider.protocol = {cfg.protocol}")
    print(f"  client.base_url   = {p.client.base_url}")
    print(f"  headers 含 anthropic-version: {'anthropic-version' in headers}")
    print(f"  headers 含 Authorization:    {'Authorization' in headers}")
    print(f"  [OK] 协议适配器正确初始化")
except Exception as e:
    print(f"  [FAIL] {e}")

# 反向验证 OpenAI 协议 provider
print()
print("=" * 60)
print("  反向验证 OpenAI 协议 provider (M3)")
print("=" * 60)
try:
    cfg2 = ProviderConfig(
        id="m3-test",
        base_url="https://api.minimaxi.com/v1",
        api_key_env="MMX_API_KEY",
        model="MiniMax-M3",
        priority=1,
        protocol="openai",
    )
    p2 = LLMProvider(cfg2, breaker=None, cooldown=None)
    headers = dict(p2.client.headers)
    print(f"  provider.protocol = {cfg2.protocol}")
    print(f"  headers 不应含 anthropic-version: {'anthropic-version' not in headers}")
    print(f"  headers 含 Authorization:        {'Authorization' in headers}")
    print(f"  [OK] OpenAI 协议构造正确")
except Exception as e:
    print(f"  [FAIL] {e}")
