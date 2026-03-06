"""证书校验工具 - 本地校验 + 远端 openssl 命令"""

import hashlib
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

_BEIJING_TZ = timezone(timedelta(hours=8))

from autocertsync.logger import get_logger


def local_cert_valid(cert_path: str) -> bool:
    """本地校验证书文件格式是否有效（使用 openssl）"""
    logger = get_logger()
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-noout", "-text"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True
        logger.warning(f"本地证书校验失败 {cert_path}: {result.stderr.strip()}")
        return False
    except FileNotFoundError:
        logger.warning("本地未安装 openssl，跳过本地校验")
        return True
    except Exception as e:
        logger.warning(f"本地证书校验异常 {cert_path}: {e}")
        return False


def file_sha256(file_path: str) -> str:
    """计算文件 SHA256 哈希"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_cert_hash_command(cert_path: str) -> str:
    """生成远端获取证书哈希的命令"""
    return f"sha256sum {cert_path} 2>/dev/null | awk '{{print $1}}'"


def remote_cert_check_expiry_command(cert_path: str) -> str:
    """生成远端检查证书有效期的命令（输出到期时间）"""
    return f"openssl x509 -in {cert_path} -noout -enddate 2>/dev/null"


def remote_cert_verify_command(cert_path: str) -> str:
    """生成远端验证证书有效性的命令（检查是否过期）"""
    return f"openssl x509 -in {cert_path} -noout -checkend 0 2>/dev/null"


def _parse_openssl_date(date_str: str) -> str:
    """将 openssl 日期字符串转换为北京时间年月日格式"""
    try:
        # openssl 格式: "May 30 12:00:00 2025 GMT"
        dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(_BEIJING_TZ)
        return dt.strftime("%Y年%m月%d日")
    except Exception:
        return date_str


def find_cert_files(directory: str) -> list[str]:
    """在目录中查找证书相关文件"""
    cert_extensions = {".crt", ".pem", ".cer", ".key", ".chain", ".fullchain", ".cert"}
    result = []
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return result
    for f in dir_path.iterdir():
        if f.is_file() and f.suffix.lower() in cert_extensions:
            result.append(str(f))
    return sorted(result)


def get_cert_info(cert_path: str) -> Optional[dict]:
    """获取证书详细信息（域名、有效期、颁发者）"""
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-noout",
             "-subject", "-issuer", "-startdate", "-enddate", "-ext", "subjectAltName"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return None

        info = {"path": cert_path}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("subject="):
                info["subject"] = line[len("subject="):].strip()
            elif line.startswith("issuer="):
                info["issuer"] = line[len("issuer="):].strip()
            elif line.startswith("notBefore="):
                info["not_before"] = _parse_openssl_date(line[len("notBefore="):].strip())
            elif line.startswith("notAfter="):
                info["not_after"] = _parse_openssl_date(line[len("notAfter="):].strip())
            elif "DNS:" in line:
                domains = [d.strip().replace("DNS:", "") for d in line.split(",") if "DNS:" in d]
                info["domains"] = domains
        return info
    except Exception:
        return None
