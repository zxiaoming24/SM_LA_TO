import { requestPythonAll } from '@/utils/request'

// ==================== 理论题 API ====================

// 获取所有理论题
export const getTheoryQuestions = (params) => {
  return requestPythonAll.get('/admin/theory-questions', { params })
}
// 获取理论题统计信息
export const getTheoryQuestionStats = () => {
  return requestPythonAll.get('/admin/theory-questions/stats')
}
// 获取指定理论题的详细信息
export const createTheoryQuestion = (data) => {
  return requestPythonAll.post('/admin/questions', data)
}
// 更新指定理论题
export const updateTheoryQuestion = (qid, data) => {
  return requestPythonAll.put(`/admin/questions/${qid}`, data)
}
// 删除指定理论题
export const deleteTheoryQuestion = (qid) => {
  return requestPythonAll.delete(`/admin/questions/${qid}`)
}
// 获取指定理论题的详细信息
export const getQuestionDetail = (qid) => {
  return requestPythonAll.get(`/admin/questions/${qid}`)
}

// ==================== 编程题 API ====================

// 获取所有编程题
export const getPracticeQuestions = (params) => {
  return requestPythonAll.get('/admin/practice-questions', { params })
}
// 获取编程题统计信息
export const getPracticeQuestionStats = () => {
  return requestPythonAll.get('/admin/practice-questions/stats')
}
// 获取指定编程题的详细信息
export const createPracticeQuestion = (data) => {
  return requestPythonAll.post('/admin/questions', data)
}
// 更新指定编程题
export const updatePracticeQuestion = (qid, data) => {
  return requestPythonAll.put(`/admin/questions/${qid}`, data)
}
// 删除指定编程题
export const deletePracticeQuestion = (qid) => {
  return requestPythonAll.delete(`/admin/questions/${qid}`)
}

// ==================== 视频 API ====================

// 获取所有视频
export const getVideos = (params) => {
  return requestPythonAll.get('/admin/videos', { params })
}
// 获取视频统计信息
export const getVideoStats = () => {
  return requestPythonAll.get('/admin/videos/stats')
}
// 获取指定视频的详细信息
export const getVideoTopics = () => {
  return requestPythonAll.get('/admin/videos/topics')
}
// 获取指定视频的详细信息
export const getVideoDetail = (vid) => {
  return requestPythonAll.get(`/admin/videos/${vid}`)
}
// 创建新视频
export const createVideo = (data) => {
  return requestPythonAll.post('/admin/videos', data)
}
// 更新指定视频
export const updateVideo = (vid, data) => {
  return requestPythonAll.put(`/admin/videos/${vid}`, data)
}
// 删除指定视频
export const deleteVideo = (vid) => {
  return requestPythonAll.delete(`/admin/videos/${vid}`)
}

// ==================== 通用 API ====================
// 获取所有题目分类
export const getQuestionTopics = () => {
  return requestPythonAll.get('/admin/questions/topics')
}