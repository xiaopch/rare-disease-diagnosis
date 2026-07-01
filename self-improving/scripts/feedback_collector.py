#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
罕见病诊断反馈收集和自我改进系统

该脚本用于：
1. 收集诊断反馈（准确率评分、正确/错误诊断）
2. 分析诊断模式和错误类型
3. 生成改进建议
4. 更新诊断模型的知识库
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DiagnosisFeedbackCollector:
    """诊断反馈收集器"""
    
    def __init__(self, memory_dir: str = None):
        """
        初始化反馈收集器
        
        Args:
            memory_dir: 记忆存储目录路径
        """
        if memory_dir is None:
            # 默认使用 self-improving 目录
            self.memory_dir = Path(__file__).parent.parent
        else:
            self.memory_dir = Path(memory_dir)
        
        self.feedback_file = self.memory_dir / "diagnosis_feedback.json"
        self.learning_file = self.memory_dir / "diagnosis_learning.json"
        self.patterns_file = self.memory_dir / "diagnosis_patterns.json"
        
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化文件
        self._init_files()
    
    def _init_files(self):
        """初始化反馈和学习文件"""
        if not self.feedback_file.exists():
            self._save_json(self.feedback_file, {
                "total_feedbacks": 0,
                "feedbacks": []
            })
        
        if not self.learning_file.exists():
            self._save_json(self.learning_file, {
                "common_errors": {},
                "accuracy_stats": {
                    "total_cases": 0,
                    "correct_cases": 0,
                    "accuracy_rate": 0.0
                },
                "symptom_patterns": {},
                "disease_patterns": {}
            })
        
        if not self.patterns_file.exists():
            self._save_json(self.patterns_file, {
                "improvement_suggestions": [],
                "learned_rules": []
            })
    
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
    
    def collect_feedback(
        self,
        symptoms: str,
        predicted_disease: str,
        actual_disease: Optional[str] = None,
        is_correct: bool = None,
        accuracy_score: int = None,
        user_comments: str = "",
        doctor_verified: bool = False
    ) -> Dict:
        """
        收集诊断反馈
        
        Args:
            symptoms: 症状描述
            predicted_disease: 预测的疾病
            actual_disease: 实际疾病（如果已知）
            is_correct: 诊断是否正确
            accuracy_score: 准确率评分 (1-5)
            user_comments: 用户评论
            doctor_verified: 是否由医生验证
            
        Returns:
            反馈记录
        """
        timestamp = datetime.now().isoformat()
        
        feedback_record = {
            "timestamp": timestamp,
            "symptoms": symptoms,
            "predicted_disease": predicted_disease,
            "actual_disease": actual_disease,
            "is_correct": is_correct,
            "accuracy_score": accuracy_score,
            "user_comments": user_comments,
            "doctor_verified": doctor_verified
        }
        
        # 加载现有反馈
        feedback_data = self._load_json(self.feedback_file)
        
        # 添加新反馈
        feedback_data["feedbacks"].append(feedback_record)
        feedback_data["total_feedbacks"] = len(feedback_data["feedbacks"])
        
        # 保存反馈
        self._save_json(self.feedback_file, feedback_data)
        
        # 分析反馈
        self._analyze_feedback(feedback_record)
        
        return feedback_record
    
    def _analyze_feedback(self, feedback: Dict):
        """分析反馈并更新学习数据"""
        learning_data = self._load_json(self.learning_file)
        
        # 更新统计
        stats = learning_data["accuracy_stats"]
        stats["total_cases"] += 1
        
        if feedback.get("is_correct") is True:
            stats["correct_cases"] += 1
        
        stats["accuracy_rate"] = (
            stats["correct_cases"] / stats["total_cases"] 
            if stats["total_cases"] > 0 else 0.0
        )
        
        # 分析症状模式
        if feedback.get("is_correct") is False and feedback.get("actual_disease"):
            symptoms = feedback["symptoms"]
            actual_disease = feedback["actual_disease"]
            predicted_disease = feedback["predicted_disease"]
            
            # 记录错误模式
            error_key = f"{predicted_disease} -> {actual_disease}"
            if error_key not in learning_data["common_errors"]:
                learning_data["common_errors"][error_key] = {
                    "count": 0,
                    "symptoms": []
                }
            
            learning_data["common_errors"][error_key]["count"] += 1
            if symptoms not in learning_data["common_errors"][error_key]["symptoms"]:
                learning_data["common_errors"][error_key]["symptoms"].append(symptoms)
        
        # 分析疾病模式
        predicted = feedback.get("predicted_disease")
        if predicted:
            if predicted not in learning_data["disease_patterns"]:
                learning_data["disease_patterns"][predicted] = {
                    "total_predictions": 0,
                    "correct_predictions": 0,
                    "accuracy": 0.0
                }
            
            learning_data["disease_patterns"][predicted]["total_predictions"] += 1
            if feedback.get("is_correct") is True:
                learning_data["disease_patterns"][predicted]["correct_predictions"] += 1
            
            total = learning_data["disease_patterns"][predicted]["total_predictions"]
            correct = learning_data["disease_patterns"][predicted]["correct_predictions"]
            learning_data["disease_patterns"][predicted]["accuracy"] = (
                correct / total if total > 0 else 0.0
            )
        
        self._save_json(self.learning_file, learning_data)
    
    def generate_improvement_suggestions(self) -> List[Dict]:
        """生成改进建议"""
        learning_data = self._load_json(self.learning_file)
        patterns_data = self._load_json(self.patterns_file)
        
        suggestions = []
        
        # 分析常见错误
        common_errors = learning_data.get("common_errors", {})
        for error_pattern, data in common_errors.items():
            if data["count"] >= 3:  # 出现3次以上的错误
                predicted, actual = error_pattern.split(" -> ")
                suggestions.append({
                    "type": "common_error",
                    "severity": "high",
                    "description": f"疾病 '{predicted}' 经常被误诊为 '{actual}'（{data['count']}次）",
                    "suggestion": f"建议加强对 '{actual}' 症状特征的识别，特别是：{', '.join(data['symptoms'][:3])}",
                    "count": data["count"],
                    "timestamp": datetime.now().isoformat()
                })
        
        # 分析低准确率疾病
        disease_patterns = learning_data.get("disease_patterns", {})
        for disease, data in disease_patterns.items():
            if data["total_predictions"] >= 5 and data["accuracy"] < 0.7:
                suggestions.append({
                    "type": "low_accuracy_disease",
                    "severity": "medium",
                    "description": f"疾病 '{disease}' 诊断准确率较低（{data['accuracy']*100:.1f}%）",
                    "suggestion": f"建议审查 '{disease}' 的诊断逻辑和症状权重",
                    "accuracy": data["accuracy"],
                    "timestamp": datetime.now().isoformat()
                })
        
        # 分析整体准确率
        stats = learning_data.get("accuracy_stats", {})
        if stats.get("total_cases", 0) >= 10:
            accuracy = stats.get("accuracy_rate", 0.0)
            if accuracy < 0.8:
                suggestions.append({
                    "type": "system_accuracy",
                    "severity": "high" if accuracy < 0.6 else "medium",
                    "description": f"整体诊断准确率为 {accuracy*100:.1f}%，需要改进",
                    "suggestion": "建议全面审查诊断算法和知识库",
                    "accuracy": accuracy,
                    "timestamp": datetime.now().isoformat()
                })
        
        # 保存建议
        patterns_data["improvement_suggestions"] = suggestions
        self._save_json(self.patterns_file, patterns_data)
        
        return suggestions
    
    def add_learned_rule(
        self,
        rule_type: str,
        condition: str,
        action: str,
        confidence: float = 1.0,
        source: str = "user_feedback"
    ) -> Dict:
        """
        添加学习规则
        
        Args:
            rule_type: 规则类型（如"symptom_override", "disease_weight"等）
            condition: 条件描述
            action: 行动/建议
            confidence: 置信度 (0.0-1.0)
            source: 来源
            
        Returns:
            学习规则记录
        """
        patterns_data = self._load_json(self.patterns_file)
        
        rule = {
            "rule_id": f"rule_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "rule_type": rule_type,
            "condition": condition,
            "action": action,
            "confidence": confidence,
            "source": source,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        patterns_data["learned_rules"].append(rule)
        self._save_json(self.patterns_file, patterns_data)
        
        return rule
    
    def get_relevant_rules(self, symptoms: str = None, disease: str = None) -> List[Dict]:
        """
        获取相关学习规则
        
        Args:
            symptoms: 症状描述
            disease: 疾病名称
            
        Returns:
            相关规则列表
        """
        patterns_data = self._load_json(self.patterns_file)
        rules = patterns_data.get("learned_rules", [])
        
        relevant_rules = []
        
        for rule in rules:
            # 检查规则是否相关
            if symptoms and symptoms.lower() in rule.get("condition", "").lower():
                relevant_rules.append(rule)
            elif disease and disease.lower() in rule.get("condition", "").lower():
                relevant_rules.append(rule)
        
        # 按置信度排序
        relevant_rules.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return relevant_rules
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        feedback_data = self._load_json(self.feedback_file)
        learning_data = self._load_json(self.learning_file)
        patterns_data = self._load_json(self.patterns_file)
        
        return {
            "total_feedbacks": feedback_data.get("total_feedbacks", 0),
            "accuracy_stats": learning_data.get("accuracy_stats", {}),
            "common_errors_count": len(learning_data.get("common_errors", {})),
            "disease_patterns_count": len(learning_data.get("disease_patterns", {})),
            "improvement_suggestions_count": len(patterns_data.get("improvement_suggestions", [])),
            "learned_rules_count": len(patterns_data.get("learned_rules", []))
        }


def main():
    """主函数 - 用于命令行调用"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python feedback_collector.py feedback <symptoms> <predicted_disease> [actual_disease] [accuracy_score] [comments]")
        print("  python feedback_collector.py suggestions")
        print("  python feedback_collector.py stats")
        print("  python feedback_collector.py rules [symptoms] [disease]")
        sys.exit(1)
    
    collector = DiagnosisFeedbackCollector()
    
    command = sys.argv[1]
    
    if command == "feedback":
        if len(sys.argv) < 3:
            print("错误: feedback 命令需要 JSON 格式的参数")
            sys.exit(1)
        
        try:
            json_data = json.loads(sys.argv[2])
            symptoms = json_data.get('symptoms', '')
            predicted_disease = json_data.get('predicted_disease', '')
            actual_disease = json_data.get('actual_disease')
            is_correct = json_data.get('is_correct')
            accuracy_score = json_data.get('accuracy_score')
            comments = json_data.get('comments', '')
        except json.JSONDecodeError as e:
            print(f"错误: JSON 解析失败: {e}")
            sys.exit(1)
        
        feedback = collector.collect_feedback(
            symptoms=symptoms,
            predicted_disease=predicted_disease,
            actual_disease=actual_disease,
            is_correct=is_correct,
            accuracy_score=accuracy_score,
            user_comments=comments
        )
        
        print(json.dumps(feedback, ensure_ascii=False, indent=2))
    
    elif command == "suggestions":
        suggestions = collector.generate_improvement_suggestions()
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))
    
    elif command == "stats":
        stats = collector.get_statistics()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    elif command == "rules":
        symptoms = sys.argv[2] if len(sys.argv) > 2 else None
        disease = sys.argv[3] if len(sys.argv) > 3 else None
        
        rules = collector.get_relevant_rules(symptoms=symptoms, disease=disease)
        print(json.dumps(rules, ensure_ascii=False, indent=2))
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()