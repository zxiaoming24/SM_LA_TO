//导入request对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

//对话提交
export const postTextApi = (data) => request.post('/aiAnswer/submit', data)

// ASR语音识别(前端——>python)
export const postAudioApi = (formData) => {
  return requestPythonAll.post('/speech/recognize', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

//轮询资源结果
export const getProgressApi = (userId, rsType, taskId) => request.get(`/aiAnswer/getProgress/${userId}/${rsType}/${taskId}`)

//重新生成某种资源
export const reCreateApi = (userId, rsType, taskId) => request.get(`/aiAnswer/reCreate/${userId}/${rsType}/${taskId}`)

//用于查询与数字人的历史对话记录
export const aiHistoryApi = (userId, lastId) => request.get(`/aiAnswer/queryHistoryRecords/${userId}/${lastId}`)

//选择/切换学习方案
export const changePlanApi = (data) => request.post('/aiAnswer/plan', data)

//获取方案（当前选择的方案和方案列表）
export const getPlanApi = (userId) => request.get(`/aiAnswer/plan/${userId}`)

//冲突弹窗选择操作
export const conflictApi = (userId, data) => request.post(`/aiAnswer/conflict/${userId}`, data)