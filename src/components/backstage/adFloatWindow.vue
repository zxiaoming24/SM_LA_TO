<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { sendHelperMessage, getHelperGreeting } from '@/api/backstage/adFloatWindows.js'

const router = useRouter()
const route = useRoute()

const visible = ref(false)
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const chatBodyRef = ref(null)
const toggleBtnRef = ref(null)

const addMessage = (type, content, extraClass = '') => {
  // 格式化内容：将换行符转换为 <br>，处理 Markdown 样式
  const formattedContent = content
    .replace(/\n/g, '<br>')  // 换行符转 <br>
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // 粗体 **text**
    .replace(/\*(.*?)\*/g, '<em>$1</em>')  // 斜体 *text*
    .replace(/`(.*?)`/g, '<code>$1</code>')  // 代码 `code`
    .replace(/^- (.*?)/gm, '• $1');  // 列表项 - item
  
  messages.value.push({ type, content: formattedContent, extraClass })
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}

const showLoading = () => {
  messages.value.push({ type: 'assistant', loading: true })
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}

const removeLoading = () => {
  const loadingIndex = messages.value.findIndex(m => m.loading)
  if (loadingIndex > -1) {
    messages.value.splice(loadingIndex, 1)
  }
}

const navigateByTool = (toolName, toolArgs, toolResult) => {
  const normalizeToolName = (name) => {
    let baseName = name.replace(/(Input|Tool)$/, '');
    return baseName.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
  };
  
  const normalizedToolName = normalizeToolName(toolName);

  const toolRouteMap = {
    get_agent_stats: () => '/admin/adAgentDraw',
    get_weight_config: (args) => '/admin/adOpSetting',
    update_weight: (args) => '/admin/adOpSetting',
    list_knowledge_files: () => '/admin/adKnowledge',
    sync_knowledge_base: () => '/admin/adKnowledge',
    delete_knowledge_file: () => '/admin/adKnowledge',
    list_questions: (args) => '/admin/adResource',
    add_question: (args) => '/admin/adResource',
    delete_question: () => '/admin/adResource',
    get_question_detail: () => '/admin/adResource',
    list_videos: () => '/admin/adResource',
    add_video: () => '/admin/adResource',
    delete_video: () => '/admin/adResource',
    get_video_detail: () => '/admin/adResource',
    update_video: () => '/admin/adResource',
    update_question: (args) => {
      return args?.sub_topic ? '/admin/adResource' : '/admin/adResource'
    },
    list_video_files: () => '/admin/adMedia',
    upload_video_file: () => '/admin/adMedia',
    delete_video_file: () => '/admin/adMedia',
    get_global_ranking_weights: () => '/admin/adRank',
    update_global_ranking_weights: () => '/admin/adRank',
    reset_weights: () => '/admin/adOpSetting'
  }

  const getRoute = toolRouteMap[normalizedToolName]
  if (!getRoute) return

  const targetRoute = typeof getRoute === 'function' ? getRoute(toolArgs) : getRoute
  if (targetRoute) {
    router.push({ 
      path: targetRoute, 
      query: { 
        tool: normalizedToolName, 
        args: toolArgs ? JSON.stringify(toolArgs) : undefined,
        result: toolResult ? JSON.stringify(toolResult) : undefined
      } 
    })
  }
}

const handleSend = async () => {
  const msg = inputMessage.value.trim()
  if (!msg || isLoading.value) return

  inputMessage.value = ''
  addMessage('user', msg)
  isLoading.value = true
  showLoading()

  try {
    const response = await sendHelperMessage(msg)

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') continue

        try {
          const event = JSON.parse(data)
          removeLoading()

          if (event.type === 'thinking' || event.type === 'answer') {
            addMessage('assistant', event.content)
          } else if (event.type === 'tool_call') {
            console.log('[DEBUG] Received tool_call:', event)
          } else if (event.type === 'tool_result') {
            console.log('[DEBUG] Received tool_result:', event)
            navigateByTool(event.tool, event.args, event.result)
          } else if (event.type === 'error') {
            addMessage('assistant', `错误: ${event.content}`, 'error')
          }
        } catch (e) { /* ignore parse errors */ }
      }
    }
    removeLoading()
  } catch (e) {
    removeLoading()
    addMessage('assistant', `连接失败: ${e.message}`, 'error')
  } finally {
    isLoading.value = false
  }
}

const togglePanel = () => {
  visible.value = !visible.value
  if (visible.value && messages.value.length === 0) {
    loadGreeting()
  }
}

// 展开面板（供外部调用）
const expandPanel = () => {
  if (!visible.value) {
    visible.value = true
    if (messages.value.length === 0) {
      loadGreeting()
    }
  }
}

defineExpose({
  expandPanel,
  getTargetElement: () => toggleBtnRef.value
})

const loadGreeting = async () => {
  try {
    const response = await getHelperGreeting()
    if (response.data && response.data.content) {
      // 将换行符替换为 <br> 标签以便在 HTML 中显示
      const formattedContent = response.data.content.replace(/\n/g, '<br>')
      addMessage('assistant', formattedContent)
    } else {
      addMessage('assistant', '你好！我是管理助手，可以帮你管理资源、查看权重配置、管理知识库等。')
    }
  } catch (e) {
    addMessage('assistant', '你好！我是管理助手，可以帮你管理资源、查看权重配置、管理知识库等。')
  }
}

onMounted(() => {
})
</script>

<template>
  <div class="float-chat-wrapper" :class="{ collapsed: !visible }">
    <!-- 展开/折叠按钮（左侧） -->
    <button ref="toggleBtnRef" class="toggle-btn" @click.stop="togglePanel" :title="visible ? '折叠' : '展开'">
      {{ visible ? '▶' : '◀' }}
    </button>

    <!-- 主面板 -->
    <div class="float-window">
      <div class="window-header">
        <div class="title">
          <span class="icon-only">🤖</span>
          <span>智能管理助手</span>
        </div>
      </div>
      
      <div class="window-body">
        <div class="chat-body" ref="chatBodyRef">
          <div 
            v-for="(msg, index) in messages" 
            :key="index" 
            class="chat-message"
            :class="[msg.type, msg.extraClass]"
          >
            <div v-if="msg.loading" class="loading-indicator">
              <span></span><span></span><span></span>
            </div>
            <div v-else class="message-bubble" v-html="msg.content"></div>
          </div>
        </div>

        <div class="chat-footer">
          <input 
            v-model="inputMessage" 
            type="text" 
            placeholder="输入指令或问题..." 
            @keydown.enter="handleSend"
            :disabled="isLoading"
          >
          <button class="send-btn" @click="handleSend" :disabled="!inputMessage.trim() || isLoading">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 2L11 13"/>
              <path d="M22 2L15 22L11 13L2 9L22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ========== 右侧悬浮窗口 ========== */
.float-chat-wrapper {
  position: fixed;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 99;
  display: flex;
  align-items: center;
  transition: top 0.3s ease;
}

.float-window {
  width: 520px;
  max-width: calc(100vw - 20px);
  min-height: 600px;
  max-height: 700px;
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 20px 0 0 20px;
  box-shadow: 0 16px 48px rgba(0, 20, 40, 0.18), -4px 0 12px rgba(0, 0, 0, 0.04);
  border: 1px solid var(--border-color);
  border-right: none;
  user-select: none;
  transition: all 0.35s cubic-bezier(0.34, 1.2, 0.64, 1);
  overflow: hidden;
  opacity: 1;
  transform: translateX(0);
  display: flex;
  flex-direction: column;
}

.float-chat-wrapper.collapsed .float-window {
  max-height: 0 !important;
  opacity: 0;
  padding: 0;
  width: 0;
  border: none;
  box-shadow: none;
  transform: translateX(20px);
  pointer-events: none;
}

/* ===== 折叠/展开按钮（左侧） ===== */
.toggle-btn {
  width: 44px;
  height: 56px;
  border-radius: 14px 0 0 14px;
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border-color);
  border-right: none;
  box-shadow: -4px 0 16px rgba(0, 20, 40, 0.10), 0 4px 12px rgba(0, 0, 0, 0.04);
  color: var(--text-body);
  font-size: 1.2rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.34, 1.2, 0.64, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  user-select: none;
  position: relative;
  z-index: 99;
}

.float-chat-wrapper:not(.collapsed) .toggle-btn {
  border-radius: 14px 0 0 14px;
  box-shadow: -4px 0 16px rgba(0, 20, 40, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
  margin-left: 0;
}

.float-chat-wrapper.collapsed .toggle-btn {
  border-radius: 16px 0 0 16px;
  box-shadow: -4px 0 20px rgba(0, 20, 40, 0.15), 0 4px 12px rgba(0, 0, 0, 0.06);
  width: 48px;
  height: 64px;
  font-size: 1.4rem;
}

.toggle-btn:hover {
  background: var(--bg-card);
  box-shadow: -4px 0 24px rgba(0, 20, 40, 0.20);
  transform: scale(1.02);
}

.toggle-btn:active {
  transform: scale(0.95);
}

/* ===== 窗口头部 ===== */
.window-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-body);
}

.icon-only {
  color: var(--primary);
  font-size: 16px;
}

/* ===== 窗口主体 ===== */
.window-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-page);
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: var(--bg-page);
}

.chat-message {
  display: flex;
  margin-bottom: 10px;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 95%;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
}

.user .message-bubble {
  background: var(--primary);
  color: #fff;
  border-radius: var(--radius-md) 0 var(--radius-md) var(--radius-md);
}

.assistant .message-bubble {
  background: var(--bg-card);
  color: var(--text-body);
  border: 1px solid var(--border-color);
  border-radius: 0 var(--radius-md) var(--radius-md) var(--radius-md);
}

.assistant.error .message-bubble {
  background: var(--main-fail-status);
  color: var(--main-delete);
  border-color: var(--main-shadow);
}

.loading-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
}

.loading-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-gray);
  animation: loading-dots 1.4s infinite ease-in-out;
}

.loading-indicator span:nth-child(1) { animation-delay: 0s; }
.loading-indicator span:nth-child(2) { animation-delay: 0.2s; }
.loading-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes loading-dots {
  0%, 80%, 100% { opacity: 0.4; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.chat-footer {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}

.chat-footer input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.chat-footer input:focus {
  border-color: var(--primary);
}

.chat-footer input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hv);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}
</style>