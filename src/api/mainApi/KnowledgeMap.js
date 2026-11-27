/**
 * 知识图谱API接口
 * 提供知识图谱相关的所有HTTP请求方法
 */

import { requestPythonAll } from '@/utils/request'

/**
 * 获取用户的所有知识图谱列表
 * @param {string} userId - 用户ID
 * @returns {Promise} 图谱列表
 */
export const listGraphsApi = (userId) => {
  return requestPythonAll.get(`/knowledge-graph/${userId}`)
}

/**
 * 上传文档生成知识图谱
 * @param {string} userId - 用户ID
 * @param {FormData} formData - 包含文件的 FormData
 * @returns {Promise} 生成结果
 */
export const uploadGraphApi = (userId, formData) => {
  return requestPythonAll.post(`/knowledge-graph/upload/${userId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

/**
 * 获取知识图谱的富化数据（含节点和边）
 * @param {string} userId - 用户ID
 * @param {string} graphId - 图谱ID
 * @returns {Promise} 图谱数据
 */
export const getEnrichedGraphApi = (userId, graphId) => {
  return requestPythonAll.get(`/knowledge-graph/${userId}/${graphId}/enriched`)
}

/**
 * 删除知识图谱
 * @param {string} userId - 用户ID
 * @param {string} graphId - 图谱ID
 * @returns {Promise} 删除结果
 */
export const deleteGraphApi = (userId, graphId) => {
  return requestPythonAll.delete(`/knowledge-graph/${userId}/${graphId}`)
}

/**
 * 合并多个知识图谱
 * @param {string} userId - 用户ID
 * @param {string[]} graphIds - 要合并的图谱ID数组
 * @returns {Promise} 合并结果
 */
export const mergeGraphsApi = (userId, graphIds) => {
  return requestPythonAll.post(`/knowledge-graph/${userId}/merge`, { graph_ids: graphIds })
}

/**
 * 为知识点生成学习计划
 * @param {string} userId - 用户ID
 * @param {Object} data - 生成参数
 * @returns {Promise} 学习计划
 */
export const generateStudyPlanApi = (userId, data) => {
  return requestPythonAll.post('/study_plan/generate', { ...data, user_id: userId })
}
