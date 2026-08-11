# Image Prompt Registry

[English](README.md) | [提示词记录格式（英文）](docs/prompt-format.md) | [JSON Schema](schema/prompt.schema.json)

集中抓取、解析和校验公开图片提示词来源，并发布统一格式的静态 JSON。Infinite Canvas、Codex Skills 或其他前端可以直接读取生成结果，不必各自维护来源解析器。

## 发布数据

同步成功后生成：

- `dist/manifest.json`：格式版本、生成时间、总数、来源元数据、文件路径和 SHA-256。
- `dist/prompts.json`：全部标准化提示词记录。
- `dist/sources/<source-id>.json`：按来源拆分的提示词记录。

消费者应先读取 `dist/manifest.json`，再通过 `promptsPath` 获取完整数据，或通过来源条目的 `path` 获取单个来源。对完整性有要求时，可以使用来源条目的 `sha256` 校验文件。

每条记录的字段含义、空值规则、标准化方式、稳定 ID 算法和版本兼容要求见 [Prompt Record Format](docs/prompt-format.md)。机器可读约束见 `schema/prompt.schema.json`。

## 内置来源

- Banana Prompt Quicker
- DavidWu GPT Image 2 Prompts
- Freestylefly GPT Image 2
- Awesome GPT Image
- Awesome GPT-4o Image Prompts
- YouMind GPT Image 2
- YouMind Nano Banana Pro

来源配置位于 `sources.json`。每个来源都有最低条目数要求；任一来源抓取失败、解析失败、格式校验失败或条目数异常时，整个同步会失败，并保留上一版有效的 `dist` 数据。

## 本地开发

要求 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m prompt_registry
.\.venv\Scripts\python -m pytest
```

只抓取并校验，不写入文件：

```powershell
.\.venv\Scripts\python -m prompt_registry --check
```

## 添加或修改来源

1. 在 `sources.json` 中添加或修改来源配置。
2. 在 `prompt_registry/parsers.py` 中实现或更新解析器。
3. 统一通过 `prompt_registry.models.make_prompt` 生成标准记录。
4. 在 `tests/` 中添加解析样例与断言。
5. 发布前运行完整测试和联网的 `--check`。

不要把来源特有字段直接写进生成记录。只有确实需要新的跨来源字段时，才应有意识地升级公共格式版本。

## 自动更新

`.github/workflows/sync.yml` 每天运行一次，也支持手动触发。只有提示词内容或来源元数据变化时才会提交新的生成文件，仅生成时间变化不会产生提交。

## 版权

同步代码和仓库文档使用 MIT License。提示词、图片、名称和其他上游内容仍受各自原始条款约束。本仓库保留来源标识和地址，不会重新授权上游内容，也只保存图片 URL，不复制图片文件。详见 [NOTICE.md](NOTICE.md)。
