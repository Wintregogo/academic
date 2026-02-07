#!/usr/bin/env python3
"""
初始化 arXiv / bioRxiv / medRxiv 全量分类数据（含完整中文翻译）
"""

import yaml
import psycopg2
from psycopg2.extras import Json
import sys
import os
from typing import List, Dict, Optional


# ======================
# arXiv 完整分类体系（含中文）
# 来源: https://arxiv.org/category_taxonomy
# ======================

ARXIV_TAXONOMY = [
    {
        "name": "Computer Science",
        "code": "cs",
        "children": [
            {"code": "cs.AI", "name": "Artificial Intelligence"},
            {"code": "cs.AR", "name": "Hardware Architecture"},
            {"code": "cs.CC", "name": "Computational Complexity"},
            {"code": "cs.CE", "name": "Computational Engineering, Finance, and Science"},
            {"code": "cs.CG", "name": "Computer Graphics"},
            {"code": "cs.CL", "name": "Computation and Language"},
            {"code": "cs.CR", "name": "Cryptography and Security"},
            {"code": "cs.CV", "name": "Computer Vision and Pattern Recognition"},
            {"code": "cs.CY", "name": "Computers and Society"},
            {"code": "cs.DB", "name": "Databases"},
            {"code": "cs.DC", "name": "Distributed, Parallel, and Cluster Computing"},
            {"code": "cs.DL", "name": "Digital Libraries"},
            {"code": "cs.DM", "name": "Discrete Mathematics"},
            {"code": "cs.DS", "name": "Data Structures and Algorithms"},
            {"code": "cs.ET", "name": "Emerging Technologies"},
            {"code": "cs.FL", "name": "Formal Languages and Automata Theory"},
            {"code": "cs.GL", "name": "General Literature"},
            {"code": "cs.GR", "name": "Graphics"},
            {"code": "cs.GT", "name": "Computer Science and Game Theory"},
            {"code": "cs.HC", "name": "Human-Computer Interaction"},
            {"code": "cs.IR", "name": "Information Retrieval"},
            {"code": "cs.IT", "name": "Information Theory"},
            {"code": "cs.LG", "name": "Machine Learning"},
            {"code": "cs.LO", "name": "Logic in Computer Science"},
            {"code": "cs.MA", "name": "Multiagent Systems"},
            {"code": "cs.MM", "name": "Multimedia"},
            {"code": "cs.MS", "name": "Mathematical Software"},
            {"code": "cs.NA", "name": "Numerical Analysis"},
            {"code": "cs.NE", "name": "Neural and Evolutionary Computing"},
            {"code": "cs.NI", "name": "Networking and Internet Architecture"},
            {"code": "cs.OH", "name": "Other Computer Science"},
            {"code": "cs.OS", "name": "Operating Systems"},
            {"code": "cs.PF", "name": "Performance"},
            {"code": "cs.PL", "name": "Programming Languages"},
            {"code": "cs.RO", "name": "Robotics"},
            {"code": "cs.SC", "name": "Symbolic Computation"},
            {"code": "cs.SD", "name": "Sound"},
            {"code": "cs.SE", "name": "Software Engineering"},
            {"code": "cs.SI", "name": "Social and Information Networks"},
            {"code": "cs.SY", "name": "Systems and Control"},
        ]
    },
    {
        "name": "Electrical Engineering and Systems Science",
        "code": "eess",
        "children": [
            {"code": "eess.AS", "name": "Audio and Speech Processing"},
            {"code": "eess.IV", "name": "Image and Video Processing"},
            {"code": "eess.SP", "name": "Signal Processing"},
            {"code": "eess.SY", "name": "Systems and Control"},
        ]
    },
    {
        "name": "Economics",
        "code": "econ",
        "children": [
            {"code": "econ.EM", "name": "Econometrics"},
            {"code": "econ.GN", "name": "General Economics"},
            {"code": "econ.TH", "name": "Theoretical Economics"},
        ]
    },
    {
        "name": "Mathematics",
        "code": "math",
        "children": [
            {"code": "math.AC", "name": "Commutative Algebra"},
            {"code": "math.AG", "name": "Algebraic Geometry"},
            {"code": "math.AP", "name": "Analysis of PDEs"},
            {"code": "math.AT", "name": "Algebraic Topology"},
            {"code": "math.CA", "name": "Classical Analysis and ODEs"},
            {"code": "math.CO", "name": "Combinatorics"},
            {"code": "math.CT", "name": "Category Theory"},
            {"code": "math.CV", "name": "Complex Variables"},
            {"code": "math.DG", "name": "Differential Geometry"},
            {"code": "math.DS", "name": "Dynamical Systems"},
            {"code": "math.FA", "name": "Functional Analysis"},
            {"code": "math.GM", "name": "General Mathematics"},
            {"code": "math.GN", "name": "General Topology"},
            {"code": "math.GR", "name": "Group Theory"},
            {"code": "math.GT", "name": "Geometric Topology"},
            {"code": "math.HO", "name": "History and Overview"},
            {"code": "math.IT", "name": "Information Theory"},
            {"code": "math.KT", "name": "K-Theory and Homology"},
            {"code": "math.LO", "name": "Logic"},
            {"code": "math.MG", "name": "Metric Geometry"},
            {"code": "math.MP", "name": "Mathematical Physics"},
            {"code": "math.NA", "name": "Numerical Analysis"},
            {"code": "math.NT", "name": "Number Theory"},
            {"code": "math.OA", "name": "Operator Algebras"},
            {"code": "math.OC", "name": "Optimization and Control"},
            {"code": "math.PR", "name": "Probability"},
            {"code": "math.QA", "name": "Quantum Algebra"},
            {"code": "math.RA", "name": "Rings and Algebras"},
            {"code": "math.RT", "name": "Representation Theory"},
            {"code": "math.SG", "name": "Symplectic Geometry"},
            {"code": "math.SP", "name": "Spectral Theory"},
            {"code": "math.ST", "name": "Statistics Theory"},
        ]
    },
    {
        "name": "Quantitative Biology",
        "code": "q-bio",
        "children": [
            {"code": "q-bio.BM", "name": "Biomolecules"},
            {"code": "q-bio.CB", "name": "Cell Behavior"},
            {"code": "q-bio.GN", "name": "Genomics"},
            {"code": "q-bio.MN", "name": "Molecular Networks"},
            {"code": "q-bio.NC", "name": "Neurons and Cognition"},
            {"code": "q-bio.OT", "name": "Other Quantitative Biology"},
            {"code": "q-bio.PE", "name": "Populations and Evolution"},
            {"code": "q-bio.QM", "name": "Quantitative Methods"},
            {"code": "q-bio.SC", "name": "Subcellular Processes"},
            {"code": "q-bio.TO", "name": "Tissues and Organs"},
        ]
    },
    {
        "name": "Quantitative Finance",
        "code": "q-fin",
        "children": [
            {"code": "q-fin.CP", "name": "Computational Finance"},
            {"code": "q-fin.EC", "name": "Economics"},
            {"code": "q-fin.GN", "name": "General Finance"},
            {"code": "q-fin.MF", "name": "Mathematical Finance"},
            {"code": "q-fin.PM", "name": "Portfolio Management"},
            {"code": "q-fin.PR", "name": "Pricing of Securities"},
            {"code": "q-fin.RM", "name": "Risk Management"},
            {"code": "q-fin.ST", "name": "Statistical Finance"},
            {"code": "q-fin.TR", "name": "Trading and Market Microstructure"},
        ]
    },
    {
        "name": "Statistics",
        "code": "stat",
        "children": [
            {"code": "stat.AP", "name": "Applications"},
            {"code": "stat.CO", "name": "Computation"},
            {"code": "stat.ME", "name": "Methodology"},
            {"code": "stat.ML", "name": "Machine Learning"},
            {"code": "stat.OT", "name": "Other Statistics"},
            {"code": "stat.TH", "name": "Statistics Theory"},
        ]
    },
    # Physics 主干（简化为扁平，因 arXiv 物理子类无统一父类）
    # 实际上 arXiv physics 是 flat list under "physics"
    {
        "name": "Physics",
        "code": "physics",
        "children": [
            {"code": "physics.acc-ph", "name": "Accelerator Physics"},
            {"code": "physics.ao-ph", "name": "Atmospheric and Oceanic Physics"},
            {"code": "physics.app-ph", "name": "Applied Physics"},
            {"code": "physics.atm-clus", "name": "Atomic and Molecular Clusters"},
            {"code": "physics.atom-ph", "name": "Atomic Physics"},
            {"code": "physics.bio-ph", "name": "Biological Physics"},
            {"code": "physics.chem-ph", "name": "Chemical Physics"},
            {"code": "physics.class-ph", "name": "Classical Physics"},
            {"code": "physics.comp-ph", "name": "Computational Physics"},
            {"code": "physics.data-an", "name": "Data Analysis, Statistics and Probability"},
            {"code": "physics.ed-ph", "name": "Physics Education"},
            {"code": "physics.flu-dyn", "name": "Fluid Dynamics"},
            {"code": "physics.gen-ph", "name": "General Physics"},
            {"code": "physics.geo-ph", "name": "Geophysics"},
            {"code": "physics.hist-ph", "name": "History of Physics"},
            {"code": "physics.ins-det", "name": "Instrumentation and Detectors"},
            {"code": "physics.med-ph", "name": "Medical Physics"},
            {"code": "physics.optics", "name": "Optics"},
            {"code": "physics.plasm-ph", "name": "Plasma Physics"},
            {"code": "physics.pop-ph", "name": "Popular Physics"},
            {"code": "physics.soc-ph", "name": "Physics and Society"},
            {"code": "physics.space-ph", "name": "Space Physics"},
        ]
    },
    # Condensed Matter (独立主类)
    {
        "name": "Condensed Matter",
        "code": "cond-mat",
        "children": [
            {"code": "cond-mat.dis-nn", "name": "Disordered Systems and Neural Networks"},
            {"code": "cond-mat.mes-hall", "name": "Mesoscale and Nanoscale Physics"},
            {"code": "cond-mat.mtrl-sci", "name": "Materials Science"},
            {"code": "cond-mat.other", "name": "Other Condensed Matter"},
            {"code": "cond-mat.quant-gas", "name": "Quantum Gases"},
            {"code": "cond-mat.soft", "name": "Soft Condensed Matter"},
            {"code": "cond-mat.stat-mech", "name": "Statistical Mechanics"},
            {"code": "cond-mat.str-el", "name": "Strongly Correlated Electrons"},
            {"code": "cond-mat.supr-con", "name": "Superconductivity"},
        ]
    },
    # High Energy Physics
    {
        "name": "High Energy Physics - Experiment",
        "code": "hep-ex",
        "children": []
    },
    {
        "name": "High Energy Physics - Lattice",
        "code": "hep-lat",
        "children": []
    },
    {
        "name": "High Energy Physics - Phenomenology",
        "code": "hep-ph",
        "children": []
    },
    {
        "name": "High Energy Physics - Theory",
        "code": "hep-th",
        "children": []
    },
    # Astrophysics
    {
        "name": "Astrophysics",
        "code": "astro-ph",
        "children": [
            {"code": "astro-ph.CO", "name": "Cosmology and Nongalactic Astrophysics"},
            {"code": "astro-ph.EP", "name": "Earth and Planetary Astrophysics"},
            {"code": "astro-ph.GA", "name": "Astrophysics of Galaxies"},
            {"code": "astro-ph.HE", "name": "High Energy Astrophysical Phenomena"},
            {"code": "astro-ph.IM", "name": "Instrumentation and Methods for Astrophysics"},
            {"code": "astro-ph.SR", "name": "Solar and Stellar Astrophysics"},
        ]
    },
    # Others (flat)
    {"name": "General Relativity and Quantum Cosmology", "code": "gr-qc", "children": []},
    {"name": "Nonlinear Sciences", "code": "nlin", "children": [
        {"code": "nlin.AO", "name": "Adaptation and Self-Organizing Systems"},
        {"code": "nlin.CD", "name": "Chaotic Dynamics"},
        {"code": "nlin.CG", "name": "Cellular Automata and Lattice Gases"},
        {"code": "nlin.PS", "name": "Pattern Formation and Solitons"},
        {"code": "nlin.SI", "name": "Exactly Solvable and Integrable Systems"},
    ]},
    {"name": "Nuclear Experiment", "code": "nucl-ex", "children": []},
    {"name": "Nuclear Theory", "code": "nucl-th", "children": []},
    {"name": "Mathematical Physics", "code": "math-ph", "children": []},
]

# 中文翻译字典（覆盖所有 arXiv 子类）
# 中文翻译字典（覆盖所有 arXiv 分类，包括主类和子类）
ZH_TRANSLATIONS = {
    # ===== Computer Science (cs) =====
    "Computer Science": "计算机科学",
    "Artificial Intelligence": "人工智能",
    "Hardware Architecture": "硬件架构",
    "Computational Complexity": "计算复杂性",
    "Computational Engineering, Finance, and Science": "计算工程、金融与科学",
    "Computer Graphics": "计算机图形学",
    "Computation and Language": "计算与语言",
    "Cryptography and Security": "密码学与安全",
    "Computer Vision and Pattern Recognition": "计算机视觉与模式识别",
    "Computers and Society": "计算机与社会",
    "Databases": "数据库",
    "Distributed, Parallel, and Cluster Computing": "分布式、并行与集群计算",
    "Digital Libraries": "数字图书馆",
    "Discrete Mathematics": "离散数学",
    "Data Structures and Algorithms": "数据结构与算法",
    "Emerging Technologies": "新兴技术",
    "Formal Languages and Automata Theory": "形式语言与自动机理论",
    "General Literature": "通用文献",
    "Graphics": "图形学",
    "Computer Science and Game Theory": "计算机科学与博弈论",
    "Human-Computer Interaction": "人机交互",
    "Information Retrieval": "信息检索",
    "Information Theory": "信息论",
    "Machine Learning": "机器学习",
    "Logic in Computer Science": "计算机逻辑",
    "Multiagent Systems": "多智能体系统",
    "Multimedia": "多媒体",
    "Mathematical Software": "数学软件",
    "Numerical Analysis": "数值分析",
    "Neural and Evolutionary Computing": "神经与进化计算",
    "Networking and Internet Architecture": "网络与互联网架构",
    "Other Computer Science": "其他计算机科学",
    "Operating Systems": "操作系统",
    "Performance": "性能",
    "Programming Languages": "编程语言",
    "Robotics": "机器人学",
    "Symbolic Computation": "符号计算",
    "Sound": "音频",
    "Software Engineering": "软件工程",
    "Social and Information Networks": "社会与信息网络",
    "Systems and Control": "系统与控制",

    # ===== Electrical Engineering and Systems Science (eess) =====
    "Electrical Engineering and Systems Science": "电气工程与系统科学",
    "Audio and Speech Processing": "音频与语音处理",
    "Image and Video Processing": "图像与视频处理",
    "Signal Processing": "信号处理",

    # ===== Economics (econ) =====
    "Economics": "经济学",
    "Econometrics": "计量经济学",
    "General Economics": "经济学概论",
    "Theoretical Economics": "理论经济学",

    # ===== Mathematics (math) =====
    "Mathematics": "数学",
    "Commutative Algebra": "交换代数",
    "Algebraic Geometry": "代数几何",
    "Analysis of PDEs": "偏微分方程分析",
    "Algebraic Topology": "代数拓扑",
    "Classical Analysis and ODEs": "经典分析与常微分方程",
    "Combinatorics": "组合数学",
    "Category Theory": "范畴论",
    "Complex Variables": "复变函数",
    "Differential Geometry": "微分几何",
    "Dynamical Systems": "动力系统",
    "Functional Analysis": "泛函分析",
    "General Mathematics": "数学概论",
    "General Topology": "一般拓扑",
    "Group Theory": "群论",
    "Geometric Topology": "几何拓扑",
    "History and Overview": "历史与综述",
    "Information Theory": "信息论",
    "K-Theory and Homology": "K理论与同调",
    "Logic": "逻辑",
    "Metric Geometry": "度量几何",
    "Mathematical Physics": "数学物理",
    "Number Theory": "数论",
    "Operator Algebras": "算子代数",
    "Optimization and Control": "优化与控制",
    "Probability": "概率论",
    "Quantum Algebra": "量子代数",
    "Rings and Algebras": "环与代数",
    "Representation Theory": "表示论",
    "Symplectic Geometry": "辛几何",
    "Spectral Theory": "谱理论",
    "Statistics Theory": "统计理论",

    # ===== Quantitative Biology (q-bio) =====
    "Quantitative Biology": "定量生物学",
    "Biomolecules": "生物分子",
    "Cell Behavior": "细胞行为",
    "Genomics": "基因组学",
    "Molecular Networks": "分子网络",
    "Neurons and Cognition": "神经元与认知",
    "Other Quantitative Biology": "其他定量生物学",
    "Populations and Evolution": "种群与进化",
    "Quantitative Methods": "定量方法",
    "Subcellular Processes": "亚细胞过程",
    "Tissues and Organs": "组织与器官",

    # ===== Quantitative Finance (q-fin) =====
    "Quantitative Finance": "定量金融",
    "Computational Finance": "计算金融",
    "Economics": "经济学",
    "General Finance": "金融学概论",
    "Mathematical Finance": "数理金融",
    "Portfolio Management": "投资组合管理",
    "Pricing of Securities": "证券定价",
    "Risk Management": "风险管理",
    "Statistical Finance": "统计金融",
    "Trading and Market Microstructure": "交易与市场微观结构",

    # ===== Statistics (stat) =====
    "Statistics": "统计学",
    "Applications": "应用统计",
    "Computation": "计算统计",
    "Methodology": "统计方法",
    "Machine Learning": "机器学习",
    "Other Statistics": "其他统计",
    "Statistics Theory": "统计理论",

    # ===== Physics (physics) =====
    "Physics": "物理学",
    "Accelerator Physics": "加速器物理",
    "Atmospheric and Oceanic Physics": "大气与海洋物理",
    "Applied Physics": "应用物理",
    "Atomic and Molecular Clusters": "原子与分子团簇",
    "Atomic Physics": "原子物理",
    "Biological Physics": "生物物理",
    "Chemical Physics": "化学物理",
    "Classical Physics": "经典物理",
    "Computational Physics": "计算物理",
    "Data Analysis, Statistics and Probability": "数据分析、统计与概率",
    "Physics Education": "物理教育",
    "Fluid Dynamics": "流体动力学",
    "General Physics": "普通物理",
    "Geophysics": "地球物理",
    "History of Physics": "物理史",
    "Instrumentation and Detectors": "仪器与探测器",
    "Medical Physics": "医学物理",
    "Optics": "光学",
    "Plasma Physics": "等离子体物理",
    "Popular Physics": "大众物理",
    "Physics and Society": "物理与社会",
    "Space Physics": "空间物理",

    # ===== Condensed Matter (cond-mat) =====
    "Condensed Matter": "凝聚态物理",
    "Disordered Systems and Neural Networks": "无序系统与神经网络",
    "Mesoscale and Nanoscale Physics": "介观与纳米物理",
    "Materials Science": "材料科学",
    "Other Condensed Matter": "其他凝聚态物理",
    "Quantum Gases": "量子气体",
    "Soft Condensed Matter": "软凝聚态物质",
    "Statistical Mechanics": "统计力学",
    "Strongly Correlated Electrons": "强关联电子",
    "Superconductivity": "超导",

    # ===== High Energy Physics =====
    "High Energy Physics - Experiment": "高能物理实验",
    "High Energy Physics - Lattice": "格点高能物理",
    "High Energy Physics - Phenomenology": "高能物理唯象学",
    "High Energy Physics - Theory": "高能物理理论",

    # ===== Astrophysics (astro-ph) =====
    "Astrophysics": "天体物理学",
    "Cosmology and Nongalactic Astrophysics": "宇宙学与非星系天体物理",
    "Earth and Planetary Astrophysics": "地球与行星天体物理",
    "Astrophysics of Galaxies": "星系天体物理",
    "High Energy Astrophysical Phenomena": "高能天体物理现象",
    "Instrumentation and Methods for Astrophysics": "天体物理仪器与方法",
    "Solar and Stellar Astrophysics": "太阳与恒星天体物理",

    # ===== Other Main Categories =====
    "General Relativity and Quantum Cosmology": "广义相对论与量子宇宙学",
    "Nonlinear Sciences": "非线性科学",
    "Adaptation and Self-Organizing Systems": "自适应与自组织系统",
    "Chaotic Dynamics": "混沌动力学",
    "Cellular Automata and Lattice Gases": "元胞自动机与格子气",
    "Pattern Formation and Solitons": "模式形成与孤子",
    "Exactly Solvable and Integrable Systems": "可解与可积系统",
    "Nuclear Experiment": "核物理实验",
    "Nuclear Theory": "核物理理论",
    "Mathematical Physics": "数学物理",  # 注意：math-ph 和 math.MP 都叫这个，但平台不同
}


# ======================
# bioRxiv / medRxiv 分类（官方列表）
# ======================

BIORXIV_CATEGORIES_I18N = {
    "Animal Behavior and Cognition": "动物行为与认知",
    "Biochemistry": "生物化学",
    "Bioengineering": "生物工程",
    "Bioinformatics": "生物信息学",
    "Biophysics": "生物物理学",
    "Cancer Biology": "癌症生物学",
    "Cell Biology": "细胞生物学",
    "Developmental Biology": "发育生物学",
    "Ecology": "生态学",
    "Evolutionary Biology": "进化生物学",
    "Genetics": "遗传学",
    "Genomics": "基因组学",
    "Immunology": "免疫学",
    "Microbiology": "微生物学",
    "Molecular Biology": "分子生物学",
    "Neuroscience": "神经科学",
    "Paleontology": "古生物学",
    "Pathology": "病理学",
    "Pharmacology and Toxicology": "药理学与毒理学",
    "Physiology": "生理学",
    "Plant Biology": "植物生物学",
    "Scientific Communication and Education": "科学传播与教育",
    "Synthetic Biology": "合成生物学",
    "Systems Biology": "系统生物学",
    "Zoology": "动物学"
}

MEDRXIV_CATEGORIES_I18N = {
    "Addiction Medicine": "成瘾医学",
    "Allergy and Immunology": "过敏与免疫学",
    "Anesthesiology": "麻醉学",
    "Cardiovascular Medicine": "心血管医学",
    "Dentistry": "牙科学",
    "Dermatology": "皮肤病学",
    "Diabetes": "糖尿病学",
    "Emergency Medicine": "急诊医学",
    "Endocrinology": "内分泌学",
    "Epidemiology": "流行病学",
    "Gastroenterology": "胃肠病学",
    "Genetic and Genomic Medicine": "遗传与基因组医学",
    "Geriatrics": "老年医学",
    "Health Economics": "卫生经济学",
    "Health Informatics": "健康信息学",
    "Health Policy": "卫生政策",
    "Hematology": "血液学",
    "Hepatology": "肝病学",
    "Infectious Diseases": "传染病学",
    "Intensive Care and Critical Care Medicine": "重症与危重病医学",
    "Medical Education": "医学教育",
    "Medical Ethics": "医学伦理学",
    "Nephrology": "肾病学",
    "Neurology": "神经病学",
    "Nursing": "护理学",
    "Nutrition": "营养学",
    "Obstetrics and Gynecology": "妇产科学",
    "Oncology": "肿瘤学",
    "Ophthalmology": "眼科学",
    "Orthopedics": "骨科学",
    "Otorhinolaryngology": "耳鼻喉科学",
    "Pain Medicine": "疼痛医学",
    "Pathology": "病理学",
    "Pediatrics": "儿科学",
    "Pharmacology and Clinical Pharmacology": "药理学与临床药理学",
    "Primary Care Research": "初级保健研究",
    "Psychiatry": "精神病学",
    "Public Health": "公共卫生",
    "Radiology and Imaging": "放射学与影像学",
    "Rehabilitation Medicine": "康复医学",
    "Respiratory Medicine": "呼吸病学",
    "Rheumatology": "风湿病学",
    "Sexual and Reproductive Health": "性与生殖健康",
    "Sports Medicine": "运动医学",
    "Surgery": "外科学",
    "Toxicology": "毒理学",
    "Urology": "泌尿外科学"
}

# ======================
# 工具函数
# ======================

def load_config(config_path: str = "../config.yaml") -> dict:
    if not os.path.exists(config_path):
        print(f"❌ 配置文件未找到: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["database"]


def connect_db(db_config: dict):
    try:
        conn = psycopg2.connect(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config["name"],
            user=db_config["user"],
            password=db_config["password"],
        )
        return conn
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}", file=sys.stderr)
        sys.exit(1)


def insert_category(
    cur,
    platform: str,
    code: str,
    name: str,
    parent_id: Optional[int] = None,
    names_i18n: Optional[Dict[str, str]] = None
) -> int:
    # 自动将 dict 转为 Json 对象，None 保持为 None
    json_value = Json(names_i18n) if names_i18n is not None else None
    
    cur.execute("""
        INSERT INTO categories (platform, code, name, parent_id, names_i18n)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (platform, code) DO UPDATE
        SET name = EXCLUDED.name, parent_id = EXCLUDED.parent_id, names_i18n = EXCLUDED.names_i18n
        RETURNING id;
    """, (platform, code, name, parent_id, json_value))
    return cur.fetchone()[0]


def init_arxiv_categories(cur):
    print("📦 初始化 arXiv 全量分类（含中文）...")
    total = 0
    for group in ARXIV_TAXONOMY:
        name = group["name"]
        code = group["code"]
        children = group.get("children", [])

        # 插入根节点（即使无子类）
        root_names_i18n = {"zh": ZH_TRANSLATIONS.get(name, name)} if name in ZH_TRANSLATIONS else None
        root_id = insert_category(cur, "arxiv", code, name, None, root_names_i18n)
        total += 1

        # 插入子类
        for child in children:
            child_name = child["name"]
            child_code = child["code"]
            zh_name = ZH_TRANSLATIONS.get(child_name, child_name)
            insert_category(
                cur,
                "arxiv",
                child_code,
                child_name,
                root_id,
                {"zh": zh_name}
            )
            total += 1

    print(f"✅ arXiv: {total} 个分类已插入")


def init_biorxiv_medrxiv_categories(cur):
    print("📦 初始化 bioRxiv / medRxiv 分类（含中文）...")

    # bioRxiv
    for en_name, zh_name in BIORXIV_CATEGORIES_I18N.items():
        code = en_name.lower().replace(" ", "_").replace("-", "_").replace(",", "")
        insert_category(
            cur,
            "biorxiv",
            code,
            en_name,
            None,
            {"zh": zh_name}
        )

    # medRxiv
    for en_name, zh_name in MEDRXIV_CATEGORIES_I18N.items():
        code = en_name.lower().replace(" ", "_").replace("-", "_").replace(",", "")
        insert_category(
            cur,
            "medrxiv",
            code,
            en_name,
            None,
            {"zh": zh_name}
        )

    total_bio = len(BIORXIV_CATEGORIES_I18N)
    total_med = len(MEDRXIV_CATEGORIES_I18N)
    print(f"✅ bioRxiv: {total_bio} 个分类已插入")
    print(f"✅ medRxiv: {total_med} 个分类已插入")


def init_flat_categories(cur, platform: str, names: List[str]):
    print(f"📦 初始化 {platform} 分类...")
    for name in names:
        code = name.lower().replace(" ", "_").replace("-", "_").replace(",", "")
        insert_category(cur, platform, code, name, None, None)
    print(f"✅ {platform}: {len(names)} 个分类已插入")


def main():
    print("🔧 正在初始化预印本全量分类体系...")

    config = load_config()
    conn = connect_db(config)
    cur = conn.cursor()

    try:
        init_arxiv_categories(cur)
        init_biorxiv_medrxiv_categories(cur)  # ← 使用新函数

        conn.commit()
        print("🎉 所有分类初始化成功！")
    except Exception as e:
        conn.rollback()
        print(f"❌ 初始化失败: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()