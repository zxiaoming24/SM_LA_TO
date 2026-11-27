// @/api/mainApi/resourcePaper.js

//导入request对象
import request from '@/utils/request.js'

//根据userId获取试卷列表
export const getPaperListApi = (userId) => request.get(`/paper/getPaperById/${userId}`)

//提交生成试卷
export const generatePaperApi = (data) => request.post('/paper/generatePaper', data)

//轮询试卷详情
export const pollPaperInfoApi = (id) => request.get(`/paper/getPaperInfoById/${id}`)

//删除试卷
export const deletePaperApi = (id) => request.delete(`/paper/deleteById/${id}`)

//理论题单题提交
export const submitSingleQuestionApi = (data) => request.post('/paper/theory/submit', data)