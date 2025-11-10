# 论文分析工具使用指南

## 概述

`analyze_papers.py` 是一个强大的论文分析工具，支持多种分析类型和灵活的参数配置。提供了Python脚本和Bash封装两种使用方式。

## 更新说明（v2.0）

- ✅ 使用 `argparse` 进行专业的参数管理
- ✅ 完整的参数验证和错误处理
- ✅ 支持长短选项（如 `-s` 和 `--sources`）
- ✅ 详细的帮助信息和示例
- ✅ 统一的返回码处理
- ✅ 可配置的输出格式（table/json/csv）
- ✅ 详细输出模式（verbose）

## 快速开始

### 基础用法

```bash
# 使用Python脚本
python scripts/analyze_papers.py <analysis_type> <days> [options]

# 使用Bash封装（推荐）
./scripts/analyze_papers.sh <analysis_type> <days> [options]
```

### 分析类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `authors` | 作者分析，显示发表论文最多的作者 | `./scripts/analyze_papers.sh authors 7` |
| `abstracts` | 摘要分析，统计摘要覆盖率和长度 | `./scripts/analyze_papers.sh abstracts 30` |
| `oa` | 开放获取状态分析 | `./scripts/analyze_papers.sh oa 7` |
| `venues` | 期刊/会议分析 | `./scripts/analyze_papers.sh venues 30` |
| `list` | 论文列表展示 | `./scripts/analyze_papers.sh list 7` |

## 参数说明

### 必需参数

- **analysis_type**: 分析类型（authors, abstracts, oa, venues, list）
- **days**: 查询天数（正整数）

### 可选参数

| 短选项 | 长选项 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| `-s` | `--sources` | str[] | 全部 | 指定数据源（arxiv, crossref, eupmc） |
| `-l` | `--limit` | int | 100 | 限制返回数量（用于list类型） |
| `-t` | `--top` | int | 10 | 显示Top N（用于authors和venues） |
| `-c` | `--config` | str | 自动 | 配置文件路径 |
| `-o` | `--output` | str | table | 输出格式（table, json, csv） |
| `-v` | `--verbose` | flag | false | 详细输出模式 |
| `-h` | `--help` | flag | - | 显示帮助信息 |

## 使用示例

### 1. 作者分析

```bash
# 分析最近7天的作者
./scripts/analyze_papers.sh authors 7

# 仅分析arxiv数据源，显示Top 20
./scripts/analyze_papers.sh authors 30 --sources arxiv --top 20

# 详细输出模式
./scripts/analyze_papers.sh authors 7 --verbose
```

### 2. 摘要分析

```bash
# 分析最近30天的摘要
./scripts/analyze_papers.sh abstracts 30

# 仅分析arxiv和crossref
./scripts/analyze_papers.sh abstracts 30 --sources arxiv crossref
```

### 3. OA状态分析

```bash
# 分析最近7天的OA状态
./scripts/analyze_papers.sh oa 7

# 详细输出
./scripts/analyze_papers.sh oa 7 --verbose
```

### 4. 期刊/会议分析

```bash
# 分析最近30天的期刊/会议
./scripts/analyze_papers.sh venues 30

# 显示Top 20
./scripts/analyze_papers.sh venues 30 --top 20
```

### 5. 论文列表

```bash
# 显示最近7天的论文列表
./scripts/analyze_papers.sh list 7

# 限制显示50条
./scripts/analyze_papers.sh list 7 --limit 50

# 仅显示arxiv论文
./scripts/analyze_papers.sh list 7 --sources arxiv
```

### 6. 高级用法

```bash
# 使用自定义配置文件
./scripts/analyze_papers.sh authors 7 --config configs/config.prod.yaml

# 输出JSON格式（便于后续处理）
./scripts/analyze_papers.sh list 7 --output json

# 组合多个选项
./scripts/analyze_papers.sh list 30 \
    --sources arxiv crossref \
    --limit 100 \
    --output table \
    --verbose
```

## 输出格式

### Table格式（默认）

使用Rich库生成美观的表格输出，适合终端查看。

### JSON格式

```bash
./scripts/analyze_papers.sh authors 7 --output json
```

输出结构化的JSON数据，便于程序处理和进一步分析。

### CSV格式

```bash
./scripts/analyze_papers.sh list 7 --output csv
```

输出CSV格式，可直接导入Excel或其他数据分析工具。

## 参数验证

脚本会自动验证参数的有效性：

- ✅ 天数必须为正整数
- ✅ 限制数量必须为正整数
- ✅ Top N必须为正整数
- ✅ 数据源必须在允许的列表中
- ✅ 分析类型必须有效
- ✅ 输出格式必须支持

## 错误处理

脚本提供友好的错误提示：

```bash
# 无效的天数
$ ./scripts/analyze_papers.sh authors -1
参数错误: 天数必须为正整数，当前值: -1

# 无效的分析类型
$ ./scripts/analyze_papers.sh invalid 7
analyze_papers.py: error: argument analysis_type: invalid choice: 'invalid'

# 缺少参数
$ ./scripts/analyze_papers.sh authors
错误: 需要至少2个参数（analysis_type和days）
使用 './scripts/analyze_papers.sh --help' 查看完整用法
```

## 详细输出模式

使用 `--verbose` 标志可以看到更多调试信息：

```bash
$ ./scripts/analyze_papers.sh list 7 --verbose
分析类型: list
查询天数: 7
数据源: 全部
输出格式: table
开始分析最近 7 天的论文...
配置文件: /path/to/configs/config.test.yaml
数据库路径: ./data/test/test.db
...
```

## 向后兼容性

虽然使用了新的参数格式，但脚本保持了基本的使用方式：

```bash
# 旧的方式仍然可用（位置参数）
python scripts/analyze_papers.py authors 7

# 新的方式（命名参数）
python scripts/analyze_papers.py authors 7 --sources arxiv
```

## 帮助信息

随时使用 `--help` 查看完整的帮助信息：

```bash
./scripts/analyze_papers.sh --help
python scripts/analyze_papers.py --help
```

## 注意事项

1. **配置文件**: 默认会按顺序查找 `config.test.yaml` 和 `config.yaml`
2. **数据源**: 不指定 `--sources` 时会分析所有数据源
3. **限制数量**: `--limit` 主要用于 `list` 类型，其他类型会忽略此参数
4. **Top N**: `--top` 主要用于 `authors` 和 `venues` 类型
5. **返回码**: 成功返回0，失败返回1

## 性能建议

- 对于大量数据（如30天以上），建议使用 `--limit` 限制输出
- 指定 `--sources` 可以加快查询速度
- 使用 JSON 输出格式比 table 格式更快

## 故障排查

### 问题：找不到配置文件

```bash
配置文件不存在，请先创建配置文件
参考: configs/config.yaml.example
```

**解决方案**: 复制示例配置文件并修改

```bash
cp configs/config.yaml.example configs/config.yaml
# 编辑配置文件
```

### 问题：数据库连接失败

**解决方案**: 检查配置文件中的数据库路径是否正确，确保数据库文件存在。

### 问题：没有数据返回

**解决方案**: 
1. 检查时间范围是否有数据
2. 尝试增加天数
3. 使用 `--verbose` 查看详细信息

## 开发者信息

### 添加新的分析类型

1. 在 `papergazer/utils/analyze.py` 中添加分析函数
2. 在 `create_parser()` 的 `choices` 中添加新类型
3. 在 `main()` 函数中添加处理逻辑

### 添加新的输出格式

1. 在 `create_parser()` 中的 `--output` 参数添加新格式
2. 在各分析类型的处理逻辑中添加格式化代码

## 版本历史

- **v2.0** (2025-01-10): 
  - 使用argparse重构参数管理
  - 添加更多可选参数
  - 改进错误处理和验证
  - 更新Bash封装脚本

- **v1.0** (2024-12-01): 
  - 初始版本
  - 基础分析功能

## 许可证

遵循项目主许可证

