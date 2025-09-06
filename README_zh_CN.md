<div align="center">
<img src="./img/logo(500x500).png" width="300px" alt="xorbits" />

<p align="center">
  <a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9?style=for-the-badge"></a>
  <a href="./README_zh_CN.md"><img alt="简体中文版自述文件" src="https://img.shields.io/badge/中文介绍-454545?style=for-the-badge"></a>
  <a href="./README_ja_JP.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-d9d9d9?style=for-the-badge"></a>
</p>
</div>
<br />


# LibRAG
LibRAG是一款突破传统RAG架构的通用智能内容召回引擎，通过​​全链路模型推理能力​​重构文档预处理与段落召回流程。产品摒弃了嵌入模型、向量数据库等复杂组件，直接利用大语言模型（LLM）的深层语义理解能力实现端到端的精准检索与召回，适用于企业知识管理、专业领域问答、合规性审查、医疗病例检索、金融风控、AI智能体等多种AI应用场景。


# 架构概览
系统采用多级语义解析 + 统一索引技术，将文本转化为可检索的知识单元，并通过语义路由层实现按需精准召回与答案生成。

![image](./img/framework.png)  

LibRAG 把传统 RAG 拆得更简、也更智能：它用 LLM 深层语义推理来「一站式」完成文档预处理、段落召回、排序与答案生成，完全抛弃了嵌入向量和向量数据库。下面是整体架构图（蓝色框为核心模块，黑色箭头为主要数据/控制流），再分层说明每块组件是如何协同工作的。


![image](./img/structruing.png)  

# 项目功能演示
![image](https://github.com/Yumben-Open-Source-AI/LibRAG/blob/main/img/LibRAG%E4%BA%A7%E5%93%81%E6%BC%94%E7%A4%BA.gif)

## 1 整体分层

### ▍Web UI + API Server

- **Vue 3 + Element-Plus** 前端（`web/`）负责上传文件、配置知识库、查询问答。使用 Vite 构建 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/web/package.json))
- **FastAPI** 后端（`rag-app/main.py`）挂载 `/ai` 路由并开放 REST 接口，启动时建表 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/main.py), [GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/db/database.py))

### ▍文档摄取管线

1. **上传**：文件先写到 `./files`，后台任务异步解析 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/web_server/ai/router.py))
2. **格式解析**：`DocumentParser` 调 `Pdf-Extract-Kit` 等模型（见 `download_models.py`）抽文本/版面 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/download_models.py))
3. **智能分块**：混合「滑窗 + 语义边界」算法拆段，随后多智能体做纠错/脱敏 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README.md), [GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README_zh_CN.md), [GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README_ja_JP.md))
4. **写入 SQLite**：所有段落/元数据存 SQLModel ORM 映射的 `KnowledgeBase / Document / Paragraph …` 表 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/db/database.py))

### ▍LLM 语义索引 & 路由层

- **索引**：不生成向量，而是把「领域→类别→文档→段落」四层元数据存库，并在更新时自动重建 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/web_server/ai/router.py))
- **Router**：查询到来时，LLM（默认 Qwen-14B 或 DeepSeek）按四级 Selector 逐层筛选：
  1. `DomainSelector`
  2. `CategorySelector`
  3. `DocumentSelector`
  4. `ParagraphSelector`（few-shot+规则见源码） ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/selector/paragraph_selector.py))

### ▍检索-排序-生成

- 候选段落先过 BM25 粗排，再由 LLM 重排打分并直接写答案草稿 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/web_server/ai/router.py))
- 若用户开启多段落拼接，答案生成器会把高分段落拼进最终 prompt，用同一 LLM 完成回答。

## 2 技术亮点

| 传统 RAG                      | **LibRAG**                                                   |
| ----------------------------- | ------------------------------------------------------------ |
| 嵌入 + 向量库 + Rerank 多组件 | 单 LLM 即做理解+索引+排序 ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README.md), [GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README_zh_CN.md), [GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/README_ja_JP.md)) |
| 精度依赖专业调参              | 通过语义推理匹配，宣称 >90 % 开箱即用                        |
| 多跳与路由易丢细节            | Selector 链 + 语义 Router 避免年份/主体丢失 ([Medium](https://medium.com/%40giacomo__95/rag-routers-semantic-routing-with-llms-and-tool-calling-b53dd8fae7fa?utm_source=chatgpt.com)) |
| 结构化数据额外 ETL            | 未来通过同一索引层融合表格/DB 数据                           |

这些设计与近一年「无向量库 RAG」「语义路由」的社区趋势一致 ([Medium](https://p-guzman-salas.medium.com/agent-based-rag-a-rag-without-vector-store-28e91f63dd9c?utm_source=chatgpt.com), [website-nine-gules.vercel.app](https://website-nine-gules.vercel.app/blog/howto-rag-without-vector-db?utm_source=chatgpt.com), [swirlaiconnect.com](https://swirlaiconnect.com/blog/using-vectors-without-a-vector-database?utm_source=chatgpt.com), [Medium](https://medium.com/%40shriyansnaik/enhancing-your-rag-pipeline-adding-semantic-routing-for-intent-handling-d95272123460?utm_source=chatgpt.com), [arXiv](https://arxiv.org/html/2404.15869v1?utm_source=chatgpt.com))。

## 3 部署/运行要点

1. **模型下载**：执行 `python download_models.py`，会拉取 PDF-Extract-Kit 和 LayoutReader 权重并自动写入 `magic-pdf.json` ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/download_models.py))
2. **启动后端**：`uvicorn rag-app.main:app --host 0.0.0.0 --port 13113`
3. **前端 Vite 热更**：`pnpm install && pnpm dev`（或 npm/yarn）
4. **持久化**：默认 SQLite，可替换 PostgreSQL 把 `sqlite_url` 改成 `postgresql+psycopg://...` ([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG/raw/main/rag-app/db/database.py))

## 4 未来改进方向

- **多 LLM 协同**：引入 function-call router，把数值计算/代码解释分流到专长模型。
- **段落向量缓存**：虽然主张无向量库，但在高并发场景可增设轻量 FAISS 缓存作首阶段过滤。
- **分布式数据库**：替换 SQLite 为 TiDB / CockroachDB 以应对海量段落。
- **安全策略**：补充身份认证中间件，配置 CORS 白名单。


# 核心技术突破
## 1.文档智能预处理引擎​​
​​动态结构化解析​​：支持PDF、Word、TXT、MarkDown等多格式文档的自动化解析，采用混合分割算法（滑动窗口+语义边界识别）生成连贯的文本块，解决传统分块导致的语义割裂问题。

内容质量增强：内置LLM多智能体、可实现预处理内容纠错、敏感信息脱敏，确保输入数据的完整性与合规性（如医疗文档中的患者信息自动匿名化）。

## 2.推理驱动的段落召回机制
语义推理匹配​​：通过模型直接分析用户查询与文档段落的多维度关联，替代传统向量相似度计算，可识别隐性逻辑关系（如因果链、对比论证）。

​​混合召回策略​​：融合关键词命中与深度语义推理评分，通过自研权重算法实现精准内容定位，召回准确率较传统方法提升40%以上。

## 3.AI原生的索引结构
创新索引结构：不依赖嵌入模型、向量数据库、图数据库，首创AI原生的高效索引结构，更适配大语言模型技术特点。

## 4.自成长免维护架构
自成长​​：文档库修改后直接触发知识库索引微调，常规文档在分钟级内完成知识同步，满足金融、法律等领域的时效性要求。

​​免维护：精准性不会随着文档增加而降低，不依赖于人工优化与干预。


# 对比传统RAG的核心优势

| 维度         | 传统RAG方案                                              | LibRAG方案                                      |
| ------------ | -------------------------------------------------------- | ----------------------------------------------- |
| 技术栈复杂度 | 需集成嵌入模型+向量库+重排序模型                         | 单一推理模型驱动，架构精简                      |
| 召回准确性   | 未经专业调优小于50%，调优成本极高且效果不确定            | 无需调优即大于90%，普通业务人员即可胜任调优工作 |
| 建设维护成本 | 大量人工介入，打标、分块、向量匹配算法迭代、嵌入模型微调 | 全流程自动处理，自成长免维护                    |
| 领域适应性   | 需按垂直领域定制嵌入模型、提示词和标准问题               | 全领域适用                                      |

### 1  基础设施与运维复杂度

| 传统做法                              | 问题                                                         | **LibRAG 改进**                                              |
| ------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 生成嵌入 → 持久化向量 → 维护 ANN 索引 | • 嵌入模型一换就要**全量重算**• 大规模向量索引调参、伸缩、冷热分层都费时费钱 | • 只存**纯文本 + 元数据 (SQLite/PostgreSQL)**，完全**无向量索引**• 模型升级不需要重建任何索引（直接生效）([Medium](https://hasanaboulhasan.medium.com/rag-without-the-vector-db-say-hi-to-multilevel-llm-routing-6e09d12eddfa)) |

------

### 2  检索精度 vs. 召回

| 传统向量检索                                 | 典型痛点                                                     | **LibRAG 多级 LLM Router**                                   |
| -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 余弦/点积最近邻 → 精度往往不高，需要后续重排 | • **高召回/低精度**：经常把主题相近但答案不相关的段落也召回• 需搭建额外重排器 | • **Domain → Category → Document → Paragraph** 四级语义筛选，相当于在检索前就做细粒度「过滤 + 改写」• 命中率提升，重排负担显著下降([meilisearch.com](https://www.meilisearch.com/blog/vector-dbs-rag)) |

------

### 3  查询理解不足

| 传统流程                 | 隐患                                                         | **LibRAG 做法**                                              |
| ------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 把**原始问题**直接转向量 | • 关键意图常常被埋没 (“react 项目组件怎么组织”会检索到“组件是什么”) | LLM 先用**Selector 链**重写、分解问题，再检索；相当于自动「先想关键字，再搜索」的过程([meilisearch.com](https://www.meilisearch.com/blog/vector-dbs-rag)) |

------

### 4  Chunk 粒度与语义断裂

| 传统固定字节/句子分块 | 风险                                                         | **LibRAG 动态语义分块**                                      |
| --------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 用长度阈值截断        | • 重要定义被切成两块，向量失真• Chunk 过多 → 索引膨胀；过少 → 语义稀释 | 解析布局 → 按**目录、标题层级、语义停顿**切块，保证段落自洽；无需在“块大小 vs. 质量”之间做痛苦权衡([Vectorize](https://vectorize.io/rag-vector-database-traps/)) |

------

### 5  更新延迟与索引陈旧

| 向量方案                               | 隐患                               | **LibRAG**                                        |
| -------------------------------------- | ---------------------------------- | ------------------------------------------------- |
| 新文档要跑「提取 → 嵌入 → 插入」流水线 | • 大集群里几十分钟到数小时才可查询 | 插库即用；Selector 实时走最新行，**零延迟**可检索 |

------

### 6  幻觉与可解释性

| 传统                        | 问题                                     | **LibRAG**                                                   |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------ |
| 低精度召回 + 大 Prompt 拼接 | • 噪音段落进入上下文，LLM 输出幻觉难溯源 | 精细筛选使每条证据都**可追溯到单段落**，上下文更短、来源更清晰，从根上降低幻觉 |

------

## 总结

> **LibRAG 把「RAG 的三大交付风险——复杂度、精度、时效」一次性收敛：**
>
> - **去向量化** → 极简运维、模型随迭代。
> - **多级语义 Router** → 精度/可解释性双提。
> - **动态分块 + 元数据索引** → 上线和增量更新秒级见效。

因此，如果你苦恼于「向量库调不准」「检索出来用不上」「嵌入一换全链重跑」这类问题，LibRAG 的设计思路就是现成的对症方案。



# 精准RAG-技术难点

## 1. 多跳（Multi-Hop）问题

所谓“多跳问题”，就是需要从多个数据源或多个步骤中提取信息，最终才能得到答案。比如，你可能需要从一堆报表中找出企业近三年的复合增长率，还要与竞争对手的发展情况进行比较。

**难点**：答案往往横跨多份文档、多个段落，甚至需要先算指标再比较。

 **LibRAG 的做法**

| 机制                                                         | 怎么缓解多跳                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| **四级 Selector 语义路由**（Domain → Category → Document → Paragraph） | LLM 在检索前就把问题拆解成“先锁定领域→分类 → 再选文档 → 再选段落”。这样每一级都是一次小范围“推理-检索”，天然支持多跳链式查找，减少一次性全库检索造成的信息缺失。([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG)) |
| **段落级元数据保留**                                         | 每段都带文档 ID、年份、页码等 meta；下游 LLM 聚合多个证据时可直接引用并做数值计算或对比，不会丢出处。([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG)) |
| **推理-驱动的重排**                                          | 初步召回后由同一 LLM 对候选段落进行“链式推理 + 打分”，将跨文档的关联证据排到前面，保证最终 Answer Synthesis 有完整上下文。([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG)) |

------

## 2. 路由（Routing）问题

相似文件（如不同年份的财报）在内容上非常接近，容易导致关键信息（如年份）在数据处理过程中丢失，从而影响最终结果的准确性。

**难点**：相似文件极多，年份等关键字段容易丢。

 **LibRAG 的做法**

| 痛点                   | 解决方案                                                     |
| ---------------------- | ------------------------------------------------------------ |
| **年份混淆**           | Selector Prompt 会显式把 `{year}`、`{fiscal_period}` 作为 hard-constraint，让 LLM 在选择阶段就过滤掉“年份不符”的段落。 |
| **文本近似导致误召回** | LLM 推理计算深层语义相似度，只有同时满足“词面对得上 + 语义对得上”才能进入下一级。([GitHub](https://github.com/Yumben-Open-Source-AI/LibRAG)) |
| **输出不可追溯**       | 最终回答附带段落 ID，可反向查询源文件页码，实现 end-to-end 可解释。 |

------

## 3. 结构化数据接入

企业中有大量结构化数据（如数据库、Excel），如何在不损失精度的情况下与RAG结合是个挑战。

**难点**：如何把 SQL/Excel 数据与纯文本一起检索且不失精度？

 **LibRAG 的做法**

1. **统一索引层就是数据库**
   - 默认用 SQLite 表存“段落 + 元数据”；往里新增一张 `structured_table`（列名、数值、单位、主键等）即可共用相同 Selector 机制检索。
2. **表格→自然语言视图**
   - 在摄取阶段把一行结构化记录自动转成句子（如「2023 年 Q1 营收 50 亿元」），写进索引；这样检索时 LLM 把它当段落处理，精准度保持不变。
3. **函数调用桥接**
   - 如果需要做聚合/计算（如 CAGR），LibRAG 在 Answer Synthesis Prompt 里预留 `call_sql()`、`call_pandas()` 等占位；当 LLM 识别出“需要算数”时，API 层会触发真正的 DB 或 Pandas 计算，然后把结果再送回 LLM 生成最终答案。

------

## 4. 技术边界 & 与其他能力协同

RAG只是应用的一部分，如何与其他技术（如function call）无缝协作，而不是过度依赖RAG。

**难点**：RAG 只是链条一环，不能包打天下。

 **LibRAG 的做法**

| 场景                         | 协同方式                                                     |
| ---------------------------- | ------------------------------------------------------------ |
| **外部 API / function call** | Selector 判断出“答案需要实时汇率/天气”等外部数据 → 返回 `need_call=xxx` 标记 → 调用外部函数，再把 JSON 结果插回 Prompt。这样 RAG 流程只负责检索本地知识，实时数据由函数提供。 |
| **Agent 框架集成**           | LibRAG API 输出包括 `route_trace`（四级选择历史）+ `evidence_set`，可被 Agent 直接接过去做进一步推理、规划或工具调用。 |
| **模块化部署**               | 文档摄取、索引服务、推理服务都是独立进程；不想用无向量索引时，可把检索微服务换成 Elasticsearch/Weaviate 而不改其余组件。 |

------

### 总结

> **LibRAG 把「Selector 链 + AI-Native 索引 + 函数式扩展」三板斧合起来，针对多跳、路由、结构化、协同这四大痛点给出了一套可落地的工程化解法。**
> 
## 线上体验请联系： 
>http://home.yumben.cn:42800/login

>lsf@yumben.com 请备注：公司名称，使用场景，文档规模
