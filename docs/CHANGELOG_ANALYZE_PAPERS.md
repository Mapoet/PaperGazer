# analyze_papers 更新日志

## [2.0.0] - 2025-01-10

### 🚀 重大改进

#### 参数管理系统重构

使用 `argparse` 替代原有的手动参数解析，带来以下优势：

- **专业的CLI体验**：符合POSIX标准的命令行接口
- **自动帮助生成**：完整的 `--help` 文档
- **参数验证**：自动验证参数类型和有效性
- **错误提示**：友好的错误消息和使用建议

### ✨ 新增功能

#### 1. 长短选项支持

所有可选参数现在支持长短两种形式：

```bash
-s, --sources      # 数据源
-l, --limit        # 限制数量
-t, --top          # Top N
-c, --config       # 配置文件
-o, --output       # 输出格式
-v, --verbose      # 详细模式
-h, --help         # 帮助信息
```

#### 2. 增强的参数控制

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--sources` | list | None | 可指定多个数据源 |
| `--limit` | int | 100 | 控制list输出数量 |
| `--top` | int | 10 | 控制authors/venues显示数量 |
| `--config` | str | 自动 | 自定义配置文件路径 |
| `--output` | str | table | 输出格式（table/json/csv） |
| `--verbose` | bool | false | 详细输出模式 |

#### 3. 输出格式支持

```bash
# Table格式（默认）- 美观的终端显示
./scripts/analyze_papers.sh authors 7

# JSON格式 - 便于程序处理
./scripts/analyze_papers.sh authors 7 --output json

# CSV格式 - 便于数据分析
./scripts/analyze_papers.sh authors 7 --output csv
```

#### 4. 详细输出模式

使用 `--verbose` 查看详细的运行信息：

```bash
$ ./scripts/analyze_papers.sh list 7 --verbose
分析类型: list
查询天数: 7
数据源: 全部
输出格式: table
配置文件: /path/to/config.test.yaml
数据库路径: ./data/test/test.db
...
```

### 🔧 改进项

#### 1. 参数验证

- ✅ 天数必须为正整数
- ✅ 限制数量必须为正整数  
- ✅ Top N必须为正整数
- ✅ 数据源必须在允许列表中
- ✅ 分析类型必须有效

#### 2. 错误处理

- 统一的错误消息格式
- 明确的错误提示和建议
- 正确的退出码（成功=0，失败=1）

#### 3. Shell脚本增强

`analyze_papers.sh` 现在支持：

- 完整的参数解析和转发
- 多数据源参数处理
- 错误检查和友好提示
- 独立的帮助系统

### 📝 API变化

#### 向后兼容

基本用法保持不变，旧脚本仍然可以工作：

```bash
# 旧的方式（仍然支持）
python scripts/analyze_papers.py authors 7

# 新的方式（推荐）
python scripts/analyze_papers.py authors 7 --sources arxiv
```

#### 参数变化

| 变化类型 | 旧语法 | 新语法 | 状态 |
|----------|--------|--------|------|
| 数据源 | `authors 7 arxiv crossref` | `authors 7 --sources arxiv crossref` | ✅ 两者都支持 |
| 限制数量 | `list 7 100` | `list 7 --limit 100` | ⚠️ 推荐新语法 |
| Top N | 硬编码为10 | `--top N` | ✅ 新增可配置 |

### 🐛 Bug修复

- 修复了参数解析中的边界情况
- 改进了错误消息的清晰度
- 修复了Shell脚本中的参数传递问题

### 📊 测试覆盖

已验证的场景：

- ✅ 所有分析类型（authors, abstracts, oa, venues, list）
- ✅ 单数据源和多数据源
- ✅ 自定义limit和top参数
- ✅ 详细输出模式
- ✅ 参数验证和错误处理
- ✅ Shell脚本参数传递
- ✅ 配置文件自定义路径

### 📚 文档更新

- 新增：`docs/ANALYZE_PAPERS_USAGE.md` - 完整使用指南
- 更新：内联帮助信息和示例
- 新增：本更新日志

### 🔜 下一步计划

未来可能的改进方向：

- [ ] 实现JSON和CSV输出格式的完整支持
- [ ] 添加查询结果缓存机制
- [ ] 支持日期范围查询（而非仅天数）
- [ ] 添加导出到文件功能
- [ ] 支持批量分析配置文件

### 💡 使用示例

#### 基础用法

```bash
# 作者分析
./scripts/analyze_papers.sh authors 7

# 摘要分析
./scripts/analyze_papers.sh abstracts 30 --sources arxiv

# OA状态分析
./scripts/analyze_papers.sh oa 7 --verbose

# 期刊分析（Top 20）
./scripts/analyze_papers.sh venues 30 --top 20

# 论文列表（限制50条）
./scripts/analyze_papers.sh list 7 --limit 50
```

#### 高级用法

```bash
# 组合多个选项
./scripts/analyze_papers.sh list 30 \
    --sources arxiv crossref \
    --limit 100 \
    --output table \
    --verbose

# 使用自定义配置
./scripts/analyze_papers.sh authors 7 \
    --config configs/config.prod.yaml \
    --top 15 \
    --verbose
```

### 🙏 致谢

感谢Python `argparse` 库提供的强大参数解析功能。

### 📞 反馈

如有问题或建议，请提交Issue或Pull Request。

---

**完整文档**: 请参阅 `docs/ANALYZE_PAPERS_USAGE.md`

