## GROBID 支持说明

PaperGazer 可以使用 [GROBID](https://grobid.readthedocs.io/) 将 PDF 转换为结构化的 TEI XML，同时也支持将已有的纯文本或 XML 内容转换/包装为 TEI。

### 配置

在 `configs/config.yaml` 中添加或修改：

```yaml
grobid:
  enabled: true
  base_url: "http://localhost:8070"
  timeout_seconds: 60
  output_dir: "./data/tei"
  tei_coordinates: false
```

> 若本地没有部署 GROBID，可参考官方文档使用 Docker 启动服务：
> ```bash
> docker run -it --rm -p 8070:8070 lfoppiano/grobid:0.8.0
> ```

### 使用示例

```python
import asyncio
from pathlib import Path

from papergazer.config import load_config
from papergazer.utils import process_fulltext_document


async def main():
    config = load_config("configs/config.yaml")

    # 1. 处理 PDF，调用 GROBID
    pdf_result = await process_fulltext_document(
        config,
        pdf_path=Path("data/papers/sample.pdf"),
        document_id="sample-pdf",
    )
    print(pdf_result.tei_path)  # data/tei/sample-pdf.tei.xml

    # 2. 处理纯文本
    text_result = await process_fulltext_document(
        config,
        text="This is a plain text snippet.\nIt will be wrapped into TEI paragraphs.",
        document_id="plain-text-demo",
    )
    print(text_result.tei_xml[:200])

    # 3. 处理已有 XML（若非 TEI，会自动包装为 TEI 并以 CDATA 形式保存）
    xml_result = await process_fulltext_document(
        config,
        xml="<article><body><p>Hello XML</p></body></article>",
        document_id="xml-demo",
    )
    print(xml_result.source)  # xml


asyncio.run(main())
```

若处于同步上下文，可使用 `process_fulltext_document_sync`。

### 注意事项

1. **PDF 输入需要 GROBID 启用**。否则会抛出 `GrobidDisabledError`。
2. **纯文本 / XML 输入不依赖 GROBID**，仍会保存为 TEI 文件。
3. 默认输出目录：
   - 指定 `output_dir` 参数；
   - 其次使用配置 `grobid.output_dir`；
   - 若仍为空且有 PDF 输入，则使用 PDF 所在目录；
   - 否则回退到 `store.papers_dir`。
4. 文件名会根据 `document_id`、PDF 文件名或随机 ID 生成，不合法字符会被替换为 `_`。


