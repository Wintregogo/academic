# evaluator.py
import os
import json
from typing import Dict, Optional
from dashscope import Generation  # Qwen

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
    """
    提取论文亮点
    :param abstract: 原始摘要（来自 arXiv）
    :param full_text: 论文全文（截断后）
    :param llm_config: LLM 配置
    :return: {"abstract": "...", "breakthrough": "..."}
    """
    # 加载 breakthrough prompt
    prompt_path = "prompts/breakthrough.txt"
    if not os.path.exists(prompt_path):
        # fallback to default logic
        return {
            "abstract": abstract,
            "breakthrough": "（未配置 breakthrough prompt，使用摘要代替）"
        }

    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 构建 prompt（注意转义）
    full_prompt = template.format(abstract=abstract, full_text=full_text)

    # 调用 LLM
    content = call_llm(
        full_prompt,
        llm_config,
        response_format={"type": "json_object"}
    )

    # 解析响应
    result = parse_json_response(content)

    # 如果解析成功且包含所需字段
    if "abstract" in result and "breakthrough" in result:
        return {
            "abstract": result["abstract"],
            "breakthrough": result["breakthrough"]
        }
    else:
        # 回退方案：用摘要 + 错误提示
        return {
            "abstract": abstract,
            "breakthrough": f"（LLM 提取失败，raw: {content[:100]}...）"
        }

