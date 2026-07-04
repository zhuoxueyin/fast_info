"""POST /api/auth/register · POST /api/auth/login · GET/PATCH /api/auth/me"""
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument

from auth import register as auth_register, login as auth_login, current_user, get_user_collection
from ..deps import require_user
from ..schemas import RegisterRequest, LoginRequest, LoginResponse, UserView, UpdateUserRequest

router = APIRouter(tags=["auth"])


def _user_to_view(u: dict) -> UserView:
    return UserView(
        id=str(u.get("_id") or u.get("id") or ""),
        username=u["username"],
        email=u.get("email"),
        plan=u.get("plan", "free"),
        role=u.get("role", "user"),
        feishu_webhook=u.get("feishu_webhook"),
        wechat_webhook=u.get("wechat_webhook"),
        webhook_url=u.get("webhook_url"),
    )


@router.post("/auth/register", response_model=UserView)
async def register_endpoint(req: RegisterRequest):
    try:
        u = auth_register(req.username, req.password, req.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _user_to_view(u)


@router.post("/auth/login", response_model=LoginResponse)
async def login_endpoint(req: LoginRequest):
    try:
        token, user = auth_login(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[login] unexpected error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"登录服务异常: {e}")
    try:
        from auth import save_session
        save_session(token, user)
    except Exception as e:
        # session 文件写入失败不影响登录流程,仅打印警告
        print(f"[login] save_session failed (non-fatal): {e}")
    return LoginResponse(token=token, user=_user_to_view(user))


@router.get("/auth/me", response_model=UserView)
async def me_endpoint(user: dict = Depends(require_user)):
    coll = get_user_collection()
    full = coll.find_one({"username": user["username"]}) or {}
    return _user_to_view({**user, **full})


@router.patch("/auth/me", response_model=UserView)
async def update_me_endpoint(req: UpdateUserRequest, user: dict = Depends(require_user)):
    update: dict = {}
    if req.email is not None:
        update["email"] = req.email
    if req.feishu_webhook is not None:
        update["feishu_webhook"] = req.feishu_webhook or None
    if req.wechat_webhook is not None:
        update["wechat_webhook"] = req.wechat_webhook or None
    if req.webhook_url is not None:
        update["webhook_url"] = req.webhook_url or None
    if not update:
        return _user_to_view(user)
    coll = get_user_collection()
    updated = coll.find_one_and_update(
        {"username": user["username"]},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _user_to_view(updated)
