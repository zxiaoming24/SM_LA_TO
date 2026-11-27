//@/api/mainApi/evaluate.js

//导入request对象
import request from '@/utils/request.js'

//获取用户最新的评估报告
export const getReportApi = (userId) => request.get(`/LearningAssessment/getAssessment/${userId}`)

//生成用户学习效果的评估报告
export const createReportApi = (userId) => request.post(`/LearningAssessment/GenerationAssessment/${userId}`)

//采纳建议
export const takeSugApi = (userId, data) => request.post(`/LearningAssessment/AdoptSuggestions/${userId}`, data)

//获取用户已经采纳的建议
export const sugListApi = (userId) => request.get(`/LearningAssessment/getSuggestions/${userId}`)

//拒绝采纳建议或者撤销采纳的建议
export const noSugApi = (userId, data) => request.post(`/LearningAssessment/rejectSuggestions/${userId}`, data)

//重新生成某一维度的学习评估
export const reCreateDimApi = (userId, data) => request.post(`/LearningAssessment/LocalGenerationEvaluation/${userId}`, data)