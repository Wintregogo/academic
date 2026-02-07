#!/usr/bin/env python3
"""
初始化数据库：读取 config.yaml，连接 PostgreSQL，并应用 schema.sql
"""

import yaml
import psycopg2
import sys
import os
from pathlib import Path


def load_config(config_path: str = "../config.yaml") -> dict:
    """加载 YAML 配置文件"""
    if not os.path.exists(config_path):
        print(f"❌ 配置文件未找到: {config_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if "database" not in config:
        print("❌ 配置文件缺少 'database' 节点", file=sys.stderr)
        sys.exit(1)
    
    return config["database"]


def connect_to_db(db_config: dict):
    """建立数据库连接"""
    try:
        conn = psycopg2.connect(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config["name"],
            user=db_config["user"],
            password=db_config["password"],
            options=db_config.get("options", None)
        )
        return conn
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}", file=sys.stderr)
        sys.exit(1)


def apply_schema(conn, schema_file: str = "../../storage/schema.sql"):
    """执行 schema.sql 文件"""
    if not os.path.exists(schema_file):
        print(f"❌ schema 文件未找到: {schema_file}", file=sys.stderr)
        sys.exit(1)

    with open(schema_file, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("✅ 数据库 schema 应用成功！")
    except Exception as e:
        conn.rollback()
        print(f"❌ 执行 schema 失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    print("🔧 正在初始化预印本数据库...")
    
    config = load_config()
    conn = connect_to_db(config)
    
    try:
        apply_schema(conn)
    finally:
        conn.close()
        print("🔌 数据库连接已关闭。")


if __name__ == "__main__":
    main()