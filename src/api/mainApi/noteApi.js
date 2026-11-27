/**
 * 笔记本API接口
 * 提供笔记本相关的所有HTTP请求方法
 */

import { requestPythonAll, requestPython } from '@/utils/request'
import request from '@/utils/request'

/**
 * 获取用户的所有笔记列表
 * @param {string} userId - 用户ID
 * @returns {Promise} 笔记列表响应
 */
export const listNotesApi = (userId) => {
  return requestPythonAll.get(`/notes/${userId}`)
}

/**
 * 创建新笔记
 * @param {string} userId - 用户ID
 * @param {Object} data - 笔记数据
 * @param {string} data.title - 笔记标题
 * @param {string} data.content - 笔记内容
 * @param {boolean} data.use_ai - 是否使用AI整理
 * @returns {Promise} 创建结果响应
 */
export const createNoteApi = (userId, data) => {
  return requestPythonAll.post(`/notes/${userId}`, data)
}

/**
 * 获取特定笔记详情
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @returns {Promise} 笔记详情响应
 */
export const getNoteApi = (userId, noteId) => {
  return requestPythonAll.get(`/notes/${userId}/${noteId}`)
}

/**
 * 更新笔记
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @param {Object} data - 更新数据
 * @param {string} data.title - 笔记标题
 * @param {string} data.content - 笔记内容
 * @returns {Promise} 更新结果响应
 */
export const updateNoteApi = (userId, noteId, data) => {
  return requestPythonAll.put(`/notes/${userId}/${noteId}`, data)
}

/**
 * 删除笔记
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @returns {Promise} 删除结果响应
 */
export const deleteNoteApi = (userId, noteId) => {
  return requestPythonAll.delete(`/notes/${userId}/${noteId}`)
}

/**
 * 使用AI整理笔记
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @param {Object} data - 整理数据
 * @param {string} data.title - 笔记标题
 * @param {string} data.content - 笔记内容
 * @returns {Promise} 整理结果响应
 */
export const organizeNoteApi = (userId, noteId, data) => {
  return requestPythonAll.post(`/notes/${userId}/${noteId}/organize-preview/accept`, data)
}

/**
 * 导出笔记
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @param {Object} data - 导出参数
 * @param {string} data.format - 导出格式 (pdf/docx)
 * @returns {Promise} 导出结果响应 (blob)
 */
export const exportNoteApi = (userId, noteId, data) => {
  return requestPython.post(`/notes/${userId}/${noteId}/export`, data, {
    responseType: 'blob'
  })
}

/**
 * 上传图片
 * @param {FormData} formData - 包含图片的表单数据
 * @returns {Promise} 上传结果响应
 */
export const uploadImageApi = (formData) => {
  return request.post('/common/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 上传附件
 * @param {string} userId - 用户ID
 * @param {FormData} formData - 包含附件的表单数据
 * @returns {Promise} 上传结果响应
 */
export const uploadAttachmentApi = (userId, formData) => {
  return requestPythonAll.post(`/notes/upload/${userId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 流式解释选中文本
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @param {string} selectedText - 选中的文本
 * @returns {Promise} 流式响应Promise
 */
export const explainSelectionStreamApi = (userId, noteId, selectedText) => {
  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(`/py/notes/${userId}/${noteId}/explain-selection?selected_text=${encodeURIComponent(selectedText)}`)
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'done' || data.type === 'error') {
          eventSource.close()
        }
        resolve({ done: data.type === 'done' || data.type === 'error', data })
      } catch (e) {
        reject(e)
      }
    }
    eventSource.onerror = (error) => {
      eventSource.close()
      reject(error)
    }
  })
}

/**
 * 搜索笔记（用于[[提及和关联笔记）
 * @param {string} userId - 用户ID
 * @param {string} query - 搜索关键词
 * @returns {Promise} 搜索结果响应
 */
export const searchNotesApi = (userId, query = '') => {
  return requestPythonAll.get(`/notes/${userId}/search?q=${encodeURIComponent(query)}`)
}

/**
 * 获取知识图谱数据
 * @param {string} userId - 用户ID
 * @returns {Promise} 图谱数据响应
 */
export const getGraphDataApi = (userId) => {
  return requestPythonAll.get(`/notes/${userId}/graph-data`)
}

/**
 * 获取知识宇宙数据（3D知识点图谱）
 * @param {string} userId - 用户ID
 * @returns {Promise} 知识宇宙数据响应
 */
export const getKnowledgeUniverseApi = (userId) => {
  return requestPythonAll.get(`/knowledge-universe/${userId}`)
}

/**
 * 生成思维导图
 * @param {string} title - 笔记标题
 * @param {string} content - 笔记内容
 * @returns {Promise} 思维导图数据响应
 */
export const generateMindmapApi = (title, content) => {
  return requestPythonAll.post('/api/note/mindmap', { title, content })
}

/**
 * AI 整理预览（获取 Diff）
 * @param {string} userId - 用户ID
 * @param {string} noteId - 笔记ID
 * @param {Object} data - 整理数据
 * @param {string} data.title - 笔记标题
 * @param {string} data.content - 笔记内容
 * @returns {Promise} 预览数据响应
 */
export const organizePreviewApi = (userId, noteId, data) => {
  return requestPythonAll.post(`/notes/${userId}/${noteId}/organize-preview`, data)
}