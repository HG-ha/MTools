# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from mcp_server import dev_ops, image_ops
from mcp_server.helpers import fail, ok, resolve_input, resolve_output
from mcp_server.handlers import register_handler
from mcp_server.runtime import get_encoding_service, get_output_dir


def register_handlers_only() -> None:
    register_handler("mtools_dev", _mtools_dev_impl())


def register(mcp) -> None:
    fn = _mtools_dev_impl()
    register_handler("mtools_dev", fn)
    mcp.tool()(fn)


def _mtools_dev_impl():
    def mtools_dev(
        action: Literal[
            "base64_to_image", "encoding_detect", "encoding_convert", "json_format", "json_minify",
            "http_request", "encoder_decoder", "regex_test", "timestamp_convert",
            "jwt_parse", "uuid_generate", "color_convert", "dns_lookup", "port_scan",
            "format_convert", "text_diff", "crypto", "sql_format", "cron_parse",
        ],
        text: str = "",
        input_path: str = "",
        output_path: str = "",
        target_encoding: str = "utf-8",
        pattern: str = "",
        timestamp: float = 0,
        timestamp_unit: Literal["s", "ms"] = "s",
        hash_algo: Literal["md5", "sha1", "sha256"] = "sha256",
        method: str = "GET",
        url: str = "",
        headers_json: str = "{}",
        body: str = "",
        body_type: str = "raw",
        source_format: str = "json",
        target_format: str = "yaml",
        color_source: str = "hex",
        color_target: str = "rgb",
        dns_type: str = "A",
        dns_server: str = "8.8.8.8",
        ports: str = "80,443,8080",
        host: str = "",
        cron_expr: str = "",
        cron_count: int = 5,
        crypto_algorithm: str = "SHA256",
        crypto_encrypt: bool = True,
        crypto_mode: str = "CBC",
        crypto_key: str = "",
        crypto_iv: str = "",
        encode_type: str = "base64",
        decode_mode: bool = False,
        left_text: str = "",
        right_text: str = "",
    ) -> str:
        """开发工具：编码/JSON/HTTP/JWT/加密/DNS/端口扫描/格式转换等（WebSocket 请用 mtools_websocket）。"""
        try:
            if action == "base64_to_image":
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "decoded.png"
                image_ops.base64_to_image(text, out)
                return ok({"output_path": str(out)})
            if action == "encoding_detect":
                enc = get_encoding_service()
                return ok(enc.detect_encoding(resolve_input(input_path)))
            if action == "encoding_convert":
                src = resolve_input(input_path)
                out = resolve_output(src, output_path or None)
                enc = get_encoding_service()
                success, message = enc.convert_encoding(src, out, target_encoding)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "json_format":
                return ok({"formatted": json.dumps(json.loads(text), ensure_ascii=False, indent=2)})
            if action == "json_minify":
                return ok({"minified": json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))})
            if action == "http_request":
                from services.http_service import HttpService
                headers = json.loads(headers_json) if headers_json else {}
                ok2, result = HttpService().send_request(method, url, headers=headers, body=body or None, body_type=body_type)
                return ok(result) if ok2 else fail(str(result))
            if action == "encoder_decoder":
                return ok({"result": dev_ops.encoder_decoder(text, encode_type, decode_mode)})
            if action == "regex_test":
                import re
                matches = re.findall(pattern, text)
                return ok({"matches": matches, "count": len(matches)})
            if action == "timestamp_convert":
                if timestamp <= 0:
                    return fail("需要 timestamp")
                ts = timestamp / 1000 if timestamp_unit == "ms" else timestamp
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                return ok({"iso": dt.isoformat(), "local": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"), "timestamp_s": ts})
            if action == "jwt_parse":
                return ok(dev_ops.parse_jwt(text))
            if action == "uuid_generate":
                return ok({"uuid": str(uuid.uuid4())})
            if action == "color_convert":
                return ok({"result": dev_ops.color_convert(text, color_source, color_target)})
            if action == "dns_lookup":
                return ok({"records": dev_ops.dns_lookup(host or text, dns_type, dns_server)})
            if action == "port_scan":
                import asyncio
                port_list = [int(p.strip()) for p in ports.split(",") if p.strip()]
                results = asyncio.run(dev_ops.port_scan(host or text, port_list))
                return ok({"results": results})
            if action == "format_convert":
                return ok({"converted": dev_ops.format_convert_data(text, source_format, target_format)})
            if action == "text_diff":
                return ok({"diff": dev_ops.text_diff(left_text or text, right_text)})
            if action == "crypto":
                result = dev_ops.crypto_process(crypto_algorithm, text, encrypt=crypto_encrypt, mode=crypto_mode, key=crypto_key, iv=crypto_iv)
                return ok({"result": result})
            if action == "sql_format":
                import sqlparse
                return ok({"formatted": sqlparse.format(text, reindent=True, keyword_case="upper")})
            if action == "cron_parse":
                return ok({"next_runs": dev_ops.cron_next_runs(cron_expr or text, cron_count)})
            return fail(f"未知 action: {action}")
        except Exception as exc:
            return fail(str(exc))

    return mtools_dev
