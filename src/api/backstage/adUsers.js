import request from '@/utils/request.js'

//查询用户列表
export const getUserListApi = (data) => request.post('/adUsersList', data)

//修改信息
export const updateUserInfoApi = (data) => request.put('/userInfoUpdate', data)

//删除用户
export const deleteUserApi = (userId) => request.delete(`/deleteUser/${userId}`)

//重置密码
export const resetPasswordApi = (userId) => request.put(`/replacePwd/${userId}`)



