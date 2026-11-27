import httpx
from openai import OpenAI, AsyncOpenAI
from config import MultiModalConfig, APIConfig
from logger import setup_module_logger
import base64
from typing import Iterable, Union, Dict, List, Optional
import re
import json
import cv2
import numpy as np


# 编码函数： 将本地文件转换为 Base64 编码的字符串
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def encode_frame_array(frame_array: np.ndarray) -> str:
    """将BGR帧编码为base64 JPEG"""
    if frame_array is None:
        raise ValueError("frame_array 不能为空")
    success, buffer = cv2.imencode(".jpg", frame_array, [cv2.IMWRITE_JPEG_QUALITY, 60])
    if not success:
        raise ValueError("frame_array 编码失败")
    return base64.b64encode(buffer).decode("utf-8")


def parse_interview_analysis(raw_text: str) -> Dict[str, List[Dict[str, str]]]:
    """
    解析模型输出为结构化对象。

    期望格式（多条）：
    - 行为维度：坐姿
      具体行为：抖腿
      对应状态：随意、焦虑、不耐烦，可能影响学习专注度
      原文依据：学习描述中提到“学生全程有轻微抖腿的动作”
    或输出 "无"。
    """
    if not raw_text or raw_text.strip() == "无":
        return {"items": []}

    items: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    key_map = {
        "行为维度": "dimension",
        "具体行为": "behavior",
        "对应状态": "state",
        "原文依据": "evidence",
    }

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*•]\s*", "", line)
        match = re.match(r"^(行为维度|具体行为|对应状态|原文依据)[:：]\s*(.+)$", line)
        if match:
            key_cn, value = match.group(1), match.group(2).strip()
            key_en = key_map[key_cn]
            current[key_en] = value
            if key_en == "evidence":
                if current:
                    items.append(current)
                current = {}
            continue

    if current:
        items.append(current)
    return {"items": items}


def analyze_learning_with_parse(
    learning_description: str,
    prompt: str = MultiModalConfig.MULTI_MODAL_ANOMALY,
    client: Optional[OpenAI] = None,
    model: str = "qwen-flash",
    # enable_thinking: bool = True,
    stream: bool = True,
) -> Dict[str, object]:
    """
    请求模型并返回完整回复，同时将结果解析为对象。

    Returns:
        {
            "raw": "完整回复文本",
            "parsed": {"items": [...]}
        }
    """
    if client is None:
        client = OpenAI(
            api_key=MultiModalConfig.QWEN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "\n\n学习描述：\n" + learning_description}
    ]

    if stream:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            # extra_body={"enable_thinking": enable_thinking},
            stream=True,
            response_format={"type": "json_object"}
        )
        full_content = ""
        for chunk in completion:
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                print(delta.reasoning_content, end="", flush=True)
            if hasattr(delta, "content") and delta.content:
                full_content += delta.content
    else:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            # extra_body={"enable_thinking": enable_thinking},
            stream=False,
            response_format={"type": "json_object"}
        )
        full_content = completion.choices[0].message.content or ""

    return json.loads(full_content)


# 多图片分析函数
async def video_chat_async_limit_frame(text, frames: Iterable[Union[str, np.ndarray]]):
    """
    使用多模态模型分析多张图片
    
    Args:
        text: 提示文本，描述需要模型做什么分析
        frames: 图片路径列表，例如 ['path/to/image1.jpg', 'path/to/image2.jpg']
    
    Returns:
        str: 模型的分析结果
    """
    logger = setup_module_logger("video_chat_async_limit_frame")
    try:
        # 将所有图片编码为base64
        base64_images = []
        for item in frames:
            if isinstance(item, np.ndarray):
                base64_img = encode_frame_array(item)
            else:
                base64_img = encode_image(item)
            base64_images.append(f"data:image/jpeg;base64,{base64_img}")
        
        logger.info(f"已编码 {len(base64_images)} 张图片")

        client = AsyncOpenAI(
            api_key=MultiModalConfig.QWEN_API_KEY,
            # 以下是北京地域base_url，如果使用新加坡地域的模型，需要将base_url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        
        completion = await client.chat.completions.create(
            model=MultiModalConfig.MULTI_MODAL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video",
                            "video": base64_images,
                        },
                        {"type": "text", "text": text},
                    ],
                }
            ],
        )

        logger.debug(f"API响应内容: {completion.choices[0].message.content}")
        return completion.choices[0].message.content
    except httpx.HTTPError as e:
        logger.error(f"API请求失败: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"处理响应数据时出错: {str(e)}", exc_info=True)
        raise





if __name__ == "__main__":
    prompt = """
    请根据输入的「学习描述」，按照以下要求完成任务：
1. 核心目标：以极度严苛的标准识别学生在「眼神交流」「坐姿」「手部动作」3个维度存在问题的行为表现，并严格依据对应表判断背后反映的状态（如紧张、自信等）。
2. 执行规则：
   - 必做：严格对照以下预设的行为-状态对应表逐字匹配进行判断，仅分析存在问题的行为；不得遗漏任何符合对应表的问题行为。
   - 禁止：不得主观臆断未在描述中提及的行为，仅基于输入的「学习描述」原文信息分析。
3. 行为-状态对应表（需严格逐字匹配，不得放宽标准）：
   - 眼神交流：
     - 回避视线 → 缺乏安全感、紧张、不信任、注意力分散；
   - 坐姿：
     - 双腿并拢 → 紧张、拘谨；
     - 弯腰驼背 → 自信心不足、精神萎靡、缺乏活力；
     - 抖腿 → 随意、焦虑、不耐烦，可能影响学习专注度；
     - 翘二郎腿 → 显得随意、不够礼貌、有防御感；
     - 身体后仰 → 可能显得懒散、疏离或过于放松；
   - 手部动作：
     - 双手夹在两腿之间 → 缺乏自信、紧张、寻求安全感；
     - 双手交叉放于胸前 → 防御心强、抗拒、没有安全感、封闭；
     - 挠头 → 着急、焦虑、思考困难；
     - 摸鼻子 → 可能紧张，或在特定情境下关联不诚实；
     - 把玩物品 → 紧张、焦虑，或心不在焉；
     - 拽衣角 → 紧张、不适应、显得不成熟；
     - 不停看表 → 制造压迫感，显得不耐烦或急于结束；
4. 输出要求：若存在问题行为，输出一个包含"problem_behaviors"键的JSON对象，其值为问题行为数组，每个数组元素需包含「behavior_dimension（行为维度）」「specific_behavior（具体行为）」「corresponding_state（对应状态）」「original_basis（原文依据）」四个字段；若不存在问题行为，则输出{"problem_behaviors": "无"}。
5. 输出格式示例：
{"problem_behaviors": [
  {
    "behavior_dimension": "坐姿",
    "specific_behavior": "抖腿",
    "corresponding_state": "随意、焦虑、不耐烦，可能影响学习专注度",
    "original_basis": "学生全程有轻微抖腿的动作"
  },
  {
    "behavior_dimension": "手部动作",
    "specific_behavior": "把玩物品",
    "corresponding_state": "紧张、焦虑，或心不在焉",
    "original_basis": "学生一直把玩手中的笔"
  }
]}

    """
    LEARNING_DESCRIPTION = """
- 学生面部表情平静，无明显微笑或紧张，眼神直视镜头，保持稳定目光接触
- 坐姿挺直，头部轻微向右偏转后恢复正中，右手抬起轻抚头顶，随后放下
- 着装为黑色带拉链的厚外套，左胸有白色标识文字，背景为室内环境，可见木质柜门与折叠被褥，墙面呈弧形，光线来自正面偏左侧，整体明亮均匀
    """
    client = OpenAI(
        # 如果没有配置环境变量，请用阿里云百炼API Key替换：api_key="sk-xxx"
        api_key=MultiModalConfig.QWEN_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    result = analyze_learning_with_parse(
        learning_description=LEARNING_DESCRIPTION,
        client=client,
        model="qwen-flash",
        # enable_thinking=True,
        stream=True,
    )
    print("\n" + "=" * 20 + "完整回复" + "=" * 20)
    print(result)