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

<table>
  <thead>
    <tr>
      <th style="width: 10%;">子模块</th>
      <th style="width: 20%;">功能描述</th>
      <th style="width: 27%;">关键技术点</th>
      <th style="width: 43%;">近期可落地的改进点</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>ArXiv Fetcher</strong></td>
      <td>从 arXiv API 获取最新/指定论文元数据</td>
      <td>
        - 使用 <code>arxiv</code> Python 包<br>
        - 支持按关键词、作者、时间范围查询<br>
        - 自动下载 PDF 到本地缓存目录
      </td>
      <td>
        • <strong>平台扩展</strong>：增加 bioRxiv/medRxiv 支持，及正式发布刊物<br>
        • <strong>增量同步</strong>：记录最后抓取时间，避免重复拉取<br>
        • <strong>元数据增强</strong>：提取 DOI、引用数（通过 Semantic Scholar API）<br>
        • <strong>使用统一查询方法</strong>：可以考虑使用 PaperScrapper 统一查询多个平台的论文
      </td>
    </tr>
    <tr>
      <td><strong>PDF Parser</strong></td>
      <td>从 PDF 中提取可读文本</td>
      <td>
        - <strong>双后端策略</strong>：<br>
          &nbsp;&nbsp;• 主路径：Grobid REST API<br>
          &nbsp;&nbsp;• 备用路径：pdfplumber<br>
        - <strong>智能缓存</strong>：<br>
          &nbsp;&nbsp;• Grobid → .xml<br>
          &nbsp;&nbsp;• pdfplumber → .json
      </td>
      <td>
        • <strong>结构化增强</strong>：提取图表、公式、算法伪代码 <br>
        • <strong>多模态融合</strong>：整合文本、表格、图表信息 <br>
        • <strong>段落结构保留</strong>：Grobid 返回 TEI XML 中提取章节标题+段落<br>
        • <strong>OCR fallback</strong>：对扫描版 PDF 调用 Tesseract（需用户安装）<br>
        • <strong>错误日志细化</strong>：区分“PDF损坏” vs “Grobid 服务不可用” <br>
      </td>
    </tr>
    <tr>
      <td><strong>LLM Analyzer</strong></td>
      <td>调用大模型生成结构化洞察</td>
      <td>
        - Jinja2 模板构建 prompt<br>
        - 支持 Qwen/OpenAI/Ollama<br>
        - 强制 JSON Schema 输出<br>
        - 自动截断长文本（≤12k 字符）
      </td>
      <td>
        • <strong>多维度评分</strong>：科学价值(30%) + 实用价值(25%) + 影响力(20%) + 可靠性(15%) + 可读性(10%) <br>
        • <strong>上下文感知</strong>：根据用户类型动态调整评分权重 <br>
        • <strong>Chain-of-Thought</strong>：分步骤推理提升分析深度 <br>
        • <strong>Ensemble评价</strong>：多模型集成降低偏差 <br>
        • <strong>领域自适应 Prompt</strong>：根据 arXiv 分类（cs.CL / cs.CV）切换提示词<br>
        • <strong>结果缓存</strong>：对相同 full_text 缓存 LLM 响应（节省 token）<br>
        • <strong>置信度评分</strong>：让 LLM 自评分析可靠性（如“高/中/低”）
      </td>
    </tr>
    <tr>
      <td><strong>Cache Manager</strong></td>
      <td>统一管理各类缓存（PDF、解析结果、LLM 响应）</td>
      <td>
        - 所有缓存存放于 <code>./cache/</code><br>
        - 缓存键含文件指纹确保一致性
      </td>
      <td>
        • <strong>自动清理</strong>：启动时删除 >30 天未访问的缓存<br>
        • <strong>磁盘用量监控</strong>：显示 cache/ 目录大小，提供“清除缓存”按钮<br>
        • <strong>缓存命中统计</strong>：日志记录 Grobid/pdfplumber/LLM 缓存命中率
      </td>
    </tr>
    <tr>
      <td><strong>Web UI (Streamlit)</strong></td>
      <td>提供交互式分析界面</td>
      <td>
        - 动态加载论文卡片<br>
        - 支持“使用 Grobid”开关<br>
        - 实时显示 LLM 分析结果
      </td>
      <td>
        • <strong>结果对比视图</strong>：并排显示 Grobid vs pdfplumber 提取效果<br>
        • <strong>用户反馈入口</strong>：“有用/无用” 按钮收集 LLM 质量反馈<br>
        • <strong>导出功能</strong>：一键保存分析结果为 Markdown 或 JSON
      </td>
    </tr>
  </tbody>
</table>

---

## 🌍 3. 扩展至其他预印本与正式期刊的改进路线

当前系统仅支持 **arXiv**。若要扩展至 **其他预印本平台**（如 bioRxiv, medRxiv, ACL Anthology）或 **正式出版物**（如 IEEE, Springer, Nature），各子模块需做如下改进：

<table>
  <thead>
    <tr>
      <th style="width: 10%;">子模块</th>
      <th style="width: 20%;">当前限制</th>
      <th style="width: 60%;">所需改进</th>
      <th style="width: 10%;">难度</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>ArXiv Fetcher</strong></td>
      <td>仅调用 arXiv API</td>
      <td>
        - 为每个平台实现独立 fetcher：<br>
          &nbsp;&nbsp;• bioRxiv/medRxiv：使用其 REST API<br>
          &nbsp;&nbsp;• ACL Anthology：解析 XML 元数据或 scrape HTML<br>
          &nbsp;&nbsp;• IEEE/Springer：需处理付费墙（仅限开放获取论文）或集成机构权限<br>
        - 统一抽象接口 <code>PaperFetcher</code>
      </td>
      <td>⭐⭐</td>
    </tr>
    <tr>
      <td><strong>PDF Parser</strong></td>
      <td>假设 PDF 来自 arXiv（LaTeX 生成，文本可选）</td>
      <td>
        - <strong>无需重大修改</strong>！Grobid 和 pdfplumber 对通用学术 PDF 兼容性良好<br>
        - 但需注意：<br>
          &nbsp;&nbsp;• 扫描版 PDF（常见于老期刊）需先 OCR（如 Tesseract）<br>
          &nbsp;&nbsp;• 某些出版社 PDF 加密 → 需解密（如 <code>qpdf --decrypt</code>）
      </td>
      <td>⭐</td>
    </tr>
    <tr>
      <td><strong>LLM Analyzer</strong></td>
      <td>Prompt 针对 arXiv 论文风格优化</td>
      <td>
        - 微调 prompt 以适应不同领域风格：<br>
          &nbsp;&nbsp;• 生物医学论文强调“方法/患者队列”<br>
          &nbsp;&nbsp;• 工程类强调“指标/对比 SOTA”<br>
        - 可引入领域适配器（Domain Adapter）
      </td>
      <td>⭐</td>
    </tr>
    <tr>
      <td><strong>Cache Manager</strong></td>
      <td>缓存键基于本地 PDF 路径</td>
      <td>- 保持不变即可，因最终输入仍是 PDF 文件</td>
      <td>—</td>
    </tr>
    <tr>
      <td><strong>Web UI</strong></td>
      <td>仅展示 arXiv ID 和分类</td>
      <td>
        - 增加来源字段（如 “Source: bioRxiv”）<br>
        - 支持按来源平台筛选
      </td>
      <td>⭐</td>
    </tr>
  </tbody>
</table>

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