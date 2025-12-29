import os
import time
from datetime import datetime, timedelta
import requests
import yaml

def download_pdf(url: str, save_path: str):
    if os.path.exists(save_path):
        return
    resp = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(resp.content)
    time.sleep(1)  # 避免请求过快

def days_ago(n: int):
    return datetime.now() - timedelta(days=n)

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """从 YAML 文件加载配置，若不存在则返回空 dict"""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}