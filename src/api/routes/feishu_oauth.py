"""飞书 OAuth 单聊绑定 (Day 7 v0.4.1)

替代"用户手填 open_id":通过 OAuth 一键绑定。

流程:
1. 用户 web 点"绑定飞书" → GET /api/auth/feishu/bind
   → 302 重定向到飞书 OAuth URL(scope=contact:user.id:basic)
2. 飞书页面让用户确认授权
3. 飞书 redirect 回 → GET /api/auth/feishu/callback?code=xxx&state=yyy
4. 后端用 code 换 access_token → 拉 user info(open_id/union_id/name/email)
5. 把 feishu_open_id / feishu_name / feishu_union_id 写到 user 文档

需要的 App scope: contact:user.id:basic(读用户基本信息)
需要的 App redirect_uri: 跟 FEISHU_REDIRECT_URI env 一致(默认 http://127.0.0.1:{FASTINFO_API_PORT}/api/auth/feishu/callback,本地 8000 / Docker 预发 18000)
"""
from __future__ import annotations
import secrets
import os
from urllib.parse import urlencode
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx

from ..deps import require_user
from storage.mongo_writer import get_db


router = APIRouter(tags=["feishu:oauth"])

LARK_AUTH_URL = "https://open.feishu.cn/open-apis/authen/v1/index"
LARK_OAUTH_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
LARK_USERINFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"


def _get_app_credentials() -> tuple[str, str, str]:
    """返 (app_id, app_secret, redirect_uri)。任一缺失抛 503。"""
    app_id = os.environ.get("LARK_APP_ID", "")
    app_secret = os.environ.get("LARK_APP_SECRET", "")
    # 默认 redirect_uri 用 env 里的端口(FASTINFO_API_PORT),让本地/Docker 自动对齐
    default_port = os.environ.get("FASTINFO_API_PORT", "8000")
    redirect_uri = os.environ.get(
        "FEISHU_REDIRECT_URI",
        f"http://127.0.0.1:{default_port}/api/auth/feishu/callback",
    )
    if not app_id or not app_secret:
        raise HTTPException(503, "LARK_APP_ID/LARK_APP_SECRET 未配置(管理员需在 fastInfo 启动环境设)")
    return app_id, app_secret, redirect_uri


@router.get("/auth/feishu/bind")
async def bind_start(user: dict = Depends(require_user)):
    """用户点"绑定飞书"按钮 → 返回飞书 OAuth URL + state(前端跳转)。"""
    app_id, _app_secret, redirect_uri = _get_app_credentials()
    state = f"{user['id']}:{secrets.token_urlsafe(16)}"  # state 含 user_id + nonce 防 CSRF
    # 把 state 暂存到 state_store(MongoDB 单文档,TTL 10min)
    db = get_db()
    db["_feishu_oauth_state"].update_one(
        {"state": state},
        {"$set": {"user_id": user["id"], "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}},
        upsert=True,
    )
    params = {
        "app_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": "contact:user.id:basic contact:user.employee_id:basic",
        "state": state,
        "response_type": "code",
    }
    return {"oauth_url": f"{LARK_AUTH_URL}?{urlencode(params)}", "state": state}


@router.get("/auth/feishu/callback")
async def bind_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """飞书回调:用 code 换 access_token + 拿 user info + 写库 + 跳回 /settings"""
    db = get_db()
    # 1) 校验 state(防 CSRF)
    state_doc = db["_feishu_oauth_state"].find_one({"state": state})
    if not state_doc:
        raise HTTPException(400, "state 无效或已过期,请重新发起绑定")
    user_id = state_doc.get("user_id")
    if not user_id:
        raise HTTPException(400, "state 中无 user_id")
    # 2) 用 code 换 user_access_token
    _app_id, app_secret, redirect_uri = _get_app_credentials()
    try:
        r = httpx.post(
            LARK_OAUTH_TOKEN_URL,
            json={
                "client_id": os.environ.get("LARK_APP_ID", ""),
                "client_secret": app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        tok_data = r.json()
    except Exception as e:
        raise HTTPException(502, f"飞书 token 接口失败: {type(e).__name__}: {e}")
    if not tok_data.get("access_token"):
        raise HTTPException(400, f"飞书 oauth token 失败: {tok_data.get('msg')}")
    user_token = tok_data["access_token"]
    # 3) 拿 user info
    try:
        r = httpx.get(
            LARK_USERINFO_URL,
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=10,
        )
        ui = r.json()
    except Exception as e:
        raise HTTPException(502, f"飞书 userinfo 接口失败: {e}")
    if ui.get("code", 0) != 0:
        raise HTTPException(400, f"飞书 userinfo 失败: {ui}")
    feishu_open_id = ui.get("open_id", "")
    union_id = ui.get("union_id", "")
    name = ui.get("name", "")
    email = ui.get("email", "")
    avatar = ui.get("avatar_url", "")
    if not feishu_open_id:
        raise HTTPException(400, f"飞书 userinfo 没返回 open_id:{ui}")
    # 4) 写库
    from datetime import datetime, timezone
    db["users"].update_one(
        {"_id": user_id},
        {"$set": {
            "feishu_open_id": feishu_open_id,
            "feishu_union_id": union_id,
            "feishu_name": name,
            "feishu_email": email,
            "feishu_avatar": avatar,
            "feishu_bind_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    # 5) 清理 state
    db["_feishu_oauth_state"].delete_one({"state": state})
    # 6) 跳回 web /settings(success=1)
    return RedirectResponse(url=f"/settings?feishu_bind=1&open_id={feishu_open_id}")


@router.get("/auth/feishu/status")
async def bind_status(user: dict = Depends(require_user)):
    """查绑定状态(给前端轮询或初次渲染)"""
    db = get_db()
    u = db["users"].find_one({"_id": user["id"]}) or {}
    feishu_open_id = u.get("feishu_open_id", "")
    return {
        "bound": bool(feishu_open_id),
        "open_id": feishu_open_id or None,
        "union_id": u.get("feishu_union_id"),
        "name": u.get("feishu_name"),
        "email": u.get("feishu_email"),
        "avatar": u.get("feishu_avatar"),
        "bind_at": u.get("feishu_bind_at"),
    }


@router.post("/auth/feishu/unbind")
async def bind_unbind(user: dict = Depends(require_user)):
    """解绑(清空 open_id 字段)"""
    db = get_db()
    db["users"].update_one(
        {"_id": user["id"]},
        {"$unset": {
            "feishu_open_id": "",
            "feishu_union_id": "",
            "feishu_name": "",
            "feishu_avatar": "",
            "feishu_bind_at": "",
            "feishu_email": "",
        }},
    )
    return {"ok": True}
