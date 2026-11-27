//导入request对象
import request from '@/utils/request.js'

//获取讲解文档列表
export const getListByUserIdApi = (userId) => request.get(`/word/getList/${userId}`)

//提交生成获取任务id
export const submitApi = (data) => request.post('/word/submit', data)

//根据任务id获取进度
export const getProgressApi = (id) => request.get(`/word/getProgress/${id}`)

//删除word
export const deleteByWordIdApi = (id) => request.delete(`/word/delete/${id}`)
