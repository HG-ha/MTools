# -*- coding: utf-8 -*-
"""其他工具 MCP 实现。"""

from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import httpx


def upload_image_to_url(file_path: Path, expires_in: str = "7d") -> Tuple[bool, dict | str]:
    try:
        url = "https://imagetourl.net/api/upload/direct"
        with open(file_path, "rb") as f:
            response = httpx.post(
                url,
                files={"file": (file_path.name, f, _mime(file_path))},
                data={"expiresIn": expires_in},
                headers={
                    "origin": "https://imagetourl.net",
                    "referer": "https://imagetourl.net/zh",
                },
                timeout=1800.0,
            )
        if response.status_code == 200:
            result = response.json()
            if "publicUrl" in result:
                return True, {"url": result["publicUrl"], "expiresAt": result.get("expiresAt")}
            if "url" in result:
                return True, {"url": result["url"]}
        return False, response.text
    except Exception as e:
        return False, str(e)


def upload_file_to_url(file_path: Path, storage_type: str = "permanent", temp_hours: str = "24h") -> Tuple[bool, dict | str]:
    try:
        if storage_type == "permanent":
            url = "https://catbox.moe/user/api.php"
            data = {"reqtype": "fileupload"}
        else:
            url = "https://litterbox.catbox.moe/resources/internals/api.php"
            data = {"reqtype": "fileupload", "time": temp_hours}
        with open(file_path, "rb") as f:
            response = httpx.post(
                url,
                files={"fileToUpload": (file_path.name, f, "application/octet-stream")},
                data=data,
                timeout=1800.0,
            )
        if response.status_code == 200:
            result_url = response.text.strip()
            if result_url.startswith("http"):
                return True, {"url": result_url}
        return False, response.text
    except Exception as e:
        return False, str(e)


def windows_update_status() -> dict:
    if platform.system() != "Windows":
        return {"supported": False, "message": "仅支持 Windows"}
    try:
        r = subprocess.run(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "/v", "PauseUpdatesExpiryTime"],
            capture_output=True,
            text=True,
        )
        paused = r.returncode == 0
        return {"supported": True, "updates_paused": paused, "detail": r.stdout.strip() if paused else "未暂停"}
    except Exception as e:
        return {"supported": True, "error": str(e)}


def windows_update_disable() -> Tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "仅支持 Windows"
    reg = r"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings]
"PauseUpdatesExpiryTime"=hex(7):00,00,00,00,00,00,00,00
"""
    with tempfile.NamedTemporaryFile("w", suffix=".reg", delete=False, encoding="utf-16") as tf:
        tf.write(reg)
        path = tf.name
    try:
        r = subprocess.run(["regedit", "/s", path], capture_output=True, text=True)
        return (True, "已尝试暂停 Windows 更新") if r.returncode == 0 else (False, r.stderr or "执行失败")
    finally:
        Path(path).unlink(missing_ok=True)


def windows_update_restore() -> Tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "仅支持 Windows"
    r = subprocess.run(
        ["reg", "delete", r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "/v", "PauseUpdatesExpiryTime", "/f"],
        capture_output=True,
        text=True,
    )
    return (True, "已尝试恢复 Windows 更新") if r.returncode == 0 else (False, r.stderr or "执行失败，可能需要管理员权限")


def _mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
