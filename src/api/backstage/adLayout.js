import request from '@/utils/request.js'

//查询申请为管理员列表
export const getApplyListApi = () => request.get('/applyAdminList')

//同意用户申请
export const agreeApplyApi = (userId) => request.put(`/acceptRequest/${userId}`)

//拒绝用户申请
export const refuseApplyApi = (userId) => request.put(`/rejectRequest/${userId}`)