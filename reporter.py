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

**Abstract**:  
> {{ paper.abstract }}

**Why it matters**:  
> {{ paper.breakthrough }}

---
{% endfor %}
"""

def generate_report(papers: List[Dict], config: Dict, output_path: str):
    template = Template(REPORT_TEMPLATE)
    report = template.render(
        keywords=config["query"]["keywords"],
        days=config["query"]["time_window_days"],
        total=len(papers),
        top_k=config["query"]["top_k"],
        papers=papers
    )
    with open(output_path, "w") as f:
        f.write(report)
