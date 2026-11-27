import { requestPythonAll } from '@/utils/request.js'


// 获取排行榜权重配置
export const getRankingWeightsApi = () => {
  return requestPythonAll.get('/admin/global-ranking/weights')
}

// 更新排行榜权重配置
export const updateRankingWeightsApi = (weights) => {
  return requestPythonAll.post('/admin/global-ranking/weights', weights)
}
