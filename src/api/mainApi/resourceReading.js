//导入request对象
import request from '@/utils/request.js'

//根据用户id获取拓展材料简单列表
export const getReadingListByUserId = (userId) => request.get(`/reading/${userId}`)

//材料生成提交
export const submitReadingApi = (data) => request.post('/reading/getId', data)

//获取生成进度
export const getReadingProgressApi = (id) => request.get(`/reading/getProgress/${id}`)

//根据id查询对应的阅读材料
export const getValueApi = (id) => request.get(`/reading/getHtml/${id}`)

//根据id删除对应的阅读材料
export const deleteReadingByIdApi = (id) => request.delete(`/reading/delete/${id}`)

// getReadingListByUserId,submitReadingApi,getReadingProgressApi,getValueApi,deleteReadingByIdApi