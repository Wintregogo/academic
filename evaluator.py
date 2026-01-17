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
        return json.loads(content)
    except Exception as e:
        return {"error": f"JSON parse failed: {str(e)}", "raw": content}

def load_cached_evaluation(paper_id: str) -> Dict:
    cache_file = f"cache/evaluate_{paper_id}.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            data = json.load(f)
            return data
    return {}

def cache_evaluation(paper_id: str, data: Dict):
    cache_file = f"cache/evaluate_{paper_id}.json"

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached = json.load(f)
            cached.update(data)
    else:
        cached = data
    
    if not os.path.exists(os.path.dirname(cache_file)):
        os.makedirs(os.path.dirname(cache_file))
    with open(cache_file, "w") as f:
        json.dump(cached, f, ensure_ascii=False, indent=2)    

def llm_evaluate(paper_id: str, text: str, prompt_template: str, llm_config: Dict) -> Dict:
    cached = load_cached_evaluation(paper_id)
    if cached is not None and "innovation" in cached:
        return {
            "innovation": cached.get("innovation", 0),
            "rigor": cached.get("rigor", 0),
            "impact": cached.get("impact", 0),
            "total_score": cached.get("total_score", 0),
            "raw_response": cached.get("raw_response", "")
        }

    full_prompt = prompt_template.format(full_text=text)
    content = call_llm(
        full_prompt,
        llm_config,
        response_format={"type": "json_object"}
    )
    data = parse_json_response(content)

    innovation = data.get("innovation", 0)
    rigor = data.get("rigor", 0)
    impact = data.get("impact", 0)
    total_score = round((innovation + rigor + impact) / 3, 2)

    cache_evaluation(paper_id, {
        "innovation": innovation,
        "rigor": rigor,
        "impact": impact,
        "total_score": total_score,
        "raw_response": content
    })

    return {
        "innovation": innovation,
        "rigor": rigor,
        "impact": impact,
        "total_score": total_score,
        "raw_response": content
    }


def extract_breakthrough(paper_id: str, abstract: str, full_text: str, llm_config: Dict) -> Dict:
    cached = load_cached_evaluation(paper_id)
    if cached is not None and "breakthrough" in cached:
        return {
            "abstract": cached.get("abstract", ""),
            "breakthrough": cached.get("breakthrough"),
            "language": cached.get("language")
        }

    lang = detect_language(abstract)
    prompt_file = f"prompts/breakthrough_{lang}.txt"
    
    if not os.path.exists(prompt_file):
        prompt_file = "prompts/breakthrough_en.txt"

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
        cache_evaluation(paper_id, {
            "abstract": result["abstract"],
            "breakthrough": result["breakthrough"],
            "language": lang
        })
        return {
            "abstract": result["abstract"],
            "breakthrough": result["breakthrough"],
            "language": lang
        }
    else:
        return {
            "abstract": abstract,
            "breakthrough": f"（LLM 提取失败）",
            "language": lang
        }

def compute_insight_score(breakthrough: str, language: str = "en") -> float:
    text = breakthrough.lower()
    score = 0.0

    if language == "zh":
        keywords = ["首次", "突破", "显著", "创新", "解决", "提出", "新方法", "性能提升"]
        for kw in keywords:
            if kw in text:
                score += 0.3
        if 30 <= len(text) <= 100:
            score += 0.5
    else:
        keywords = ["first", "novel", "breakthrough", "significant", "propose", "achieve", "solve", "improve"]
        for kw in keywords:
            if kw in text:
                score += 0.3
        if 50 <= len(text) <= 150:
            score += 0.5

    return min(score, 2.0)


# ==============================
# ✅ 新增功能：翻译摘要 & 生成脑图
# ==============================

def translate_abstract(paper_id: str, abstract: str, llm_config: Dict) -> str:
    """翻译英文摘要为中文，复用缓存机制"""
    cached = load_cached_evaluation(paper_id)
    if cached and "translation" in cached:
        return cached["translation"]

    # 构造简洁翻译 prompt
    prompt = f"""Translate the following academic abstract into fluent Chinese. Output only the translation.

Abstract:
\"\"\"
{abstract}
\"\"\""""

    translation = call_llm(prompt, llm_config)
    
    # 缓存结果
    cache_evaluation(paper_id, {"translation": translation})
    return translation


def generate_mindmap(paper_id: str, full_text: str, llm_config: Dict) -> str:
    """生成 Markdown 格式的脑图（最多三层）"""
    cached = load_cached_evaluation(paper_id)
    if cached and "mindmap_markdown" in cached:
        return cached["mindmap_markdown"]

    # 截断长文本以适应上下文窗口
    input_text = full_text[:18000] if len(full_text) > 18000 else full_text

    prompt = f"""Based on the paper content below, generate a hierarchical mind map in Markdown list format (max 3 levels). 
- Root: "论文核心内容"
- Use short phrases (≤15 words), no sentences
- Cover: Introduction, Method, Experiment, Conclusion

Paper:
\"\"\"
{input_text}
\"\"\"

Output only the Markdown list."""

    mindmap = call_llm(prompt, llm_config)
    
    # 缓存结果
    cache_evaluation(paper_id, {"mindmap_markdown": mindmap})
    return mindmap