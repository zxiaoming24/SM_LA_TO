//@/api/mainApi/layout.js
//导入request,requestPythonAll对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

//查询收藏列表
export const collectListApi = (userId) => request.get(`/getCollectionList/${userId}`)

//取消收藏
export const collectCancelApi = (data) => request.post('/CancelCollect', data)

//复习提醒（查询所有提醒信息）
export const reviewRemindApi = (userId) => request.get(`/pathPlan/reviewReminder/${userId}`)

//获取复习sessionId
export const getSessionIdApi = (data) => requestPythonAll.post('/review/session/get-or-create', data)

//复习次数加一
export const reviewCountAddOneApi = (userId) => request.put(`/draw/review/${userId}`)

//获取评估报告的通知
export const getEvaluateReportNotifyApi = (userId) => request.get(`/LearningAssessment/notifications/${userId}`)

//标记评估报告通知为已读
export const markEvaluateReportNotifyAsReadApi = (userId, data) => request.post(`/LearningAssessment/notifications/${userId}/read`, data)

//复习提醒-近七天复习
export const reviewRemindSevenDaysApi = (userId) => request.get(`/pathPlan/reviewReminder/sevenDays/${userId}`)

//复习提醒-总计
export const reviewRemindTotalApi = (userId) => request.get(`/pathPlan/reviewReminder/allCount/${userId}`)

//新用户漫游引导关闭
export const closeTourApi = (userId) => request.put(`/cancelTour/${userId}`)
