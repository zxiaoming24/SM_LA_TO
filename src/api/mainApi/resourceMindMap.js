//导入request对象
import request from '@/utils/request.js'

//获取思维导图简单信息列表
export const getListByUserIdApi = (userId) => request.get(`/mindMap/getList/${userId}`)

//查询单个思维导图展示信息值
export const getValueByMindMapIdApi = (mindMapId) => request.get(`/mindMap/getValue/${mindMapId}`)

//思维导图换页
export const changeMindMapApi = (mindMapId, userId, operation) => request.get(`/mindMap/page/${mindMapId}/${userId}/${operation}`)

//提交文本获取思维导图生成id
export const submitGetMindMapIdApi = (data) => request.post('/mindMap/getTaskId', data)

//思维导图任务id获取生成进度
export const getProgressApi = (taskId) => request.get(`/mindMap/getProgress/${taskId}`)

//删除单个思维导图
export const deleteByMindMapIdApi = (mindMapId) => request.delete(`/mindMap/delete/${mindMapId}`)

