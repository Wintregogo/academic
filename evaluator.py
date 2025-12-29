# evaluator.py
import os
import json
from typing import Dict, Optional
from dashscope import Generation  # Qwen
from langdetect import detect, LangDetectException

def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return "zh" if lang.startswith("zh") else "en"
    except LangDetectException:
        return "en"  # 默认英文
    except Exception as e:
        return "en"

def load_prompt(template_name: str = "default") -> str:
    path = f"prompts/{template_name}.txt"
    if not os.path.exists(path):
        path = "prompts/default.txt"
    with open(path, "r") as f:
        return f.read()

def call_llm(prompt: str, llm_config: Dict, response_format: Optional[Dict] = None) -> str:
    """
    通用 LLM 调用函数
    """
    kwargs = {
        "model": llm_config["model"],
        "api_key": llm_config["api_key"],
        "prompt": prompt,
    }
    if response_format:
        kwargs["response_format"] = response_format

    resp = Generation.call(**kwargs)
    #content = resp.output.choices[0].message.content.strip()
    content = resp.output.text.strip()

    # 清理可能的 code block
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def parse_json_response(content: str) -> Dict:
    """安全解析 JSON，失败时返回错误信息"""
    try:
        # 转义花括号已处理，直接解析
        return json.loads(content)
    except Exception as e:
        return {"error": f"JSON parse failed: {str(e)}", "raw": content}


def llm_evaluate(text: str, prompt_template: str, llm_config: Dict) -> Dict:
    full_prompt = prompt_template.format(full_text=text)
    content = call_llm(
        full_prompt,
        llm_config,
        response_format={"type": "json_object"}  # 启用结构化输出（Qwen 支持）
    )
    data = parse_json_response(content)

    # 安全提取评分字段
    innovation = data.get("innovation", 0)
    rigor = data.get("rigor", 0)
    impact = data.get("impact", 0)
    total_score = round((innovation + rigor + impact) / 3, 2)

    return {
        "innovation": innovation,
        "rigor": rigor,
        "impact": impact,
        "total_score": total_score,
        "raw_response": content
    }


def extract_breakthrough(abstract: str, full_text: str, llm_config: Dict) -> Dict:
    # 自动检测语言
    lang = detect_language(abstract)
    prompt_file = f"prompts/breakthrough_{lang}.txt"
    
    if not os.path.exists(prompt_file):
        prompt_file = "prompts/breakthrough_en.txt"  # fallback

    with open(prompt_file, "r", encoding="utf-8") as f:
        template = f.read()

    full_prompt = template.format(abstract=abstract, full_text=full_text)

    content = call_llm(
        full_prompt,
        llm_config,
        response_format={"type": "json_object"}
    )

    result = parse_json_response(content)

    if "abstract" in result and "breakthrough" in result:
        return {
            "abstract": result["abstract"],
            "breakthrough": result["breakthrough"],
            "language": lang  # 记录语言，便于后续分析
        }
    else:
        return {
            "abstract": abstract,
            "breakthrough": f"（LLM 提取失败）",
            "language": lang
        }

def compute_insight_score(breakthrough: str, language: str = "en") -> float:
    """
    基于关键词和长度计算亮点质量分（0~2.0），作为 total_score 的加成
    """
    text = breakthrough.lower()
    score = 0.0

    if language == "zh":
        keywords = ["首次", "突破", "显著", "创新", "解决", "提出", "新方法", "性能提升"]
        for kw in keywords:
            if kw in text:
                score += 0.3
        # 长度适中加分（30~100 字）
        if 30 <= len(text) <= 100:
            score += 0.5
    else:
        keywords = ["first", "novel", "breakthrough", "significant", "propose", "achieve", "solve", "improve"]
        for kw in keywords:
            if kw in text:
                score += 0.3
        # length: 50~150 chars
        if 50 <= len(text) <= 150:
            score += 0.5

    return min(score, 2.0)  # 最多加 2 分