"""原始资料文件浏览与下载路由。

资源文件（PDF / docx 等）存放于项目根目录 resources/，供知识库页面浏览与点击查看。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.config import get_settings
from app.schemas.common import ApiError, NOT_FOUND, ok

router = APIRouter(prefix="/api/knowledge", tags=["resources"])

# 无需展示的元文件
_IGNORED_NAMES = {"README.md", "readme.md", ".DS_Store", "Thumbs.db"}
# 浏览器可直接内联预览的类型，其余类型走下载
_INLINE_EXTS = {".pdf", ".txt", ".md"}
# 支持展示的文件后缀
_SUPPORTED_EXTS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
}


def _resources_dir() -> Path:
    """返回资源目录（相对 backend 目录解析，默认项目根下 resources）。"""
    backend_dir = Path(__file__).resolve().parents[2]
    settings = get_settings()
    return (backend_dir / settings.resources_dir).resolve()


def _list_files(root: Path) -> dict:
    """返回文件树：{ directories: [{name, path, files}], files }。"""
    if not root.exists() or not root.is_dir():
        return {"directories": [], "files": []}

    directories: list[dict] = []
    files: list[dict] = []

    for child in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name in _IGNORED_NAMES:
            continue
        if child.is_dir():
            folder_files: list[dict] = []
            for f in sorted(child.rglob("*")):
                if (
                    f.is_file()
                    and f.name not in _IGNORED_NAMES
                    and f.suffix.lower() in _SUPPORTED_EXTS
                ):
                    folder_files.append(
                        {
                            "name": f.name,
                            "path": f.relative_to(root).as_posix(),
                            "ext": f.suffix.lstrip(".").lower(),
                            "size": f.stat().st_size,
                        }
                    )
            if folder_files:
                directories.append(
                    {"name": child.name, "path": child.name, "files": folder_files}
                )
        elif child.suffix.lower() in _SUPPORTED_EXTS:
            files.append(
                {
                    "name": child.name,
                    "path": child.name,
                    "ext": child.suffix.lstrip(".").lower(),
                    "size": child.stat().st_size,
                }
            )
    return {"directories": directories, "files": files}


def _safe_resolve(root: Path, rel: str) -> Path | None:
    """将相对路径安全解析到 root 内，防止路径穿越。"""
    try:
        target = (root / rel).resolve()
        target.relative_to(root)
        if not target.is_file():
            return None
        return target
    except (ValueError, OSError):
        return None


@router.get("/files")
async def list_resource_files():
    """列出资源目录下的资料文件（按目录分组）。"""
    return ok(_list_files(_resources_dir()))


@router.get("/files/download")
async def download_resource_file(
    path: str = Query(..., min_length=1, description="文件相对路径"),
):
    """下载或预览资料文件：PDF 内联预览，docx 等触发下载。"""
    root = _resources_dir()
    target = _safe_resolve(root, path)
    if target is None:
        raise ApiError(NOT_FOUND, "文件不存在", status_code=404)

    ext = target.suffix.lower()
    inline = ext in _INLINE_EXTS
    media_type = (
        "application/pdf"
        if ext == ".pdf"
        else "text/plain"
        if ext in {".txt", ".md"}
        else "application/octet-stream"
    )
    return FileResponse(
        target,
        media_type=media_type,
        filename=target.name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"Access-Control-Expose-Headers": "Content-Disposition"},
    )
