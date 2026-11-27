//导入request对象
import request from '@/utils/request.js'
import { submitSingleQuestionApi } from './resourcePaper.js'

//获取用户错题本统计信息
export const getSummaryApi = (userId) => request.get(`/WrongQuestions/getStats/${userId}`)

//获取 待巩固 列表
export const getPendingListApi = (page, pageSize, question_type, userId) => request.get(`/WrongQuestions/getList/${page}/${pageSize}/${question_type}/${userId}`)

//获取 已掌握 列表
export const getOkListApi = (page, pageSize, userId) => request.get(`/WrongQuestions/Mastered/${page}/${pageSize}/${userId}`)

//删除帖子
export const deleteQuestionApi = (userId, recordId) => request.delete(`/WrongQuestions/deleteById/${recordId}/${userId}`)

//获取错题的推荐材料（错三次及以上就会有推荐材料）
export const getInfoApi = (userId, recordId) => request.get(`/WrongQuestions/getRecommendedResources/${recordId}/${userId}`)

//AI生成推荐材料
export const getAiRecommendApi = (data) => request.post('/WrongQuestions/getAiRecommend', data)

// 获取 易错题 信息列表
export const getFrequentlyListApi = (page, pageSize, userId) => request.get(`/WrongQuestions/getList/frequently-wrong/${page}/${pageSize}/${userId}`)

//获取 易错题 统计信息
export const getFrequentlyMesApi = (userId) => request.get(`/WrongQuestions/getList/frequently-wrong/${userId}/stats`)

export { submitSingleQuestionApi }

//getSummaryApi,getPendingListApi,getOkListApi,deleteQuestionApi,getInfoApi