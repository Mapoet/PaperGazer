# 配置文件说明

## 概述

PaperGazer 使用 YAML 格式的配置文件管理所有配置项，包括敏感信息（如邮箱、API密钥等）。所有配置都从 YAML 文件读取，不再使用 `.env` 文件或环境变量。

## 配置文件位置

- **示例文件**: `configs/config.yaml.example` - 包含所有配置项的说明和默认值
- **实际配置**: `configs/config.yaml` - 用户的实际配置文件（已加入 `.gitignore`）
- **测试配置**: `configs/config.test.yaml` - 测试时使用的配置文件（已加入 `.gitignore`）

## 必需配置项

### `mailto`
- **用途**: 联系邮箱，用于 Crossref/Unpaywall API 礼貌池
- **类型**: 字符串
- **示例**: `mailto: "your-email@domain.com"`
- **说明**: Unpaywall API 要求使用真实邮箱地址，不能使用 `test@example.com`

## 配置方式

### 1. 创建配置文件

复制示例文件并编辑：

```bash
cp configs/config.yaml.example configs/config.yaml
```

### 2. 编辑配置文件

使用文本编辑器打开 `configs/config.yaml`，修改相应配置项：

```yaml
# 联系邮箱（用于 Crossref/Unpaywall API 礼貌池）
mailto: "your-email@domain.com"

# arXiv 配置
arxiv:
  categories:
    - "eess.SP"
    - "physics.space-ph"
  max_results: 100
  delay_seconds: 3

# 存储配置
store:
  root: "./data"
  db_path: "./data/db.sqlite3"
  papers_dir: "./data/papers"
```

### 3. 使用配置文件

在代码中加载配置：

```python
from papergazer.config import load_config

# 使用默认路径 (configs/config.yaml)
config = load_config()

# 或指定配置文件路径
config = load_config("configs/config.test.yaml")
```

## 所有配置项说明

参考 `configs/config.yaml.example` 文件，其中包含所有可配置项的详细说明和默认值。

主要配置类别：

1. **mailto**: 联系邮箱（必需）
2. **arxiv**: arXiv 相关配置（分类、结果数、延迟等）
3. **cns**: CNS 期刊 ISSN 配置
4. **store**: 存储路径配置
5. **schedule**: 定时任务配置
6. **logging**: 日志配置
7. **retry**: 重试机制配置

## 使用示例

### 运行巡检

```bash
# 使用默认配置文件 (configs/config.yaml)
python -m papergazer.cli check

# 或使用测试配置
python -m papergazer.cli check --config configs/config.test.yaml
```

### 测试脚本

```bash
# 脚本中可以通过参数指定配置文件
python scripts/daily_ingest.py --config configs/config.test.yaml
```

## 验证配置

可以通过以下方式验证配置是否正确加载：

```python
from papergazer.config import load_config

config = load_config()
print(f"Mailto: {config.mailto}")
print(f"ArXiv categories: {config.arxiv.categories}")
print(f"Database path: {config.store.db_path}")
```

## 注意事项

1. **邮箱验证**: Unpaywall API 要求使用真实邮箱地址，不能使用 `test@example.com` 等测试邮箱
2. **安全性**: 
   - `config.yaml` 和 `config.test.yaml` 已加入 `.gitignore`，不会被提交到版本控制
   - `config.yaml.example` 是示例文件，可以安全地提交到版本控制
3. **配置文件优先级**: 
   - 如果指定了配置文件路径，使用指定的文件
   - 如果未指定，默认使用 `configs/config.yaml`
   - 如果配置文件不存在，会抛出 `FileNotFoundError` 并提供提示

## 相关文件

- 配置文件示例: `configs/config.yaml.example`
- 配置加载逻辑: `papergazer/config.py`
- Git 忽略规则: `.gitignore`

---

**文档更新时间**: 2025-11-10
