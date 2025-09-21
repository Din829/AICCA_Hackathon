"""
C2PA凭证工具 - 内容来源与真实性验证
C2PA Credential Tool - 验证数字内容的来源、历史和篡改状态
"""

import asyncio
import os
import json
from typing import Dict, Any, Optional, Union, Callable, List
from pathlib import Path
from datetime import datetime

# 使用dbrheo接口
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal
from dbrheo.tools.base import DatabaseTool, DatabaseConfirmationDetails
from dbrheo.config.base import DatabaseConfig
from dbrheo.utils.debug_logger import log_info


class C2PACredentialTool(DatabaseTool):
    """
    C2PA凭证验证工具
    验证内容的数字凭证，检测篡改，提取创建者信息和编辑历史
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        self._i18n = i18n
        super().__init__(
            name="c2pa_verify",
            display_name=self._('c2pa_verify_name', default="C2PA Credential Verifier") if i18n else "C2PA Credential Verifier",
            description="Content authenticity and provenance verification via C2PA standard. Validates cryptographic signatures, detects tampering, and extracts creation/editing history. Essential for verifying content origin and chain of custody.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "content_path": {
                        "type": "string",
                        "description": "File path or URL (supports images/videos/PDFs)"
                    },
                    "verification_mode": {
                        "type": "string",
                        "enum": ["quick", "standard", "comprehensive"],
                        "description": "quick=basic, standard=normal, comprehensive=full verification",
                        "default": "standard"
                    },
                    "extract_thumbnails": {
                        "type": "boolean",
                        "description": "Extract embedded thumbnails",
                        "default": False
                    },
                    "check_trust_chain": {
                        "type": "boolean",
                        "description": "Verify certificate trust chain",
                        "default": True
                    },
                    "include_ingredients": {
                        "type": "boolean",
                        "description": "Include source assets information",
                        "default": True
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
        
        # C2PA配置（灵活、可配置）
        self.c2pa_config = self._initialize_c2pa_config()
        
        # 支持的文件格式
        self.supported_formats = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.avif': 'image/avif',
            '.heic': 'image/heic',
            '.heif': 'image/heif',
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.pdf': 'application/pdf',
            '.c2pa': 'application/c2pa'  # C2PA manifest file
        }
    
    def _initialize_c2pa_config(self) -> Dict[str, Any]:
        """初始化C2PA配置（最小侵入、灵活配置）"""
        config = {}
        
        # C2PA库配置
        config["library"] = {
            "use_fast_reader": self.config.get("c2pa_use_fast_reader", False),  # 是否使用fast-c2pa-python
            "verify_trust": self.config.get("c2pa_verify_trust", True),
            "extract_resources": self.config.get("c2pa_extract_resources", True)
        }
        
        # 信任配置（可选）
        config["trust"] = {
            "anchors_path": os.environ.get("C2PA_TRUST_ANCHORS") or self.config.get("c2pa_trust_anchors"),
            "allowed_path": os.environ.get("C2PA_ALLOWED_CERTS") or self.config.get("c2pa_allowed_certs"),
            "config_path": os.environ.get("C2PA_TRUST_CONFIG") or self.config.get("c2pa_trust_config")
        }
        
        # 验证选项
        config["validation"] = {
            "strict_mode": self.config.get("c2pa_strict_validation", False),
            "allow_untrusted": self.config.get("c2pa_allow_untrusted", True),  # 黑客松环境允许未信任证书
            "check_revocation": self.config.get("c2pa_check_revocation", False)
        }
        
        return config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        params = self._normalize_params(params)
        
        content_path = params.get("content_path", "")
        if not content_path:
            return "Content path cannot be empty"
        
        # 处理file:ID格式
        if content_path.startswith('file:'):
            # file:ID格式，暂时跳过验证（会在execute时通过ContentLoader处理）
            return None
        
        # 如果是本地路径，检查文件
        if not content_path.startswith(('http://', 'https://')):
            path = Path(content_path)
            if not path.exists():
                return f"Content file not found: {content_path}"
            
            # 检查文件格式
            if path.suffix.lower() not in self.supported_formats:
                return f"Unsupported file format: {path.suffix}. Supported formats: {', '.join(self.supported_formats.keys())}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        content_path = params.get("content_path", "")
        mode = params.get("verification_mode", "standard")
        
        # 获取文件名
        if content_path.startswith('file:'):
            filename = f"uploaded_{content_path[5:][:8]}"
        elif content_path.startswith(('http://', 'https://')):
            filename = content_path.split('/')[-1][:50]
        else:
            filename = Path(content_path).name
        
        return f"Verifying C2PA credentials ({mode} mode): {filename}"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认"""
        # C2PA验证不需要确认
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行C2PA凭证验证"""
        params = self._normalize_params(params)
        
        content_path = params.get("content_path", "")
        mode = params.get("verification_mode", "standard")
        extract_thumbnails = params.get("extract_thumbnails", False)
        check_trust = params.get("check_trust_chain", True)
        include_ingredients = params.get("include_ingredients", True)
        
        try:
            # 1. 准备内容
            if update_output:
                update_output("Loading content...")
            
            content_stream, mime_type = await self._prepare_content(content_path)
            
            # 2. 检查C2PA库可用性
            reader_result = await self._get_c2pa_reader()
            if reader_result.get("error"):
                # 如果C2PA库不可用，返回说明
                return self._handle_library_unavailable(reader_result["error"])
            
            Reader = reader_result["reader"]
            
            # 3. 读取C2PA凭证
            if update_output:
                update_output("Reading C2PA manifest...")
            
            manifest_data = await self._read_c2pa_manifest(
                Reader, content_stream, mime_type, mode
            )
            
            if manifest_data.get("error"):
                # 没有C2PA凭证或读取失败
                return self._handle_no_credentials(manifest_data["error"], content_path)
            
            # 4. 验证和分析
            results = {}
            
            # 基础manifest数据
            results["manifest_store"] = manifest_data
            
            # 验证状态分析
            if update_output:
                update_output("Analyzing validation status...")
            validation_analysis = self._analyze_validation_status(manifest_data)
            results["validation_analysis"] = validation_analysis
            
            # 提取活动manifest详情
            if update_output:
                update_output("Extracting manifest details...")
            active_details = self._extract_active_manifest_details(manifest_data)
            results["active_manifest_details"] = active_details
            
            # 信任链验证（如果配置且模式需要）
            if check_trust and mode in ["standard", "comprehensive"]:
                if update_output:
                    update_output("Checking trust chain...")
                trust_result = await self._verify_trust_chain(manifest_data)
                results["trust_verification"] = trust_result
            
            # 成分分析（如果有且需要）
            if include_ingredients and active_details.get("ingredients"):
                if update_output:
                    update_output("Analyzing ingredients...")
                ingredients_analysis = self._analyze_ingredients(active_details["ingredients"])
                results["ingredients_analysis"] = ingredients_analysis
            
            # 缩略图提取（如果需要）
            if extract_thumbnails and active_details.get("thumbnail_uri"):
                if update_output:
                    update_output("Extracting thumbnails...")
                # 注：实际提取需要使用Reader的resource_to_stream方法
                results["thumbnail_available"] = True
            
            # 5. 生成报告
            report = self._generate_verification_report(results, mode)
            
            # 6. 构建返回结果
            summary = self._generate_summary(validation_analysis, active_details)
            
            return ToolResult(
                summary=summary,
                llm_content=results,  # 原始数据供Agent分析
                return_display=report
            )
            
        except Exception as e:
            error_msg = f"C2PA verification failed: {str(e)}"
            log_info("C2PAVerify", f"Error: {e}")
            return ToolResult(
                error=error_msg,
                llm_content={"error": str(e)},
                return_display=f"[ERROR] {error_msg}"
            )
    
    async def _prepare_content(self, content_path: str) -> tuple[bytes, str]:
        """准备内容和MIME类型"""
        # 处理file:ID格式
        actual_path = content_path
        if content_path.startswith('file:'):
            try:
                from aicca.utils.content_loader import ContentLoader
                loader = ContentLoader()
                actual_path, metadata = await loader.load_content(content_path)
                log_info("C2PAVerify", f"Resolved file:ID to {actual_path}")
            except Exception as e:
                log_info("C2PAVerify", f"ContentLoader failed: {e}, using fallback")
                actual_path = content_path[5:]  # 降级处理
        
        # 确定MIME类型
        if actual_path.startswith(('http://', 'https://')):
            # URL - 从扩展名推断
            ext = '.' + actual_path.split('.')[-1].lower()
            mime_type = self.supported_formats.get(ext, 'application/octet-stream')
        else:
            # 本地文件
            ext = Path(actual_path).suffix.lower()
            mime_type = self.supported_formats.get(ext, 'application/octet-stream')
        
        # 获取内容
        if actual_path.startswith(('http://', 'https://')):
            import urllib.request
            with urllib.request.urlopen(actual_path) as response:
                content = response.read()
        else:
            with open(actual_path, 'rb') as f:
                content = f.read()
        
        return content, mime_type
    
    async def _get_c2pa_reader(self) -> Dict[str, Any]:
        """获取C2PA Reader（支持多种库）"""
        try:
            # 优先尝试标准c2pa-python库
            try:
                from c2pa import Reader
                log_info("C2PAVerify", "Using c2pa-python library")
                return {"reader": Reader}
            except ImportError:
                pass
            
            # 备选：fast-c2pa-python（只读，更快）
            if self.c2pa_config["library"]["use_fast_reader"]:
                try:
                    from fast_c2pa_python import read_c2pa_from_file
                    log_info("C2PAVerify", "Using fast-c2pa-python library")
                    return {"reader": read_c2pa_from_file, "is_fast": True}
                except ImportError:
                    pass
            
            # 都没有安装
            return {
                "error": "C2PA library not installed. Install with: pip install c2pa-python"
            }
            
        except Exception as e:
            return {"error": f"Failed to load C2PA library: {str(e)}"}
    
    async def _read_c2pa_manifest(
        self, 
        Reader, 
        content_stream: bytes,
        mime_type: str,
        mode: str
    ) -> Dict[str, Any]:
        """读取C2PA manifest"""
        try:
            # 使用标准c2pa-python Reader
            from io import BytesIO
            
            with BytesIO(content_stream) as stream:
                with Reader(mime_type, stream) as reader:
                    # 获取JSON格式的manifest
                    manifest_json = reader.json()
                    manifest_data = json.loads(manifest_json)
                    
                    # 如果是comprehensive模式，尝试获取更多信息
                    if mode == "comprehensive" and manifest_data:
                        # 尝试获取更多详情（如果方法存在）
                        try:
                            # 某些版本的c2pa-python可能有不同的方法
                            if hasattr(reader, 'get_active_manifest'):
                                active_manifest = reader.get_active_manifest()
                                if active_manifest:
                                    manifest_data["_active_manifest_details"] = active_manifest
                        except:
                            pass  # 忽略，使用基础manifest数据
                    
                    return manifest_data
                    
        except Exception as e:
            # 可能没有C2PA凭证或格式不支持
            return {"error": f"No C2PA credentials found or read error: {str(e)}"}
    
    def _analyze_validation_status(self, manifest_data: Dict) -> Dict[str, Any]:
        """分析验证状态（核心功能）"""
        analysis = {
            "has_c2pa": True,
            "is_valid": True,
            "validation_errors": [],
            "trust_status": "unknown"
        }
        
        # 检查validation_status字段（只在有错误时出现）
        if "validation_status" in manifest_data:
            validation = manifest_data["validation_status"]
            analysis["is_valid"] = False
            
            # 提取验证错误
            if isinstance(validation, dict):
                if "code" in validation:
                    analysis["validation_errors"].append({
                        "code": validation["code"],
                        "message": validation.get("message", "Validation failed")
                    })
        
        # 检查validation_results（更详细的验证信息）
        if "validation_results" in manifest_data:
            results = manifest_data["validation_results"]
            
            # 检查活动manifest的验证
            if "activeManifest" in results:
                active_validation = results["activeManifest"]
                if "failure" in active_validation:
                    analysis["is_valid"] = False
                    for failure in active_validation["failure"]:
                        analysis["validation_errors"].append({
                            "code": failure.get("code", "unknown"),
                            "explanation": failure.get("explanation", "Unknown error")
                        })
                        
                        # 特殊处理常见错误
                        if "dataHash.mismatch" in failure.get("code", ""):
                            analysis["tampering_detected"] = True
                        elif "signingCredential.untrusted" in failure.get("code", ""):
                            analysis["trust_status"] = "untrusted"
        
        # 如果没有错误，状态为valid
        if not analysis["validation_errors"]:
            analysis["trust_status"] = "valid"
        
        return analysis
    
    def _extract_active_manifest_details(self, manifest_data: Dict) -> Dict[str, Any]:
        """提取活动manifest的详细信息"""
        details = {}
        
        # 获取活动manifest
        active_label = manifest_data.get("active_manifest")
        if not active_label:
            return {"error": "No active manifest found"}
        
        manifests = manifest_data.get("manifests", {})
        active_manifest = manifests.get(active_label)
        if not active_manifest:
            return {"error": f"Active manifest '{active_label}' not found"}
        
        # 提取关键信息
        details["label"] = active_label
        
        # 签名信息
        if "signature_info" in active_manifest:
            sig_info = active_manifest["signature_info"]
            details["signature"] = {
                "issuer": sig_info.get("issuer", "Unknown"),
                "time": sig_info.get("time"),
                "cert_serial": sig_info.get("cert_serial_number")
            }
        
        # 声明信息（创建者、工具等）
        if "claim_generator_info" in active_manifest:
            generator = active_manifest["claim_generator_info"]
            # claim_generator_info可能是列表
            if isinstance(generator, list) and len(generator) > 0:
                generator = generator[0]  # 取第一个
            if isinstance(generator, dict):
                details["generator"] = {
                    "name": generator.get("name", "Unknown"),
                    "version": generator.get("version"),
                    "icon": generator.get("icon")
                }
        
        # 断言（assertions）- 包含各种声明
        if "assertions" in active_manifest:
            assertions = active_manifest["assertions"]
            details["assertions"] = self._parse_assertions(assertions)
        
        # 标题和格式
        details["title"] = active_manifest.get("title", "Untitled")
        details["format"] = active_manifest.get("format", "unknown")
        
        # 缩略图
        if "thumbnail" in active_manifest:
            thumbnail = active_manifest["thumbnail"]
            details["thumbnail_uri"] = thumbnail.get("identifier")
        
        # 成分（ingredients）- 用于创建此内容的其他资产
        if "ingredients" in active_manifest:
            details["ingredients"] = active_manifest["ingredients"]
        
        return details
    
    def _parse_assertions(self, assertions: List) -> Dict[str, Any]:
        """解析断言信息"""
        parsed = {
            "actions": [],
            "creative_work": None,
            "training_mining": None,
            "other": []
        }
        
        for assertion in assertions:
            if isinstance(assertion, dict):
                label = assertion.get("label", "")
                data = assertion.get("data", {})
                
                # 动作（编辑历史）
                if "c2pa.actions" in label:
                    if "actions" in data:
                        for action in data["actions"]:
                            parsed["actions"].append({
                                "action": action.get("action"),
                                "software": action.get("softwareAgent"),
                                "when": action.get("when"),
                                "parameters": action.get("parameters")
                            })
                
                # 创作信息
                elif "stds.schema-org.CreativeWork" in label:
                    parsed["creative_work"] = {
                        "author": data.get("author", []),
                        "date_published": data.get("datePublished")
                    }
                
                # AI训练限制
                elif "c2pa.training-mining" in label:
                    parsed["training_mining"] = {
                        "use": data.get("use", "notAllowed"),
                        "constraint_info": data.get("constraint_info")
                    }
                
                # 其他断言
                else:
                    parsed["other"].append({
                        "label": label,
                        "data": data
                    })
        
        return parsed
    
    async def _verify_trust_chain(self, manifest_data: Dict) -> Dict[str, Any]:
        """验证信任链（可选功能）"""
        trust_result = {
            "verified": False,
            "trust_level": "unknown",
            "certificate_chain": []
        }
        
        # 如果没有配置信任锚点，跳过
        if not self.c2pa_config["trust"]["anchors_path"]:
            trust_result["note"] = "Trust verification skipped - no trust anchors configured"
            return trust_result
        
        # 这里可以实现更复杂的信任链验证
        # 但对于黑客松，我们保持简单
        trust_result["note"] = "Trust chain verification requires additional configuration"
        
        return trust_result
    
    def _analyze_ingredients(self, ingredients: List) -> List[Dict]:
        """分析成分信息"""
        analyzed = []
        
        for ingredient in ingredients:
            if isinstance(ingredient, dict):
                analysis = {
                    "title": ingredient.get("title", "Unknown"),
                    "format": ingredient.get("format"),
                    "instance_id": ingredient.get("instance_id"),
                    "has_c2pa": "manifest" in ingredient,
                    "relationship": ingredient.get("relationship", "componentOf")
                }
                
                # 如果成分也有C2PA manifest
                if "manifest" in ingredient:
                    manifest = ingredient["manifest"]
                    if "signature_info" in manifest:
                        analysis["signed_by"] = manifest["signature_info"].get("issuer")
                
                analyzed.append(analysis)
        
        return analyzed
    
    def _generate_summary(self, validation: Dict, details: Dict) -> str:
        """生成简洁摘要"""
        status_parts = []
        
        # 验证状态
        if validation["is_valid"]:
            status_parts.append("Valid C2PA")
        else:
            if validation.get("tampering_detected"):
                status_parts.append("TAMPERED")
            elif validation["trust_status"] == "untrusted":
                status_parts.append("Untrusted")
            else:
                status_parts.append("Invalid")
        
        # 签名者
        if details.get("signature"):
            issuer = details["signature"]["issuer"]
            # 简化发行者名称
            if "CN=" in issuer:
                issuer = issuer.split("CN=")[1].split(",")[0]
            status_parts.append(f"by {issuer}")
        
        return "C2PA: " + " - ".join(status_parts)
    
    def _generate_verification_report(self, results: Dict, mode: str) -> str:
        """生成验证报告"""
        report = "# C2PA Credential Verification Report\n\n"
        report += f"**Verification Mode**: {mode}\n\n"
        
        # 验证状态
        validation = results.get("validation_analysis", {})
        report += "## Validation Status\n"
        
        if validation.get("is_valid"):
            report += "**VALID** - Content credentials verified successfully\n"
        else:
            if validation.get("tampering_detected"):
                report += "**TAMPERING DETECTED** - Content has been modified after signing\n"
            elif validation["trust_status"] == "untrusted":
                report += "**UNTRUSTED CERTIFICATE** - Content intact but certificate not in trust list (may be test/self-signed)\n"
            else:
                report += "**INVALID** - Credential verification failed\n"
            
            # 列出错误
            if validation.get("validation_errors"):
                report += "\n**Validation Errors**:\n"
                for error in validation["validation_errors"]:
                    report += f"- {error.get('code', 'unknown')}: {error.get('explanation', error.get('message', 'Unknown error'))}\n"
        
        report += "\n"
        
        # Manifest详情
        details = results.get("active_manifest_details", {})
        if details and "error" not in details:
            report += "## Content Information\n"
            
            # 签名信息
            if details.get("signature"):
                sig = details["signature"]
                report += f"**Signed by**: {sig['issuer']}\n"
                if sig.get("time"):
                    report += f"**Signed at**: {sig['time']}\n"
            
            # 生成器信息
            if details.get("generator"):
                gen = details["generator"]
                report += f"**Created with**: {gen['name']}"
                if gen.get("version"):
                    report += f" v{gen['version']}"
                report += "\n"
            
            # 断言信息
            if details.get("assertions"):
                assertions = details["assertions"]
                
                # 编辑历史
                if assertions.get("actions"):
                    report += "\n**Edit History**:\n"
                    for action in assertions["actions"][:3]:  # 最多显示3个
                        report += f"- {action.get('action', 'Unknown action')}"
                        if action.get("software"):
                            report += f" (using {action['software']})"
                        report += "\n"
                
                # AI训练限制
                if assertions.get("training_mining"):
                    tm = assertions["training_mining"]
                    report += f"\n**AI Training**: {tm.get('use', 'not specified')}\n"
            
            # 成分
            if details.get("ingredients"):
                report += f"\n**Ingredients**: {len(details['ingredients'])} source asset(s)\n"
        
        # 信任验证
        if "trust_verification" in results:
            trust = results["trust_verification"]
            report += "\n## Trust Chain\n"
            report += trust.get("note", "Trust verification not performed") + "\n"
        
        return report
    
    def _handle_library_unavailable(self, error: str) -> ToolResult:
        """处理库不可用的情况"""
        message = f"""
# C2PA Verification Unavailable

The C2PA Python library is not installed. To enable C2PA credential verification:

```bash
pip install c2pa-python
```

**Note**: This library requires Python 3.10 or higher.

**What is C2PA?**
C2PA (Coalition for Content Provenance and Authenticity) provides cryptographically signed credentials that verify:
- Who created the content
- When it was created
- What tools were used
- Whether it has been tampered with

This complements the image_verify tool by focusing on content provenance rather than AI detection.
"""
        
        return ToolResult(
            summary="C2PA library not installed",
            llm_content={"error": error, "library_required": "c2pa-python"},
            return_display=message
        )
    
    def _handle_no_credentials(self, error: str, content_path: str) -> ToolResult:
        """处理没有C2PA凭证的情况"""
        # 处理file:ID格式
        if content_path.startswith('file:'):
            filename = f"uploaded_file_{content_path[5:][:8]}"  # 使用ID的前8位
        elif content_path.startswith('http'):
            filename = content_path.split('/')[-1]
        else:
            filename = Path(content_path).name
        
        message = f"""
# No C2PA Credentials Found

**File**: {filename}

This content does not contain C2PA credentials. This could mean:
1. The content was created without C2PA support
2. The credentials were stripped (intentionally or unintentionally)
3. The file format doesn't support C2PA

**Note**: The absence of C2PA credentials doesn't mean the content is fake or tampered with - it simply means there's no cryptographic provenance information attached.

Consider using other verification tools:
- `image_verify` for AI detection and image analysis
- `ai_detector` for text content AI detection
"""
        
        return ToolResult(
            summary="No C2PA credentials found",
            llm_content={
                "has_c2pa": False,
                "filename": filename,
                "error": error
            },
            return_display=message
        )