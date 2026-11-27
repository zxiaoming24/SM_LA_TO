//导入request对象
import request from '@/utils/request.js'

// 获取路径市场的分类
export const categoriesApi = () => request.get(`/channelMarket/categories`)

// 获取路径市场的列表
export const getRouteListApi = (userId, sort = null, search = null) => {
  let url = `/channelMarket/getRouteList?userId=${userId}`
  if (sort) url += `&sort=${sort}`
  if (search) url += `&search=${encodeURIComponent(search)}`
  return request.get(url)
}

// 获取路径市场的详情
export const getRouteDetailApi = (routeId) => request.get(`/channelMarket/getRouteDetail/${routeId}`)

// 采纳路径市场中的路径
export const adoptRouteApi = (routeId, data) => request.post(`/channelMarket/adoptRoute/${routeId}`, data)

// 获取路径市场中用户已采纳的路径
export const getAdoptedRoutesApi = (userId) => request.get(`/channelMarket/getAdoptedRoutes/${userId}`)

// 删除路径市场中的路径（仅发布者可删）
export const deleteRouteApi = (routeId, userId) => request.delete(`/channelMarket/deleteRoute/${routeId}/${userId}`)

// 用户对路径进行评价
export const evaluateRouteApi = (routeId, data) => request.post(`/channelMarket/evaluateRoute/${routeId}`, data)

// 编辑路径市场中的路径（仅发布者可编辑，PUT方法）
export const updateRouteApi = (routeId, data) => request.put(`/channelMarket/updateRoute/${routeId}`, data)


