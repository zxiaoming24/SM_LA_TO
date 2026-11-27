// @/api/mainApi/pathPlan.js

//导入request对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

// 查看是否生成过学习路径
export const isCreateApi = (userId) => request.get(`/pathPlan/checkCreate/${userId}`)

//生成学习路径
export const startPlanApi = (data) => request.post('/pathPlan/createPathPlan', data)

//获取学习计划当前进度
export const getProgressApi = (userId, planId) => request.get(`/pathPlan/currentPhase/${userId}?planId=${planId}`)

//一键生成所有的资源
export const createRsApi = (userId, phaseIndex, knowledgePoint) =>
  request.post(`/pathPlan/OneClickGenerate/${userId}/${phaseIndex}?KonwledgePoints=${knowledgePoint}`)

//获取某阶段的完成度
export const phaseProgressApi = (userId, phaseIndex, planId) => request.get(`/pathPlan/completion/query/${userId}/${phaseIndex}/${planId}`)//调用java
// export const phaseProgressApi = (userId, phaseIndex, planId) => requestPythonAll.get(`/study_plan/${userId}/phase/${phaseIndex}/progress`)//调用py

// 获取学习计划列表
export const getPathPlanListApi = (userId) => request.get(`/pathPlan/getPathPlan/${userId}`)

// 删除指定学习计划
export const delPathPlanApi = (userId, planId) => request.delete(`/pathPlan/deletePathPlan/${userId}/plan/${planId}`)

// 获取单个学习计划详情
export const getPlanDetailApi = (userId, planId) => request.get(`/pathPlan/checkCreate/${userId}?planId=${planId}`)

// 检查续期状态
export const checkStatusApi = (userId, planId) => request.get(`/pathPlan/checkPathPlan/${userId}/${planId}`)

// 接收续期建议
export const getCheckMsgApi = (userId, planId) => request.post(`/pathPlan/receiveContinuation/${userId}/${planId}`)

//拒绝续期建议
export const rejectCheckMsgApi = (userId, planId) => request.post(`/pathPlan/rejectRenewalSuggestion/${userId}/${planId}`)

// 用户选择是否进行阶段性考试
export const isOpenExamApi = (userId, phaseIndex, planId) =>
  request.post(`/pathPlan/exam/choice/${userId}/${phaseIndex}/${planId}`)

// 获取阶段性考题数据
export const getExamQuestionsApi = (userId, phaseIndex) => request.get(`/pathPlan/getExamQuestions/${userId}/${phaseIndex}`)

// 提交考试答案
export const submitExamAnswersApi = (userId, phaseIndex, data) => request.post(`/pathPlan/submitAnswers/${userId}/${phaseIndex}`, data)

// 接受阶段评估，触发下一阶段计划生成
export const phaseApplyApi = (userId, phaseIndex) => requestPythonAll.post(`/assessment/phase-apply/${userId}/${phaseIndex}`)

// 确认通知
export const ackNotificationApi = (userId, phaseIndex) => requestPythonAll.post(`/study_plan/${userId}/notification/ack?phase_index=${phaseIndex}`)

// 获取阶段通知（用于轮询评估报告是否生成完成）
export const getPhaseNotificationApi = (userId) => requestPythonAll.get(`/study_plan/${userId}/notification`)

//====================================版本树====================================
//获取学习计划版本树
export const getVersionTreeApi = (userId, planId) => request.get(`/pathPlan/getVersionTree/${userId}/${planId}`)

//切换版本树的当前执行中版本
export const changeVersionApi = (userId, planId) => request.get(`/pathPlan/switchVersionTree/${userId}/${planId}`)

//重新生成某一阶段的计划
export const reCreatePlanApi = (userId, data) => request.post(`/pathPlan/LocalRegeneration/${userId}`, data)

//====================================学习路线市场相关====================================
//分享到市场-ai分析学习计划
export const aiShareApi = (data) => request.post(`/channelMarket/aiArrangeRoute`, data)

//分享到市场
export const shareToMarketApi = (data) => request.post(`/channelMarket/publishRouteToMarket`, data)

