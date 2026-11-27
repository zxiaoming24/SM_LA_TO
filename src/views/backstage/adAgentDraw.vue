<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgentStats, getAgentHistory, resetAgentStats } from '@/api/backstage/adAgentDraw.js'

const agentStats = ref({})
const agentHistory = ref([])
const totalCalls = ref(0)
const liveCount = ref(0)
const loading = ref(true)
const showRanking = ref(false)

let refreshInterval = null

const route = useRoute()

const groupedAgents = computed(() => {
  const ranking = agentStats.value.ranking || []
  const groups = {}
  ranking.forEach(agent => {
    const group = agent.group || '未分类'
    if (!groups[group]) {
      groups[group] = []
    }
    groups[group].push(agent)
  })
  return groups
})

const agentNameMap = {
  'SuperAgent': '超级智能体',
  'PracticeAgent': '编程题智能体',
  'QuestionGeneratorAgent': '试卷理论题智能体',
  'CourseDocAgent': '讲解文档智能体',
  'ExtensionReadingAgent': '拓展阅读智能体',
  'VideoSearchAgent': '视频搜索智能体',
  'MindMapAgent': '思维导图智能体',
  'PPTCreationAgent': 'PPT生成智能体',
  'AnimationAgent': '动画智能体',
  'StudyPlanAgent': '学习计划智能体',
  'WrongAnswerService': '错题服务智能体',
  'ChatAgent': '对话智能体',
  'KnowledgeBaseAgent': '知识库智能体',
  'MainAgent(DES)': '用户处理智能体',
  'JudgeAgent': '代码评估智能体'
}

const agentDetailMap = {
  'SuperAgent': {
    file: 'super_agent.py',
    desc: '超级智能体(ReAct) — 自主分析复杂问题并调度子Agent',
    badges: ['复合任务', '调度'],
    store: '无存储（动态调用子Agent）',
    detail: '基于 LangGraph ReAct 模式的超级智能体，自主分析复杂/复合学习问题，拆解为多步计划，动态调用子Agent工具（练习/视频/文档等），支持顺序和并行执行，思维链可见。'
  },
  'PracticeAgent': {
    file: 'practice_agent.py',
    desc: '生成编程练习题，支持代码评判和算法可视化',
    badges: ['编程题', '评判', '可视化'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '根据知识点和难度生成个性化编程练习题。支持代码提交评判、测试用例验证、多维度评分。可生成算法可视化 HTML。'
  },
  'QuestionGeneratorAgent': {
    file: 'question_generator_agent.py',
    desc: '生成 5 类理论题：单选、多选、判断、填空、简答',
    badges: ['理论题', '5种题型'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '针对知识点生成个性化理论题，自动判题（精确匹配），答题后更新用户特征画像，答错自动记入错题本。'
  },
  'CourseDocAgent': {
    file: 'course_doc_agent_ali.py',
    desc: '生成结构化 Word 课程讲解文档',
    badges: ['文档', 'Word'],
    store: 'ResourceDB + SemanticStore + OSS + 文件系统',
    detail: '基于课程名称生成完整课程文档，包含知识点讲解、案例分析和总结。支持 OSS 上传和本地文件导出。'
  },
  'ExtensionReadingAgent': {
    file: 'extension_reading_agent.py',
    desc: '生成个性化拓展阅读材料，含 6 大板块',
    badges: ['拓展阅读', '个性化'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '围绕知识点生成背景溯源、易混淆辨析、底层原理、避坑建议、应用场景、个性化建议六个板块的拓展阅读。'
  },
  'VideoSearchAgent': {
    file: 'video_search_agent.py',
    desc: '搜索 B 站教学视频并自动入库',
    badges: ['视频', 'B站'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '根据知识点在 Bilibili 搜索相关教学视频，按质量评分排序，自动将搜索结果（标题/链接/时长/UP主）入库供推荐系统使用。'
  },
  'MindMapAgent': {
    file: 'mindmap_agent.py',
    desc: '生成层级化知识点思维导图',
    badges: ['思维导图', 'JSON'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '围绕核心知识点生成多级思维导图 JSON，包含主题关联和层级关系，帮助学生建立知识体系。'
  },
  'PPTCreationAgent': {
    file: 'ppt_agent.py',
    desc: '6 步流水线生成 PPT 课件',
    badges: ['PPT', '课件'],
    store: 'ResourceDB + SemanticStore + OSS + 文件系统',
    detail: '包含大纲生成、配色设计、图片描述、背景图生成、视频嵌入、PPTX 合成 6 个步骤，自动设计配色方案和背景图。'
  },
  'AnimationAgent': {
    file: 'wx_html_create.py',
    desc: '生成带动画效果的教育 HTML 内容',
    badges: ['动画', 'HTML'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '针对知识点生成交互式动画 HTML 页面，支持 TTS 语音讲解，视觉效果丰富。'
  },
  'StudyPlanAgent': {
    file: 'study_plan_agent.py',
    desc: '生成分阶段学习计划，支持版本管理',
    badges: ['学习计划', '阶段'],
    store: 'MemoryHub(StudyPlanner)',
    detail: '根据用户画像和目标生成个性化分阶段学习计划，每阶段含知识点、任务和里程碑，支持动态调整和重规划。'
  },
  'WrongAnswerService': {
    file: 'wrong_answer_service.py',
    desc: '分析错题，生成补练习题和推荐资料',
    badges: ['错题', '补练'],
    store: 'ResourceDB + SemanticStore + ContentStore',
    detail: '记录用户错题，分析薄弱知识点，LLM 生成针对性补练习题。提供知识点掌握度分析、学习资料推荐。'
  },
  'ChatAgent': {
    file: 'super_agent_tools.py',
    desc: '日常对话问答 — SuperAgent 内部兜底工具',
    badges: ['问答', '兜底'],
    store: '无存储（LLM 直接回答）',
    detail: 'SuperAgent 调用的通用知识问答工具，当用户问一般性知识问题、概念解释、学习方法建议且不需要专门子Agent时使用。不处理视频/编程题等需要专门工具的任务。'
  },
  'KnowledgeBaseAgent': {
    file: 'knowledge_base_agent.py',
    desc: '知识库检索与问答服务',
    badges: ['知识库', '检索'],
    store: 'ResourceDB + SemanticStore',
    detail: '提供知识库文档检索、语义匹配和问答功能，支持向量检索和关键词匹配。'
  },
  'MainAgent(DES)': {
    file: 'main_agent_des.py',
    desc: '用户请求处理入口智能体',
    badges: ['入口', '路由'],
    store: 'MemoryHub',
    detail: '作为用户请求的统一入口，负责解析意图、路由到对应子Agent，并协调多Agent协作完成复杂任务。'
  },
  'JudgeAgent': {
    file: 'judge_agent.py',
    desc: '代码评估与质量检测',
    badges: ['代码评估', '检测'],
    store: 'ResourceDB',
    detail: '对提交的代码进行静态分析、运行时测试和质量评估，提供代码优化建议。'
  }
}

const getAgentDisplayName = (name) => {
  return agentNameMap[name] || name
}

const getAgentDetail = (name) => {
  return agentDetailMap[name] || {}
}

const getStatusClass = (status) => {
  return status === 'working' ? 'working' : 'idle'
}

const getStatusText = (status) => {
  return status === 'working' ? '工作中' : '休息中'
}

const formatDateTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  const s = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${h}:${min}:${s}`
}

const getRankClass = (index) => {
  if (index === 0) return 'rank-1'
  if (index === 1) return 'rank-2'
  if (index === 2) return 'rank-3'
  return 'rank-other'
}

const getRankText = (index) => {
  return index + 1
}

const loadAgentStats = async () => {
  try {
    const res = await getAgentStats()
    if (res.success) {
      agentStats.value = res.data || {}
      const agents = agentStats.value.ranking || []
      totalCalls.value = agents.reduce((sum, a) => sum + (a.call_count || 0), 0)
      liveCount.value = agents.filter(a => a.status === 'working').length
    }
    loading.value = false
  } catch (e) {
    loading.value = false
    console.error('加载Agent统计失败', e)
  }
}

const loadAgentHistory = async () => {
  try {
    const res = await getAgentHistory()
    if (res.success) {
      agentHistory.value = res.data || []
    }
  } catch (e) {
    console.error('加载Agent历史失败', e)
  }
}

const handleResetStats = async () => {
  try {
    await ElMessageBox.confirm('确定要重置Agent统计数据吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await resetAgentStats()
    if (res.success) {
      ElMessage.success(res.message || '重置成功')
      loadAgentStats()
      loadAgentHistory()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重置失败')
    }
  }
}

const toggleRanking = () => {
  showRanking.value = !showRanking.value
  if (showRanking.value) {
    loadAgentHistory()
  }
}

const processToolParams = async () => {
  const tool = route.query.tool
  if (!tool) {
    loadAgentStats()
    if (!refreshInterval) {
      refreshInterval = setInterval(loadAgentStats, 5000)
    }
    return
  }

  switch (tool) {
    case 'get_agent_stats': {
      loadAgentStats()
      if (!refreshInterval) {
        refreshInterval = setInterval(loadAgentStats, 5000)
      }
      break
    }
    default:
      loadAgentStats()
      if (!refreshInterval) {
        refreshInterval = setInterval(loadAgentStats, 5000)
      }
      break
  }
}

onMounted(() => {
  processToolParams()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

watch(() => route.query, () => {
  processToolParams()
}, { deep: true })
</script>

<template>
  <div class="container">
    <div class="header-section">
      <div class="stats-cards">
        <div class="stat-card">
          <div class="stat-icon agents">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ (agentStats.ranking || []).length }}</div>
            <div class="stat-label">Agent总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon working">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ liveCount }}</div>
            <div class="stat-label">工作中</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon calls">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ totalCalls }}</div>
            <div class="stat-label">总调用次数</div>
          </div>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <span class="description">系统中负责资源生成的AI Agent一览，鼠标悬浮查看详情</span>
      <el-button type="primary" @click="loadAgentStats">刷新</el-button>
      <span class="status-legend">
        <span class="legend-item">
          <span class="status-dot working"></span>
          <span>工作中</span>
        </span>
        <span class="legend-item">
          <span class="status-dot idle"></span>
          <span>休息中</span>
        </span>
      </span>
      <span class="live-count">{{ liveCount }} 个工作中</span>
    </div>

    <div class="main-content">
      <div class="agent-grid-container">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <div class="loading-text">加载中...</div>
        </div>

        <div v-else class="agent-grid">
          <div v-for="(groupAgents, groupName) in groupedAgents" :key="groupName" class="agent-group">
            <div class="group-header">{{ groupName }}</div>
            <div class="group-grid">
              <div v-for="agent in groupAgents" :key="agent.agent_key" class="agent-item">
                <div class="agent-icon" :class="getStatusClass(agent.status)">
                  {{ agent.icon || '🤖' }}
                  <span v-if="agent.status === 'working'" class="pulse-dot"></span>
                </div>
                <div class="agent-name">{{ getAgentDisplayName(agent.name) }}</div>
                <div class="agent-status" :class="getStatusClass(agent.status)">
                  {{ getStatusText(agent.status) }}
                </div>

                <div class="agent-tooltip">
                  <div class="at-icon">{{ agent.icon || '🤖' }}</div>
                  <div class="at-name">{{ getAgentDisplayName(agent.name) }}</div>
                  <div class="at-file">{{ getAgentDetail(agent.name).file || agent.agent_key }}</div>
                  <div class="at-badges">
                    <span v-for="badge in getAgentDetail(agent.name).badges || []" :key="badge" class="at-badge">{{ badge }}</span>
                    <span v-if="getAgentDetail(agent.name).store && getAgentDetail(agent.name).store.includes('ResourceDB')" class="at-badge db">DB</span>
                    <span v-if="agent.status === 'working'" class="at-badge db">工作中</span>
                  </div>
                  <div class="at-desc">{{ getAgentDetail(agent.name).desc || agent.desc || '' }}</div>
                  <div class="at-detail">
                    <div>📦 {{ getAgentDetail(agent.name).store || '未知存储' }}</div>
                    <div>{{ getAgentDetail(agent.name).detail || '' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!agentStats.ranking || agentStats.ranking.length === 0" class="empty-state">
            <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <div class="empty-text">暂无Agent</div>
          </div>
        </div>
      </div>

      <div class="ranking-section">
        <div class="ranking-header">
          <span class="ranking-icon">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 10h-14"/>
              <path d="M6 16h12"/>
              <path d="M16 10h6"/>
              <path d="M2 10h6"/>
              <path d="M14 16h6"/>
              <path d="M2 16h6"/>
            </svg>
          </span>
          <span class="ranking-title">Agent调用排行</span>
        </div>

        <div class="ranking-content">
          <div class="ranking-summary">
            <span class="summary-item">总调用:  <strong>{{ totalCalls }}</strong></span>
            <span class="summary-item">排行根据调用次数降序</span>
            <el-button type="danger" size="small" @click="handleResetStats">重置统计</el-button>
          </div>

          <div class="ranking-table-container">
            <table class="ranking-table">
              <thead>
                <tr>
                  <th width="35">排名</th>
                  <th width="35"></th>
                  <th>Agent</th>
                  <th width="80">状态</th>
                  <th width="60">调用</th>
                  <th width="75">平均耗时</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(agent, index) in ((agentStats.ranking || []).sort((a, b) => (b.call_count || 0) - (a.call_count || 0)))" :key="agent.agent_key">
                  <td align="center">
                    <span class="rank-badge" :class="getRankClass(index)">
                      {{ getRankText(index) }}
                    </span>
                  </td>
                  <td align="center">
                    <span class="ranking-icon-emoji">{{ agent.icon || '🤖' }}</span>
                  </td>
                  <td>
                    <strong>{{ getAgentDisplayName(agent.name) }}</strong>
                    <div class="ranking-desc">{{ getAgentDetail(agent.name).desc || agent.desc || '' }}</div>
                  </td>
                  <td align="center">
                    <span class="agent-status-dot" :class="getStatusClass(agent.status)"></span>
                    {{ getStatusText(agent.status) }}
                  </td>
                  <td align="center"><strong>{{ agent.call_count || 0 }}</strong></td>
                  <td align="center">{{ agent.avg_duration > 0 ? agent.avg_duration + 's' : '--' }}</td>
                </tr>
                <tr v-if="!agentStats.ranking || agentStats.ranking.length === 0">
                  <td colspan="6" align="center">暂无数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  padding: 20px;
  min-height: 100%;
  background-color: var(--bg-page);
}

.header-section {
  margin-bottom: 20px;
}

.stats-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-normal);
  min-width: 200px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--primary-light);
  border-radius: var(--radius-md);
  color: var(--primary);
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 12px 16px;
  background-color: var(--bg-card);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}

.main-content {
  display: flex;
  gap: 10px;
  align-items: stretch;
  height: 630px;
}

.agent-grid-container {
  flex: 1;
  min-width: 772px;
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-normal);
  padding: 16px;
  height: 100%;
  /* overflow: hidden; */
}

.description {
  font-size: 13px;
  color: var(--text-gray);
}

.status-legend {
  display: flex;
  gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-gray);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot.working {
  background-color: var(--pass);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.status-dot.idle {
  background-color: #94A3B8;
}

@keyframes pulse-dot {
  0%, 100% {
    opacity: 1;
    box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4);
  }
  50% {
    opacity: 0.7;
    box-shadow: 0 0 0 6px rgba(103, 194, 58, 0);
  }
}

.live-count {
  margin-left: auto;
  font-size: 13px;
  color: var(--primary);
  font-weight: 500;
}

.agent-grid-container {
  background-color: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-normal);
  min-height: 140px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 8px;
}

.agent-grid {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.agent-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  padding-left: 10px;
  border-left: 3px solid var(--primary);
}

.group-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 5px;
  padding-left: 8px;
}

.agent-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
}

.agent-icon {
  width: 70px;
  height: 70px;
  border-radius: 20px;
  background-color: var(--bg-page);
  border: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-gray);
  position: relative;
  transition: all 0.25s ease;
  font-size: 36px;
}

.agent-icon:hover {
  border-color: var(--primary);
  background-color: var(--primary-light);
  color: var(--primary);
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.2);
}

.agent-icon.working {
  border-color: var(--pass);
  background-color: var(--pass-bg-color);
  color: var(--pass);
}

.agent-icon.working:hover {
  border-color: var(--pass);
  background-color: var(--pass-bg-color);
  color: var(--pass);
}

.pulse-dot {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--pass);
  bottom: 4px;
  right: 4px;
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.agent-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.agent-status-dot.idle {
  background-color: #BDC3C7;
}

.agent-status-dot.working {
  background-color: var(--pass);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

.agent-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-title);
  margin-top: 8px;
  text-align: center;
  max-width: 100px;
  word-break: break-all;
  line-height: 1.4;
}

.agent-status {
  font-size: 11px;
  margin-top: 2px;
}

.agent-status.working {
  color: var(--pass);
}

.agent-status.idle {
  color: #94A3B8;
}

.agent-tooltip {
  position: absolute;
  left: 94px;
  top: 50%;
  transform: translateY(-50%);
  background-color: #fff;
  border: 1px solid #e0e4f0;
  border-radius: 12px;
  padding: 14px 16px;
  width: 300px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: all 0.2s ease;
}

.agent-item:hover .agent-tooltip {
  opacity: 1;
  pointer-events: auto;
}

.at-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.at-name {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.at-file {
  font-size: 10px;
  color: #bbb;
  font-family: monospace;
  margin-bottom: 4px;
}

.at-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin: 6px 0;
}

.at-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f2ff;
  color: #667eea;
}

.at-badge.db {
  background: #e8f5e9;
  color: #2e7d32;
}

.at-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 6px;
}

.at-detail {
  font-size: 11px;
  color: #999;
  border-top: 1px dashed #eee;
  padding-top: 6px;
}

.detail-label {
  color: #94A3B8;
}

.detail-value {
  color: var(--text-title);
  font-weight: 500;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--text-gray);
}

.empty-text {
  font-size: 14px;
  margin-top: 12px;
}

.ranking-section {
  width: 600px;
  height: 100%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-normal);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.ranking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  cursor: pointer;
  background: var(--primary);
  transition: all 0.2s;
}

.ranking-header:hover {
  background: rgba(45, 125, 219, 0.9);
}

.ranking-icon {
  color: #fff;
}

.ranking-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.ranking-arrow {
  margin-left: auto;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.8);
  transition: transform 0.2s;
}

.ranking-arrow.expanded {
  transform: rotate(180deg);
}

.ranking-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.ranking-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.summary-item {
  font-size: 12px;
  color: #94A3B8;
}

.summary-item strong {
  color: var(--text-title);
}

.ranking-table-container {
  overflow-x: auto;
}

.ranking-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.ranking-table th {
  background-color: transparent;
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-gray);
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
  font-size: 12px;
}

.ranking-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  vertical-align: middle;
}

.ranking-table tr:hover td {
  background-color: rgba(45, 125, 219, 0.08);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}

.rank-1 {
  background: linear-gradient(135deg, #F1C40F, #F39C12);
  color: #fff;
  box-shadow: 0 2px 8px rgba(241, 196, 15, 0.4);
}

.rank-2 {
  background: linear-gradient(135deg, #BDC3C7, #95A5A6);
  color: #fff;
  box-shadow: 0 2px 8px rgba(189, 195, 199, 0.4);
}

.rank-3 {
  background: linear-gradient(135deg, #E67E22, #D35400);
  color: #fff;
  box-shadow: 0 2px 8px rgba(230, 126, 34, 0.4);
}

.rank-other {
  background-color: #F5F5F5;
  color: #94A3B8;
}

.ranking-icon-emoji {
  font-size: 18px;
  margin-right: 8px;
  vertical-align: middle;
}

.ranking-desc {
  font-size: 10px;
  color: #999;
  margin-top: 2px;
}
</style>