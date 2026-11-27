import request from '@/utils/request.js'

//用户相关的数据查询（用户总计，用户新增，今日活跃用户，已构建画像用户）
export const getUserStatisticsApi = () => request.get('/admin/user/basicInfo')

//资源相关的数据查询（资源总量，今日新增资源量）
export const getResourceStatisticsApi = () => request.get('/admin/resource/basicInfo')

//用户喜爱资源排行榜（资源点击量总的）
export const getResourceRankApi = () => request.get('/admin/popularResourcesRank')

//生成资源的趋势图（echarts）（近一周，近三个月，近一年）
export const getResourceTrendApi = (rangeType = 'mouth') => request.get(`/admin/resourceGenerationTrend/${rangeType}`)

