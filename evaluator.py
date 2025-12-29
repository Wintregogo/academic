import os
import json
import time
from typing import Dict, List
from dashscope import Generation  # Qwen
# 若用 OpenAI: from openai import OpenAI

def load_prompt(template_name: str = "default") -> str:
    path = f"prompts/{template_name}.txt"
    if not os.path.exists(path):
        path = "prompts/default.txt"
    with open(path, "r") as f:
        return f.read()

def llm_evaluate(text: str, prompt_template: str, llm_config: Dict) -> Dict:
    full_prompt = prompt_template.format(full_text=text)
    
    if llm_config["provider"] == "qwen":
        resp = Generation.call(
            model=llm_config["model"],
            api_key=llm_config["api_key"],
            prompt=full_prompt,
            result_format="message"
        )
        content = resp.output.choices[0].message.content
    else:
        raise NotImplementedError("Only Qwen supported in this template")

    # 尝试解析 JSON
    try:
        # 清理可能的 markdown code block
        content = content.strip().strip("```json").strip("```")
        data = json.loads(content)
        score = (data.get("innovation", 0) + data.get("rigor", 0) + data.get("impact", 0)) / 3
        data["total_score"] = round(score, 2)
        return data
    except Exception as e:
        print(f"Parse error: {e}, raw: {content}")
        return {"total_score": 0, "error": str(e)}

def extract_breakthrough(text: str, llm_config: Dict) -> Dict:
    prompt = """
请从以下论文中提取两项信息：
1. 原始摘要（保持原样）
2. 突破性成就（用一句话概括其最值得关注的创新或成果）

输出严格 JSON 格式：
{"abstract": "...", "breakthrough": "..."}
""".format(full_text=text)
    
    # 类似调用 LLM...
    # 为简洁，此处复用 llm_evaluate 逻辑（实际应封装）
    # ...（略，可复用上述逻辑）
    return {"abstract": "mock", "breakthrough": "mock"}  # TODO: 实现
