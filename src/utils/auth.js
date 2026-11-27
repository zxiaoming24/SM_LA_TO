// 暂时无用 src/utils/auth.js
import { ElMessage } from 'element-plus';
import router from '@/router';
import { validateTokenApi } from '@/api/check';

/**
 * 检查用户是否已登录（token 是否有效）
 * @returns {Promise<boolean>} 返回 true 表示 token 有效，false 表示无效
 */

// 跳转到登录页面
const redirectToLogin = () => {
  // 清除登录信息
  localStorage.removeItem('loginUser')
  // 根据设备类型跳转
  router.push('/login')
}
export const checkToken = async () => {
  // 从 localStorage 中获取 loginUser 字符串 (注意键名变化)
  const userStr = localStorage.getItem('loginUser');

  // 如果没有存储数据，直接跳转
  if (!userStr) {
    ElMessage.warning('请先登录');
    redirectToLogin()
    return false
  }

  let token = null;

  // 尝试解析 JSON 字符串并提取 token
  try {
    const userObj = JSON.parse(userStr);
    token = userObj.token;
  } catch (e) {
    // 如果数据损坏（不是合法的 JSON），视为无效登录
    console.error('本地用户数据格式错误:', e);
    ElMessage.error('登录信息异常，请重新登录');
    redirectToLogin();
    return false;
  }

  // 二次检查：确保解析出来的对象里确实有 token
  if (!token) {
    ElMessage.warning('登录信息不完整，请重新登录');
    redirectToLogin();
    return false;
  }

  // 调用后端接口验证 token 是否有效
  try {
    const result = await validateTokenApi(token);
    if (result.code === 1 && result.data === true) {
      return true; // token 有效
    } else {
      ElMessage.error(result.msg || '登录已过期，请重新登录');
      redirectToLogin()
      return false;
    }
  } catch (error) {
    console.error('Token 验证请求失败:', error);
    ElMessage.error('验证登录状态失败，请稍后再试');
    redirectToLogin()
    return false;
  }
};