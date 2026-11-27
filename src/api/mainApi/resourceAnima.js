// @/api/mainApi/resourceAnima.js

//导入request对象
import request from '@/utils/request.js'

//根据userId获取动画列表
export const getAnimaListApi = (userId) => request.get(`/animation/getList/${userId}`)

//提交生成动画获取任务id
export const generateAnimaApi = (data) => request.post('/animation/generateAnimation', data)

//根据任务id轮询进度
export const pollAnimaApi = (id) => request.get(`/animation/poll/${id}`)

//删除动画
export const deleteAnimaApi = (id) => request.delete(`/animation/deleteAnimation/${id}`)