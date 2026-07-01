import os
import sys
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

try:
    import openai
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'openai'])
    import openai

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QTextEdit, QPushButton, QLabel, QProgressBar, QSplitter,
                                 QListWidget, QListWidgetItem, QMessageBox, QSizePolicy,
                                 QScrollArea, QFrame, QComboBox, QDialog, QSpinBox,
                                 QCheckBox, QRadioButton, QButtonGroup, QGroupBox)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyQt6'])
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QTextEdit, QPushButton, QLabel, QProgressBar, QSplitter,
                                 QListWidget, QListWidgetItem, QMessageBox, QSizePolicy,
                                 QScrollArea, QFrame, QComboBox, QDialog, QSpinBox,
                                 QCheckBox, QRadioButton, QButtonGroup, QGroupBox)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

api_key: str = os.environ.get('STEP_API_KEY', '')
base_url: str = os.environ.get('STEP_API_BASE', 'https://api.stepfun.com/v1')
model: str = os.environ.get('STEP_MODEL', 'step-3.7-flash')

client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

DIAGNOSE_SCRIPT = os.path.join(os.path.dirname(__file__), 'rare-disease-diagnosis/scripts/diagnose.py')
EVIDENCE_SEARCH_SCRIPT = os.path.join(os.path.dirname(__file__), 'knows-evidence-search/scripts/evidence_search.py')
FEEDBACK_COLLECTOR_SCRIPT = os.path.join(os.path.dirname(__file__), 'self-improving/scripts/feedback_collector.py')
DIAGNOSIS_IMPROVER_SCRIPT = os.path.join(os.path.dirname(__file__), 'self-improving/scripts/diagnosis_improver.py')


def save_diagnosis_result(symptoms: str, result: str) -> str:
    timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
    output_dir = './output'
    os.makedirs(output_dir, exist_ok=True)
    result_save_path = os.path.join(output_dir, timestamp + '_diagnosis.md')
    
    markdown_content = f"""# 罕见病辅助诊断报告

## 基本信息

- **诊断时间**: {timestamp}
- **症状描述**: {symptoms}

---

## 诊断结果

{result}

---

## 免责声明

本诊断结果仅供参考，不能替代专业医疗诊断。建议您咨询专业医生进行详细检查和诊断。
"""
    
    with open(result_save_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    return result_save_path


async def expand_symptoms_with_llm(symptoms: str) -> dict:
    system_prompt = """你是一个医学术语专家。你的任务是：
1. 分析用户的症状描述
2. 识别关键症状和医学术语
3. 扩展症状描述，添加医学同义词和相关症状
4. 判断是否需要调用罕见病诊断skill

重要原则：
- 几乎所有症状都可能是罕见病的表现，包括常见的腹痛、腹泻、发热、皮疹等
- 即使是普通症状，如果反复发作、病因不明或伴有其他异常，都应考虑罕见病可能
- 罕见病并非都是"极其罕见的症状"，而是"相对罕见的疾病"
- 除非明显是外伤、骨折等明确病因的情况，否则应默认调用诊断skill

请输出JSON格式，包含以下字段：
- expanded_symptoms: string - 扩展后的症状描述（包含同义词和相关症状）
- key_symptoms: array - 提取的关键症状列表
- need_diagnosis: boolean - 是否需要调用诊断skill（除非明确排除罕见病可能，否则应为true）
- suggested_top_k: int - 建议返回的诊断结果数量（1-5，默认3）
- reasoning: string - 你的分析理由
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'用户症状描述：{symptoms}'}
            ],
            temperature=0.1,
        )
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
        
        result = json.loads(content)
        
        # 确保 need_diagnosis 默认为 True，避免漏诊
        if result.get('need_diagnosis') is False:
            # 检查是否有明确的排除理由
            reasoning = result.get('reasoning', '').lower()
            # 只有明确是外伤、骨折等非疾病症状时才跳过
            exclude_keywords = ['外伤', '骨折', '烫伤', '割伤', '中毒', '异物']
            should_exclude = any(kw in reasoning for kw in exclude_keywords)
            if not should_exclude:
                result['need_diagnosis'] = True
                result['reasoning'] = f"[自动修正] {result.get('reasoning', '')} - 已自动启用罕见病诊断"
        
        return result
    except Exception as e:
        return {
            'expanded_symptoms': symptoms,
            'key_symptoms': [],
            'need_diagnosis': True,
            'suggested_top_k': 3,
            'reasoning': f'LLM分析失败，使用原始症状: {str(e)}'
        }


async def enhance_result_with_llm(symptoms: str, diagnosis_result: str, evidence_data: str = '') -> str:
    system_prompt = """你是一个罕见病诊断专家。你的任务是：
1. 阅读诊断skill返回的结果
2. 阅读医学证据搜索结果（如果有）
3. 基于原始症状描述，对诊断结果进行专业解读和补充
4. 使用证据搜索结果来验证和支持诊断结论
5. 如果证据与诊断不一致，指出差异并提供可能的解释
6. 添加鉴别诊断要点、进一步检查建议、预后信息等
7. 保持专业但易懂的语言风格

输出格式要求：
- 在原始诊断结果基础上添加专业解读部分
- 使用清晰的标题和列表
- 添加必要的医学背景信息
- 列出引用的证据来源
- 保持免责声明
"""

    user_content = f'原始症状：{symptoms}\n\n诊断结果：\n{diagnosis_result}'
    
    if evidence_data:
        try:
            import json
            evidence_json = json.loads(evidence_data)
            if evidence_json.get('total_evidences', 0) > 0:
                user_content += f'\n\n医学证据搜索结果：\n{evidence_data}'
            else:
                user_content += f'\n\n医学证据搜索结果：未找到相关证据'
        except json.JSONDecodeError:
            user_content += f'\n\n医学证据搜索结果：{evidence_data}'
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content}
            ],
            temperature=0.3,
        )
        
        content = response.choices[0].message.content.strip()
        return content
    except Exception as e:
        return f'\n[LLM专业解读失败: {str(e)}]\n\n{diagnosis_result}'


def run_diagnosis_script(symptoms: str, top_k: int = 3) -> str:
    try:
        result = subprocess.run(
            [sys.executable, DIAGNOSE_SCRIPT, symptoms, str(top_k), '--cases'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=os.path.dirname(__file__)
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f'诊断脚本执行失败：{result.stderr.strip()}'
    except Exception as e:
        return f'执行诊断脚本时出错：{str(e)}'


def extract_disease_name(diagnosis_result: str) -> str:
    """从诊断结果中提取疾病名称（用于证据搜索）"""
    try:
        lines = diagnosis_result.split('\n')
        for line in lines:
            if '可能患有' in line:
                parts = line.split('可能患有')
                if len(parts) > 1:
                    disease_part = parts[1].strip()
                    if '（' in disease_part:
                        return disease_part.split('（')[0].strip()
                    return disease_part.split('—')[0].strip()
        return ''
    except Exception:
        return ''


def search_evidence_for_disease(disease_name: str) -> str:
    """搜索疾病相关的医学证据"""
    if not disease_name:
        return '[证据搜索跳过：未识别疾病名称]'
    
    try:
        result = subprocess.run(
            [sys.executable, EVIDENCE_SEARCH_SCRIPT, disease_name, '--json'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=os.path.dirname(__file__),
            timeout=60
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f'[证据搜索失败：{result.stderr.strip()[:200]}]'
    except subprocess.TimeoutExpired:
        return '[证据搜索超时]'
    except FileNotFoundError:
        return '[证据搜索跳过：Node.js 未安装或 evidence_search.py 不存在]'
    except Exception as e:
        return f'[证据搜索异常：{str(e)}]'


async def diagnose(symptoms: str, progress_callback=None):
    if progress_callback:
        progress_callback(10, "正在分析症状，请稍候...")
    
    llm_result = await expand_symptoms_with_llm(symptoms)
    
    if progress_callback:
        key_symptoms = ', '.join(llm_result.get('key_symptoms', []))
        progress_callback(25, f"关键症状: {key_symptoms}")
        progress_callback(30, f"扩展症状: {llm_result.get('expanded_symptoms')}")
        progress_callback(35, f"分析理由: {llm_result.get('reasoning')}")
    
    if llm_result.get('need_diagnosis', True):
        top_k = llm_result.get('suggested_top_k', 3)
        
        if progress_callback:
            progress_callback(40, f"建议返回数量: {top_k}")
            progress_callback(50, "正在调用罕见病诊断skill...")
        
        expanded_symptoms = llm_result.get('expanded_symptoms', symptoms)
        diagnosis_result = run_diagnosis_script(expanded_symptoms, top_k)
        
        if progress_callback:
            progress_callback(60, "正在提取疾病名称...")
        
        disease_name = extract_disease_name(diagnosis_result)
        
    if progress_callback:
        progress_callback(65, f"识别疾病: {disease_name}")
        progress_callback(70, "正在检索 KnowS 医学证据库（论文/指南/临床试验）...")
        
        evidence_data = search_evidence_for_disease(disease_name)
        
        if progress_callback:
            progress_callback(85, "正在生成专业解读（整合证据）...")
        
        enhanced_result = await enhance_result_with_llm(symptoms, diagnosis_result, evidence_data)
    else:
        enhanced_result = "根据分析，此问题不需要调用罕见病诊断skill。"
    
    if progress_callback:
        progress_callback(100, "诊断完成")
    
    save_path = save_diagnosis_result(symptoms, enhanced_result)
    
    return {
        'result': enhanced_result,
        'save_path': save_path,
        'llm_result': llm_result,
        'disease_name': disease_name if 'disease_name' in locals() else ''
    }


class FeedbackDialog(QDialog):
    """诊断反馈对话框"""
    
    def __init__(self, symptoms: str, predicted_disease: str, parent=None):
        super().__init__(parent)
        self.symptoms = symptoms
        self.predicted_disease = predicted_disease
        self.result = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("诊断反馈")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 13px;
                color: #334155;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#submitBtn {
                background-color: #3b82f6;
                color: white;
            }
            QPushButton#submitBtn:hover {
                background-color: #2563eb;
            }
            QPushButton#cancelBtn {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
            }
            QPushButton#cancelBtn:hover {
                background-color: #e2e8f0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 症状信息
        info_label = QLabel(f"📝 预测疾病: {self.predicted_disease}")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e3a5f;")
        layout.addWidget(info_label)
        
        # 诊断是否正确
        correct_group = QGroupBox("诊断是否正确？")
        correct_layout = QVBoxLayout(correct_group)
        
        self.correct_yes_radio = QRadioButton("✅ 正确")
        self.correct_no_radio = QRadioButton("❌ 错误")
        self.correct_unsure_radio = QRadioButton("🤔 不确定")
        
        self.correct_button_group = QButtonGroup(self)
        self.correct_button_group.addButton(self.correct_yes_radio)
        self.correct_button_group.addButton(self.correct_no_radio)
        self.correct_button_group.addButton(self.correct_unsure_radio)
        
        correct_layout.addWidget(self.correct_yes_radio)
        correct_layout.addWidget(self.correct_no_radio)
        correct_layout.addWidget(self.correct_unsure_radio)
        
        layout.addWidget(correct_group)
        
        # 实际疾病
        actual_disease_group = QGroupBox("实际疾病（如果诊断错误）")
        actual_disease_layout = QVBoxLayout(actual_disease_group)
        
        self.actual_disease_input = QTextEdit()
        self.actual_disease_input.setPlaceholderText("请输入实际疾病名称...")
        self.actual_disease_input.setMaximumHeight(80)
        actual_disease_layout.addWidget(self.actual_disease_input)
        
        layout.addWidget(actual_disease_group)
        
        # 准确率评分
        score_group = QGroupBox("诊断准确率评分（1-5分）")
        score_layout = QHBoxLayout(score_group)
        
        score_label = QLabel("评分：")
        self.score_spinbox = QSpinBox()
        self.score_spinbox.setRange(1, 5)
        self.score_spinbox.setValue(3)
        
        score_layout.addWidget(score_label)
        score_layout.addWidget(self.score_spinbox)
        score_layout.addStretch()
        
        layout.addWidget(score_group)
        
        # 用户评论
        comments_group = QGroupBox("其他评论或建议")
        comments_layout = QVBoxLayout(comments_group)
        
        self.comments_input = QTextEdit()
        self.comments_input.setPlaceholderText("请输入您的评论或建议...")
        self.comments_input.setMaximumHeight(100)
        comments_layout.addWidget(self.comments_input)
        
        layout.addWidget(comments_group)
        
        # 医生验证
        doctor_group = QGroupBox("验证信息")
        doctor_layout = QVBoxLayout(doctor_group)
        
        self.doctor_verified_checkbox = QCheckBox("🏥 此反馈已由医生验证")
        doctor_layout.addWidget(self.doctor_verified_checkbox)
        
        layout.addWidget(doctor_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.submit_btn = QPushButton("提交反馈")
        self.submit_btn.setObjectName("submitBtn")
        self.submit_btn.clicked.connect(self.submit_feedback)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.submit_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def submit_feedback(self):
        """提交反馈"""
        is_correct = None
        if self.correct_yes_radio.isChecked():
            is_correct = True
        elif self.correct_no_radio.isChecked():
            is_correct = False
        
        actual_disease = self.actual_disease_input.toPlainText().strip() or None
        accuracy_score = self.score_spinbox.value()
        comments = self.comments_input.toPlainText().strip()
        doctor_verified = self.doctor_verified_checkbox.isChecked()
        
        if is_correct is False and not actual_disease:
            QMessageBox.warning(self, "提示", "诊断错误时，请输入实际疾病名称！")
            return
        
        self.result = {
            "is_correct": is_correct,
            "actual_disease": actual_disease,
            "accuracy_score": accuracy_score,
            "comments": comments,
            "doctor_verified": doctor_verified
        }
        
        self.accept()


class DiagnosisThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, symptoms):
        super().__init__()
        self.symptoms = symptoms
    
    def run(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            
            def progress_callback(percent, message):
                self.progress.emit(percent, message)
            
            result = loop.run_until_complete(diagnose(self.symptoms, progress_callback))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DiagnosisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.history_items = []
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("罕见病辅助诊断系统 (含证据搜索)")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f0f4f8, stop:1 #d9e2ec);
            }
            QLabel {
                font-size: 14px;
                font-weight: 500;
            }
            QTextEdit {
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
            }
            QPushButton {
                font-size: 14px;
                font-weight: 600;
                padding: 8px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#diagnoseBtn {
                background-color: #3b82f6;
                color: white;
            }
            QPushButton#diagnoseBtn:disabled {
                background-color: #93c5fd;
                color: #e0f2fe;
            }
            QPushButton#diagnoseBtn:hover {
                background-color: #2563eb;
            }
            QPushButton#clearBtn {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
            }
            QPushButton#clearBtn:hover {
                background-color: #e2e8f0;
            }
            QPushButton#saveBtn {
                background-color: #22c55e;
                color: white;
            }
            QPushButton#saveBtn:hover {
                background-color: #16a34a;
            }
            QProgressBar {
                height: 24px;
                border-radius: 12px;
                background-color: #e2e8f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 12px;
            }
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:hover {
                background-color: #eff6ff;
            }
            QListWidget::item:selected {
                background-color: #dbeafe;
                color: #1d4ed8;
            }
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
            QComboBox {
                font-size: 13px;
                padding: 6px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_label = QLabel("🏥 罕见病辅助诊断系统")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet("color: #1e3a5f;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        subtitle_label = QLabel("AI辅助诊断 + 本地知识库关键词匹配 + KnowS医学证据检索")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #64748b;")
        title_layout.addWidget(subtitle_label)
        main_layout.addWidget(title_frame)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)
        
        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setSpacing(8)
        
        input_label = QLabel("症状描述")
        input_label.setStyleSheet("color: #334155;")
        input_layout.addWidget(input_label)
        
        self.symptoms_input = QTextEdit()
        self.symptoms_input.setPlaceholderText("请详细描述患者的症状，包括：年龄、性别、起病过程、主要症状体征、病程时长、加重/缓解因素...\n\n示例：男性12岁，反复双足和手指烧灼样疼痛3年，出汗明显少，皮肤散在红色小丘疹\n\n💡 描述越全面，诊断越精准。系统将自动搜索医学论文和指南作为依据。")
        self.symptoms_input.setMinimumHeight(150)
        input_layout.addWidget(self.symptoms_input)
        
        example_layout = QHBoxLayout()
        example_label = QLabel("💡 临床病例示例（下拉选择）：")
        example_label.setStyleSheet("color: #64748b; font-size: 12px;")
        example_layout.addWidget(example_label)
        
        self.example_combo = QComboBox()
        self.example_combo.addItems([
            "12岁男童，反复双足手指烧灼样剧痛伴少汗、皮肤红色丘疹，体育课出汗明显少于同龄人",
            "28岁女性，右眼睑下垂晨轻暮重、视物重影，近1周咀嚼硬物费力、说话带鼻音",
            "5岁男童，走路摇摆如鸭步，从地上爬起需双手撑膝，小腿粗硬没力",
            "22岁男性身高195cm，手指细长、高度近视800度，打篮球时突发剧烈胸痛",
            "15岁少年转氨酶不明原因升高1年，双手细微抖动、性格从开朗变沉默",
            "32岁男性突发左侧肢体无力，追问青少年期有反复手足痛和少汗史",
            "8月龄婴儿成串点头样抽搐，面部红色小疙瘩，躯干四肢多处白色斑",
            "35岁男性皮肤进行性变黑、全身乏力、血压偏低、特别想吃咸的食物"
        ])
        self.example_combo.setStyleSheet("font-size: 12px;")
        self.example_combo.currentTextChanged.connect(self.load_example)
        example_layout.addWidget(self.example_combo)
        example_layout.addStretch()
        input_layout.addLayout(example_layout)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.diagnose_btn = QPushButton("🔍 开始诊断")
        self.diagnose_btn.setObjectName("diagnoseBtn")
        self.diagnose_btn.clicked.connect(self.start_diagnosis)
        button_layout.addWidget(self.diagnose_btn)
        
        self.feedback_btn = QPushButton("📝 提交反馈")
        self.feedback_btn.setObjectName("feedbackBtn")
        self.feedback_btn.clicked.connect(self.submit_feedback)
        self.feedback_btn.setEnabled(False)
        self.feedback_btn.setStyleSheet("background-color: #f59e0b; color: white;")
        button_layout.addWidget(self.feedback_btn)
        
        self.improvement_report_btn = QPushButton("📊 改进报告")
        self.improvement_report_btn.setObjectName("improvementReportBtn")
        self.improvement_report_btn.clicked.connect(self.view_improvement_report)
        self.improvement_report_btn.setStyleSheet("background-color: #8b5cf6; color: white;")
        button_layout.addWidget(self.improvement_report_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_input)
        button_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("💾 保存结果")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self.save_current_result)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)
        
        input_layout.addLayout(button_layout)
        left_layout.addWidget(input_frame)
        
        progress_frame = QFrame()
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setSpacing(8)
        
        progress_label = QLabel("诊断进度")
        progress_label.setStyleSheet("color: #334155;")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        progress_layout.addWidget(self.status_label)
        
        left_layout.addWidget(progress_frame)
        
        history_frame = QFrame()
        history_layout = QVBoxLayout(history_frame)
        history_layout.setSpacing(8)
        
        history_label = QLabel("📋 历史记录")
        history_label.setStyleSheet("color: #334155;")
        history_layout.addWidget(history_label)
        
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(200)
        self.history_list.itemClicked.connect(self.load_history)
        history_layout.addWidget(self.history_list)
        
        left_layout.addWidget(history_frame)
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12)
        
        result_label = QLabel("诊断结果")
        result_label.setStyleSheet("color: #334155;")
        right_layout.addWidget(result_label)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("诊断结果将显示在这里...")
        right_layout.addWidget(self.result_text)
        
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 800])
        
        main_layout.addWidget(splitter)
        
        self.load_history_list()
    
    def load_example(self, text):
        self.symptoms_input.setText(text)
    
    def clear_input(self):
        self.symptoms_input.clear()
        self.result_text.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("就绪")
        self.save_btn.setEnabled(False)
    
    def start_diagnosis(self):
        symptoms = self.symptoms_input.toPlainText().strip()
        
        if not symptoms:
            QMessageBox.warning(self, "提示", "请输入有效的症状描述！")
            return
        
        self.diagnose_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在分析症状...")
        self.result_text.clear()
        
        self.diagnosis_thread = DiagnosisThread(symptoms)
        self.diagnosis_thread.progress.connect(self.update_progress)
        self.diagnosis_thread.finished.connect(self.on_diagnosis_finished)
        self.diagnosis_thread.error.connect(self.on_diagnosis_error)
        self.diagnosis_thread.start()
    
    def update_progress(self, percent, message):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        
        current_text = self.result_text.toPlainText()
        if current_text:
            current_text += "\n"
        current_text += f"[{percent}%] {message}"
        self.result_text.setText(current_text)
        self.result_text.verticalScrollBar().setValue(
            self.result_text.verticalScrollBar().maximum()
        )
    
    def on_diagnosis_finished(self, result):
        self.diagnose_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.feedback_btn.setEnabled(True)  # 启用反馈按钮
        
        self.progress_bar.setValue(100)
        self.status_label.setText("诊断完成")
        
        self.current_result = result
        
        result_text = f"{'='*60}\n诊断结果\n{'='*60}\n\n{result['result']}\n\n{'='*60}\n结果已保存至：{result['save_path']}\n{'='*60}"
        self.result_text.setText(result_text)
        
        self.add_to_history(result)
    
    def on_diagnosis_error(self, error_msg):
        self.diagnose_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("诊断失败")
        
        QMessageBox.critical(self, "错误", f"诊断过程中发生错误：\n{error_msg}")
    
    def add_to_history(self, result):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symptoms = self.symptoms_input.toPlainText().strip()[:50] + "..." if len(self.symptoms_input.toPlainText().strip()) > 50 else self.symptoms_input.toPlainText().strip()
        
        history_item = {
            'timestamp': timestamp,
            'symptoms': symptoms,
            'full_symptoms': self.symptoms_input.toPlainText().strip(),
            'result': result['result'],
            'save_path': result['save_path']
        }
        
        self.history_items.insert(0, history_item)
        
        if len(self.history_items) > 10:
            self.history_items.pop()
        
        self.update_history_list()
    
    def update_history_list(self):
        self.history_list.clear()
        
        for item in self.history_items:
            list_item = QListWidgetItem(f"📅 {item['timestamp']}\n🏥 {item['symptoms']}")
            list_item.setToolTip(item['full_symptoms'])
            self.history_list.addItem(list_item)
    
    def load_history_list(self):
        output_dir = './output'
        if os.path.exists(output_dir):
            files = sorted(os.listdir(output_dir), reverse=True)
            for file in files[:10]:
                if file.endswith('_diagnosis.md'):
                    file_path = os.path.join(output_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        timestamp = file.replace('_diagnosis.md', '')
                        lines = content.split('\n')
                        symptoms = ""
                        for line in lines:
                            if '症状描述' in line and '**症状描述**' not in line:
                                symptoms = line.split('**症状描述**:')[1].strip() if '**症状描述**:' in line else ""
                                if not symptoms:
                                    symptoms = line.split('症状描述:')[1].strip() if '症状描述:' in line else ""
                                break
                        
                        if symptoms:
                            history_item = {
                                'timestamp': timestamp,
                                'symptoms': symptoms[:50] + "..." if len(symptoms) > 50 else symptoms,
                                'full_symptoms': symptoms,
                                'result': content,
                                'save_path': file_path
                            }
                            self.history_items.append(history_item)
                    except:
                        pass
        
        self.update_history_list()
    
    def load_history(self, item):
        index = self.history_list.row(item)
        if index < len(self.history_items):
            history_item = self.history_items[index]
            
            reply = QMessageBox.question(
                self, "确认",
                f"是否加载此历史记录？\n\n时间：{history_item['timestamp']}\n症状：{history_item['symptoms']}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.symptoms_input.setText(history_item['full_symptoms'])
                self.result_text.setText(history_item['result'])
                self.save_btn.setEnabled(True)
                self.current_result = {
                    'result': history_item['result'],
                    'save_path': history_item['save_path']
                }
    
    def save_current_result(self):
        if hasattr(self, 'current_result') and self.current_result:
            QMessageBox.information(self, "提示", f"诊断结果已保存至：\n{self.current_result['save_path']}")
    
    def submit_feedback(self):
        """提交诊断反馈"""
        if not hasattr(self, 'current_result') or not self.current_result:
            QMessageBox.warning(self, "提示", "请先进行诊断！")
            return
        
        # 从诊断结果中提取疾病名称
        result_text = self.current_result.get('result', '')
        predicted_disease = self.current_result.get('disease_name', '')
        
        if not predicted_disease:
            # 尝试从结果文本中提取疾病名称
            if '可能患有' in result_text:
                lines = result_text.split('\n')
                for line in lines:
                    if '可能患有' in line:
                        parts = line.split('可能患有')
                        if len(parts) > 1:
                            predicted_disease = parts[1].strip().split('（')[0].strip().split('—')[0].strip()
                            break
        
        if not predicted_disease:
            QMessageBox.warning(self, "提示", "无法从诊断结果中提取疾病名称！")
            return
        
        # 显示反馈对话框
        symptoms = self.symptoms_input.toPlainText().strip()
        dialog = FeedbackDialog(symptoms, predicted_disease, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result:
            # 收集反馈数据
            feedback_data = dialog.result
            
            try:
                # 调用反馈收集脚本 - 使用 JSON 格式传递参数
                feedback_json = json.dumps({
                    'symptoms': symptoms,
                    'predicted_disease': predicted_disease,
                    'actual_disease': feedback_data.get('actual_disease'),
                    'is_correct': feedback_data.get('is_correct'),
                    'accuracy_score': feedback_data.get('accuracy_score'),
                    'comments': feedback_data.get('comments', '')
                }, ensure_ascii=False)
                
                result = subprocess.run(
                    [
                        sys.executable,
                        FEEDBACK_COLLECTOR_SCRIPT,
                        'feedback',
                        feedback_json
                    ],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    cwd=os.path.dirname(__file__)
                )
                
                if result.returncode == 0:
                    QMessageBox.information(
                        self,
                        "成功",
                        "反馈已提交！\n\n系统将根据您的反馈不断改进诊断效果。\n\n感谢您的参与！"
                    )
                    
                    # 自动生成改进建议
                    self._generate_improvement_suggestions()
                else:
                    QMessageBox.warning(
                        self,
                        "警告",
                        f"反馈提交失败：{result.stderr.strip()[:200]}"
                    )
            except Exception as e:
                QMessageBox.critical(self, "错误", f"提交反馈时发生错误：{str(e)}")
    
    def view_improvement_report(self):
        """查看改进报告"""
        try:
            # 检查报告文件是否存在
            report_file = os.path.join(
                os.path.dirname(__file__),
                'self-improving/improvement_report.md'
            )
            
            if not os.path.exists(report_file):
                # 先生成报告
                result = subprocess.run(
                    [sys.executable, DIAGNOSIS_IMPROVER_SCRIPT, 'report'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    cwd=os.path.dirname(__file__)
                )
                
                if result.returncode != 0:
                    QMessageBox.warning(
                        self,
                        "提示",
                        "暂无足够反馈数据生成改进报告。\n\n请先进行诊断并提交反馈。"
                    )
                    return
            
            # 读取报告内容
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            # 显示报告内容
            self.result_text.clear()
            self.result_text.setPlainText(report_content)
            
            # 显示统计信息
            try:
                stats_result = subprocess.run(
                    [sys.executable, FEEDBACK_COLLECTOR_SCRIPT, 'stats'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    cwd=os.path.dirname(__file__)
                )
                
                if stats_result.returncode == 0:
                    stats_data = json.loads(stats_result.stdout.strip())
                    stats_text = f"\n\n{'='*60}\n反馈统计\n{'='*60}\n"
                    stats_text += f"总反馈数：{stats_data.get('total_feedbacks', 0)}\n"
                    stats_text += f"整体准确率：{stats_data.get('accuracy_stats', {}).get('accuracy_rate', 0)*100:.1f}%\n"
                    stats_text += f"常见错误数：{stats_data.get('common_errors_count', 0)}\n"
                    stats_text += f"学习规则数：{stats_data.get('learned_rules_count', 0)}\n"
                    
                    self.result_text.appendPlainText(stats_text)
            except:
                pass
            
            QMessageBox.information(
                self,
                "改进报告",
                "改进报告已显示在结果区域。\n\n请查看报告中的优先处理事项和行动清单。"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查看改进报告时发生错误：{str(e)}")
    
    def _generate_improvement_suggestions(self):
        """生成改进建议"""
        try:
            subprocess.run(
                [sys.executable, DIAGNOSIS_IMPROVER_SCRIPT, 'plan'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=os.path.dirname(__file__)
            )
        except:
            pass  # 静默失败，不影响用户体验


def main():
    app = QApplication(sys.argv)
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 244, 248))
    app.setPalette(palette)
    
    window = DiagnosisMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()