#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
罕见病诊断改进器

该脚本用于：
1. 分析诊断反馈数据
2. 识别常见错误模式
3. 生成诊断改进建议
4. 生成改进报告
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class DiagnosisImprover:
    """诊断改进器"""
    
    def __init__(self, memory_dir: str = None):
        """
        初始化诊断改进器
        
        Args:
            memory_dir: 记忆存储目录路径
        """
        if memory_dir is None:
            self.memory_dir = Path(__file__).parent.parent
        else:
            self.memory_dir = Path(memory_dir)
        
        self.feedback_file = self.memory_dir / "diagnosis_feedback.json"
        self.learning_file = self.memory_dir / "diagnosis_learning.json"
        self.patterns_file = self.memory_dir / "diagnosis_patterns.json"
        self.report_file = self.memory_dir / "improvement_report.md"
    
    def _load_json(self, file_path: Path) -> Dict:
        """加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_json(self, file_path: Path, data: Dict):
        """保存JSON文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def analyze_feedback_patterns(self) -> Dict:
        """
        分析反馈模式
        
        Returns:
            分析结果
        """
        feedback_data = self._load_json(self.feedback_file)
        feedbacks = feedback_data.get("feedbacks", [])
        
        if not feedbacks:
            return {
                "status": "no_data",
                "message": "暂无反馈数据"
            }
        
        analysis = {
            "total_feedbacks": len(feedbacks),
            "recent_feedbacks": [],
            "error_patterns": defaultdict(list),
            "accuracy_trend": [],
            "symptom_disease_map": defaultdict(lambda: defaultdict(int)),
            "disease_accuracy": defaultdict(lambda: {"correct": 0, "total": 0})
        }
        
        # 分析最近30天的反馈
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        for feedback in feedbacks:
            timestamp = datetime.fromisoformat(feedback["timestamp"])
            
            if timestamp > thirty_days_ago:
                analysis["recent_feedbacks"].append(feedback)
                
                # 记录错误模式
                if feedback.get("is_correct") is False:
                    predicted = feedback.get("predicted_disease", "")
                    actual = feedback.get("actual_disease", "")
                    if predicted and actual:
                        error_key = f"{predicted}|{actual}"
                        analysis["error_patterns"][error_key].append({
                            "symptoms": feedback.get("symptoms", ""),
                            "timestamp": feedback["timestamp"],
                            "comments": feedback.get("user_comments", "")
                        })
                
                # 记录症状-疾病映射
                symptoms = feedback.get("symptoms", "")
                predicted = feedback.get("predicted_disease", "")
                if symptoms and predicted:
                    analysis["symptom_disease_map"][symptoms][predicted] += 1
                
                # 记录疾病准确率
                disease = feedback.get("predicted_disease", "")
                if disease:
                    analysis["disease_accuracy"][disease]["total"] += 1
                    if feedback.get("is_correct") is True:
                        analysis["disease_accuracy"][disease]["correct"] += 1
        
        # 转换defaultdict为普通dict
        analysis["error_patterns"] = dict(analysis["error_patterns"])
        analysis["symptom_disease_map"] = {
            k: dict(v) for k, v in analysis["symptom_disease_map"].items()
        }
        analysis["disease_accuracy"] = {
            k: dict(v) for k, v in analysis["disease_accuracy"].items()
        }
        
        return analysis
    
    def generate_improvement_plan(self) -> Dict:
        """
        生成改进计划
        
        Returns:
            改进计划
        """
        analysis = self.analyze_feedback_patterns()
        
        if analysis.get("status") == "no_data":
            return {
                "status": "no_data",
                "message": "需要更多反馈数据来生成改进计划"
            }
        
        improvement_plan = {
            "generated_at": datetime.now().isoformat(),
            "priority_issues": [],
            "quick_wins": [],
            "long_term_improvements": [],
            "action_items": []
        }
        
        # 分析错误模式
        error_patterns = analysis.get("error_patterns", {})
        for error_key, instances in error_patterns.items():
            if len(instances) >= 3:  # 出现3次以上的错误模式
                predicted, actual = error_key.split("|")
                improvement_plan["priority_issues"].append({
                    "type": "frequent_error",
                    "severity": "high",
                    "description": f"疾病 '{predicted}' 经常被误诊为 '{actual}'",
                    "occurrences": len(instances),
                    "examples": instances[:3],
                    "suggestion": f"需要加强对 '{actual}' 症状特征的识别能力"
                })
        
        # 分析疾病准确率
        disease_accuracy = analysis.get("disease_accuracy", {})
        for disease, stats in disease_accuracy.items():
            if stats["total"] >= 5:  # 至少有5个案例
                accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                if accuracy < 0.7:
                    improvement_plan["priority_issues"].append({
                        "type": "low_accuracy",
                        "severity": "medium",
                        "description": f"疾病 '{disease}' 的诊断准确率仅为 {accuracy*100:.1f}%",
                        "occurrences": stats["total"],
                        "accuracy": accuracy,
                        "suggestion": f"建议审查 '{disease}' 的诊断规则和症状权重"
                    })
        
        # 生成快速改进建议
        if improvement_plan["priority_issues"]:
            improvement_plan["quick_wins"].append({
                "action": "审查高频率错误模式",
                "description": "针对出现3次以上的错误模式，调整诊断逻辑",
                "expected_impact": "减少30-50%的常见错误"
            })
        
        # 生成长期改进建议
        improvement_plan["long_term_improvements"].extend([
            {
                "action": "扩充疾病知识库",
                "description": "为准确率低于70%的疾病添加更多症状特征",
                "timeline": "1-2周"
            },
            {
                "action": "优化症状权重",
                "description": "基于反馈数据调整症状的权重系数",
                "timeline": "2-3周"
            },
            {
                "action": "引入鉴别诊断",
                "description": "为易混淆的疾病对添加鉴别诊断规则",
                "timeline": "3-4周"
            }
        ])
        
        # 生成具体行动项
        for issue in improvement_plan["priority_issues"]:
            if issue["type"] == "frequent_error":
                predicted, actual = issue["description"].split("'")[1], issue["description"].split("'")[3]
                improvement_plan["action_items"].append({
                    "priority": "high",
                    "action": f"为 '{actual}' 添加特异性症状规则",
                    "reason": issue["description"],
                    "estimated_effort": "中等"
                })
            elif issue["type"] == "low_accuracy":
                disease = issue["description"].split("'")[1]
                improvement_plan["action_items"].append({
                    "priority": "medium",
                    "action": f"审查 '{disease}' 的诊断逻辑",
                    "reason": issue["description"],
                    "estimated_effort": "中等"
                })
        
        return improvement_plan
    
    def generate_report(self) -> str:
        """
        生成改进报告
        
        Returns:
            Markdown格式的报告
        """
        analysis = self.analyze_feedback_patterns()
        plan = self.generate_improvement_plan()
        
        report_lines = [
            "# 罕见病诊断系统改进报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 一、数据概览",
            ""
        ]
        
        if analysis.get("status") == "no_data":
            report_lines.append("暂无反馈数据。请先收集诊断反馈。")
            return "\n".join(report_lines)
        
        report_lines.extend([
            f"- **总反馈数**: {analysis['total_feedbacks']}",
            f"- **最近30天反馈数**: {len(analysis['recent_feedbacks'])}",
            f"- **错误模式数**: {len(analysis['error_patterns'])}",
            f"- **涉及疾病数**: {len(analysis['disease_accuracy'])}",
            "",
            "---",
            "",
            "## 二、错误模式分析",
            ""
        ])
        
        error_patterns = analysis.get("error_patterns", {})
        if error_patterns:
            for i, (error_key, instances) in enumerate(error_patterns.items(), 1):
                predicted, actual = error_key.split("|")
                report_lines.extend([
                    f"### {i}. 误诊模式: {predicted} → {actual}",
                    f"- **出现次数**: {len(instances)}次",
                    f"- **示例症状**: {instances[0]['symptoms'][:100]}...",
                    ""
                ])
        else:
            report_lines.append("暂无错误模式。\n")
        
        report_lines.extend([
            "---",
            "",
            "## 三、疾病准确率分析",
            ""
        ])
        
        disease_accuracy = analysis.get("disease_accuracy", {})
        if disease_accuracy:
            sorted_diseases = sorted(
                disease_accuracy.items(),
                key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] > 0 else 0
            )
            
            for disease, stats in sorted_diseases:
                accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                accuracy_pct = accuracy * 100
                emoji = "[OK]" if accuracy >= 0.8 else "[WARN]" if accuracy >= 0.6 else "[FAIL]"
                
                report_lines.extend([
                    f"### {emoji} {disease}",
                    f"- **诊断次数**: {stats['total']}",
                    f"- **正确次数**: {stats['correct']}",
                    f"- **准确率**: {accuracy_pct:.1f}%",
                    ""
                ])
        else:
            report_lines.append("暂无疾病准确率数据。\n")
        
        report_lines.extend([
            "---",
            "",
            "## 四、改进计划",
            ""
        ])
        
        priority_issues = plan.get("priority_issues", [])
        if priority_issues:
            report_lines.append("### 优先处理事项\n")
            for i, issue in enumerate(priority_issues, 1):
                report_lines.extend([
                    f"{i}. **{issue['description']}**",
                    f"   - 严重程度: {issue['severity']}",
                    f"   - 建议: {issue['suggestion']}",
                    ""
                ])
        
        quick_wins = plan.get("quick_wins", [])
        if quick_wins:
            report_lines.append("### 快速改进建议\n")
            for i, win in enumerate(quick_wins, 1):
                report_lines.extend([
                    f"{i}. **{win['action']}**",
                    f"   - 说明: {win['description']}",
                    f"   - 预期效果: {win['expected_impact']}",
                    ""
                ])
        
        long_term = plan.get("long_term_improvements", [])
        if long_term:
            report_lines.append("### 长期改进计划\n")
            for i, improvement in enumerate(long_term, 1):
                report_lines.extend([
                    f"{i}. **{improvement['action']}**",
                    f"   - 说明: {improvement['description']}",
                    f"   - 时间线: {improvement['timeline']}",
                    ""
                ])
        
        action_items = plan.get("action_items", [])
        if action_items:
            report_lines.extend([
                "---",
                "",
                "## 五、行动清单",
                ""
            ])
            
            for i, item in enumerate(action_items, 1):
                priority_emoji = "[HIGH]" if item["priority"] == "high" else "[MED]" if item["priority"] == "medium" else "[LOW]"
                report_lines.extend([
                    f"{i}. {priority_emoji} **{item['action']}**",
                    f"   - 原因: {item['reason']}",
                    f"   - 工作量: {item['estimated_effort']}",
                    ""
                ])
        
        report_lines.extend([
            "---",
            "",
            "## 六、下一步行动",
            "",
            "1. 审查本报告中的优先处理事项",
            "2. 针对高频错误模式调整诊断逻辑",
            "3. 为低准确率疾病添加更多症状特征",
            "4. 继续收集诊断反馈",
            "5. 定期（每周）生成改进报告",
            "",
            "---",
            "",
            "*本报告由 Self-Improving Skill 自动生成*"
        ])
        
        report_content = "\n".join(report_lines)
        
        # 保存报告
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_content
    
    def apply_learned_rules(self, diagnosis_data: Dict) -> Dict:
        """
        应用学习规则到诊断数据
        
        Args:
            diagnosis_data: 诊断数据
            
        Returns:
            应用规则后的诊断数据
        """
        patterns_data = self._load_json(self.patterns_file)
        rules = patterns_data.get("learned_rules", [])
        
        symptoms = diagnosis_data.get("symptoms", "").lower()
        predicted_disease = diagnosis_data.get("predicted_disease", "")
        
        applied_rules = []
        
        for rule in rules:
            if rule.get("confidence", 0) < 0.8:  # 只应用高置信度规则
                continue
            
            condition = rule.get("condition", "").lower()
            
            # 检查规则是否适用
            if condition in symptoms or condition in predicted_disease.lower():
                # 应用规则
                action = rule.get("action", "")
                
                if "override" in rule.get("rule_type", ""):
                    # 覆盖诊断
                    if "|" in action:
                        old_disease, new_disease = action.split("|")
                        if old_disease.lower() in predicted_disease.lower():
                            diagnosis_data["predicted_disease"] = new_disease
                            diagnosis_data["rule_applied"] = rule.get("rule_id")
                            applied_rules.append(rule)
                
                elif "boost" in rule.get("rule_type", ""):
                    # 增强置信度
                    if "confidence_adjustments" not in diagnosis_data:
                        diagnosis_data["confidence_adjustments"] = []
                    
                    diagnosis_data["confidence_adjustments"].append({
                        "rule_id": rule.get("rule_id"),
                        "adjustment": action
                    })
                    applied_rules.append(rule)
                
                # 更新规则使用次数
                rule["usage_count"] = rule.get("usage_count", 0) + 1
        
        # 保存更新后的规则
        self._save_json(self.patterns_file, patterns_data)
        
        if applied_rules:
            diagnosis_data["applied_rules"] = applied_rules
        
        return diagnosis_data


def main():
    """主函数 - 用于命令行调用"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python diagnosis_improver.py analyze")
        print("  python diagnosis_improver.py plan")
        print("  python diagnosis_improver.py report")
        print("  python diagnosis_improver.py apply <diagnosis_json>")
        sys.exit(1)
    
    improver = DiagnosisImprover()
    
    command = sys.argv[1]
    
    if command == "analyze":
        analysis = improver.analyze_feedback_patterns()
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    
    elif command == "plan":
        plan = improver.generate_improvement_plan()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    
    elif command == "report":
        report = improver.generate_report()
        print(report)
        print(f"\n报告已保存至: {improver.report_file}")
    
    elif command == "apply":
        if len(sys.argv) < 3:
            print("错误: apply 命令需要诊断数据JSON")
            sys.exit(1)
        
        diagnosis_json = sys.argv[2]
        try:
            diagnosis_data = json.loads(diagnosis_json)
        except json.JSONDecodeError:
            print("错误: 无效的JSON格式")
            sys.exit(1)
        
        result = improver.apply_learned_rules(diagnosis_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()