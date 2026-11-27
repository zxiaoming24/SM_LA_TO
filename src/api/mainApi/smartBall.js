/**
 * 智能球 API 接口模块
 * 用于与 Python 后端进行智能球聊天、页面上下文上报等交互
 * 所有请求通过 /py 代理转发到 Python 后端服务
 */
import { requestPythonAll } from '@/utils/request.js'

import request from '@/utils/request.js'// 引入 request 模块（java端）

/**
 * 智能球聊天接口
 * 发送用户消息，获取智能球的回复（支持上下文感知）
 * 
 * @param {Object} data - 请求参数
 * @param {string} data.user_input - 用户输入的消息内容
 * @param {string} data.user_id - 用户ID
 * @param {Object} data.page_context - 页面上下文信息
 *   - {string} page_context.page - 当前页面名称（如 'home', 'study_plan', 'code'）
 *   - {string} page_context.title - 页面标题
 *   - {string} page_context.action - 用户行为（如 'viewing', 'editing'）
 *   - {string} page_context.detail - 页面细节（如题目内容、学习进度等）
 * @param {boolean} data.enable_tts - 是否启用语音合成（可选，默认false）
 * @returns {Promise} 返回智能球回复数据
 *   - response.data.reply - 智能球的回复文本
 *   - response.data.intent - 用户意图分析结果
 *   - response.data.type - 对话类型（如 'casual_chat', 'learning_help'）
 */
export const smartBallChatApi = (data) => requestPythonAll.post('/chat/context', data)

/**
 * 上报页面上下文接口
 * 当用户切换页面或执行重要操作时，上报当前页面上下文信息
 * 智能球可以根据上下文提供更精准的帮助
 * 
 * @param {Object} data - 页面上下文数据
 * @param {string} data.user_id - 用户ID
 * @param {string} data.page - 当前页面名称
 * @param {string} data.title - 页面标题
 * @param {string} data.action - 用户当前行为
 * @param {string} data.detail - 页面细节信息（可选）
 * @returns {Promise} 返回上报结果
 */
export const reportPageContextApi = (data) => requestPythonAll.post('/api/user/context/update', data)

/**
 * 上报资源上下文接口
 * 当用户访问特定学习资源时（如视频、题目、文档），上报资源信息
 * 用于智能球了解用户正在学习的具体内容
 * 
 * @param {Object} data - 资源上下文数据
 * @param {string} data.user_id - 用户ID
 * @param {string} data.resource_type - 资源类型（如 'video', 'question', 'document'）
 * @param {string} data.resource_id - 资源ID
 * @param {string} data.resource_title - 资源标题（可选）
 * @returns {Promise} 返回上报结果
 */
export const reportResourceContextApi = (data) => requestPythonAll.post('/api/user/resource-context', data)

/**
 * 获取用户上下文接口
 * 获取指定用户的历史上下文信息，用于恢复会话或分析用户状态
 * 
 * @param {string} userId - 用户ID
 * @returns {Promise} 返回用户上下文数据
 *   - 历史页面访问记录
 *   - 学习资源访问记录
 *   - 对话历史摘要
 */
export const getUserContextApi = (userId) => requestPythonAll.get(`/api/user/context/${userId}`)


/**
 * 上线主动提醒发送问候
 * 与用户打招呼
 * 
 * @param {string} userId - 用户ID
 * @returns {Promise} 返回问候结果
 */
export const onlineRemindApi = (userId) => request.get(`/aiAnswer/sendGreetings/${userId}`)


//游戏页面接口
//1:喵星叠叠乐
//2:迷宫算法导航
// export const gamePageApi = (page) => requestPythonAll.get(`/game/${page}`)