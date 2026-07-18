# -*- coding: utf-8 -*-
"""开发工具 MCP 实现。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import difflib
import hashlib
import json
import re
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote

import dns.resolver
import sqlparse
import yaml
import xmltodict
from croniter import croniter
from Crypto.Cipher import AES, DES, DES3, ARC4
from Crypto.Util.Padding import pad, unpad


def parse_jwt(token: str) -> dict:
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("无效的 JWT 格式")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    return {"header": header, "payload": payload, "signature": parts[2]}


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8")


def crypto_process(
    algorithm: str,
    text: str,
    *,
    encrypt: bool = True,
    mode: str = "CBC",
    key: str = "",
    iv: str = "",
) -> str:
    algo = algorithm.upper()
    if algo in ("MD5", "SHA1", "SHA256", "SHA512"):
        h = hashlib.new(algo.lower(), text.encode("utf-8"))
        return h.hexdigest()
    key_b = key.encode("utf-8")
    iv_b = iv.encode("utf-8") if iv else b"\0" * 8
    data = text.encode("utf-8")
    if algo == "AES":
        cipher_mode = AES.MODE_ECB if mode == "ECB" else AES.MODE_CBC
        if encrypt:
            c = AES.new(key_b.ljust(16)[:16], cipher_mode, iv_b[:16] if mode == "CBC" else None)
            enc = c.encrypt(pad(data, AES.block_size))
            return base64.b64encode(enc).decode()
        c = AES.new(key_b.ljust(16)[:16], cipher_mode, iv_b[:16] if mode == "CBC" else None)
        return unpad(c.decrypt(base64.b64decode(text)), AES.block_size).decode("utf-8", errors="replace")
    if algo == "DES":
        cipher_mode = DES.MODE_ECB if mode == "ECB" else DES.MODE_CBC
        if encrypt:
            c = DES.new(key_b.ljust(8)[:8], cipher_mode, iv_b[:8] if mode == "CBC" else None)
            return base64.b64encode(c.encrypt(pad(data, DES.block_size))).decode()
        c = DES.new(key_b.ljust(8)[:8], cipher_mode, iv_b[:8] if mode == "CBC" else None)
        return unpad(c.decrypt(base64.b64decode(text)), DES.block_size).decode("utf-8", errors="replace")
    if algo == "3DES":
        cipher_mode = DES3.MODE_ECB if mode == "ECB" else DES3.MODE_CBC
        if encrypt:
            c = DES3.new(key_b.ljust(24)[:24], cipher_mode, iv_b[:8] if mode == "CBC" else None)
            return base64.b64encode(c.encrypt(pad(data, DES3.block_size))).decode()
        c = DES3.new(key_b.ljust(24)[:24], cipher_mode, iv_b[:8] if mode == "CBC" else None)
        return unpad(c.decrypt(base64.b64decode(text)), DES3.block_size).decode("utf-8", errors="replace")
    if algo == "RC4":
        c = ARC4.new(key_b)
        result = c.encrypt(data) if encrypt else c.decrypt(base64.b64decode(text))
        return base64.b64encode(result).decode() if encrypt else result.decode("utf-8", errors="replace")
    raise ValueError(f"不支持的算法: {algorithm}")


def format_convert_data(text: str, source_format: str, target_format: str) -> str:
    src = source_format.lower()
    tgt = target_format.lower()
    if src == "json":
        obj = json.loads(text)
    elif src == "yaml":
        obj = yaml.safe_load(text)
    elif src == "xml":
        obj = xmltodict.parse(text)
    elif src == "toml":
        import tomllib
        obj = tomllib.loads(text)
    else:
        raise ValueError(f"不支持的源格式: {source_format}")
    if tgt == "json":
        return json.dumps(obj, ensure_ascii=False, indent=2)
    if tgt == "yaml":
        return yaml.dump(obj, allow_unicode=True, default_flow_style=False)
    if tgt == "xml":
        return xmltodict.unparse(obj, pretty=True)
    if tgt == "toml":
        import tomli_w
        return tomli_w.dumps(obj)
    raise ValueError(f"不支持的目标格式: {target_format}")


def dns_lookup(host: str, record_type: str = "A", dns_server: str = "8.8.8.8") -> List[str]:
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [dns_server]
    answers = resolver.resolve(host, record_type.upper())
    return [str(r) for r in answers]


async def port_scan(host: str, ports: List[int], timeout: float = 3.0) -> List[dict]:
    results = []
    for port in ports:
        start = datetime.now()
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
            writer.close()
            await writer.wait_closed()
            ms = (datetime.now() - start).total_seconds() * 1000
            results.append({"port": port, "open": True, "latency_ms": round(ms, 2)})
        except Exception:
            results.append({"port": port, "open": False, "latency_ms": None})
    return results


def color_convert(value: str, source: str, target: str) -> str:
    source, target = source.lower(), target.lower()
    if source == "hex" and target == "rgb":
        c = value.lstrip("#")
        return str((int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)))
    if source == "rgb" and target == "hex":
        parts = [int(x.strip()) for x in value.strip("()").split(",")]
        return "#{:02x}{:02x}{:02x}".format(*parts[:3])
    raise ValueError(f"不支持 {source} -> {target}")


def cron_next_runs(expr: str, count: int = 5) -> List[str]:
    base = datetime.now()
    it = croniter(expr, base)
    return [it.get_next(datetime).strftime("%Y-%m-%d %H:%M:%S") for _ in range(count)]


def text_diff(left: str, right: str) -> List[str]:
    return list(difflib.ndiff(left.splitlines(), right.splitlines()))


def encoder_decoder(text: str, encoding: str, decode: bool = False) -> str:
    enc = encoding.lower()
    if decode:
        if enc == "base64":
            return base64.b64decode(text).decode("utf-8", errors="replace")
        if enc == "hex":
            return bytes.fromhex(text).decode("utf-8", errors="replace")
        if enc == "url":
            return unquote(text)
    else:
        if enc == "base64":
            return base64.b64encode(text.encode()).decode()
        if enc == "hex":
            return text.encode().hex()
        if enc == "url":
            return quote(text)
    raise ValueError(f"不支持的编码: {encoding}")

