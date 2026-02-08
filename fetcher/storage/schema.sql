
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ======================
-- 1. 论文主表
-- ======================
CREATE TABLE papers (
    id SERIAL PRIMARY KEY,
    paper_id TEXT NOT NULL,                          -- 平台唯一ID（如 arXiv:2405.12345）
    source TEXT NOT NULL,                            -- 来源平台：'arxiv', 'biorxiv', etc.

    -- 多语言内容
    title TEXT NOT NULL,                             -- 默认语言（通常英文）
    title_i18n JSONB,                                -- {"zh": "...", "es": "..."}
    abstract TEXT,
    abstract_i18n JSONB,

    -- 元数据
    doi TEXT,
    ver TEXT,
    pdf_url TEXT,
    published_at TIMESTAMPTZ NOT NULL,               -- 论文在平台发布日期
    updated_at TIMESTAMPTZ,                          -- 论文更新时间（如 arXiv v2）

    -- 自由关键词（非结构化）
    keywords TEXT[],

    -- 引用信息（由外部 API 定期更新）
    citation_count INTEGER DEFAULT 0,
    last_citation_update TIMESTAMPTZ,

    -- 原始数据快照
    raw_metadata JSONB NOT NULL,

    -- 去重与主从关系
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    primary_paper_id TEXT,

    -- 内容哈希（用于跨平台去重）
    hash_sha256 TEXT,

    -- 本地存储路径
    local_pdf_path TEXT,

    -- 系统字段
    created_at TIMESTAMPTZ DEFAULT NOW(),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),

    -- 约束
    UNIQUE(paper_id, source),
    CHECK (is_primary OR primary_paper_id IS NOT NULL)
);

-- ======================
-- 2. 分类体系
-- ======================
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,                          -- 'arxiv', 'biorxiv', 'generic'
    code TEXT NOT NULL,                              -- 如 'cs.CV'
    name TEXT NOT NULL,                              -- 英文名称
    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    names_i18n JSONB,                                -- {"zh": "计算机视觉"}
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, code)
);

-- ======================
-- 3. 论文-分类关联
-- ======================
CREATE TABLE paper_categories (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (paper_id, category_id)
);

-- ======================
-- 4. 机构表（标准化）
-- ======================
CREATE TABLE institutions (
    id SERIAL PRIMARY KEY,
    ror_id VARCHAR(50) UNIQUE,        -- 如 "https://ror.org/038sjwq74"
    name TEXT NOT NULL,               -- 标准名称（英文）
    name_zh TEXT,                     -- 中文名（可选，后期补充）
    country_code CHAR(2),             -- ISO 3166-1 alpha-2
    types TEXT[],                     -- ["Education", "Facility"]
    aliases TEXT[],                   -- 别名列表
    acronyms TEXT[],
    status VARCHAR(20) DEFAULT 'active', -- active / inactive / merged
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ======================
-- 5. 作者表
-- ======================
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,                              -- 标准化姓名格式
    orcid TEXT UNIQUE,
    openalex_id TEXT UNIQUE,
    current_institution_id INTEGER REFERENCES institutions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ======================
-- 6. 作者-机构历史
-- ======================
CREATE TABLE author_affiliations (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    institution_id INTEGER NOT NULL REFERENCES institutions(id) ON DELETE RESTRICT,
    start_date DATE,
    end_date DATE,                                   -- NULL 表示至今
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- 同一作者不能在同一时间段有多个当前机构
    EXCLUDE USING gist (
        author_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    ) WHERE (is_current = TRUE)
);

-- ======================
-- 7. 论文-作者关联
-- ======================
CREATE TABLE paper_authors (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    author_order INTEGER NOT NULL,                   -- 作者顺序（1=第一作者）
    raw_affiliations TEXT[],                         -- 投稿时原始机构字符串
    affiliation_institution_ids INTEGER[],           -- 标准化后的机构ID列表
    PRIMARY KEY (paper_id, author_id),
    UNIQUE (paper_id, author_order)
);

-- ======================
-- 8. 每日统计（可选，用于监控）
-- ======================
CREATE TABLE daily_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    stats_json JSONB NOT NULL,                       -- {"arxiv": 120, "total_deduped": 158}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ======================
-- 索引优化
-- ======================
-- Papers
CREATE INDEX idx_papers_hash ON papers (hash_sha256);
CREATE INDEX idx_papers_source_published ON papers (source, published_at);
CREATE INDEX idx_papers_is_primary ON papers (is_primary) WHERE is_primary = TRUE;
CREATE INDEX idx_papers_title_gin ON papers USING GIN (title gin_trgm_ops);
CREATE INDEX idx_papers_abstract_gin ON papers USING GIN (abstract gin_trgm_ops);

-- Categories
CREATE INDEX idx_categories_platform_code ON categories (platform, code);
CREATE INDEX idx_categories_parent ON categories (parent_id);

-- Paper-Categories
CREATE INDEX idx_paper_categories_category ON paper_categories (category_id);

-- Authors & Institutions
CREATE INDEX idx_authors_name ON authors (name);
CREATE INDEX idx_institutions_ror ON institutions (ror_id);
CREATE INDEX idx_author_affiliations_author ON author_affiliations (author_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_institutions_ror_id ON institutions(ror_id);
CREATE INDEX IF NOT EXISTS idx_institutions_name ON institutions(name);
CREATE INDEX IF NOT EXISTS idx_institutions_country ON institutions(country_code);
CREATE INDEX idx_paper_authors_paper ON paper_authors (paper_id);
CREATE INDEX idx_paper_authors_author ON paper_authors (author_id);
-- 确保每篇论文最多只有一个主分类
CREATE UNIQUE INDEX idx_paper_categories_primary 
ON paper_categories (paper_id) 
WHERE is_primary = TRUE;

-- 加速通过 OpenAlex ID 或 ORCID 查作者（未来可能加 openalex_id）
CREATE INDEX IF NOT EXISTS idx_authors_orcid ON authors(orcid);

-- 加速按机构查作者
CREATE INDEX IF NOT EXISTS idx_author_affiliations_institution ON author_affiliations(institution_id);

-- 加速按日期范围查论文
CREATE INDEX IF NOT EXISTS idx_papers_published_date ON papers(published_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_authors_openalex_id 
ON authors(openalex_id) 
WHERE openalex_id IS NOT NULL;