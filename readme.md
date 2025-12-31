# arXiv Insight

> 一个面向科研人员的智能论文分析工具，自动解析 arXiv 预印本 PDF，结合大语言模型（LLM）生成深度摘要、创新点提炼与研究趋势洞察。

---

## 🎯 1. 项目目的与已实现功能

### 目的
在信息爆炸的科研环境中，帮助研究者**快速理解论文核心价值**，减少阅读负担，提升文献调研效率。  
本项目聚焦 **arXiv 预印本**，通过自动化 PDF 解析 + LLM 智能分析，提供超越传统摘要的“高维洞察”。

### 已实现功能
- ✅ **自动抓取 arXiv 论文元数据**（标题、作者、摘要、分类、PDF 链接）
- ✅ **双模 PDF 解析**：
  - 优先使用 **Grobid** 提取结构化全文（含章节、参考文献）
  - 自动降级至 **pdfplumber** 提取原始文本（容错机制）
- ✅ **解析结果缓存**：避免重复解析同一 PDF，显著提升响应速度
- ✅ **LLM 驱动的深度分析**（支持 Qwen、OpenAI 等）：
  - 生成简洁中文摘要
  - 提炼 3 项核心创新点
  - 判断研究类型（理论/实验/综述等）
  - 识别关键技术术语
- ✅ **Streamlit Web 界面**：支持关键词搜索、论文列表浏览、一键分析
- ✅ **本地化部署**：所有数据存储于本地，无需依赖外部数据库服务

---

## 🧩 2. 子模块详解与关键技术点

| 子模块 | 功能描述 | 关键技术点 | 改进点 |
|--------|--------|-----------|-------|
| **ArXiv Fetcher** | 从 arXiv API 获取最新/指定论文元数据 | - 使用 `arxiv` Python 包<br>- 支持按关键词、作者、时间范围查询<br>- 自动下载 PDF 到本地缓存目录 | • **语义搜索**：引入 sciBERT/SPECTER 生成论文向量表示<br>• **混合检索**：结合关键词匹配和语义相似度<br>• **自适应查询**：基于用户兴趣自动生成扩展查询<br>• **跨平台扩展**：支持 bioRxiv、medRxiv 等其他预印本平台 |
| **PDF Parser** | 从 PDF 中提取可读文本 | - **双后端策略**：<br>  • 主路径：调用 Grobid REST API<br>  • 备用路径：`pdfplumber` 提取纯文本<br>- **智能缓存**：<br>  • 基于文件指纹的缓存机制<br>• 多层级结果存储（XML/JSON） | • **结构化增强**：提取图表、公式、算法伪代码<br>• **段落级语义分析**：识别方法、实验、结论等核心段落<br>• **OCR容错**：处理扫描版PDF文档<br>• **多模态融合**：整合文本、表格、图表信息 |
| **LLM Analyzer** | 调用大模型生成结构化洞察 | - 使用 Jinja2 模板构建 prompt<br>- 支持多后端（Qwen, OpenAI, Ollama）<br>- 输出强制 JSON Schema<br>- 自动截断长文本以控制成本 | • **多维度评分**：科学价值(30%) + 实用价值(25%) + 影响力(20%) + 可靠性(15%) + 可读性(10%)<br>• **上下文感知**：根据用户类型动态调整评分权重<br>• **Chain-of-Thought**：分步骤推理提升分析深度<br>• **Ensemble评价**：多模型集成降低偏差 |
| **Cache Manager** | 统一管理各类缓存（PDF、解析结果、LLM 响应） | - 所有缓存存放于 `./cache/` 目录<br>- 缓存键包含文件指纹，确保一致性<br>- 可选：未来支持 LRU 或 TTL 过期策略 | • **智能清理**：基于访问频率的LRU策略<br>• **分布式缓存**：支持Redis集群扩展<br>• **版本管理**：缓存数据版本化和渐进式更新<br>• **一致性保障**：实时同步和冲突解决机制 |
| **Web UI (Streamlit)** | 提供交互式分析界面 | - 动态加载论文卡片<br>- 支持“使用 Grobid”开关<br>- 实时显示 LLM 分析结果<br>- 错误友好提示 | • **个性化推荐**：基于用户行为的多模态布局<br>• **渐进式展示**：分层信息展现减少认知负载<br>• **智能摘要**：根据用户兴趣动态调整展示内容<br>• **交互式探索**：支持论文关联图谱可视化 |

---

## 🌍 3. 扩展至其他预印本与正式期刊的改进路线

当前系统仅支持 **arXiv**。若要扩展至 **其他预印本平台**（如 bioRxiv, medRxiv, ACL Anthology）或 **正式出版物**（如 IEEE, Springer, Nature），各子模块需做如下改进：

| 子模块 | 当前限制 | 所需改进 | 难度 |
|--------|--------|--------|------|
| **ArXiv Fetcher** | 仅调用 arXiv API | - 为每个平台实现独立 fetcher：<br>  • bioRxiv/medRxiv：使用其 REST API<br>  • ACL Anthology：解析 XML 元数据或 scrape HTML<br>  • IEEE/Springer：需处理付费墙（仅限开放获取论文）或集成机构权限<br>- 统一抽象接口 `PaperFetcher` | ⭐⭐ |
| **PDF Parser** | 假设 PDF 来自 arXiv（LaTeX 生成，文本可选） | - **无需重大修改**！Grobid 和 pdfplumber 对通用学术 PDF 兼容性良好<br>- 但需注意：<br>  • 扫描版 PDF（常见于老期刊）需先 OCR（如 Tesseract）<br>  • 某些出版社 PDF 加密 → 需解密（如 `qpdf --decrypt`） | ⭐ |
| **LLM Analyzer** | Prompt 针对 arXiv 论文风格优化 | - 微调 prompt 以适应不同领域风格：<br>  • 生物医学论文强调“方法/患者队列”<br>  • 工程类强调“指标/对比 SOTA”<br>- 可引入领域适配器（Domain Adapter） | ⭐ |
| **Cache Manager** | 缓存键基于本地 PDF 路径 | - 保持不变即可，因最终输入仍是 PDF 文件 | — |
| **Web UI** | 仅展示 arXiv ID 和分类 | - 增加来源字段（如 “Source: bioRxiv”）<br>- 支持按来源平台筛选 | ⭐ |

### 补充说明
- **正式期刊的最大挑战**：**PDF 获取**而非解析。多数出版社不提供公开 PDF 下载链接。
  - 解决方案：
    1. 仅支持 **开放获取（Open Access）** 论文
    2. 集成 **Unpaywall API** 或 **LibGen**（法律风险需评估）
    3. 用户手动上传 PDF（当前已支持！）
- **推荐策略**：初期可优先扩展 **bioRxiv / medRxiv / ACL Anthology**，因其：
  - 提供标准 API
  - PDF 质量高（文本可选）
  - 社区开放

---

## 🚀 快速开始

```bash

# 1. 启动 Grobid（推荐 Docker）
docker run -t --rm -p 8070:8070 lfoppiano/grobid:latest-crf

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 Web 应用
streamlit run app.py