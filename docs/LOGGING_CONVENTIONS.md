## 日志规范（PaperGazer）

为确保各模块日志输出一致、便于排查问题，制定如下规范：

### 1. 日志目录与命名

- 默认日志根目录：`./logs/`
- 子目录建议：
  - `./logs/app/`：主应用运行日志（如 CLI、定时任务）
  - `./logs/etl/`：ETL/数据拉取脚本日志
  - `./logs/errors/`：异常或告警日志（可使用 `TimedRotatingFileHandler` 分文件）
- 日志文件命名规则：`{模块名}_{日期}.log`，例如 `daily_ingest_2025-11-11.log`

### 2. 日志级别

统一使用 Python `logging` 模块等级：

- `DEBUG`：调试信息（仅本地或特定诊断时开启）
- `INFO`：关键流程节点、成功摘要
- `WARNING`：非致命异常 / 重试提示
- `ERROR`：导致任务失败的错误
- `CRITICAL`：系统级错误（极少使用）

### 3. 日志格式

建议格式（与 `logging` 配置保持一致）：

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

- `asctime`：包含时区，例如 `2025-11-11 12:34:56,789`
- `name`：模块或 logger 名称（如 `papergazer.utils.daily_ingest`）

### 4. 日志配置示例

在 `config.yaml` 中增加或调整：

```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/app/papergazer.log"
```

在代码中统一调用 `setup_logging(config.logging)`，确保日志输出到指定目录。

### 5. 实施步骤

1. 在项目根目录创建 `logs/`（并在 `.gitignore` 中忽略日志文件）。
2. 将现有脚本中自定义 `basicConfig` 更新为 `papergazer.utils.setup_logging`。
3. 每个脚本/模块使用模块 logger：
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info("任务开始...")
   ```
4. 对批处理脚本输出关键统计（处理数量、耗时、失败列表），便于追踪。
5. 异常捕获：`logger.exception("任务失败")`，确保堆栈信息写入日志。

> 后续可扩展集中式日志（如 ELK/Grafana Loki），但 P1 阶段以本地文件记录为主。

