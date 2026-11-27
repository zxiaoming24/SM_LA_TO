//导入request对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

//获取评论区列表
export const getPostsListApi = (page, pageSize, zone) => request.get(`/comment/getPostsList/${page}/${pageSize}/${zone}`)

//根据帖子id查询某个帖子的具体信息（含回复）
export const getPostApi = (postId) => request.get(`/comment/getPost/${postId}`)

//根据帖子id回复帖子
export const replyPostApi = (data) => request.post('/comment/replyPost', data)

//删除回复
export const deleteReplyApi = (userId, replyId) => request.delete(`/comment/deleteReply/${userId}/${replyId}`)

//删除帖子
export const deletePostApi = (userId, postId) => request.delete(`/comment/deletePost/${userId}/${postId}`)

//根据用户id序列查询用户信息序列
export const getUserInfoApi = (data) => request.post('/comment/getNameData', data)

//发布帖子
export const submitPostApi = (data) => request.post('/comment/submitPost', data)

/**
 * 上传文件
 * @param {FormData} formData - 包含文件的表单数据
 * @returns {Promise} 上传结果响应
 */
export const uploadCommonFileApi = (formData) => {
  return request.post('/common/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}


// getPostsListApi,getPostApi,replyPostApi,deleteReplyApi,deletePostApi,getUserInfoApi,submitPostApi


//===========================排行榜相关=================================

// 获取全局排行榜
export const getGlobalRankingApi = (limit = 20, userId = '') => {
  const params = new URLSearchParams()
  params.append('limit', limit)
  if (userId) params.append('user_id', userId)
  return requestPythonAll.get(`api/global-ranking?${params.toString()}`)
}

// 获取用户详情
export const getUserRankDetailApi = (userId) => requestPythonAll.get(`api/global-ranking/user/${userId}`)
