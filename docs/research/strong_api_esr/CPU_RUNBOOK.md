# 无显卡运行 BC+ 的实际配置

本机负责实验调度、证据检索、状态更新和日志记录。policy 与 auditor 都由用户授权的远程 EB-GLM-5.2 API 推理。本地不加载模型权重，不需要 CUDA。

本轮已将完整的 100,195 篇 BC+ 语料建立为 SQLite FTS5 BM25 索引：

```text
D:/AgentSearchAssets/BrowseComp-Plus/indexes/esr-sqlite-bm25-20260909.sqlite
```

检索由 Python 进程直接调用 CPU 上的 SQLite，不依赖端口 8000 的检索服务。search 查询完整索引，open/read 使用正常返回的文档与窗口；没有按题号过滤 gold 文档。索引保存语料 SHA256、文档数、分词器与完成标记。

该配置使用新建的 SQLite BM25，与下载的 Lucene BM25、Qwen 稠密检索索引均有区别。当前结果只能归于已记录的检索配置。B、E-off、E-soft 使用相同索引；将来换成稠密检索或重排器时，需要给 baseline 同等能力并重新比较。

已有索引可直接运行，无需重复建索引。需要独立重建时，必须提供不存在的新输出路径：

```powershell
& D:/AgentSearchAssets/.venv-download/Scripts/python.exe -B scripts/build_cpu_index.py `
  --corpus D:/AgentSearchAssets/BrowseComp-Plus/data/prepared/corpus.parquet `
  --output D:/AgentSearchAssets/BrowseComp-Plus/indexes/esr-sqlite-bm25-NEW.sqlite
```

建索引使用已有环境中的 pyarrow。运行检索只使用 Python 标准库；API 与实验入口还使用已有的 httpx、PyYAML。不要把 CPU 检索延迟与远端模型推理延迟混在一起，完整账本分别保存二者。

在仓库根目录运行一个已暴露的历史回归题：

```powershell
$researchRoot = (Get-Content runs/strong_api_esr/CURRENT -Raw).Trim()
python -B -u scripts/strong_api.py run `
  --questions "$researchRoot/dataset_splits/known-regression.questions.jsonl" `
  --qid 120 --arms B E-off E-soft
```

凭证从 ANTHROPIC_AUTH_TOKEN 环境变量或无回显输入读取。运行会产生真实调用并计入全局预算。历史题用于检查工程链路，不能作为新题准确率。继续研究时应先检查已有注册记录，避免重复消耗固定 pilot 的次数。

当前主要资源限制是远端 API 的延迟、上下文容量与调用预算。无显卡不会阻止这条研究路径；全量权重本地推理和 GPU 稠密检索不属于本轮实际配置。
