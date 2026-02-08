# fetcher/ingest.py
import json
import logging
import traceback
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def normalize_orcid(orcid_url: Optional[str]) -> Optional[str]:
    if not orcid_url:
        return None
    # 输入可能是 "https://orcid.org/0000-0001-2345-6789" 或 "0000-0001-2345-6789"
    if orcid_url.startswith("http"):
        orcid =  orcid_url.split("/")[-1]
    else:
        orcid = orcid_url  # 假设已是 ID 格式
    return None if orcid == "" else orcid


def normalize_ror(ror: Optional[str]) -> Optional[str]:
    if not ror:
        return None
    # ROR 格式如 "https://ror.org/05gq02987" 或 "05gq02987"
    if ror.startswith("http"):
        return ror.split("/")[-1]
    return ror.strip() if ror else None


# ===== 数据库查重函数 =====
def is_paper_exists(cur, paper_id: str, source: str) -> int | None:
    """
    检查论文是否已存在于数据库
    :return: 数据库 id（如果存在），否则 None
    """
    cur.execute("""
        SELECT id, local_pdf_path FROM papers 
        WHERE paper_id = %s AND source = %s;
    """, (paper_id, source))
    row = cur.fetchone()
    return (row['id'], row['local_pdf_path']) if row else (None, None)


def fetch_paper_ids_by_keys(db_conn, papers: list) -> dict:
    """
    根据 papers 列表中的 (paper_id, source) 批量查询数据库中的 id
    返回: {(paper_id, source): db_id, ...}
    """
    if not papers:
        return {}

    # 构造 VALUES 列表用于 JOIN 查询
    values_list = []
    for p in papers:
        values_list.append((p["paper_id"], p["source"]))

    # 使用 unnest 或 VALUES 进行批量 lookup
    # 这里用 execute_values + VALUES 更兼容
    from psycopg2.extras import execute_values

    sql = """
        SELECT p.paper_id, p.source, p.id
        FROM papers p
        INNER JOIN (VALUES %s) AS v(pid, src)
            ON p.paper_id = v.pid AND p.source = v.src
    """

    try:
        with db_conn.cursor() as cur:
            execute_values(
                cur,
                sql,
                values_list,
                template=None,
                page_size=100
            )

            paper_ids = {}
            for row in cur.fetchall():
                paper_id = row['paper_id']
                source = row['source']
                db_id = row['id']
                paper_ids[(paper_id, source)] = db_id

            for p in papers:
                p['paper_db_id'] = paper_ids.get((p["paper_id"], p["source"]), -1)
    except Exception as e:
        logger.error(f"fetch_paper_ids_by_keys error: {e}")

    return papers


def insert_papers(papers: list, db_conn):
    """
    将论文列表写入数据库
    - 先插入所有主论文（is_primary=True）
    - 再插入从属论文（is_primary=False）
    - 使用 ON CONFLICT DO NOTHING 实现幂等
    """

    if not papers:
        logger.info("No papers to insert.")
        return

    # 分离主论文和从属论文
    primary_papers = [p for p in papers if p.get("is_primary", False)]
    duplicate_papers = [p for p in papers if not p.get("is_primary", False)]

    try:
        with db_conn.cursor() as cur:
            # 1. 插入主论文
            _bulk_insert_papers(cur, primary_papers)
            logger.info(f"Inserted {len(primary_papers)} primary papers.")

            # 2. 插入从属论文（依赖主论文已存在）
            _bulk_insert_papers(cur, duplicate_papers)
            logger.info(f"Inserted {len(duplicate_papers)} duplicate papers.")

        db_conn.commit()
        logger.info("All papers committed successfully.")
    except Exception as e:
        db_conn.rollback()
        logger.error(f"Database insertion failed: {e}")
        raise


def _bulk_insert_papers(cur, papers: list):
    if not papers:
        return

    records = []
    for p in papers:
        record = (
            p["paper_id"],
            p["source"],
            p["title"],
            json.dumps(p.get("title_i18n", {})),
            p.get("abstract", ""),
            json.dumps(p.get("abstract_i18n", {})),
            p.get("doi"),
            p.get("version", ""),  # ← 确保有值
            p["pdf_url"],
            p["published_at"],
            p.get("updated_at"),
            p.get("keywords", []),
            p.get("citation_count", 0),
            p.get("last_citation_update"),
            json.dumps(p["raw_metadata"]),
            p.get("is_primary", False),
            p.get("primary_paper_id"),
            p.get("hash_sha256", ""),
            p.get("local_pdf_path"),
            p.get("fetched_at", datetime.utcnow()),
        )
        records.append(record)

    from psycopg2.extras import execute_values

    sql = """
        INSERT INTO papers (
            paper_id, source, title, title_i18n, abstract, abstract_i18n,
            doi, version, pdf_url, published_at, updated_at, keywords,
            citation_count, last_citation_update, raw_metadata,
            is_primary, primary_paper_id, hash_sha256, local_pdf_path, fetched_at
        ) VALUES %s
        ON CONFLICT (paper_id, source) DO UPDATE SET
            version = EXCLUDED.version,
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract,
            title_i18n = EXCLUDED.title_i18n,
            abstract_i18n = EXCLUDED.abstract_i18n,
            pdf_url = EXCLUDED.pdf_url,
            published_at = EXCLUDED.published_at,
            updated_at = EXCLUDED.updated_at,
            keywords = EXCLUDED.keywords,
            raw_metadata = EXCLUDED.raw_metadata,
            hash_sha256 = EXCLUDED.hash_sha256,
            local_pdf_path = EXCLUDED.local_pdf_path,
            fetched_at = EXCLUDED.fetched_at
    """

    execute_values(cur, sql, records, template=None, page_size=100)

    
def upsert_institution(cur, inst: dict) -> Optional[int]:
    """插入或更新 institution，优先使用 ROR ID，其次 OpenAlex ID"""
    ror_id = normalize_ror(inst.get("ror_id"))  # 注意：你写的是 normalize_orcid，应为 normalize_ror
    openalex_id = inst.get("openalex_id")
    name = inst["name"]
    country = inst.get("country_code")
    inst_type = inst.get("type")

    # 提取 OpenAlex 中的 aliases 和 acronyms（如果存在）
    aliases = inst.get("aliases", [])
    acronyms = inst.get("acronyms", [])

    if not name:
        return None

    # 如果两个标识符都缺失，跳过（或可扩展为 name+country 唯一，但需加索引）
    if not ror_id and not openalex_id:
        return None

    # === 第一步：尝试用 ROR ID upsert（ROR 更权威）===
    if ror_id:
        cur.execute("""
            INSERT INTO institutions (
                ror_id, openalex_id, name, country_code, types, aliases, acronyms, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'active'
            )
            ON CONFLICT (ror_id)
            DO UPDATE SET
                openalex_id = COALESCE(institutions.openalex_id, EXCLUDED.openalex_id),
                name = EXCLUDED.name,
                country_code = EXCLUDED.country_code,
                types = EXCLUDED.types,
                aliases = EXCLUDED.aliases,
                acronyms = EXCLUDED.acronyms,
                status = 'active',
                updated_at = NOW()
            RETURNING id;
        """, (
            ror_id,
            openalex_id,
            name,
            country,
            [inst_type] if inst_type else [],
            aliases,
            acronyms,
        ))
        row = cur.fetchone()
        if row:
            return row['id']

    # === 第二步：尝试用 OpenAlex ID upsert ===
    if openalex_id:
        cur.execute("""
            INSERT INTO institutions (
                ror_id, openalex_id, name, country_code, types, aliases, acronyms, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'active'
            )
            ON CONFLICT (openalex_id)
            DO UPDATE SET
                ror_id = COALESCE(institutions.ror_id, EXCLUDED.ror_id),
                name = EXCLUDED.name,
                country_code = EXCLUDED.country_code,
                types = EXCLUDED.types,
                aliases = EXCLUDED.aliases,
                acronyms = EXCLUDED.acronyms,
                status = 'active',
                updated_at = NOW()
            RETURNING id;
        """, (
            ror_id,
            openalex_id,
            name,
            country,
            [inst_type] if inst_type else [],
            aliases,
            acronyms,
        ))
        row = cur.fetchone()
        if row:
            return row['id']

    # === 第三步：两者都无？理论上不会到这，但兜底 ===
    return None

def upsert_author(cur, author) -> int:
    name = author["display_name"]
    orcid = normalize_orcid(author.get("orcid"))
    openalex_id = author.get("openalex_author_id")
    openalex_id = None if openalex_id == "" else openalex_id

    # 标准化 ORCID（可选）
    if orcid and orcid.startswith("http"):
        orcid = orcid.split("/")[-1]

    if orcid:
        cur.execute("""
            INSERT INTO authors (name, orcid, openalex_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (orcid)
            DO UPDATE SET
                name = EXCLUDED.name,
                openalex_id = COALESCE(authors.openalex_id, EXCLUDED.openalex_id)
            RETURNING id;
        """, (name, orcid, openalex_id))

        row = cur.fetchone()
        if row:
            return row['id']

        # 如果 orcid 为空，尝试用 openalex_id
    if openalex_id:
        cur.execute("""
            INSERT INTO authors (name, orcid, openalex_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (openalex_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                orcid = COALESCE(authors.orcid, EXCLUDED.orcid)
            RETURNING id;
        """, (name, orcid, openalex_id))
        row = cur.fetchone()
        if row:
            return row['id']

    # 两者都空？插入无标识作者（谨慎）
    cur.execute("""
        INSERT INTO authors (name, orcid, openalex_id)
        VALUES (%s, %s, %s)
        RETURNING id;
    """, (name, orcid, openalex_id))
    return cur.fetchone()['id']


def upsert_author2(cur, author: dict) -> int:
    name = author["display_name"]
    orcid = author.get("orcid")
    openalex_id = author.get("openalex_author_id")

    # 尝试插入，冲突则跳过
    cur.execute("""
        INSERT INTO authors (name, orcid, openalex_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (orcid) WHERE orcid IS NOT NULL DO NOTHING;
    """, (name, orcid, openalex_id))

    cur.execute("""
        INSERT INTO authors (name, orcid, openalex_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (openalex_id) WHERE openalex_id IS NOT NULL DO NOTHING;
    """, (name, orcid, openalex_id))

    # 最后，通过 ORCID 或 OpenAlex ID 查询 ID
    if orcid:
        cur.execute("SELECT id FROM authors WHERE orcid = %s", (orcid,))
        row = cur.fetchone()
        if row:
            return row['id']

    if openalex_id:
        cur.execute("SELECT id FROM authors WHERE openalex_id = %s", (openalex_id,))
        row = cur.fetchone()
        if row:
            return row['id']

    # 都没有？插入无标识作者（不推荐，但兜底）
    cur.execute("""
        INSERT INTO authors (name, orcid, openalex_id)
        VALUES (%s, %s, %s)
        RETURNING id;
    """, (name, orcid, openalex_id))
    row = cur.fetchone()
    return row['id'] if row else None


def upsert_author1(cur, author: dict) -> int:
    """优先用 ORCID，其次 OpenAlex ID，最后 fallback 到 name"""
    name = author["display_name"]
    orcid = normalize_orcid(author["orcid"])
    openalex_id = author["openalex_author_id"]

    # 1. 尝试用 ORCID upsert
    if orcid:
        cur.execute("""
            INSERT INTO authors (name, orcid, openalex_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (orcid) WHERE orcid IS NOT NULL
            DO UPDATE SET
                name = EXCLUDED.name,
                openalex_id = EXCLUDED.openalex_id
            RETURNING id;
        """, (name, orcid, openalex_id))
        row = cur.fetchone()
        if row:
            return row['id']

    # 2. 尝试用 OpenAlex ID upsert
    if openalex_id:
        cur.execute("""
            INSERT INTO authors (name, orcid, openalex_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (openalex_id) WHERE openalex_id IS NOT NULL
            DO UPDATE SET
                name = EXCLUDED.name,
                orcid = EXCLUDED.orcid
            RETURNING id;
        """, (name, orcid, openalex_id))
        row = cur.fetchone()
        if row:
            return row['id']

    # 3. 两者都无，插入新记录（可能重复，但可接受）
    cur.execute("""
        INSERT INTO authors (name, orcid, openalex_id)
        VALUES (%s, %s, %s)
        RETURNING id;
    """, (name, orcid, openalex_id))
    row = cur.fetchone()
    return row['id'] if row else None


def link_paper_to_authors(cur, paper_db_id: int, enriched_authors: List[dict]):   
    for idx, auth in enumerate(enriched_authors, start=1):
        # Upsert 所有机构（目前只处理第一个，可扩展为多机构）
        inst_ids = []
        primary_inst_id = None
        for inst in auth["institutions"]:
            inst_id = upsert_institution(cur, inst)
            if inst_id:
                inst_ids.append(inst_id)
                if primary_inst_id is None:
                    primary_inst_id = inst_id

        # Upsert 作者
        author_id = upsert_author(cur, auth)
        if not author_id:
            continue

        # 更新作者当前机构（取第一个）
        if primary_inst_id:
            cur.execute("""
                UPDATE authors
                SET current_institution_id = %s
                WHERE id = %s AND current_institution_id IS DISTINCT FROM %s;
            """, (primary_inst_id, author_id, primary_inst_id))

        # 插入 paper_authors
        cur.execute("""
            INSERT INTO paper_authors (
                paper_id, author_id, author_order, author_position,
                raw_affiliations, affiliation_institution_ids
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (paper_id, author_id) DO NOTHING;
        """, (
            paper_db_id,
            author_id,
            idx,  # 顺序
            auth['author_position'],
            auth["raw_affiliations"],
            inst_ids  # 支持多机构
        ))

        # （可选）插入 author_affiliations 历史
        for inst_id in inst_ids:
            cur.execute("""
                INSERT INTO author_affiliations (author_id, institution_id, is_current)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (author_id, institution_id) WHERE is_current = TRUE
                DO NOTHING;
            """, (author_id, inst_id))


def update_authors_info_to_db(db_conn, papers):
    try:
        with db_conn.cursor() as cur:
            logger.info("Updating authors ...")
            for paper in papers:
                logger.info(f"Update author of paper {paper['paper_id']}")
                link_paper_to_authors(cur, paper['paper_db_id'], paper['authors'])
            logger.info("Done update authors")
        db_conn.commit()
    except Exception as e:
        logger.error(f"update_authors_info error: {e}")
        traceback.print_exc()
        db_conn.rollback()
        raise