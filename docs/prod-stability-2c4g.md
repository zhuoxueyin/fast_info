# 生产稳定性方案 · 2C4G · kemi-ai.cn

日期:2026-07-09 · 环境:阿里云 ECS 2C4G · 域名:`https://kemi-ai.cn`

## 1. 目标

| 目标 | 标准 |
|---|---|
| 域名稳定可访问 | `https://kemi-ai.cn/` 与 `/healthz` 持续 200 |
| 服务常驻 | 容器 `restart: unless-stopped` + cron 自愈 |
| 资源可控 | 单套 prod 常驻,总容器内存预算 ≤ ~2.2G,留给系统/Caddy/pagecache |

## 2. 入口链路(不要改乱)

```text
用户浏览器
  → Cloudflare? / 公网 DNS → 43.x (本机)
  → Caddy(:443, 自动 HTTPS)  →  reverse_proxy 127.0.0.1:18080
  → web 容器 Nginx(:80)
       ├─ /api /healthz /swagger… → api:8000  (Docker DNS 动态解析)
       └─ / 静态 SPA + /docs
  → api 容器 FastAPI → mongo / redis
  → ingest_daemon / subs_scheduler 后台常驻
```

**铁律**:对外只认 `https://kemi-ai.cn`(Caddy→18080)。不要把 Caddy 改回直连 18000 却忘了 SPA,也不要在生产机并行常驻 `fast_info_dev`。

## 3. 已修根因(502 半挂)

**现象**:首页 200,接口/healthz 502;直连 `18000` 正常。

**根因**:Nginx 启动时把 `api` 解析成固定 IP;api 容器 recreate 后 IP 变了,Nginx 仍打旧 IP。

**修复**:

1. `docker/nginx/default.conf` 使用 `resolver 127.0.0.11` + **变量** `proxy_pass`
2. `deploy-prod.sh` 每次部署 **force-recreate web**
3. `scripts/prod-watchdog.sh` 每 2 分钟探测,web 502 自动 `compose restart web`

热更新 conf(无需 rebuild 镜像):

```bash
bash scripts/prod-apply-nginx.sh
```

## 4. 2C4G 资源预算

| 服务 | mem_limit | 说明 |
|---|---|---|
| mongo | 768m | `--wiredTigerCacheSizeGB 0.5` |
| redis | 192m | maxmemory 128mb |
| api | 512m | FastAPI |
| web | 128m | Nginx 静态 + 反代 |
| ingest_daemon | 384m | LLM 峰值 |
| subs_scheduler | 256m | 调度 |
| **合计上限** | **~2.2G** | 系统+Caddy+pagecache 留 ~1.4G |

日志:全部 `json-file` `max-size=20m × 3`,防止磁盘被日志打满。

**同机 dev**:生产机默认 **stop** `fast_info_dev`(数据 volume 保留,可再起)。

```bash
cd /home/ubuntu/fast_info_dev && docker compose stop
```

## 5. 常驻自愈

```bash
# 安装 cron(每 2 分钟,幂等)
bash scripts/prod-watchdog.sh --install

# 看状态
bash scripts/prod-watchdog.sh --status

# 手动跑一次
bash scripts/prod-watchdog.sh
```

探测顺序:

1. API `18000/healthz` 不通 → restart api  
2. API 通但 `18080/healthz` 不通 → restart web  
3. 本机 web 通但 `https://kemi-ai.cn/healthz` 不通 → restart caddy  

日志:`data/prod-watchdog.log`

## 6. 日常运维命令

```bash
# 部署(只走 master)
cd /home/ubuntu/fast_info
bash scripts/deploy-prod.sh

# 健康
curl -sS https://kemi-ai.cn/healthz
curl -sS http://127.0.0.1:18080/healthz
docker compose ps
docker stats --no-stream

# 日志
docker compose logs -f --tail=100 api web
tail -f data/prod-watchdog.log
```

## 7. 禁止事项(稳定性红线)

| 禁止 | 原因 |
|---|---|
| 生产机常驻 `fast_info_dev` 全套 | 双 mongo/api/worker,2C4G swap 飙升 |
| 只 `compose up api` 不碰 web | 旧方案会 502;新方案动态 DNS 已缓解,但仍建议全套 up |
| `docker compose down -v` | 删 volume = 删生产数据 |
| 在 `/home/ubuntu/fast_info` 上直接改 master 乱 commit | 走分支 → 验证 → 合 master → deploy-prod |
| 关闭 Caddy / 改证书路径无备份 | 域名 HTTPS 入口 |

## 8. 后续可选(非必须)

- 外网 Uptime(UptimeRobot / 自建)告警飞书  
- Caddy 增加 `/healthz` 失败自动日志告警  
- Mongo 迁云托管,进一步降本机内存  
- 生产构建在 CI,机器只 pull 镜像(降部署期 OOM 风险)
