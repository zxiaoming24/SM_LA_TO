"""
oss_storage.py - 阿里云 OSS 对象存储封装

功能：
1. upload_file() - 上传文件到 OSS
2. get_presigned_url() - 生成签名下载 URL（私有 bucket 可用）
3. delete_file() - 删除 OSS 文件

使用前需要在项目根目录的 .env 中配置：
    OSS_ACCESS_KEY_ID=xxx
    OSS_ACCESS_KEY_SECRET=xxx
    OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
    OSS_BUCKET=all-tame-max-oss
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

try:
    import oss2
except ImportError:
    oss2 = None
    print("⚠️ [OSS] oss2 未安装，文件上传功能不可用。请执行: pip install oss2")


def _load_config() -> dict:
    """从 .env 加载 OSS 配置"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ[key.strip()] = val.strip()
    return {
        "access_key_id": os.getenv("OSS_ACCESS_KEY_ID", ""),
        "access_key_secret": os.getenv("OSS_ACCESS_KEY_SECRET", ""),
        "endpoint": os.getenv("OSS_ENDPOINT", "https://oss-cn-beijing.aliyuncs.com"),
        "bucket": os.getenv("OSS_BUCKET", "all-tame-max-oss"),
    }


def _get_bucket():
    """获取 OSS Bucket 对象"""
    if oss2 is None:
        return None
    cfg = _load_config()
    if not cfg["access_key_id"] or not cfg["access_key_secret"]:
        print("⚠️ [OSS] 缺少 OSS 凭证，请在 .env 中配置")
        return None
    auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
    return oss2.Bucket(auth, cfg["endpoint"], cfg["bucket"])


def _generate_object_key(user_id: str, resource_type: str, filename: str) -> str:
    """生成 OSS 对象键（按用户/类型隔离，保留原文件名以便搜索）"""
    p = Path(filename) if filename else Path("unknown.bin")
    stem = p.stem                     # 原文件名（不含扩展名）
    ext = p.suffix.lower() if p.suffix else ".bin"
    short_id = uuid.uuid4().hex[:8]   # 短 UUID 防止同名文件覆盖
    # 格式: {resource_type}/{user_id}/{原文件名}_{短uuid}{ext}
    # 例: video/admin/队列_a55444dc.mp4
    return f"{resource_type}/{user_id}/{stem}_{short_id}{ext}"


def upload_file(
    local_path: str,
    user_id: str,
    resource_type: str,
    filename: Optional[str] = None,
) -> Optional[str]:
    """
    上传本地文件到 OSS

    Args:
        local_path: 本地文件路径
        user_id: 用户 ID
        resource_type: 资源类型 (ppt, document, ...)
        filename: 原文件名（用于推断扩展名）

    Returns:
        str: OSS 对象键（object key），失败返回 None
    """
    bucket = _get_bucket()
    if bucket is None:
        return None

    local_path = Path(local_path)
    if not local_path.exists():
        print(f"  ❌ [OSS] 文件不存在: {local_path}")
        return None

    object_key = _generate_object_key(user_id, resource_type, filename or local_path.name)

    try:
        # ★★★ 根据文件扩展名设置正确的 Content-Type ★★★
        content_type_map = {
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        suffix = Path(local_path).suffix.lower()
        headers = {}
        if suffix in content_type_map:
            headers["Content-Type"] = content_type_map[suffix]

        result = bucket.put_object_from_file(object_key, str(local_path), headers=headers)
        if result.status == 200:
            print(f"  ✅ [OSS] 上传成功: {object_key} ({local_path.stat().st_size / 1024:.1f} KB)")
            return object_key
        else:
            print(f"  ❌ [OSS] 上传失败: HTTP {result.status}")
            return None
    except Exception as e:
        print(f"  ❌ [OSS] 上传异常: {e}")
        return None


def get_presigned_url(object_key: str, expires_hours: int = 24) -> Optional[str]:
    """
    获取 OSS 对象的签名下载 URL（私有 bucket 使用）

    Args:
        object_key: OSS 对象键
        expires_hours: 链接有效期（小时）

    Returns:
        str: 签名 URL，失败返回 None
    """
    bucket = _get_bucket()
    if bucket is None:
        return None
    if not object_key:
        return None

    try:
        url = bucket.sign_url("GET", object_key, expires_hours * 3600)
        return url
    except Exception as e:
        print(f"  ❌ [OSS] 生成签名 URL 失败: {e}")
        return None


def get_public_url(object_key: str) -> Optional[str]:
    """
    获取 OSS 对象的公开访问 URL（公共 bucket 使用，永不过期）

    Args:
        object_key: OSS 对象键

    Returns:
        str: 公开 URL，格式 https://{bucket}.{endpoint}/{object_key}
    """
    cfg = _load_config()
    bucket_name = cfg.get("bucket", "")
    endpoint = cfg.get("endpoint", "")
    if not bucket_name or not endpoint or not object_key:
        return None
    # 去掉 endpoint 中的 https:// 前缀
    host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{bucket_name}.{host}/{object_key}"


def delete_file(object_key: str) -> bool:
    """
    从 OSS 删除文件

    Args:
        object_key: OSS 对象键

    Returns:
        bool: 是否成功
    """
    bucket = _get_bucket()
    if bucket is None:
        return False
    try:
        bucket.delete_object(object_key)
        print(f"  ✅ [OSS] 已删除: {object_key}")
        return True
    except Exception as e:
        print(f"  ❌ [OSS] 删除失败: {e}")
        return False


def list_files(prefix: str = "", max_keys: int = 100) -> list:
    """
    列出 OSS 上的文件

    Args:
        prefix: 前缀过滤（如 "video/"）
        max_keys: 最大返回数量

    Returns:
        list: [{"key": "...", "size": ..., "last_modified": ..., "filename": ...}, ...]
    """
    bucket = _get_bucket()
    if bucket is None:
        return []

    try:
        result = bucket.list_objects(prefix=prefix, max_keys=max_keys)
        files = []
        for obj in result.object_list:
            # 跳过目录本身（以 / 结尾的）
            if obj.key.endswith("/"):
                continue
            # last_modified 可能是 int 时间戳或 datetime 对象
            lm = obj.last_modified
            if isinstance(lm, (int, float)):
                lm_str = datetime.fromtimestamp(lm, tz=timezone.utc).isoformat()
            elif hasattr(lm, "isoformat"):
                lm_str = lm.isoformat()
            else:
                lm_str = str(lm) if lm else ""
            files.append({
                "key": obj.key,
                "size": obj.size,
                "last_modified": lm_str,
                "filename": Path(obj.key).name,
                "ext": Path(obj.key).suffix.lower(),
            })
        return files
    except Exception as e:
        print(f"  ❌ [OSS] 列出文件失败: {e}")
        return []


def get_object_url(object_key: str, public: bool = True, expires_hours: int = 24) -> Optional[str]:
    """
    获取 OSS 对象访问 URL

    Args:
        object_key: OSS 对象键
        public: 是否返回公开 URL（否则返回签名 URL，有时效）
        expires_hours: 签名 URL 有效期（小时）

    Returns:
        str: 访问 URL，失败返回 None
    """
    if public:
        return get_public_url(object_key)
    else:
        return get_presigned_url(object_key, expires_hours=expires_hours)
