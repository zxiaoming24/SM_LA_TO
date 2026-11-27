import argparse
import json
import os
import uuid
from datetime import datetime
from typing import Optional, List

import asyncio

from fastapi import BackgroundTasks, FastAPI, File, Form, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from logger import get_logger
from insert_sql import DatabaseInserter
from config import DatabaseConfig
from video_deal_video import analyze_video_file
from resume_sim import match_student_with_courses, reload_corpus_embeddings

logger = get_logger(__name__)

app = FastAPI()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_UPLOADS_DIR = os.path.join(_BASE_DIR, "uploaded_videos")

# Track background task status by session_id
_task_status_lock = asyncio.Lock()
_task_status_by_session_id: dict[str, str] = {}

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.post("/analyze-video")
async def analyze_video_endpoint(
	background_tasks: BackgroundTasks,
	file: UploadFile = File(...),
	analysis: Optional[str] = Form(None),
	session_id: Optional[str] = Form(None),
):
	if not session_id:
		return {
			"error": "session_id is required to track background task status"
		}

	analysis_config = {
		"behaviorAnalysis": True,
		"expressionAnalysis": False,
		"postureAnalysis": False,
        "faceAnalysis": False,
		"sessionId": session_id,
		"display": True,
	}

	if analysis:
		try:
			parsed = json.loads(analysis)
			if isinstance(parsed, dict):
				analysis_config.update(parsed)
		except json.JSONDecodeError:
			logger.warning("analysis 参数不是有效 JSON，已忽略")

	# 上传分析默认不显示实时窗口
	analysis_config["display"] = False

	if session_id and not analysis_config.get("sessionId"):
		analysis_config["sessionId"] = session_id

	interview_dir = os.path.join(_UPLOADS_DIR, session_id)
	os.makedirs(interview_dir, exist_ok=True)

	safe_name = os.path.basename(file.filename or "upload.mp4")
	_, ext = os.path.splitext(safe_name)
	if not ext:
		ext = ".mp4"
	stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
	unique_id = uuid.uuid4().hex
	video_filename = f"{session_id}_{stamp}_{unique_id}{ext}"
	video_path = os.path.join(interview_dir, video_filename)

	async def _save_and_analyze() -> None:
		async with _task_status_lock:
			_task_status_by_session_id[session_id] = "running"

		try:
			with open(video_path, "wb") as f:
				while True:
					chunk = await file.read(1024 * 1024)
					if not chunk:
						break
					f.write(chunk)

			await analyze_video_file(
				video_path,
				analysis_config=analysis_config,
				video_filename=video_filename,
			)
			async with _task_status_lock:
				_task_status_by_session_id[session_id] = "completed"
		except Exception:
			logger.exception("上传保存或分析处理失败")
			async with _task_status_lock:
				_task_status_by_session_id[session_id] = "failed"
		finally:
			await file.close()

	background_tasks.add_task(_save_and_analyze)

	return {
		"video_path": video_path,
		"video_filename": video_filename,
	}


def _list_interview_videos(session_id: str) -> List[str]:
	interview_dir = os.path.join(_UPLOADS_DIR, session_id)
	if not os.path.isdir(interview_dir):
		return []
	items = []
	for name in os.listdir(interview_dir):
		if not name.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
			continue
		file_path = os.path.join(interview_dir, name)
		try:
			mtime = os.path.getmtime(file_path)
		except OSError:
			mtime = 0
		items.append((mtime, name))
	items.sort(key=lambda item: item[0])
	return [name for _, name in items]


@app.get("/videos/{session_id}/{filename}", name="get_uploaded_video")
async def get_uploaded_video(session_id: str, filename: str):
	file_path = os.path.join(_UPLOADS_DIR, session_id, os.path.basename(filename))
	if not os.path.exists(file_path):
		return {"error": "video not found"}
	return FileResponse(file_path)



@app.get("/analyze-status")
async def analyze_status(session_id: str, request: Request):
	async with _task_status_lock:
		status = _task_status_by_session_id.get(session_id)
	filenames = _list_interview_videos(session_id)
	urls = {
		name: str(request.url_for("get_uploaded_video", session_id=session_id, filename=name))
		for name in filenames
	}

	analysis_by_video: dict[str, list] = {}
	if DatabaseConfig.ENABLE_DATABASE:
		try:
			session_id_int = int(session_id)
		except ValueError:
			session_id_int = None
			logger.warning("session_id 不是有效数字，跳过数据库查询: %s", session_id)
		if session_id_int is not None:
			db = DatabaseInserter(
				host=DatabaseConfig.DB_HOST,
				user=DatabaseConfig.DB_USER,
				password=DatabaseConfig.DB_PASSWORD,
				database=DatabaseConfig.DB_NAME,
				port=DatabaseConfig.DB_PORT,
			)
			try:
				results = db.get_analysis_data_by_session_id(session_id_int)
				if results:
					for row in results:
						video_name = row.get("video_name")
						if not video_name:
							continue
						payload = row.get("data")
						if isinstance(payload, str):
							try:
								payload = json.loads(payload)
							except json.JSONDecodeError:
								pass
						entry = {
							"type": row.get("type"),
							"start_analysis_ts": row.get("start_analysis_ts"),
							"end_analysis_ts": row.get("end_analysis_ts"),
							"data": payload,
						}
						analysis_by_video.setdefault(video_name, []).append(entry)
			except Exception:
				logger.exception("查询多模态分析结果失败")
			finally:
				db.close()

	video_results = []
	for name in filenames:
		file_path = os.path.join(_UPLOADS_DIR, session_id, name)
		try:
			mtime = os.path.getmtime(file_path)
			created_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
		except OSError:
			created_at = None
		video_results.append({
			"video_name": name,
			"url": urls.get(name),
			"created_at": created_at,
			"analysis": analysis_by_video.get(name, []),
		})

	return {
		"session_id": session_id,
		"status": status or "not_found",
		"videos": video_results,
	}


@app.post("/match-student-courses")
async def match_student_courses(
	student_id: int,
	city: Optional[str] = None,
	topn: int = 5,
	education: Optional[str] = None,
	experience: Optional[str] = None,
):
	"""
	根据学生档案信息匹配相似的学习资源/课程
	
	Args:
		student_id: 学生ID
		city: 城市（可选，用于过滤学习资源）
		topn: 返回相似学习资源的数量（默认5）
		education: 学历（可选，如果不提供则从学生档案中提取）
		experience: 经验（可选，如果不提供则从学生档案中提取）
	
	Returns:
		包含学生信息、提取的学历和经验、过滤后的学习资源数、以及匹配的完整学习资源列表
	"""
	try:
		result = match_student_with_courses(
			student_id=student_id,
			city=city,
			topn=topn,
			education=education,
			experience=experience
		)
		
		if result is None:
			return {
				"error": "Failed to match student courses",
				"student_id": student_id
			}
		
		return {
			"success": True,
			"data": result
		}
	except Exception as e:
		logger.exception("学生课程匹配失败")
		return {
			"error": str(e),
			"student_id": student_id
		}


@app.post("/reload-corpus-embeddings")
async def reload_corpus_embeddings_endpoint():
	"""
	重新从MongoDB加载语料库并保存嵌入向量
	
	用于MongoDB中的学习资源更新后，
	重新计算嵌入向量并保存到本地文件。
	
	Returns:
		包含重新加载状态的响应
	"""
	try:
		result = reload_corpus_embeddings()
		return result
	except Exception as e:
		logger.exception("重新加载语料库失败")
		return {
			"success": False,
			"error": str(e)
		}


if __name__ == "__main__":
	import uvicorn

	parser = argparse.ArgumentParser(description="Video upload analysis server")
	parser.add_argument(
		"--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
	)
	parser.add_argument(
		"--port", type=int, default=8088, help="Port for HTTP server (default: 8088)"
	)
	args = parser.parse_args()

	uvicorn.run(app, host=args.host, port=args.port)
