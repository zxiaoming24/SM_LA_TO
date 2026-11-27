# -*- coding: utf-8 -*-
corpus = []

from pymongo import MongoClient


class RecruitmentQuery:
    def __init__(self, uri="mongodb://localhost:27017/", db_name="study_learning"):
        self.client = MongoClient(uri)
        self.collection = self.client[db_name]["learning_resources"]

    def get_requirements(self, query_filter=None, include_id=False):
        """查询学习目标/课程要求"""
        if query_filter is None:
            query_filter = {}

        projection = {"learning_objectives": 1}
        if not include_id:
            projection["_id"] = 0

        cursor = self.collection.find(query_filter, projection)
        return list(cursor)

    def close(self):
        self.client.close()


query = RecruitmentQuery()
try:
    requirements = query.get_requirements()
    print(f"查询到 {len(requirements)} 条记录")
    for i, req in enumerate(requirements, 1):
        corpus.append(req.get("learning_objectives"))
finally:
    query.close()

import sys
import os

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

sys.path.append("../..")
from similarities import BertSimilarity

# 嵌入向量持久化文件路径
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_EMBEDDINGS_FILE = os.path.join(_BASE_DIR, "corpus_embeddings.jsonl")

# 初始化模型
model = BertSimilarity(model_name_or_path="shibing624/text2vec-base-chinese")


# 尝试加载已保存的嵌入向量，如果不存在则重新计算并保存
if os.path.exists(CORPUS_EMBEDDINGS_FILE):
    print(f"加载已保存的语料库嵌入向量: {CORPUS_EMBEDDINGS_FILE}")
    model.load_corpus_embeddings(CORPUS_EMBEDDINGS_FILE)
    print(f"成功加载 {len(model.corpus)} 条语料库")
else:
    print("未找到已保存的嵌入向量，重新计算中...")
    model.add_corpus(corpus)
    print(f"已添加 {len(corpus)} 条语料库到模型")
    # 自动保存到本地，避免下次重新计算
    try:
        model.save_corpus_embeddings(CORPUS_EMBEDDINGS_FILE)
        print(f"已自动保存嵌入向量到: {CORPUS_EMBEDDINGS_FILE}")
    except Exception as e:
        print(f"自动保存失败: {e}")


import json
from insert_sql import DatabaseInserter
from config import DatabaseConfig


def reload_corpus_embeddings():
    """
    重新从MongoDB加载语料库并保存嵌入向量

    用于MongoDB数据更新后，重新计算并保存嵌入向量

    Returns:
        dict: 包含重新加载状态的字典
    """
    try:
        global corpus
        corpus = []

        # 重新从MongoDB查询
        query = RecruitmentQuery()
        try:
            requirements = query.get_requirements()
            print(f"重新查询到 {len(requirements)} 条记录")
            for req in requirements:
                corpus.append(req.get("learning_objectives"))
        finally:
            query.close()

        # 重新添加到模型
        model.add_corpus(corpus)
        print(f"已重新添加 {len(corpus)} 条语料库到模型")

        # 保存嵌入向量
        model.save_corpus_embeddings(CORPUS_EMBEDDINGS_FILE)
        print(f"语料库嵌入向量已保存到: {CORPUS_EMBEDDINGS_FILE}")

        return {
            "success": True,
            "message": "语料库重新加载并保存成功",
            "file_path": CORPUS_EMBEDDINGS_FILE,
            "corpus_count": len(corpus),
        }
    except Exception as e:
        print(f"重新加载语料库失败: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "message": f"重新加载失败: {str(e)}"}


def extract_student_profile_info(profile_content):
    """
    从学生档案content_data中提取关键信息

    Args:
        profile_content: json.loads后的student_profile_data["content_data"]

    Returns:
        dict: 包含学历、学习经验、技能、项目经历、自我评价等信息
    """
    extracted_info = {
        "education": None,
        "experience": None,
        "skills": "",
        "projects": "",
        "self_evaluation": "",
    }

    # 从basicInfo中提取学历和学习年限
    if "basicInfo" in profile_content and "basicInfos" in profile_content["basicInfo"]:
        for item in profile_content["basicInfo"]["basicInfos"]:
            if item.get("basicKey") == "学历":
                extracted_info["education"] = item.get("basicVal")
            elif item.get("basicKey") == "学习年限":
                study_exp = item.get("basicVal")
                # 映射学习年限到标准时间范围
                if "初学者" in study_exp or "无" in study_exp or "在校" in study_exp:
                    extracted_info["experience"] = "经验不限"
                elif (
                    "1-3" in study_exp
                    or "1年" in study_exp
                    or "2年" in study_exp
                    or "3年以内" in study_exp
                ):
                    extracted_info["experience"] = "1-3年"
                elif "3-5" in study_exp:
                    extracted_info["experience"] = "3-5年"
                elif "5-10" in study_exp:
                    extracted_info["experience"] = "5-10年"
                elif "10" in study_exp:
                    extracted_info["experience"] = "10年以上"

    # 从otherInfos中提取技能、项目经历和个人评价
    if "otherInfos" in profile_content:
        for section in profile_content["otherInfos"]:
            if section.get("title") == "相关技能":
                extracted_info["skills"] = section.get("content", "")
            elif section.get("title") == "项目经历":
                extracted_info[
                    "projects"
                ] += f"[{section.get('subject', '')}] {section.get('content', '')} "
            elif section.get("title") == "自我评价":
                extracted_info["self_evaluation"] = section.get("content", "")

    return extracted_info


def get_matched_requirements_by_filters(education, experience, city=None):
    """
    根据学历和经验从MongoDB中匹配的学习资源（返回完整的学习资源信息）

    Args:
        education: 学历（如：本科、大专）
        experience: 经验（如：1-3年、3-5年、经验不限等）
        city: 城市（可选）

    Returns:
        list: 匹配条件的完整学习资源列表（包含所有字段）
    """
    try:
        query_filter = {}

        # 添加学历过滤条件
        if education:
            # 使用正则表达式进行模糊匹配学历
            query_filter["学历要求"] = {"$regex": education, "$options": "i"}

        # 添加经验过滤条件
        if experience:
            # 支持经验不限
            if experience == "经验不限":
                # 不添加经验过滤，表示不限制
                pass
            else:
                # 精确匹配或模糊匹配经验
                query_filter["经验要求"] = {"$regex": experience, "$options": "i"}

        # 添加城市过滤条件
        if city:
            query_filter["城市"] = {"$regex": city, "$options": "i"}

        print(f"\n=== MongoDB过滤条件 ===")
        print(f"学历: {education}")
        print(f"经验: {experience}")
        print(f"城市: {city if city else '不限'}")
        print(f"查询过滤器: {query_filter}")

        client = MongoClient("mongodb://localhost:27017/")
        collection = client["study_learning"]["learning_resources"]

        # 执行查询，返回完整的学习资源信息（所有字段）
        results = list(collection.find(query_filter, {"_id": 0}))

        client.close()

        print(f"过滤后找到 {len(results)} 条学习资源")
        return results

    except Exception as e:
        print(f"MongoDB查询失败: {e}")
        import traceback

        traceback.print_exc()
        return []


def match_student_with_courses(
    student_id: int,
    city: str = None,
    topn: int = 5,
    education: str = None,
    experience: str = None,
):
    """
    根据学生档案信息匹配相似的学习资源/课程

    先按学历和经验过滤MongoDB中的学习资源，再使用预训练的全局model进行相似度匹配

    Args:
        student_id: 学生ID
        city: 城市（可选，用于过滤学习资源）
        topn: 返回相似学习资源的数量
        education: 学历（可选，如果不提供则从学生档案中提取）
        experience: 经验（可选，如果不提供则从学生档案中提取）

    Returns:
        dict: 包含学生信息、提取的学历和经验、过滤后的学习资源数、以及匹配的完整学习资源列表
    """
    try:
        # 初始化数据库连接
        db = DatabaseInserter(
            host=DatabaseConfig.DB_HOST,
            user=DatabaseConfig.DB_USER,
            password=DatabaseConfig.DB_PASSWORD,
            database=DatabaseConfig.DB_NAME,
            port=DatabaseConfig.DB_PORT,
        )
        db.connect()

        # 获取学生档案数据
        student_data = db.get_student_by_id(student_id)
        if not student_data:
            print(f"未找到学生ID: {student_id}")
            return None

        # 解析学生档案的content_data字段
        profile_content = json.loads(student_data["content_data"])

        # 提取学生档案中的关键信息
        extracted_info = extract_student_profile_info(profile_content)
        # 如果接口未提供education和experience，则从学生档案中获取
        if education is None:
            education = extracted_info["education"]
        if experience is None:
            experience = extracted_info["experience"]
        skills = extracted_info["skills"]
        projects = extracted_info["projects"]
        self_evaluation = extracted_info["self_evaluation"]

        print(f"\n=== 学生信息提取结果 ===")
        print(f"学生ID: {student_id}")
        print(f"学历: {education}")
        print(f"经验: {experience}")
        print(f"技能: {skills[:100]}..." if skills else "技能: 无")
        print(f"项目: {projects[:100]}..." if projects else "项目: 无")
        print(f"评价: {self_evaluation[:100]}..." if self_evaluation else "评价: 无")

        # 第一步：根据学历和经验从MongoDB过滤学习资源
        filtered_learning_resources = get_matched_requirements_by_filters(
            education=education, experience=experience, city=city
        )

        if not filtered_learning_resources:
            print("未找到符合学历和经验的学习资源")
            return None

        # 从过滤后的学习资源中提取学习目标文本
        objective_texts = [
            res.get("learning_objectives", "")
            for res in filtered_learning_resources
            if res.get("learning_objectives")
        ]

        if not objective_texts:
            print("未找到学习目标文本")
            return None

        # 构建查询文本（组合学生档案的核心信息）
        query_text_parts = []
        if education:
            query_text_parts.append(f"学历:{education}")
        if experience and experience != "经验不限":
            query_text_parts.append(f"经验:{experience}")
        if skills:
            query_text_parts.append(f"技能:{skills}")
        if projects:
            query_text_parts.append(f"项目:{projects}")
        if self_evaluation:
            query_text_parts.append(f"评价:{self_evaluation}")

        query_text = (
            "。".join(query_text_parts) if query_text_parts else str(profile_content)
        )

        print(f"\n=== 相似度匹配 ===")
        print(f"查询文本: {query_text[:150]}...")
        print(f"待匹配学习资源数: {len(objective_texts)}")

        # 第二步：使用全局预训练的model进行相似度计算
        # 在全局corpus中搜索，获取相似度匹配结果
        similar_results = model.most_similar(queries=[query_text], topn=topn)
        # print("similar_results",similar_results)
        # 第三步：根据相似度匹配的学习目标，找到对应的完整学习资源
        matched_full_info = []
        if similar_results and len(similar_results) > 0:
            # similar_results[0] 是一个列表，包含相似的结果
            for item in similar_results[0]:
                # 处理可能的不同返回格式
                # 格式1: [text, score]
                # 格式2: [index, text, score]
                # 格式3: {"text": ..., "score": ...} 等其他格式

                position_text = None
                score = None

                position_text = item["corpus_doc"]
                score = item["score"]

                # 在过滤后的学习资源中找到对应的完整记录
                if position_text:
                    for resource in filtered_learning_resources:
                        if resource.get("learning_objectives", "") == position_text:
                            matched_full_info.append(
                                {
                                    "similarity_score": score,
                                    "resource_info": resource,
                                }
                            )
                            break

        # 构建返回结果
        result = {
            "student_id": student_id,
            "extracted_info": {
                "education": education,
                "experience": experience,
                "skills": skills,
                "projects": projects,
                "self_evaluation": self_evaluation,
            },
            "query_city": city,
            "filtered_count": len(objective_texts),  # 过滤后的学习资源数
            "matched_courses": matched_full_info,  # 返回完整的学习资源+相似度分数
        }

        print(f"\n=== 最终匹配结果 ===")
        print(f"过滤后的学习资源: {len(objective_texts)} 条")
        print(f"返回的相似学习资源: {len(matched_full_info)} 条")

        db.close()
        return result

    except Exception as e:
        print(f"匹配失败: {e}")
        import traceback

        traceback.print_exc()
        return None


# 使用示例
# result = match_student_with_courses(student_id=1, city="北京", topn=100)
