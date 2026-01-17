# reporter.py
import os
from typing import List, Dict
from jinja2 import Template

REPORT_TEMPLATE = """
# arXiv Insight Report

- Keywords: {{ keywords }}
- Time Window: Last {{ days }} days
- Total Papers Analyzed: {{ total }}
- Top {{ top_k }} Selected

{% for paper in papers %}
## {{ loop.index }}. [{{ paper.title }}](https://arxiv.org/abs/{{ paper.id }})

**Published**: {{ paper.published[:10] }}  
**Score**: {{ paper.total_score }}/10  

### 📘 导读（Why it matters）
> {{ paper.breakthrough }}

### 🌐 译文（Abstract Translation）
{% raw %}```text{% endraw %}
{{ paper.translation }}
{% raw %}```{% endraw %}

### 🧠 脑图（Mind Map）
{% raw %}```markdown{% endraw %}
{{ paper.mindmap_markdown }}
{% raw %}```{% endraw %}

---
{% endfor %}
"""


def generate_report(papers: List[Dict], config: Dict, output_path: str):
    """
    Generate a Markdown report with enhanced Qwen-style analysis:
    - Guide (breakthrough)
    - Translation of abstract
    - Mind map in Markdown list format
    """
    template = Template(REPORT_TEMPLATE)
    report = template.render(
        keywords=config["query"]["keywords"],
        days=config["query"]["time_window_days"],
        total=len(papers),
        top_k=config["query"]["top_k"],
        papers=papers
    )

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Generating report to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)