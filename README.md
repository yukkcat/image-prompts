# Image Prompt Registry

集中抓取、解析和校验公开图片提示词来源，并发布统一格式的静态 JSON。Infinite Canvas、Codex Skills 或其他前端可以直接读取生成结果，不必各自维护来源解析器。

## 内置来源

- Banana Prompt Quicker
- DavidWu GPT Image 2 Prompts
- Awesome GPT Image
- Awesome GPT-4o Image Prompts
- YouMind GPT Image 2
- YouMind Nano Banana Pro

来源配置位于 `sources.json`。同步任务要求所有来源都达到最低条目数；任一来源抓取或解析失败时，不会覆盖上一版 `dist` 数据。

## 使用数据

同步后生成：

- `dist/manifest.json`：版本、总数、来源列表、文件路径和 SHA-256。
- `dist/prompts.json`：全部提示词。
- `dist/sources/<source-id>.json`：按来源拆分的提示词。

消费者应先读取 `manifest.json`，再根据 `path` 获取所需来源。仓库发布到 GitHub 后，可以通过 GitHub Raw、GitHub Pages 或 jsDelivr 读取这些文件。

## 本地同步

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

## 数据字段

每条提示词包含稳定 ID、来源 ID、标题、正文、说明、封面、参考图、标签、作者、原始地址、创建时间和图像模型信息。完整约束见 `schema/prompt.schema.json`。

## 自动更新

`.github/workflows/sync.yml` 每天运行一次，也支持手动触发。只有提示词内容或来源元数据发生变化时才会提交新的 `dist` 文件，避免仅因更新时间变化产生无意义提交。

## 版权

同步代码使用 MIT License。提示词和图片仍属于各上游作者或仓库，本仓库不会重新授权这些内容，也不会复制图片文件。详见 `NOTICE.md`。
