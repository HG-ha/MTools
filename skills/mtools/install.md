# 将 MTools MCP 接到 OpenClaw / Hermes / Cursor

前提：本机已安装并运行 **MTools**，在 **设置 → MCP 服务** 中开启服务。  
默认地址：`http://127.0.0.1:8765/mcp`（端口可在设置里改）。

同时把本目录（`skills/mtools/`）安装为 Agent Skill，Agent 才会按正确流程调用工具。

---

## 1. Hermes

编辑 `~/.hermes/config.yaml`（或 `$HERMES_HOME/config.yaml`）：

```yaml
mcp_servers:
  mtools:
    url: "http://127.0.0.1:8765/mcp"
    timeout: 300
    connect_timeout: 60
```

Skill 安装（任选其一）：

- 复制本目录到 Hermes workspace 的 `skills/mtools/`
- 或放到 `~/.hermes/skills/mtools/`（以你本机 Hermes 版本文档为准）

验证：

```bash
hermes mcp list
```

对话里先让 Agent 调 `mtools_status`。

---

## 2. OpenClaw

### MCP

按你使用的 OpenClaw 版本，用 **HTTP MCP** 指向：

```text
http://127.0.0.1:8765/mcp
```

常见方式：

- Gateway / 插件里的 MCP 服务器配置（`url`）
- 或用 bundled skill **mcporter** 管理外部 MCP：  
  `mcporter config add` / `mcporter call …`

> 具体字段以 [OpenClaw Skills 文档](https://docs.openclaw.ai/tools/skills) 与当前版本为准。

### Skill

将本目录安装到 OpenClaw 可加载的 skills 根下，例如：

```text
~/.openclaw/skills/mtools/SKILL.md
```

或 workspace：

```text
<workspace>/skills/mtools/SKILL.md
```

也可用：

```bash
openclaw skills install <本仓库或 skills/mtools 的路径/URL>
```

（命令以当前 OpenClaw CLI 为准。）

---

## 3. Cursor

在 Cursor → Settings → MCP → 编辑 `mcp.json`：

```json
{
  "mcpServers": {
    "mtools": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

也可在 MTools **设置 → MCP 服务** 点「复制 Cursor 配置」一键复制。

Skill（可选）：把 `skills/mtools` 拷到项目 `.agents/skills/mtools/` 或个人 `~/.agents/skills/mtools/`。

---

## 4. 自检清单

1. MTools 已启动，MCP 状态为「运行中」
2. 浏览器或 Agent 能访问 `http://127.0.0.1:8765/mcp`
3. 调用 `mtools_status` 返回 `ok: true`
4. 调用 `mtools_help("image.compress")` 能看到参数与示例
5. 用真实绝对路径试一次 `mtools_image_compress`

---

## 5. 常见问题

| 问题 | 处理 |
|------|------|
| 连不上 | 确认 MTools 在跑、防火墙未拦本机 8765、端口未被占用 |
| AI 功能失败 | 在 MTools GUI 对应功能页先下载模型 |
| 路径错误 | 必须用本机绝对路径，如 `C:/Users/.../a.jpg` |
| 录屏 | 仅桌面 GUI，MCP 不支持 |

更多工具映射与工作流见同目录 [SKILL.md](SKILL.md)。
