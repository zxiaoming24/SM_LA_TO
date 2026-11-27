// 暂时无用，token以通过请求头传给后端校验

//导入request对象
import request from '@/utils/request.js'

//令牌校验
/**
 * 向后端发送令牌校验请求
 * @param {string} token - 用户的登录令牌
 * @returns {Promise<Object>} 返回后端响应数据
 */
export const validateTokenApi = async (token) => {
  return request.post('/check', { token }) // 将 token 放入请求体
}