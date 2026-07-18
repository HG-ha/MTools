# MTools 内置 MCP

MTools 桌面应用可在本地暴露 **Streamable HTTP MCP**，供 OpenClaw、Hermes、Cursor 等 Agent 调用桌面版工具能力（63 项 tool_id，不含 Markdown 查看器）。

## 启用

1. 打开 MTools → **设置 → MCP 服务**
2. 打开开关，可选修改端口（默认 `8765`）
3. 复制连接地址或「Cursor 配置」

默认端点：

```text
http://127.0.0.1:8765/mcp
```

服务随 MTools 进程启停；关闭应用即停止 MCP。

## Agent Skills

面向 OpenClaw / Hermes 的用法说明在仓库：

```text
skills/mtools/SKILL.md      # Agent 调用规范与工作流
skills/mtools/install.md    # 各平台接入配置
```

安装 Skill 后，Agent 会优先使用原子工具（如 `mtools_image_compress`），并在不确定时先调 `mtools_help`。

## 工具面

| 类型 | 说明 |
|------|------|
| 原子工具 | `mtools_<category>_<action>`，每工具仅含该场景参数 |
| `mtools_help` / `mtools_tool_ids` | 查参数与能力列表 |
| `mtools_run` | 统一入口：`tool_id` + `params_json` |
| `mtools_websocket` | WebSocket 完整生命周期 |
| `mtools_subtitle_convert` / `mtools_ai_subtitle_fix` | 字幕独立工具 |

推荐调用顺序：

```text
mtools_status → mtools_help(tool_id) → 原子工具
```

## 限制

- 文件路径必须是本机绝对路径
- AI/ONNX 功能需用户先在 GUI 下载模型
- `video.screen_record` 仅 GUI，MCP 不可用
- 部分能力相对 GUI 为简化实现（复杂可视化裁剪、完整增强管线等）

## 开发说明

实现位于 `src/mcp_server/`，生命周期由 `src/services/mcp_server_service.py` 管理。
