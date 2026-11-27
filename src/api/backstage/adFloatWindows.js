import { requestPythonAll } from '@/utils/request.js'
// 发送助手消息
export const sendHelperMessage = (message) => {
  return fetch('/py/admin/helper/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
}
// 获取助手问候
export const getHelperGreeting = () => {
  return Promise.resolve({
    data: {
      content: '你好！我是管理助手，可以帮你：\n\n📋 解答操作问题 — 字段含义、功能说明\n📝 执行管理操作 — 增删改题目/视频/知识库\n⚙ 查看和修改权重配置\n📊 查看 Agent 运行状态\n\n直接说你想做什么即可。'
    }
  })
}