# AI API 服务商

MTools 的 AI 相关功能（字幕修复、AI 翻译、文本翻译等）均使用 **OpenAI 兼容接口**，你可以自行选择 API 服务商并填写 Base URL、API Key 和模型名称。

## 支持的服务商

| 优先级 | 服务商 | Base URL | 说明 |
|--------|--------|----------|------|
| ⭐ 推荐 | [Atlas Cloud](https://www.atlascloud.ai/) | `https://api.atlascloud.ai/v1` | 一个 API 接入 300+ 模型，OpenAI 兼容，支持 LLM / 图像 / 视频 / 音频 |
| 通用 | OpenAI | `https://api.openai.com/v1` | 官方 OpenAI API |
| 通用 | 其他兼容服务 | 按服务商文档填写 | 只要支持 `/v1/chat/completions` 即可 |

> Atlas Cloud 为本项目提供 API 赞助支持，详见 [README](../README.md#合作伙伴--赞助)。

## 在 MTools 中配置

以 **Atlas Cloud** 为例：

1. 前往 [Atlas Cloud](https://www.atlascloud.ai/) 注册并获取 API Key
2. 在对应功能中填写：
   - **Base URL**：`https://api.atlascloud.ai/v1`
   - **API Key**：你的 Atlas Cloud API Key
   - **模型**：从 [Model Library](https://www.atlascloud.ai/models) 选择模型 ID

### 适用功能

| 功能 | 配置位置 |
|------|----------|
| AI 字幕修复 | 视频配字幕 / 语音转文字 → 预处理设置 |
| AI 翻译 | 视频配字幕 → 翻译引擎；文本翻译 → AI 翻译 |
| 其他 OpenAI 兼容功能 | 各工具视图中的 Base URL / API Key / 模型字段 |

## 参考链接

- [Atlas Cloud 开发者文档](https://atlascloud.ai/docs/en/)
- [Atlas Cloud Get Started](https://atlascloud.ai/docs/en/models/get-start)
