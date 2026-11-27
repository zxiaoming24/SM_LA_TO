import { requestPythonAll } from '@/utils/request.js'

//获取全部权重设置
export const getAllWeights = async () => {
  return requestPythonAll.get('/admin/weights')
}
//获取指定分类的权重设置
export const getCategoryWeights = async (category) => {
  return requestPythonAll.get(`/admin/weights/${category}`)
}
//更新指定分类的权重设置
export const updateCategoryWeights = async (category, updates) => {
  return requestPythonAll.post(`/admin/weights/${category}`, { updates })
}
//重置权重设置
export const resetWeights = async (category = null) => {
  return requestPythonAll.post('/admin/weights/reset', { category })
}