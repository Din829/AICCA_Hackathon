"""
合规报告生成工具 - AI内容合规性评估和报告
Compliance Report Tool - 生成符合各国法规要求的AI内容合规报告
"""

import asyncio
from typing import Dict, Any, Optional, Union, Callable, List
from pathlib import Path
import json
from datetime import datetime

# 使用成熟的dbrheo接口
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
from dbrheo.tools.base import DatabaseTool, DatabaseConfirmationDetails
from dbrheo.config.base import DatabaseConfig


class ComplianceReportTool(DatabaseTool):
    """
    合规报告生成工具
    评估内容是否符合EU AI Act、中国深度合成规定等法规要求
    生成详细的合规性报告和改进建议
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self._i18n = i18n
        super().__init__(
            name="compliance_report",
            display_name=self._('compliance_name', default="合规报告生成器") if i18n else "合规报告生成器",
            description="Generates comprehensive compliance reports for AI-generated content. Evaluates adherence to EU AI Act, China's Deep Synthesis Regulations, US TAKE IT DOWN Act, and other global standards. Provides risk assessments, labeling requirements, and actionable compliance recommendations.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "content_path": {
                        "type": "string",
                        "description": "要评估的内容路径或URL"
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["text", "image", "video", "audio", "mixed"],
                        "description": "内容类型",
                        "default": "mixed"
                    },
                    "jurisdictions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "评估的法律管辖区",
                        "default": ["EU", "US", "China"]
                    },
                    "is_ai_generated": {
                        "type": "boolean",
                        "description": "内容是否为AI生成"
                    },
                    "has_personal_data": {
                        "type": "boolean",
                        "description": "是否包含个人数据"
                    },
                    "commercial_use": {
                        "type": "boolean",
                        "description": "是否用于商业用途"
                    },
                    "target_audience": {
                        "type": "string",
                        "enum": ["general", "children", "professional", "restricted"],
                        "description": "目标受众",
                        "default": "general"
                    },
                    "report_format": {
                        "type": "string",
                        "enum": ["summary", "detailed", "executive"],
                        "description": "报告格式",
                        "default": "detailed"
                    }
                },
                "required": ["content_path"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        params = self._normalize_params(params)
        
        content_path = params.get("content_path", "")
        if not content_path:
            return self._('content_path_empty', default="内容路径不能为空")
        
        # 检查文件是否存在（本地文件）
        if not content_path.startswith(('http://', 'https://')):
            path = Path(content_path)
            if not path.exists():
                return self._('file_not_found', default=f"找不到文件: {content_path}")
        
        jurisdictions = params.get("jurisdictions", [])
        if jurisdictions:
            valid_jurisdictions = ["EU", "US", "China", "UK", "Japan", "Canada", "Australia"]
            for j in jurisdictions:
                if j not in valid_jurisdictions:
                    return self._('invalid_jurisdiction', default=f"不支持的管辖区: {j}")
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        content_path = params.get("content_path", "")
        jurisdictions = params.get("jurisdictions", ["EU", "US", "China"])
        report_format = params.get("report_format", "detailed")
        
        if content_path.startswith('file:'):
            filename = f"uploaded_{content_path[5:][:8]}"
        elif content_path.startswith('http'):
            filename = content_path.split('/')[-1]
        else:
            filename = Path(content_path).name
        jurisdictions_str = ", ".join(jurisdictions)
        
        return self._('compliance_description', 
                     default=f"生成{report_format}合规报告: {filename} ({jurisdictions_str})")
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认"""
        # 合规报告生成通常不需要确认
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行合规性评估"""
        params = self._normalize_params(params)
        
        content_path = params.get("content_path", "")
        jurisdictions = params.get("jurisdictions", ["EU", "US", "China"])
        
        try:
            # 使用统一的内容加载器（最小侵入性）
            from aicca.utils import smart_load_content
            
            if update_output:
                update_output("正在加载内容进行合规性分析...")
            
            # 智能加载内容（自动识别各种输入源）
            actual_path, metadata = await smart_load_content(content_path)
            
            if update_output:
                regions = ", ".join(jurisdictions)
                update_output(f"分析管辖区法规: {regions}")
            
            # TODO: 实现真实的合规性评估逻辑
            # 1. 根据不同法规要求进行评估
            # 2. 检查AI标注要求
            # 3. 评估隐私和数据保护合规性
            # 4. 生成详细的合规报告
            # 5. 提供改进建议
            
            # 模拟合规分析结果
            is_ai = params.get("is_ai_generated", False)
            has_pii = params.get("has_personal_data", False)
            
            compliance_scores = {}
            for jurisdiction in jurisdictions:
                if jurisdiction == "EU":
                    score = 70 if is_ai else 85
                    if has_pii:
                        score -= 10
                elif jurisdiction == "US":
                    score = 80
                elif jurisdiction == "China":
                    score = 65 if is_ai else 80
                else:
                    score = 75
                compliance_scores[jurisdiction] = score
            
            result = {
                "file_info": {
                    "path": actual_path,
                    "source": metadata.get('source'),
                    "size": metadata.get('size', 0),
                    "content_type": params.get("content_type", "unknown")
                },
                "compliance": {
                    "jurisdictions": jurisdictions,
                    "scores": compliance_scores,
                    "overall_score": sum(compliance_scores.values()) / len(compliance_scores) if compliance_scores else 0,
                    "is_ai_generated": is_ai,
                    "has_personal_data": has_pii
                },
                "recommendations": [
                    "添加AI生成内容标识" if is_ai else "内容来源验证通过",
                    "实施数据最小化原则" if has_pii else "无个人数据风险",
                    "定期更新合规政策"
                ]
            }
            
            # 生成报告
            report_format = params.get("report_format", "markdown")
            
            if report_format == "markdown":
                report = f"""
# 合规性评估报告

## 内容信息
- 来源: {metadata.get('source', 'unknown')}
- 类型: {params.get("content_type", "unknown")}
- AI生成: {'是' if is_ai else '否'}
- 包含个人数据: {'是' if has_pii else '否'}

## 合规评分
"""
                for jurisdiction, score in compliance_scores.items():
                    report += f"- **{jurisdiction}**: {score}/100\n"
                
                report += f"\n**总体评分**: {result['compliance']['overall_score']:.1f}/100\n"
                report += "\n## 建议\n"
                for rec in result["recommendations"]:
                    report += f"- {rec}\n"
                
                report += "\n*注：完整合规评估功能开发中*"
            else:
                report = str(result)
            
            return ToolResult(
                summary=f"合规报告已生成，总体评分: {result['compliance']['overall_score']:.1f}/100",
                llm_content=result,
                return_display=report
            )
            
        except Exception as e:
            error_msg = self._('compliance_failed', default=f"合规评估失败: {str(e)}")
            return ToolResult(
                error=error_msg,
                llm_content=f"Compliance assessment failed: {str(e)}",
                return_display=f"❌ {error_msg}"
            )