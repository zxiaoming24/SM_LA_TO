// @/api/mainApi/pop.js

//导入request对象
import request from '@/utils/request.js'

//收藏资源
export const collectApi = (data) => request.post('/CollectResources', data)

//分享资源给学伴/社区
export const shareApi = (data) => request.post('/StudyBuddy/shareResources', data)

//获取ai规划发帖信息/发帖助手(AI生成发帖内容)
export const getAiPostInfoApi = (data) => request.post('/comment/postAssistant', data)

//发帖助手(将用户修改好的帖子发布到社区)
export const postAiApi = (data) => request.post('/comment/postAssistant/submitPost', data)

//发起共学请求
export const studyTogetherApi = (data) => request.post('/ColearningRecords/SendInvitation', data)
