import os
import hashlib
import json
import requests
import pdfplumber
from pathlib import Path
from typing import Dict, Tuple, Optional

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

class PDFParser:
    def __init__(self, use_grobid: bool = False, grobid_url: str = "http://localhost:8070"):
        self.use_grobid = use_grobid
        self.grobid_url = grobid_url

    def _get_cache_key(self, pdf_path: str, parser_type: str) -> str:
        """生成唯一缓存 key，基于 PDF 路径和解析器类型"""
        # 使用绝对路径 + 修改时间确保一致性
        #abs_path = os.path.abspath(pdf_path)
        mtime = str(os.path.getmtime(pdf_path)).split('.')[0]
        #key_str = f"{abs_path}|{mtime}|{parser_type}"
        #return hashlib.md5(key_str.encode()).hexdigest()
        return f"{parser_type}_{os.path.basename(pdf_path)}_{mtime}"

    def _load_from_cache(self, cache_key: str, parser_type: str) -> Optional[Dict]:
        if parser_type == "grobid":
            cache_file = CACHE_DIR / f"{cache_key}.xml"
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        xml_content = f.read()
                    return {"xml": xml_content}
                except Exception as e:
                    print(f"Failed to load Grobid cache: {e}")
        elif parser_type == "pdfplumber":
            cache_file = CACHE_DIR / f"{cache_key}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Failed to load pdfplumber cache: {e}")
        return None

    def _save_to_cache(self, cache_key: str, parser_type: str, data):
        try:
            if parser_type == "grobid":
                cache_file = CACHE_DIR / f"{cache_key}.xml"
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(data["xml"])
            elif parser_type == "pdfplumber":
                cache_file = CACHE_DIR / f"{cache_key}.json"
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save cache for {parser_type}: {e}")

    def parse(self, pdf_path: str) -> Tuple[Optional[Dict], str]:
        if not os.path.exists(pdf_path):
            error = f"PDF not found: {pdf_path}"
            print(error)
            return None, error

        # === 尝试 Grobid ===
        if self.use_grobid:
            cache_key_grobid = self._get_cache_key(pdf_path, "grobid")
            cached = self._load_from_cache(cache_key_grobid, "grobid")
            if cached:
                # 从缓存重建结果
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(cached["xml"], "xml")
                text = soup.get_text()[:12000]
                return {"full_text": text}, ""

            # 否则调用 Grobid
            try:
                with open(pdf_path, "rb") as f:
                    resp = requests.post(
                        f"{self.grobid_url}/api/processFulltextDocument",
                        files={"input": f},
                        timeout=30
                    )
                if resp.status_code == 200:
                    xml_content = resp.text
                    # 缓存原始 XML
                    self._save_to_cache(cache_key_grobid, "grobid", {"xml": xml_content})
                    # 提取文本
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(xml_content, "xml")
                    text = soup.get_text()[:12000]
                    return {"full_text": text}, ""
                else:
                    print(f"Grobid returned status {resp.status_code}")
            except Exception as e:
                print(f"Grobid failed for {pdf_path}: {e}")

        # === Fallback to pdfplumber ===
        cache_key_pdfplumber = self._get_cache_key(pdf_path, "pdfplumber")
        cached = self._load_from_cache(cache_key_pdfplumber, "pdfplumber")
        if cached:
            return cached, ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            result = {"full_text": text[:12000]}
            self._save_to_cache(cache_key_pdfplumber, "pdfplumber", result)
            return result, ""
        except Exception as e:
            error = f"Failed to parse PDF with pdfplumber {os.path.basename(pdf_path)}: {e}"
            print(error)
            return None, error