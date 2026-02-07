# utils/db.py
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import yaml

def get_project_root() -> str:
    """返回项目根目录（包含 config.yaml 的目录）"""
    # __file__ 是 .../your_project/utils/db.py
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(utils_dir)  # 上一级就是 your_project/
    return project_root

def load_config_absolute():
    project_root = get_project_root()
    config_path = os.path.join(project_root, "config.yaml")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_config():
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_db_connection():
    config = load_config()
    db_conf = config['database']
    return psycopg2.connect(
        host=db_conf.get('host', 'localhost'),
        port=db_conf.get('port', 5432),
        database=db_conf['name'],
        user=db_conf['user'],
        password=db_conf['password'],
        cursor_factory=RealDictCursor
    )