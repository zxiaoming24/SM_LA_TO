//导入request对象
import request from '@/utils/request.js'

//发送验证码
export const getCodeApi = (data) => request.get(`/email/sendCode?email=${data}`, data)

//注册、修改密码
export const regAndPwdApi = (data) => request.post('/register', data)

//登录（邮箱/用户名）
export const loginApi = (data) => request.post('/login', data)

//退出登录
export const exitApi = (userId) => request.put(`/exit/${userId}`)

