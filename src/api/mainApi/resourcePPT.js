//导入request对象
import request from '@/utils/request.js'

//根据用户id获取ppt列表
export const getPPTListByUserId = (userId) => request.get(`/ppt/getTable/${userId}`)

//获取ppt任务id
export const getTaskIdApi = (userId, data) => request.post(`/ppt/getId/${userId}`, data)

//获取ppt生成进度
export const getPPTProgressApi = (taskId) => request.get(`/ppt/getProgress/${taskId}`)

//根据pptId删除ppt
export const deletePPTByIdApi = (pptId) => request.delete(`/ppt/delPPT/${pptId}`)