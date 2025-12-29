import os
import pdfplumber
import requests
from typing import Dict

class PDFParser:
    def __init__(self, use_grobid: bool = False, grobid_url: str = "http://localhost:8070"):
        self.use_grobid = use_grobid
        self.grobid_url = grobid_url

    def parse(self, pdf_path: str) -> Dict[str, str]:
        if self.use_grobid:
            try:
                with open(pdf_path, "rb") as f:
                    resp = requests.post(f"{self.grobid_url}/api/processFulltextDocument", files={"input": f})
                if resp.status_code == 200:
                    # 简化：只取全文文本（实际可解析章节）
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "xml")
                    text = soup.get_text()
                    return {"full_text": text[:12000]}  # 截断
            except Exception as e:
                print(f"Grobid failed: {e}")

        # fallback to pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return {"full_text": text[:12000]}