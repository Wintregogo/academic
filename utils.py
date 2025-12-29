import os
import time
from datetime import datetime, timedelta
import requests

def download_pdf(url: str, save_path: str):
    if os.path.exists(save_path):
        return
    resp = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(resp.content)
    time.sleep(1)  # 避免请求过快

def days_ago(n: int):
    return datetime.now() - timedelta(days=n)