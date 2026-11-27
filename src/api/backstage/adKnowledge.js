import { requestPythonAll } from '@/utils/request.js'

// 获取知识文件列表
export const getKnowledgeFiles = () => {
  return requestPythonAll.get('/admin/knowledge/files')
}
// 上传知识文件
export const uploadKnowledgeFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return requestPythonAll.post('/admin/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
// 删除知识文件
export const deleteKnowledgeFile = (filename) => {
  return requestPythonAll.delete(`/admin/knowledge/files/${encodeURIComponent(filename)}`)
}
// 同步知识文件
export const syncKnowledge = (data = {}) => {
  const formData = new FormData()
  formData.append('user_id', data.user_id || 'admin')
  formData.append('recreate', String(data.recreate || false))
  return requestPythonAll.post('/admin/knowledge/sync', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
// 获取知识文件统计信息
export const getKnowledgeStats = (user_id = 'admin') => {
  return requestPythonAll.get(`/admin/knowledge/stats?user_id=${encodeURIComponent(user_id)}`)
}