"""
fastInfo · Banner 配置路由(公开读 + 管理员写)
"""
from fastapi import APIRouter, Depends

from api.deps_admin import require_admin
from storage.mongo_writer import get_banner, set_banner
from api.schemas import BannerConfig, BannerUpdateRequest

router = APIRouter(tags=["banner"])


@router.get("/banner", response_model=BannerConfig)
def read_banner():
    """公开:获取当前 banner 类目配置(公域首页按这个分组)"""
    return get_banner()


@router.put("/banner", response_model=BannerConfig)
def update_banner(payload: BannerUpdateRequest, admin: dict = Depends(require_admin)):
    """管理员:更新 banner 配置"""
    return set_banner(
        categories=payload.categories,
        max_per_category=payload.max_per_category,
        updated_by=admin["username"],
    )