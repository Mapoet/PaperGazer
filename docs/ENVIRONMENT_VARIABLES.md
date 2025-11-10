# 环境变量配置说明

## 概述

PaperGazer 支持通过环境变量配置敏感信息（如邮箱、API密钥等），这样可以避免在配置文件中硬编码敏感信息。

## 支持的环境变量

### 必需配置

#### `MAILTO` 或 `PAPERGAZER_MAILTO`
- **用途**: 联系邮箱，用于 Crossref/Unpaywall API 礼貌池
- **示例**: `MAILTO=your-email@domain.com`
- **优先级**: 环境变量 > 配置文件
- **说明**: Unpaywall API 要求使用真实邮箱地址，不能使用 `test@example.com`

### 可选配置

#### `API_KEY` 或 `PAPERGAZER_API_KEY`
- **用途**: API密钥（如果未来需要）
- **示例**: `API_KEY=your-api-key-here`
- **优先级**: 环境变量 > 配置文件

## 配置方式

### 方式1：使用 .env 文件（推荐）

1. 复制 `.env.example` 为 `.env`：
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env` 文件，填写实际值：
   ```bash
   MAILTO=your-email@domain.com
   ```

3. `.env` 文件已加入 `.gitignore`，不会被提交到版本控制

### 方式2：直接设置环境变量

在运行命令前设置环境变量：

```bash
export MAILTO=your-email@domain.com
python scripts/test_unpaywall_query.py
```

或者在命令中直接设置：

```bash
MAILTO=your-email@domain.com python scripts/test_unpaywall_query.py
```

### 方式3：在配置文件中设置

如果环境变量未设置，系统会从配置文件中读取：

```yaml
# configs/config.yaml
mailto: "your-email@domain.com"
```

## 优先级顺序

配置值的优先级（从高到低）：

1. **环境变量** (`MAILTO` 或 `PAPERGAZER_MAILTO`)
2. **配置文件** (`configs/config.yaml` 中的 `mailto`)

## 使用示例

### 测试 Unpaywall API

```bash
# 使用 .env 文件中的邮箱
python scripts/test_unpaywall_query.py 7

# 或直接设置环境变量
MAILTO=your-email@domain.com python scripts/test_unpaywall_query.py 7
```

### 运行巡检

```bash
# 使用 .env 文件中的邮箱
python -m papergazer.cli check

# 或直接设置环境变量
MAILTO=your-email@domain.com python -m papergazer.cli check
```

## 验证配置

可以通过以下方式验证环境变量是否正确加载：

```python
from papergazer.config import load_config

config = load_config()
print(f"Mailto: {config.mailto}")
```

## 注意事项

1. **邮箱验证**: Unpaywall API 要求使用真实邮箱地址，不能使用 `test@example.com` 等测试邮箱
2. **安全性**: `.env` 文件包含敏感信息，不应提交到版本控制
3. **环境变量格式**: 支持两种格式：
   - `MAILTO` (不带前缀)
   - `PAPERGAZER_MAILTO` (带前缀，pydantic-settings 自动处理)

## 相关文件

- 环境变量示例: `.env.example`
- 配置文件示例: `configs/config.yaml.example`
- 配置加载逻辑: `papergazer/config.py`

---

**文档创建时间**: 2025-11-10

