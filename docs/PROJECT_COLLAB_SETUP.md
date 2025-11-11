## 协作看板与知识库配置

为保障 P1 及后续阶段的协同效率，项目建立了统一的任务看板与文档知识库，具体说明如下。

### 1. 任务管理看板

- 平台：Trello（可根据团队习惯切换至 JIRA/飞书项目等）
- 看板地址：`https://trello.com/b/PROJECT-PAPERGAZER`  （请在团队内部替换为实际链接）
- 栏目约定：
  1. **Backlog**：待规划事项，含路线图中尚未分解的需求
  2. **Ready**：任务拆解完成、可随时领取
  3. **In Progress**：执行中任务，需同步负责人与预计完成时间
  4. **Review**：待同伴复核/验收，或等待数据验证
  5. **Done**：已完成并整理成果
- 任务卡示例字段：
  - 描述：目标、依赖、验收标准
  - Checklist：子任务及负责人
  - Labels：阶段（P1/P2/...）、任务类型（ETL、NLP、可视化等）
  - Attachments：关联文档、PR 链接或数据快照

### 2. 文档与知识库

- 平台：Project Docs（本仓库 `docs/`）+ Notion（可选）
- 建议结构：
  - `docs/INTELLIGENT_PLATFORM_ROADMAP.md`：总览路线图
  - `docs/INTELLIGENT_PLATFORM_ACTION_PLAN.md`：阶段行动方案
  - `docs/P0_EXECUTION_REPORT.md`：阶段执行记录
  - `docs/LOGGING_CONVENTIONS.md`：日志规范
  - 其他专题文档（GNSS、NLP 模型等）按需创建
- Notion 页面建议：
  - Meeting Notes：会议纪要
  - Decisions Log：关键决策
  - Data Issues：数据异常与处理记录

### 3. 工作流建议

1. 新需求 → 在看板 Backlog 建卡 → 评估后进入 Ready。
2. 领取任务后将卡片拖至 In Progress，并在卡片中标注负责人、预估时间及关联文档。
3. 完成后提交成果/PR，移至 Review；经验证通过后进入 Done。
4. 每周例会对看板进行梳理，更新任务状态并沉淀到知识库。

> 注：若团队最终决定使用其它平台（例如飞书项目/JIRA），请同步更新本文件的看板地址及流程说明，以维持信息一致性。

