#!/usr/bin/env python3
"""
罕见病诊断脚本 v3.0
基于本地 JSON 疾病知识库，通过关键词加权匹配 + 否定检测 + 年龄感知 + 同义词扩展进行罕见病辅助诊断。

Usage:
  python diagnose.py "<症状描述>"
  python diagnose.py "<症状描述>" --top 3
  python diagnose.py "<症状描述>" --json
  python diagnose.py "<症状描述>" --output
  python diagnose.py "<症状描述>" --fuzzy
  python diagnose.py --list-diseases
"""

import json
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

__version__ = "3.0.0"

# ─────────────────────────────────────────────
# 全局缓存
# ─────────────────────────────────────────────
_diseases_cache: Optional[list] = None
_diseases_cache_path: Optional[str] = None


def _clear_cache():
    global _diseases_cache, _diseases_cache_path
    _diseases_cache = None
    _diseases_cache_path = None


# ─────────────────────────────────────────────
# 中文医学术语同义词映射
# ─────────────────────────────────────────────
MEDICAL_SYNONYMS: Dict[str, List[str]] = {
    "少汗": ["不出汗", "无汗", "出汗少", "汗少", "汗少或无汗", "不出汗"],
    "烧灼痛": ["烧灼感", "灼痛", "烧痛", "烧灼样疼痛", "烧灼样痛", "灼热痛"],
    "烧灼感": ["烧灼痛", "灼痛", "烧痛", "烧灼样疼痛"],
    "无力": ["乏力", "虚弱", "肌无力", "没力气", "浑身没劲", "乏力"],
    "疼痛": ["痛", "疼", "疼痛感", "酸痛", "胀痛", "刺痛"],
    "肿胀": ["肿", "肿大", "浮肿", "水肿", "肿胀感"],
    "皮疹": ["红点", "斑点", "疹子", "丘疹", "皮肤红点", "皮疹"],
    "抽搐": ["惊厥", "癫痫", "羊癫疯", "抽风", "抽搐"],
    "腹泻": ["拉肚子", "水样便", "稀便", "大便稀", "泄泻"],
    "腹痛": ["肚子疼", "肚痛", "腹部疼痛", "腹痛"],
    "蛋白尿": ["尿蛋白", "尿蛋白阳性", "蛋白尿阳性"],
    "贫血": ["血红蛋白低", "贫血貌", "贫血"],
    "血小板减少": ["血小板低", "血小板减少症", "血小板低下"],
    "肝脾肿大": ["肝大", "脾大", "肝脏大", "脾脏大"],
    "肌萎缩": ["肌肉萎缩", "肌肉变小", "肌肉消瘦", "肌肉体积减小"],
    "肌束震颤": ["肉跳", "肌肉跳动", "肌束跳动", "肌肉震颤"],
    "肌张力低下": ["肌肉松软", "肌张力低", "软绵绵", "肌张力减退"],
    "角膜环": ["k-f环", "kf环", "角膜k-f环", "角膜色素环", "棕色角膜环", "角膜棕褐色环"],
    "色素沉着": ["皮肤变黑", "皮肤发黑", "色素沉着", "皮肤色素沉着"],
    "低血压": ["血压低", "血压偏低", "血压下降"],
    "高血压": ["血压高", "血压升高", "血压偏高"],
    "头痛": ["头疼", "头部疼痛", "头痛"],
    "恶心": ["想吐", "恶心感", "恶心呕吐"],
    "呕吐": ["吐", "呕吐", "恶心呕吐"],
    "发热": ["发烧", "体温升高", "发热", "发烧"],
    "咳嗽": ["咳嗽", "咳", "咳嗽不止"],
    "肺炎": ["肺部感染", "肺炎", "肺感染"],
    "发育迟缓": ["发育慢", "发育落后", "生长发育迟缓", "发育延迟"],
    "关节脱位": ["脱臼", "关节脱臼", "脱位"],
    "关节过度活动": ["关节活动度过大", "关节松弛", "关节活动范围大"],
    "皮肤脆弱": ["皮肤易破", "皮肤一碰就破", "皮肤脆弱", "皮肤菲薄"],
    "白瞳": ["瞳孔发白", "白瞳孔", "猫眼反射", "猫眼"],
    "斜视": ["斗鸡眼", "斜视", "眼球偏斜"],
    "血尿": ["尿血", "血尿", "尿中带血"],
    "耳聋": ["听力下降", "耳聋", "听力减退", "失聪"],
    "咖啡斑": ["牛奶咖啡斑", "咖啡牛奶斑", "棕褐色斑"],
    "血管纤维瘤": ["面部疙瘩", "面部小疙瘩", "血管纤维瘤", "面部血管纤维瘤"],
    "结节": ["皮下结节", "结节", "皮下包块"],
    "多汗": ["出汗多", "多汗", "大汗", "出汗增多"],
    "少食": ["食欲差", "食欲不振", "吃得少", "食欲不好"],
    "暴食": ["吃得多", "食欲亢进", "贪吃", "暴饮暴食", "永远吃不饱"],
    "肥胖": ["超重", "肥胖", "体重超标", "体重过重"],
    "身材矮小": ["矮小", "个子矮", "身材偏矮", "比同龄人矮"],
    "特殊面容": ["面容特殊", "长相特殊", "特殊面容", "面容异常"],
    "关节僵硬": ["关节伸不直", "关节活动受限", "关节僵硬", "关节不能伸直"],
    "反复感染": ["经常感染", "反复感染", "易感染", "反复感冒", "反复肺炎"],
    "癫痫": ["抽搐", "惊厥", "羊癫疯", "抽风"],
    "点头样抽搐": ["点头样发作", "点头抽搐", "婴儿痉挛"],
    "智力低下": ["智力障碍", "智力低下", "智能低下", "智力发育迟缓"],
    "性格改变": ["性格异常", "性格变化", "性格改变", "行为异常"],
    "震颤": ["抖动", "手抖", "震颤", "发抖"],
    "黄疸": ["皮肤黄", "巩膜黄", "黄疸", "皮肤黄染"],
    "紫癜": ["皮肤紫斑", "紫癜", "出血点", "瘀斑"],
    "瘀青": ["瘀斑", "瘀青", "青一块", "皮下出血"],
    "鼻出血": ["流鼻血", "鼻衄", "鼻出血"],
    "脱发": ["掉头发", "头发脱落", "脱发"],
    "光敏感": ["怕光", "光过敏", "光敏感", "日光过敏"],
    "口腔溃疡": ["口疮", "口腔溃疡", "口腔破损"],
    "蝶形红斑": ["面部红斑", "蝶形红斑", "面部蝴蝶斑"],
    "关节炎": ["关节痛", "关节疼痛", "关节炎", "关节肿痛"],
    "肌炎": ["肌肉炎症", "肌炎", "肌肉发炎"],
    "钙化": ["钙沉积", "钙化", "钙盐沉积"],
    "垂体瘤": ["垂体肿瘤", "垂体腺瘤", "垂体瘤"],
    "视网膜母细胞瘤": ["视网膜肿瘤", "眼底肿瘤", "视网膜瘤"],
    "嗜铬细胞瘤": ["肾上腺肿瘤", "嗜铬细胞瘤", "儿茶酚胺瘤"],
    "肾囊肿": ["肾囊肿", "肾脏囊肿", "多囊肾"],
    "动脉瘤": ["动脉扩张", "动脉瘤", "动脉膨出"],
    "主动脉夹层": ["主动脉撕裂", "主动脉夹层", "主动脉剥离"],
    "胸痛": ["胸口痛", "胸部疼痛", "胸痛"],
    "气短": ["呼吸困难", "气短", "喘不上气", "呼吸急促"],
    "心悸": ["心慌", "心跳快", "心悸", "心跳加速"],
    "大汗": ["出汗多", "大汗淋漓", "多汗", "大汗"],
    "面色苍白": ["脸色苍白", "苍白", "面色苍白", "脸色发白"],
    "肢端发绀": ["手脚发紫", "肢端青紫", "肢端发绀"],
    "杵状指": ["鼓槌指", "杵状指", "手指呈鼓槌状"],
    "蜘蛛痣": ["蜘蛛斑", "蜘蛛痣", "蜘蛛状血管痣"],
    "肝掌": ["手掌发红", "肝掌", "肝掌红斑"],
    "男性乳房发育": ["乳房增大", "男性乳房发育", "男性乳腺发育"],
    " fertility": ["生育能力", "生育", "生育问题"],
    "流产": ["自然流产", "反复流产", "习惯性流产"],
}


# ─────────────────────────────────────────────
# 中文否定词检测
# 注意：仅检测真正"否认症状存在"的否定词（如"没有少汗"）
# 不包含描述"丧失能力"的词汇（如"不会翻身"描述的是运动障碍症状，不应被否定）
# ─────────────────────────────────────────────
NEGATION_PATTERNS = [
    r'没有', r'无', r'未', r'否认', r'除外', r'排除', r'不曾', r'从未',
    r'不是', r'非', r'莫', r'没有过', r'无明显', r'未见', r'不伴有',
]


def is_negated(text: str, keyword: str, window: int = 5) -> bool:
    """检测关键词是否被否定词修饰（如"没有少汗"中的"少汗"）"""
    if not keyword or len(keyword) == 0:
        return False
    kw_norm = keyword.strip()
    pos = text.find(kw_norm)
    if pos == -1:
        return False
    start = max(0, pos - window)
    context = text[start:pos + len(kw_norm) + window]
    for pat in NEGATION_PATTERNS:
        if re.search(pat, context):
            return True
    return False


# ─────────────────────────────────────────────
# 年龄解析
# ─────────────────────────────────────────────
def parse_age_from_text(text: str) -> Optional[float]:
    """从症状描述中提取年龄（单位：岁）"""
    m = re.search(r'(\d+)\s*岁', text)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+)\s*个月', text)
    if m:
        return float(m.group(1)) / 12.0
    m = re.search(r'(\d+)\s*天', text)
    if m:
        return float(m.group(1)) / 365.0
    age_keywords = {
        '新生儿': 0.1, '婴儿': 0.5, '宝宝': 0.5, '幼儿': 2.0,
        '儿童': 6.0, '少年': 12.0, '青少年': 15.0,
        '青年': 25.0, '成年': 30.0, '中年': 45.0, '老年': 65.0,
    }
    for kw, age in age_keywords.items():
        if kw in text:
            return float(age)
    return None


def onset_age_to_range(onset_age: str) -> Tuple[Optional[float], Optional[float]]:
    """将 onset_age 字符串转换为 (min_age, max_age) 范围（单位：岁）"""
    if not onset_age:
        return None, None
    s = onset_age.lower()
    if '出生' in s or '新生儿' in s:
        if '婴幼儿' in s:
            return 0.0, 3.0
        if '婴儿' in s:
            return 0.0, 1.0
        return 0.0, 0.5
    if '儿童' in s and '青少年' in s:
        return 3.0, 18.0
    if '儿童' in s:
        return 3.0, 12.0
    if '青少年' in s:
        return 13.0, 18.0
    if '成年' in s:
        return 18.0, 100.0
    if '老年' in s:
        return 60.0, 100.0
    m = re.search(r'(\d+)\s*[-–—]\s*(\d+)\s*岁', s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'(\d+)\s*岁', s)
    if m:
        return float(m.group(1)), float(m.group(1)) + 10.0
    return None, None


def age_alignment_score(patient_age: Optional[float], onset_min: Optional[float], onset_max: Optional[float]) -> float:
    """计算患者年龄与疾病好发年龄的匹配度，返回 -1.0 ~ +1.0"""
    if patient_age is None or onset_min is None or onset_max is None:
        return 0.0
    if onset_min <= patient_age <= onset_max:
        return 1.0
    if patient_age < onset_min:
        gap = onset_min - patient_age
        if gap <= 3.0:
            return 0.5
        return max(-1.0, -gap / 10.0)
    gap = patient_age - onset_max
    if gap <= 5.0:
        return 0.5
    return max(-1.0, -gap / 10.0)


# ─────────────────────────────────────────────
# 同义词匹配
# ─────────────────────────────────────────────
def synonym_match(keyword: str, text: str) -> bool:
    """检查关键词的同义词是否出现在文本中"""
    syns = MEDICAL_SYNONYMS.get(keyword, [])
    for syn in syns:
        if syn in text:
            return True
    # 反向查找：text 中的词是否是 keyword 的同义词
    for k, syns in MEDICAL_SYNONYMS.items():
        if keyword == k:
            continue
        for syn in syns:
            if syn in text and keyword in syn:
                return True
    return False


# ─────────────────────────────────────────────
# 文本预处理
# ─────────────────────────────────────────────
def normalize_text(text: str) -> str:
    """标准化文本：全角转半角、去标点、合并空格、转小写"""
    chars = []
    for c in text:
        code = ord(c)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            chars.append(' ')
        else:
            chars.append(c)
    text = ''.join(chars).lower()
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def fuzzy_match_chars(keyword: str, text: str) -> tuple[bool, float]:
    """字符级模糊匹配"""
    if keyword in text:
        return True, 1.0
    chars = list(keyword)
    pos = 0
    first_pos = -1
    for c in chars:
        found = text.find(c, pos)
        if found == -1:
            return False, 0.0
        if first_pos < 0:
            first_pos = found
        pos = found + 1
    span = pos - first_pos
    quality = max(0.1, min(1.0, len(chars) / span)) if span > 0 else 1.0
    return True, quality


# ─────────────────────────────────────────────
# 数据加载（带缓存）
# ─────────────────────────────────────────────
def load_disease_db(data_path: Optional[str] = None) -> list[dict]:
    """加载本地罕见病 JSON 数据库，带模块级缓存"""
    global _diseases_cache, _diseases_cache_path
    if data_path is None:
        script_dir = Path(__file__).resolve().parent
        skill_root = script_dir.parent
        data_path = str(skill_root / 'data' / 'diseases.json')
    else:
        data_path = str(Path(data_path))
    if _diseases_cache is not None and _diseases_cache_path == data_path:
        return _diseases_cache
    if not Path(data_path).exists():
        print(f'错误：数据文件不存在 → {data_path}', file=sys.stderr)
        sys.exit(1)
    with open(data_path, 'r', encoding='utf-8-sig') as f:
        db = json.load(f)
    _diseases_cache = db.get('diseases', [])
    _diseases_cache_path = data_path
    return _diseases_cache


# ─────────────────────────────────────────────
# 匹配引擎 v3.0
# ─────────────────────────────────────────────
def match_disease(symptoms: str, diseases: list[dict], top_k: int = 1,
                  fuzzy: bool = False) -> list[dict]:
    """
    基于关键词加权匹配 + 否定检测 + 年龄感知 + 同义词扩展进行罕见病诊断。
    """
    normalized = normalize_text(symptoms)
    patient_age = parse_age_from_text(normalized)
    results = []

    for disease in diseases:
        keywords = disease.get('keywords', [])
        core_symptoms = disease.get('core_symptoms', [])
        onset_min, onset_max = onset_age_to_range(disease.get('onset_age', ''))
        age_score = age_alignment_score(patient_age, onset_min, onset_max)

        keyword_hits = []
        keyword_score = 0.0
        symptom_hits = []
        symptom_score = 0.0

        for kw in keywords:
            kw_norm = normalize_text(kw)
            if kw_norm in normalized:
                if not is_negated(normalized, kw_norm):
                    keyword_hits.append(kw)
                    keyword_score += 1.0 + (0.2 if len(kw_norm) >= 3 else 0.0)
            elif fuzzy:
                matched, quality = fuzzy_match_chars(kw_norm, normalized)
                if matched and not is_negated(normalized, kw_norm):
                    keyword_hits.append(kw + '(模糊)')
                    keyword_score += quality
            elif synonym_match(kw_norm, normalized):
                if not is_negated(normalized, kw_norm):
                    keyword_hits.append(kw + '(同义)')
                    keyword_score += 0.7

        for s in core_symptoms:
            s_norm = normalize_text(s)
            if s_norm in normalized:
                if not is_negated(normalized, s_norm):
                    symptom_hits.append(s)
                    symptom_score += 1.5 + (0.3 if len(s_norm) >= 3 else 0.0)
            elif fuzzy:
                matched, quality = fuzzy_match_chars(s_norm, normalized)
                if matched and not is_negated(normalized, s_norm):
                    symptom_hits.append(s + '(模糊)')
                    symptom_score += 1.5 * quality
            elif synonym_match(s_norm, normalized):
                if not is_negated(normalized, s_norm):
                    symptom_hits.append(s + '(同义)')
                    symptom_score += 1.0

        total_possible = len(keywords) * 1.0 + len(core_symptoms) * 1.5
        raw_score = keyword_score + symptom_score
        if age_score > 0:
            raw_score *= (1.0 + 0.15 * age_score)
        elif age_score < 0:
            raw_score *= (1.0 + 0.15 * age_score)
        normalized_score = raw_score / total_possible if total_possible > 0 else 0

        if raw_score > 0:
            results.append({
                'id': disease['id'],
                'name': disease['name'],
                'name_en': disease.get('name_en', ''),
                'icd10': disease.get('icd10', ''),
                'category': disease.get('category', ''),
                'prevalence': disease.get('prevalence', ''),
                'key_features': disease.get('key_features', ''),
                'onset_age': disease.get('onset_age', ''),
                'diagnostic_criteria': disease.get('diagnostic_criteria', ''),
                'lab_markers': disease.get('lab_markers', []),
                'genetic_test': disease.get('genetic_test', ''),
                'treatment_summary': disease.get('treatment_summary', ''),
                'keyword_hits': keyword_hits,
                'symptom_hits': symptom_hits,
                'raw_score': round(raw_score, 2),
                'normalized_score': round(normalized_score, 4),
                'confidence': _score_to_confidence(raw_score, normalized_score),
                'cases': disease.get('cases', []),
            })

    results.sort(key=lambda x: x['raw_score'], reverse=True)
    return results[:top_k]


def _score_to_confidence(raw_score: float, normalized_score: float = 0.0) -> str:
    """
    将原始得分转换为置信度等级（v3.0）。
    - 高：raw_score >= 5.0 或 (raw_score >= 3.5 且 normalized_score >= 0.4)
    - 中：raw_score >= 3.0 或 (raw_score >= 2.0 且 normalized_score >= 0.3)
    - 低：raw_score >= 1.5
    """
    if raw_score >= 5.0 or (raw_score >= 3.5 and normalized_score >= 0.4):
        return '高'
    elif raw_score >= 3.0 or (raw_score >= 2.0 and normalized_score >= 0.3):
        return '中'
    elif raw_score >= 1.5:
        return '低'
    return '极低'


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────
def format_cases(cases: list[dict]) -> str:
    """将案例数据格式化为可读文本"""
    if not cases:
        return ''
    lines = []
    lines.append('')
    lines.append(f'【相关临床案例共 {len(cases)} 例】')
    lines.append('')
    for i, case in enumerate(cases, 1):
        lines.append(f'  ┌─ 案例 {i}: {case.get("title", "")}')
        lines.append(f'  │ 患者: {case.get("patient", "")}')
        lines.append(f'  │ 主诉: {case.get("chief_complaint", "")}')
        lines.append(f'  ├─ 病史')
        for h_line in case.get('history', '').split('。'):
            if h_line.strip():
                lines.append(f'  │    {h_line.strip()}。')
        lines.append(f'  ├─ 检查发现')
        for f_line in case.get('findings', '').split('。'):
            if f_line.strip():
                lines.append(f'  │    {f_line.strip()}。')
        lines.append(f'  ├─ 诊断')
        for d_line in case.get('diagnosis', '').split('。'):
            if d_line.strip():
                lines.append(f'  │    {d_line.strip()}。')
        lines.append(f'  ├─ 治疗经过')
        for t_line in case.get('treatment', '').split('。'):
            if t_line.strip():
                lines.append(f'  │    {t_line.strip()}。')
        lines.append(f'  └─ 【启示】{case.get("key_takeaway", "")}')
        lines.append('')
    return '\n'.join(lines)


def format_result_text(results: list[dict], symptoms: str,
                       detail: bool = False, show_cases: bool = False) -> str:
    """将匹配结果格式化为可读文本"""
    if not results:
        return '该用户可能患有其他疾病（未在罕见病知识库中找到匹配）'

    lines = []
    top = results[0]

    if top['confidence'] == '高':
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）')
    elif top['confidence'] == '中':
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）— 建议进一步检查')
    else:
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）— 匹配度较低，仅供参考')

    lines.append('')
    lines.append('【疾病信息】')
    lines.append(f'  ICD-10: {top["icd10"]}')
    lines.append(f'  分类: {top["category"]}')
    lines.append(f'  患病率: {top["prevalence"]}')
    lines.append(f'  好发年龄: {top["onset_age"]}')
    lines.append(f'  核心特征: {top["key_features"]}')
    if top.get('diagnostic_criteria'):
        lines.append(f'  诊断标准: {top["diagnostic_criteria"]}')
    if top.get('genetic_test'):
        lines.append(f'  基因检测: {top["genetic_test"]}')

    lines.append('')
    lines.append('【匹配详情】')
    lines.append(f'  置信度: {top["confidence"]}')
    if detail:
        lines.append(f'  原始得分: {top["raw_score"]}')
        lines.append(f'  归一化得分: {top["normalized_score"]}')
    if top['keyword_hits']:
        lines.append(f'  命中关键词: {", ".join(top["keyword_hits"])}')
    if top['symptom_hits']:
        lines.append(f'  命中核心症状: {", ".join(top["symptom_hits"])}')

    if len(results) > 1:
        lines.append('')
        lines.append('【鉴别诊断】')
        for r in results[1:3]:
            if detail:
                lines.append(f'  - {r["name"]}（{r["name_en"]}），置信度: {r["confidence"]}（得分: {r["raw_score"]}）')
            else:
                lines.append(f'  - {r["name"]}（{r["name_en"]}），置信度: {r["confidence"]}')

    lines.append('')
    lines.append('【实验室检查】')
    if top.get('lab_markers'):
        for marker in top['lab_markers']:
            lines.append(f'  • {marker}')

    lines.append('')
    lines.append('【治疗概要】')
    if top.get('treatment_summary'):
        lines.append(f'  {top["treatment_summary"]}')

    if show_cases and top.get('cases'):
        lines.append(format_cases(top['cases']))

    lines.append('')
    lines.append('[!] 免责声明：本结果仅供学习参考，不构成医疗诊断依据。如有健康疑虑，请及时就医。')

    return '\n'.join(lines)


def format_result_json(results: list[dict]) -> str:
    """将匹配结果格式化为 JSON"""
    if not results:
        return json.dumps({
            'diagnosis': '该用户可能患有其他疾病',
            'matches': [],
            'disclaimer': '本结果仅供学习参考，不构成医疗诊断依据。'
        }, ensure_ascii=False, indent=2)

    output = {
        'diagnosis': f'该用户可能患有{results[0]["name"]}',
        'top_match': {
            'name': results[0]['name'],
            'name_en': results[0]['name_en'],
            'icd10': results[0]['icd10'],
            'category': results[0]['category'],
            'confidence': results[0]['confidence'],
            'raw_score': results[0]['raw_score'],
            'normalized_score': results[0]['normalized_score'],
            'key_features': results[0]['key_features'],
        },
        'differential_diagnosis': [
            {
                'name': r['name'],
                'name_en': r['name_en'],
                'confidence': r['confidence'],
                'raw_score': r['raw_score'],
            }
            for r in results[1:3]
        ],
        'disclaimer': '本结果仅供学习参考，不构成医疗诊断依据。'
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def save_output(text: str, symptoms: str) -> str:
    """将诊断结果保存至 output/ 目录"""
    output_dir = Path.cwd() / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
    filepath = output_dir / f'{timestamp}_diagnosis.md'
    markdown = (
        f'# 罕见病辅助诊断报告\n\n'
        f'## 基本信息\n\n'
        f'- **诊断时间**: {timestamp}\n'
        f'- **症状描述**: {symptoms}\n\n'
        f'---\n\n'
        f'## 诊断结果\n\n{text}\n'
    )
    filepath.write_text(markdown, encoding='utf-8')
    return str(filepath)


# ─────────────────────────────────────────────
# 辅助功能
# ─────────────────────────────────────────────
def list_diseases(diseases: list[dict]) -> str:
    """列出数据库中所有罕见病"""
    lines = [f'罕见病知识库共收录 {len(diseases)} 种疾病：', '']
    for i, d in enumerate(diseases, 1):
        lines.append(f'  {i:2d}. {d["name"]}（{d.get("name_en", "")}）— {d.get("category", "")}')
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='罕见病辅助诊断脚本 — 基于本地 JSON 知识库的关键词匹配',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('symptoms', nargs='*', help='症状描述文本（支持多个参数，自动拼接）')
    parser.add_argument('--top', '-k', type=int, default=3,
                        help='返回前 K 个匹配结果（默认 3）')
    parser.add_argument('--json', '-j', action='store_true',
                        help='以 JSON 格式输出')
    parser.add_argument('--data', '-d', help='指定疾病数据库 JSON 文件路径')
    parser.add_argument('--list-diseases', '-l', action='store_true',
                        help='列出数据库中所有疾病')
    parser.add_argument('--fuzzy', '-f', action='store_true',
                        help='启用字符级模糊匹配（降低准确度换取更高召回率）')
    parser.add_argument('--output', '-o', action='store_true',
                        help='将诊断结果保存至 output/ 目录（同时打印到终端）')
    parser.add_argument('--detail', action='store_true',
                        help='显示详细匹配得分信息')
    parser.add_argument('--cases', '-c', action='store_true',
                        help='显示匹配疾病的详细临床案例')
    return parser.parse_args()


def main():
    args = parse_args()
    diseases = load_disease_db(args.data)

    if args.list_diseases:
        print(list_diseases(diseases))
        return

    symptoms_parts = args.symptoms if isinstance(args.symptoms, list) else [args.symptoms]
    top_k = args.top

    if len(symptoms_parts) >= 2 and symptoms_parts[-1].isdigit():
        try:
            top_k = int(symptoms_parts[-1])
            symptoms_parts = symptoms_parts[:-1]
        except ValueError:
            pass

    symptoms_text = ' '.join(symptoms_parts) if symptoms_parts else ''

    if not symptoms_text:
        print('用法: python diagnose.py "<症状描述>"')
        print('      python diagnose.py --list-diseases')
        sys.exit(1)

    results = match_disease(symptoms_text, diseases, top_k=top_k, fuzzy=args.fuzzy)

    if args.json:
        output = format_result_json(results)
    else:
        output = format_result_text(results, symptoms_text, detail=args.detail, show_cases=args.cases)

    print(output)

    if args.output and not args.json:
        saved_path = save_output(output, symptoms_text)
        print(f'\n[已保存至] {saved_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
