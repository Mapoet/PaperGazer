好的，Mapoet！下面给你一套“**CNS+arXiv 每日巡检 + 按需抓取 OA 全文/非 OA 摘要**”的完整 Python 方案（含接口选型、架构设计、数据表、调度与去重策略、核心代码片段与配置示例）。所有外部接口均选择了**无需授权或仅需邮箱**即可调用的官方/权威来源，并注明关键依据。

---

# 1) 数据源与接口（权威可用）

* **arXiv**：官方 Atom API `http://export.arxiv.org/api/query`，支持 `search_query / start / max_results / sortBy / sortOrder` 分页与排序；返回 Atom（含 `<entry>` 的 `<link>`，其中 `rel=related title=pdf` 指向 PDF）。arXiv 明确说明**每天午夜（当地周期）统一更新**，同一查询一天无需多次调用；并建议批量请求间**加入 3 秒延时**；单次最多 30,000 条、每片不超过 2,000 条。([arXiv][1])

* **Crossref REST API**：面向**期刊论文元数据**的开放接口；支持 **ISSN 过滤**、日期过滤（`from-created-date / from-index-date / from-pub-date` 等），可用 `select` 精简字段，支持游标分页（`cursor=*`）做**每日增量抓取**；官方建议在请求中带 `mailto=you@example.com` 以进入“Polite Pool”。**适合拉取 Nature/Science/Cell 的“最新元数据（含 DOI、标题、作者、摘要（若出版社提供）、全文链接线索）”**。([www.crossref.org][2])

* **Unpaywall API**：按 DOI 查询 OA 状态与**最佳 OA 落点**（`best_oa_location.url_for_pdf / url`），只需提供邮箱参数 `?email=`。**用于获取可合法下载的 PDF 或 OA 登陆页**。([Unpaywall][3])

* **Europe PMC Articles API**：覆盖生命科学文献与预印本；可用 DOI 检索，若文章在 PMC/Europe PMC 存有 OA 版本，可通过 **`/{PMCID}/fullTextXML`** 获取全文 XML（或落到其 PDF 下载）；常用于补充跨出版社的 OA 获取通道。([Europe PMC][4])

* **期刊订阅/增量的 RSS 备选**（可选）：Nature/Science/Cell 均提供 RSS（各站路径不同），可作为“备用提醒源”（**不建议作为主采集源**，因 RSS 字段较少）。([Nature][5])

* **CNS 三刊 ISSN**（便于 Crossref 过滤）

  * Nature：**0028-0836（print），1476-4687（online）**（nature.com 页脚列出）。([Nature][5])
  * Science：**0036-8075（print），1095-9203（online）**。([OpenAlex][6])
  * Cell：**0092-8674（print），1097-4172（online）**。([OpenAlex][7])

---

# 2) 系统总体架构

**语言/库**：Python 3.11+；`httpx`（异步 HTTP）、`feedparser`（解析 arXiv Atom，可选也能用 `lxml`）、`pydantic`（配置与模型）、`SQLAlchemy`/`sqlite3`（存储）、`tenacity`（重试）、`typer`（CLI）、`apscheduler` 或 cron（调度）、`rapidfuzz`（弱匹配去重，可选）。

**模块划分**

* `sources/`

  * `arxiv.py`：构造查询、拉取与解析 Atom、提取 arXiv id/标题/作者/分类/摘要/PDF 链接
  * `crossref.py`：按 **ISSN + 日期** 增量拉取 CNS 新作（DOI、标题、作者、期刊、摘要、publisher 链接等）
  * `unpaywall.py`：按 DOI 取 `is_oa / best_oa_location`（直取 PDF 或 OA 登陆页）
  * `europe_pmc.py`：由 DOI 换 PMCID，再走 `/{PMCID}/fullTextXML` 拉全文
* `store/`

  * `db.py`：SQLite；表结构见下
  * `files.py`：PDF/XML 存储路径规范、重复检查（hash）
* `core/`

  * `ingest.py`：每日巡检 Pipeline（arXiv + Crossref）
  * `fetch.py`：**按需**抓取流程（DOI 或 arXiv id → OA PDF/全文 → 回退到摘要）
* `cli.py`：命令行子命令（`check`, `fetch`, `search`, `export`…）
* `config.yaml`：你的学科、arXiv 分类、CNS 期刊清单、邮箱、抓取窗口等

**数据表（SQLite）**

* `items`
  `id`(pk), `source`(enum: arxiv/crossref), `identifier`(arxiv_id 或 doi),
  `title`, `authors_json`, `venue`, `issn_print`, `issn_online`,
  `published_date`, `updated_date`,
  `doi`, `url_landing`, `is_oa`(bool), `oa_source`(unpaywall/eupmc/arxiv),
  `oa_pdf_url`, `pdf_path`, `abstract_jats`, `ingested_at`, `hash`
* `runs`：`id`, `source`, `last_checkpoint`（ISO 日期/时间戳）
* `seen`（可选）：存历史去重键（doi / arxiv_id 的标准化）

**存储规范**

* `./data/papers/{year}/{doi_sanitized or arxivid}/paper.pdf`
* `./data/papers/{...}/fulltext.xml`（来自 Europe PMC）
* `./data/db.sqlite3`

---

# 3) 巡检与抓取工作流（稳健、可复现）

## A. 每日巡检（定时）

1. **arXiv**

   * 由配置指定分类（如 `eess.SP`, `physics.space-ph`, `astro-ph.IM`, `cs.LG` 等），请求：
     `.../query?search_query=cat:eess.SP+OR+cat:physics.space-ph&sortBy=lastUpdatedDate&sortOrder=descending&max_results=100`
   * **本地按 `<updated>` 过滤**出“晚于上次巡检”的记录（arXiv 结果每日午夜统一刷新，不必同日二刷）。([arXiv][1])
   * 写入 `items`（若已有 DOI 则回填）。

2. **Crossref（CNS）**

   * 以 **ISSN 清单**+ **日期过滤**做增量：
     建议用 `from-index-date=YYYY-MM-DD` + `cursor=*`（官方推荐 Europe PMC 即用此法做日更）；也可混用 `from-created-date`（首存）、`from-update-date`（修订）。([www.crossref.org][8])
   * `/works?filter=issn:0028-0836,1476-4687&from-index-date=2025-11-09&select=DOI,title,author,issued,container-title,ISSN,link,abstract&rows=1000&cursor=* &mailto=you@domain`（示例）
   * 解析并落库；记录 `runs.last_checkpoint`。

> 说明：`from-index-date` 更像“**Crossref 索引更新时间**”窗口，用于“新进/更新”都不漏；`from-pub-date` 是“**最早出版日**”过滤，可能漏掉“补注册/补修订”的条目。([www.crossref.org][9])

## B. 按需抓取（用户输入 DOI 或 arXiv id）

优先级：**arXiv → Unpaywall → Europe PMC → Crossref 摘要**

1. **arXiv id**：直接取 `<link rel=related title=pdf>`（或 `abs → pdf` 映射）下载 PDF。([arXiv][1])
2. **DOI → Unpaywall**：若 `is_oa`，用 `best_oa_location.url_for_pdf`（或 `url`）下载 PDF；存 `oa_source=unpaywall`。([Unpaywall][3])
3. **DOI → Europe PMC**：用 Articles API 搜索 DOI，命中则取 PMCID，再 `/{PMCID}/fullTextXML`（可转 PDF/提取正文）；存 `oa_source=eupmc`。([Europe PMC][4])
4. **若仍非 OA**：调用 Crossref `/works/{doi}` 读取**摘要**（若出版社有存入）；存 `abstract_jats`。([www.crossref.org][2])

---

# 4) 速用代码片段（可直接嵌入你的工程）

> 依赖：`pip install httpx feedparser typer pydantic sqlalchemy tenacity`

**(1) Crossref：按 ISSN+日期 增量拉取**

```python
# crossref.py
import httpx, datetime as dt

CR_API = "https://api.crossref.org/works"

async def fetch_crossref_issn_increment(issns, since, mailto, rows=1000):
    params = {
        "filter": f"issn:{','.join(issns)},from-index-date:{since}",
        "select": "DOI,title,author,issued,container-title,ISSN,link,abstract",
        "rows": rows,
        "sort": "indexed",
        "order": "asc",
        "cursor": "*",
        "mailto": mailto,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            r = await client.get(CR_API, params=params)
            r.raise_for_status()
            data = r.json()["message"]
            for item in data.get("items", []):
                yield item
            cur = data.get("next-cursor")
            if not cur: break
            params["cursor"] = cur
```

> 依据：Crossref 支持日期过滤（`from-index-date`等）、`select` 精简字段与游标分页；建议附 `mailto`。([www.crossref.org][9])

**(2) arXiv：分类巡检 + 解析 PDF 链接**

```python
# arxiv.py
import feedparser, httpx

ARXIV = "http://export.arxiv.org/api/query"

async def query_arxiv(cats: list[str], max_results=100):
    q = "+OR+".join([f"cat:{c}" for c in cats])
    params = {
        "search_query": q,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        text = (await client.get(ARXIV, params=params)).text
    feed = feedparser.parse(text)
    for e in feed.entries:
        pdf = None
        for link in e.get("links", []):
            if link.get("rel") == "related" and link.get("title") == "pdf":
                pdf = link.get("href")
        yield {
            "arxiv_id": e.id.rsplit("/",1)[-1],
            "title": e.title,
            "summary": e.summary,
            "updated": e.updated,
            "pdf": pdf,
            "doi": getattr(e, "arxiv_doi", None),
        }
```

> 依据：arXiv API 的参数、返回 Atom、`<link>` 中 `rel=related title=pdf` 为 PDF 链接；每日更新与分页限制。([arXiv][1])

**(3) Unpaywall：按 DOI 取最佳 OA**

```python
# unpaywall.py
import httpx

UPW = "https://api.unpaywall.org/v2"

async def best_oa(doi: str, email: str):
    url = f"{UPW}/{doi}"
    r = httpx.get(url, params={"email": email}, timeout=30)
    r.raise_for_status()
    js = r.json()
    if js.get("is_oa"):
        loc = js.get("best_oa_location") or {}
        return {"is_oa": True, "pdf": loc.get("url_for_pdf"), "landing": loc.get("url")}
    return {"is_oa": False}
```

> 依据：Unpaywall `/v2/{doi}` 返回 `is_oa` 与 `best_oa_location`（含 `url_for_pdf`）。([Unpaywall][3])

**(4) Europe PMC：DOI → PMCID → FullTextXML**

```python
# europe_pmc.py
import httpx

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

def doi_to_pmcid(doi: str) -> str | None:
    q = f"search?query=DOI:{doi}&format=json"
    r = httpx.get(f"{EPMC}/{q}", timeout=30)
    r.raise_for_status()
    hits = r.json().get("resultList", {}).get("result", [])
    for it in hits:
        if "pmcid" in it:
            return it["pmcid"]
    return None

def fetch_fulltext_xml(pmcid: str) -> bytes:
    r = httpx.get(f"{EPMC}/{pmcid}/fullTextXML", timeout=60)
    r.raise_for_status()
    return r.content
```

> 依据：Europe PMC Articles API 与 `/{PMCID}/fullTextXML` 全文端点。([Europe PMC][4])

**(5) 抓取调度逻辑（按需）**

```python
# fetch.py
from pathlib import Path
from .unpaywall import best_oa
from .europe_pmc import doi_to_pmcid, fetch_fulltext_xml

def save_bytes(p: Path, data: bytes):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return str(p)

async def fetch_by_identifier(identifier: str, email: str, outdir=Path("data/papers")):
    if identifier.lower().startswith("arxiv:") or "/" not in identifier:
        # 认为是 arXiv id
        arxid = identifier.split(":")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxid}.pdf"
        b = httpx.get(pdf_url, timeout=60).content
        return {"pdf_path": save_bytes(outdir / arxid / "paper.pdf", b), "source": "arxiv"}

    doi = identifier.lower()
    upw = await best_oa(doi, email)
    if upw.get("is_oa") and (u := (upw.get("pdf") or upw.get("landing"))):
        b = httpx.get(u, timeout=60).content
        return {"pdf_path": save_bytes(outdir / doi.replace("/","_") / "paper.pdf", b), "source": "unpaywall"}

    pmcid = doi_to_pmcid(doi)
    if pmcid:
        xml = fetch_fulltext_xml(pmcid)
        return {"xml_path": save_bytes(outdir / doi.replace("/","_") / "fulltext.xml", xml), "source": "europe_pmc"}

    # 回退：Crossref 摘要（省略：调用 /works/{doi} 取 abstract 字段）
    return {"abstract_only": True}
```

---

# 5) 配置与 CLI（示例）

**`config.yaml`**

```yaml
mailto: "you@domain.com"       # Crossref/Unpaywall 联系邮箱
arxiv:
  categories: ["eess.SP","physics.space-ph","astro-ph.IM","cs.LG"]
  max_results: 100
cns:
  issn:
    nature: ["0028-0836","1476-4687"]
    science: ["0036-8075","1095-9203"]
    cell: ["0092-8674","1097-4172"]
store:
  root: "./data"
schedule:
  hour: 7        # Asia/Singapore 每天 07:00 运行
```

**CLI 子命令（Typer）**

* `check`：跑每日巡检（arXiv + CNS via Crossref），写库。
* `fetch DOI_or_arxivid`：即时抓取 OA 全文或回退摘要。
* `search --q "GNSS radio occultation"`：可选：透传 Crossref / arXiv 查询。
* `export --since 2025-11-01 --format csv`：导出新论文清单。

---

# 6) 去重与质量控制

* **主键**：`doi`（有则唯一）；对 arXiv 用 `arxiv_id`。
* **归一化**：DOI 小写、去空格；arXiv id 去版本号（保留 `vN` 另存 `updated_date` 追踪更新）。
* **日期策略**：Crossref 以 `from-index-date` 做日更（不漏补注册/修订）；arXiv 使用 `<updated>` 与本地 `last_checkpoint` 比较。([www.crossref.org][8])
* **礼貌与限流**：arXiv 相邻请求加 **≥3s** 间隔；Crossref 请求中加 `mailto` 并合理分页；失败重试（指数退避）。([arXiv][1])

---

# 7) 调度部署

* **本机/服务器**：`apscheduler`（应用内定时）或系统 `cron`（更可靠）。
* **日志**：结构化日志（json），记录每源抓取数、失败重试、PDF 命中率。
* **存档**：PDF/XML 与 SQLite 每周归档；防重复下载（文件存在则跳过，或比对 ETag/Content-Length）。

---

# 8) 合规与边界

* **不跨越付费墙**：仅走 OA 渠道（arXiv / Unpaywall / Europe PMC），或使用 Crossref 元数据中的**摘要**。([www.crossref.org][2])
* **出版社专有 API（可选）**：Springer Nature/Elsevier 等均有开发者平台，但多数需要申请 key/受限；本方案优先选用**开放接口**即可覆盖需求。

---

## 你可以直接做的两步

1. 把上面代码片段按模块存到你的工程里（或我可以按你的偏好整合成单文件/包结构）。
2. 按你的学科改好 `config.yaml` 中的 arXiv 分类&邮箱，先跑：

   ```bash
   python -m yourpkg.cli check   # 首次巡检
   python -m yourpkg.cli fetch 10.1038/s41586-xxxx-xxxx-x   # 测试 DOI 抓取
   python -m yourpkg.cli fetch arXiv:2501.01234             # 测试 arXiv 抓取
   ```

若你希望，我可以把以上模块**打包成一个可运行的最小仓库（含 Typer CLI、SQLite 建表、简单 UI 导出）**，并按你现在的 GNSS 学科把 arXiv 分类与关键词预置好。

[1]: https://info.arxiv.org/help/api/user-manual.html "arXiv API User's Manual - arXiv info"
[2]: https://www.crossref.org/documentation/retrieve-metadata/rest-api/?utm_source=chatgpt.com "REST API"
[3]: https://unpaywall.org/products/api?utm_source=chatgpt.com "REST API"
[4]: https://europepmc.org/RestfulWebService?utm_source=chatgpt.com "Articles RESTful API"
[5]: https://www.nature.com/nature/research-articles "Research articles | Nature"
[6]: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/filter-entity-lists?utm_source=chatgpt.com "Filter entity lists"
[7]: https://docs.openalex.org/api-entities/works/work-object/location-object?utm_source=chatgpt.com "Location object"
[8]: https://www.crossref.org/blog/using-the-crossref-rest-api.-part-12-with-europe-pmc/?utm_source=chatgpt.com "Using the Crossref REST API. Part 12 (with Europe PMC)"
[9]: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/?utm_source=chatgpt.com "Tips for using the Crossref REST API"
