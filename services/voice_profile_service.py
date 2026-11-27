"""
音色偏好管理服务 - 管理用户的 TTS 音色配置

核心功能：
1. 上传语音样本文件
2. 设置/获取/重置音色偏好
3. 预览音色效果
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional


USER_VOICES_DIR = Path(__file__).resolve().parent.parent / "user_voices"


class VoiceProfileService:

    def upload_sample(self, user_id: str, filename: str, content: bytes) -> Dict[str, Any]:
        """上传用户的语音样本"""
        user_dir = USER_VOICES_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        suffix = os.path.splitext(filename or "sample.wav")[1] or ".wav"
        filepath = user_dir / f"reference{suffix}"

        with open(filepath, "wb") as f:
            f.write(content)

        print(f"✅ 用户 {user_id} 的语音样本已保存: {filepath} ({len(content)} bytes)")
        return {
            "filename": f"reference{suffix}",
            "path": str(filepath),
            "size_bytes": len(content),
        }

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户的音色偏好配置"""
        profile_path = USER_VOICES_DIR / f"{user_id}.json"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def set_profile(self, user_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """设置音色偏好"""
        USER_VOICES_DIR.mkdir(parents=True, exist_ok=True)
        profile_path = USER_VOICES_DIR / f"{user_id}.json"

        if profile.get("method") == "voxcpm" and profile.get("reference_audio_filename"):
            ref_path = USER_VOICES_DIR / user_id / profile["reference_audio_filename"]
            if not ref_path.exists():
                raise FileNotFoundError(f"参考音频文件未找到: {ref_path}")
            profile["reference_audio"] = str(ref_path)

        # 只存持久化字段，去掉临时字段
        saved = {"method": profile.get("method", "edge_tts")}
        if profile.get("method") == "voxcpm":
            for key in ("mode", "control", "reference_audio", "prompt_text", "cfg_value", "inference_timesteps"):
                if key in profile:
                    saved[key] = profile[key]

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)

        print(f"✅ 用户 {user_id} 的音色偏好已保存: {saved}")
        return saved

    def reset_profile(self, user_id: str) -> bool:
        """重置音色偏好为默认"""
        profile_path = USER_VOICES_DIR / f"{user_id}.json"
        if profile_path.exists():
            profile_path.unlink()
            print(f"✅ 用户 {user_id} 的音色偏好已重置为默认")
        return True

    def build_voice_profile_for_preview(self, request_data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """构建预览用的音色配置"""
        if request_data.get("method") != "voxcpm":
            return None

        profile = {"mode": request_data.get("mode", "design")}
        if request_data.get("control"):
            profile["control"] = request_data["control"]
        if request_data.get("reference_audio_filename"):
            ref_path = USER_VOICES_DIR / user_id / request_data["reference_audio_filename"]
            if ref_path.exists():
                profile["reference_audio"] = str(ref_path)
            else:
                raise FileNotFoundError(f"参考音频文件未找到: {ref_path}")
        if request_data.get("prompt_text"):
            profile["prompt_text"] = request_data["prompt_text"]
        profile["cfg_value"] = request_data.get("cfg_value", 2.0)
        profile["inference_timesteps"] = request_data.get("inference_timesteps", 10)
        return profile
