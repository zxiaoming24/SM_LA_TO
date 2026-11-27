"""
distraction_analyzer.py - 大模型分析模块
功能：
1. 构建结构化特征描述
2. 调用大模型API分析
3. 解析分析结果
"""

import json
import time
from typing import Dict, Any, Optional
import os
import asyncio
import aiohttp

from eyesss_test_mm.config import LLMConfig, PromptConfig


class DistractionAnalyzer:
    """分心分析器 - 基于大模型"""
    
    def __init__(self):
        """初始化分析器"""
        # 根据配置选择模型
        self.api_key = None
        self.api_url = None
        self.model = None
        
        if LLMConfig.ACTIVE_MODEL == "deepseek":
            self.api_key = LLMConfig.DEEPSEEK_API_KEY
            self.api_url = LLMConfig.DEEPSEEK_API_URL
            self.model = LLMConfig.DEEPSEEK_MODEL
        elif LLMConfig.ACTIVE_MODEL == "moonshot":
            self.api_key = LLMConfig.MOONSHOT_API_KEY
            self.api_url = LLMConfig.MOONSHOT_API_URL
            self.model = LLMConfig.MOONSHOT_MODEL
        elif LLMConfig.ACTIVE_MODEL == "qwen":
            self.api_key = LLMConfig.QWEN_API_KEY
            self.api_url = LLMConfig.QWEN_API_URL
            self.model = LLMConfig.QWEN_MODEL
        
        if not self.api_key:
            print(f"⚠️ 未配置{LLMConfig.ACTIVE_MODEL.upper()}_API_KEY，大模型分析功能将不可用")
        
        # 统计信息
        self.analysis_count = 0
        self.last_analysis_time = 0
    
    def _build_feature_description(self, 
                                   gaze_data: Dict[str, Any],
                                   object_data: Dict[str, Any],
                                   emotion_data: Dict[str, Any],
                                   statistics: Dict[str, Any],
                                   behavior_result: Dict[str, Any] = None) -> str:
        """
        构建结构化特征描述
        
        Args:
            gaze_data: 视线检测数据
            object_data: 物品检测数据
            emotion_data: 情绪检测数据
            statistics: 时序统计数据
            behavior_result: 行为规则判定结果（来自_make_final_decision）
            
        Returns:
            结构化描述文本
        """
        # 行为规则结果
        behavior_result = behavior_result or {}
        behavior_distracted = behavior_result.get("is_distracted", False)
        behavior_reasons = behavior_result.get("reasons", [])
        behavior_suggestions = behavior_result.get("suggestions", [])
        
        # 头部姿态数据
        head_pose = gaze_data.get("head_pose", {})
        head_yaw = head_pose.get("yaw", 0.0)
        head_pitch = head_pose.get("pitch", 0.0)
        head_roll = head_pose.get("roll", 0.0)
        
        # 视线数据
        gaze_direction = gaze_data.get("gaze_direction", "未知")
        gaze_offset_x = gaze_data.get("gaze_offset_x", 0.0)
        gaze_offset_y = gaze_data.get("gaze_offset_y", 0.0)
        blink_rate = gaze_data.get("blink_rate", 0.0)
        attention_level = gaze_data.get("attention_level", "未知")
        
        # 嘴部/瞌睡数据
        mouth_mar = gaze_data.get("mouth_mar", 0.0)
        is_yawning = gaze_data.get("is_yawning", False)
        yawn_count = gaze_data.get("yawn_count", 0)
        is_drowsy = gaze_data.get("is_drowsy", False)
        drowsiness_score = gaze_data.get("drowsiness_score", 0.0)
        nodding_intensity = gaze_data.get("nodding_intensity", 0.0)
        
        # 物品检测
        detected_objects = object_data.get("objects", [])
        distraction_objects = object_data.get("distraction_objects", [])
        
        # 格式化检测到的物品
        if detected_objects:
            objects_str = ", ".join([
                f"{obj.get('name', '未知')}({obj['confidence']:.2f})" 
                for obj in detected_objects
            ])
        else:
            objects_str = "无"
        
        # 格式化分心物品
        if distraction_objects:
            distraction_str = ", ".join([
                f"{obj.get('name', '未知')}({obj['confidence']:.2f})" 
                for obj in distraction_objects
            ])
        else:
            distraction_str = "无"
        
        # 情绪数据
        emotion_detected = emotion_data.get("emotion_detected", False)
        if emotion_detected:
            emotion = emotion_data.get("emotion", "neutral")
            emotion_state = emotion_data.get("state", "平静")
            emotion_confidence = emotion_data.get("confidence", 0.0)
            emotion_str = f"{emotion_state}({emotion_confidence:.2f})"
        else:
            emotion_str = "未检测"
        
        # 时序统计
        duration = statistics.get("duration", 0.0)
        gaze_change = statistics.get("gaze_change", "未知")
        recent_objects = statistics.get("recent_objects", {})
        
        # 格式化最近物品
        if recent_objects:
            recent_str = ", ".join([
                f"{name}: {count}次" 
                for name, count in recent_objects.items()
            ])
        else:
            recent_str = "无"
        
        # 构建提示词
        prompt = PromptConfig.USER_PROMPT_TEMPLATE.format(
            behavior_distracted="是" if behavior_distracted else "否",
            behavior_reasons="; ".join(behavior_reasons) if behavior_reasons else "无",
            behavior_suggestions="; ".join(behavior_suggestions) if behavior_suggestions else "无",
            head_yaw=head_yaw,
            head_pitch=head_pitch,
             head_roll=head_roll,
             mouth_mar=mouth_mar,
             is_yawning="是" if is_yawning else "否",
             yawn_count=yawn_count,
             is_drowsy="是" if is_drowsy else "否",
             drowsiness_score=drowsiness_score,
             nodding_intensity=nodding_intensity,
             gaze_direction=gaze_direction,
            gaze_offset_x=gaze_offset_x,
            gaze_offset_y=gaze_offset_y,
            blink_rate=blink_rate,
            attention_level=attention_level,
            detected_objects=objects_str,
            distraction_objects=distraction_str,
            emotion=emotion_str,
            duration=duration,
            gaze_change=gaze_change,
            recent_objects=recent_str
        )
        
        return prompt
    
    async def async_analyze(self, 
                            gaze_data: Dict[str, Any],
                            object_data: Dict[str, Any],
                            emotion_data: Dict[str, Any],
                            statistics: Dict[str, Any],
                            behavior_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        异步分析是否分心
        
        Args:
            gaze_data: 视线检测数据
            object_data: 物品检测数据
            emotion_data: 情绪检测数据
            statistics: 时序统计数据
            behavior_result: 行为规则判定结果
            
        Returns:
            分析结果
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "未配置API_KEY",
                "is_distracted": False,
                "distraction_level": "unknown",
                "confidence": 0.0,
                "reasons": ["大模型分析功能未启用"],
                "suggestions": [f"请配置{LLMConfig.ACTIVE_MODEL.upper()}_API_KEY"],
                "attention_score": 50
            }
        
        try:
            # 构建特征描述（包含行为规则结果）
            user_prompt = self._build_feature_description(gaze_data, object_data, emotion_data, statistics, behavior_result)

            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": PromptConfig.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": LLMConfig.TEMPERATURE,
                "max_tokens": LLMConfig.MAX_TOKENS
            }
            
            # 异步发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=LLMConfig.REQUEST_TIMEOUT
                ) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"API请求失败: {response.status}",
                            "is_distracted": False,
                            "distraction_level": "unknown",
                            "confidence": 0.0,
                            "reasons": [f"API错误: {await response.text()}"],
                            "suggestions": [],
                            "attention_score": 50
                        }
                    
                    # 解析响应
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # 检查内容是否为空
                    if not content or not content.strip():
                        return {
                            "success": False,
                            "error": "API返回内容为空",
                            "is_distracted": False,
                            "distraction_level": "unknown",
                            "confidence": 0.0,
                            "reasons": ["大模型返回空结果，可能是内容被过滤或API异常"],
                            "suggestions": [],
                            "attention_score": 50
                        }
                    
                    # 尝试解析JSON
                    try:
                        # 提取JSON部分（可能包含markdown代码块）
                        if "```json" in content:
                            json_str = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            json_str = content.split("```")[1].split("```")[0].strip()
                        else:
                            json_str = content.strip()
                        
                        analysis_result = json.loads(json_str)
                        
                        # 更新统计
                        self.analysis_count += 1
                        self.last_analysis_time = time.time()
                        
                        return {
                            "success": True,
                            "is_distracted": analysis_result.get("is_distracted", False),
                            "distraction_level": analysis_result.get("distraction_level", "none"),
                            "confidence": analysis_result.get("confidence", 0.0),
                            "reasons": analysis_result.get("reasons", []),
                            "suggestions": analysis_result.get("suggestions", []),
                            "attention_score": analysis_result.get("attention_score", 50),
                            "raw_response": content
                        }
                        
                    except json.JSONDecodeError as e:
                        return {
                            "success": False,
                            "error": f"JSON解析失败: {e}",
                            "is_distracted": False,
                            "distraction_level": "unknown",
                            "confidence": 0.0,
                            "reasons": ["大模型输出格式错误"],
                            "suggestions": [],
                            "attention_score": 50,
                            "raw_response": content
                        }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "请求超时",
                "is_distracted": False,
                "distraction_level": "unknown",
                "confidence": 0.0,
                "reasons": ["大模型分析超时"],
                "suggestions": [],
                "attention_score": 50
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "is_distracted": False,
                "distraction_level": "unknown",
                "confidence": 0.0,
                "reasons": [f"分析失败: {e}"],
                "suggestions": [],
                "attention_score": 50
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "analysis_count": self.analysis_count,
            "last_analysis_time": self.last_analysis_time
        }
