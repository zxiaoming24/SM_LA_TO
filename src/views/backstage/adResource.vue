<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getTheoryQuestions, getPracticeQuestions, getVideos,
  getQuestionTopics, getVideoTopics,
  getTheoryQuestionStats, getPracticeQuestionStats, getVideoStats,
  createTheoryQuestion, updateTheoryQuestion, deleteTheoryQuestion as apiDeleteTheoryQuestion,
  createPracticeQuestion, updatePracticeQuestion, deletePracticeQuestion as apiDeletePracticeQuestion,
  createVideo, updateVideo, deleteVideo as apiDeleteVideo,
  getQuestionDetail, getVideoDetail
} from '@/api/backstage/adResource'

// ==================== 状态 ====================

const activeTab = ref('theory')
const tabs = [
  {
    key: 'theory', label: '理论题',
    icon: { viewBox: '0 0 24 24', path: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z' }
  },
  {
    key: 'practice', label: '编程题',
    icon: { viewBox: '0 0 24 24', path: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM6 20V4h7v5h5v11H6z' }
  },
  {
    key: 'videos', label: '视频',
    icon: { viewBox: '0 0 24 24', path: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zm-9 2.28l-5-2.88V9.6l5 2.88v6.88z' }
  }
]

// 列表数据
const theoryTopics = ref([])
const practiceTopics = ref([])
const videoTopics = ref([])
const theoryQuestions = ref([])
const practiceQuestions = ref([])
const videos = ref([])

// 加载状态
const theoryLoading = ref(false)
const practiceLoading = ref(false)
const videoLoading = ref(false)

// 分页
const theoryPage = reactive({ page: 1, pageSize: 20, total: 0 })
const practicePage = reactive({ page: 1, pageSize: 20, total: 0 })
const videoPage = reactive({ page: 1, pageSize: 20, total: 0 })

// 搜索条件
const theorySearch = reactive({ keyword: '', topic: '', difficulty: '' })
const practiceSearch = reactive({ keyword: '', topic: '', difficulty: '' })
const videoSearch = reactive({ keyword: '', topic: '', platform: '', difficulty: '' })

// 统计
const theoryStats = reactive({ total: 0 })
const practiceStats = reactive({ total: 0 })
const videoStats = reactive({ total: 0 })

// 理论题弹窗
const theoryDialogVisible = ref(false)
const theoryDialogTitle = ref('新增理论题')
const theoryForm = reactive({
  id: '',
  title: '',
  topic: '',
  sub_topic: '',
  difficulty: 3,
  knowledge_points_str: '',
  content: '',
  solution: '',
  hints: '',
  options_str: ''
})

// 编程题弹窗
const practiceDialogVisible = ref(false)
const practiceDialogTitle = ref('新增编程题')
const practiceForm = reactive({
  id: '',
  title: '',
  topic: '',
  sub_topic: '',
  difficulty: 3,
  knowledge_points_str: '',
  content: '',
  solution: '',
  hints: ''
})

// 视频弹窗
const videoDialogVisible = ref(false)
const videoDialogTitle = ref('新增视频')
const videoForm = reactive({
  id: '',
  platform: '',
  title: '',
  topic: '',
  difficulty: 3,
  duration_sec: 0,
  url: '',
  knowledge_points_str: ''
})

const route = useRoute()

// ==================== 工具函数 ====================

const parseKnowledgePoints = (kp) => {
  if (Array.isArray(kp)) return kp
  if (typeof kp === 'string' && kp) return kp.split(',').map(s => s.trim()).filter(Boolean)
  return []
}

const getDifficultyLabel = (level) => {
  const labels = { 1: '简单', 2: '较易', 3: '中等', 4: '较难', 5: '困难' }
  return labels[level] || '未知'
}

const questionType = (type) => {
  const map = {
    fill_blank: '填空题',
    programming: '编程题',
    single_choice: '单选题',
    multiple_choice: '多选题',
    judge: '判断题',
    short_answer: '简答题'
  }
  return map[type] || '未知题型'
}

const formatDuration = (seconds) => {
  if (!seconds || seconds <= 0) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

// ==================== 标签页 ====================

const switchTab = (key) => {
  activeTab.value = key
  if (key === 'theory' && theoryQuestions.value.length === 0) loadTheoryQuestions()
  else if (key === 'practice' && practiceQuestions.value.length === 0) loadPracticeQuestions()
  else if (key === 'videos' && videos.value.length === 0) loadVideos()
}

const getTabCount = (key) => {
  if (key === 'theory') return theoryStats.total
  if (key === 'practice') return practiceStats.total
  if (key === 'videos') return videoStats.total
  return 0
}

// ==================== 数据加载 ====================

const loadTheoryQuestions = async () => {
  theoryLoading.value = true
  try {
    const params = {
      page: theoryPage.page,
      page_size: theoryPage.pageSize,
      keyword: theorySearch.keyword || undefined,
      topic: theorySearch.topic || undefined,
      difficulty: theorySearch.difficulty || undefined
    }
    const res = await getTheoryQuestions(params)
    if (res.success) {
      theoryQuestions.value = res.items || []
      theoryPage.total = res.total || 0
    }
  } catch (error) {
    console.error('加载理论题失败:', error)
  } finally {
    theoryLoading.value = false
  }
}

const loadPracticeQuestions = async () => {
  practiceLoading.value = true
  try {
    const params = {
      page: practicePage.page,
      page_size: practicePage.pageSize,
      keyword: practiceSearch.keyword || undefined,
      topic: practiceSearch.topic || undefined,
      difficulty: practiceSearch.difficulty || undefined
    }
    const res = await getPracticeQuestions(params)
    if (res.success) {
      practiceQuestions.value = res.items || []
      practicePage.total = res.total || 0
    }
  } catch (error) {
    console.error('加载编程题失败:', error)
  } finally {
    practiceLoading.value = false
  }
}

const loadVideos = async () => {
  videoLoading.value = true
  try {
    const params = {
      page: videoPage.page,
      page_size: videoPage.pageSize,
      keyword: videoSearch.keyword || undefined,
      topic: videoSearch.topic || undefined,
      platform: videoSearch.platform || undefined,
      difficulty: videoSearch.difficulty || undefined
    }
    const res = await getVideos(params)
    if (res.success) {
      videos.value = res.items || []
      videoPage.total = res.total || 0
    }
  } catch (error) {
    console.error('加载视频失败:', error)
  } finally {
    videoLoading.value = false
  }
}

// ==================== 搜索重置 ====================

const resetTheorySearch = () => {
  theorySearch.keyword = ''
  theorySearch.topic = ''
  theorySearch.difficulty = ''
  theoryPage.page = 1
  loadTheoryQuestions()
}

const resetPracticeSearch = () => {
  practiceSearch.keyword = ''
  practiceSearch.topic = ''
  practiceSearch.difficulty = ''
  practicePage.page = 1
  loadPracticeQuestions()
}

const resetVideoSearch = () => {
  videoSearch.keyword = ''
  videoSearch.topic = ''
  videoSearch.platform = ''
  videoSearch.difficulty = ''
  videoPage.page = 1
  loadVideos()
}

// ==================== 理论题 CRUD ====================

const openTheoryDialog = () => {
  theoryDialogTitle.value = '新增理论题'
  resetTheoryForm()
  theoryDialogVisible.value = true
}

const resetTheoryForm = () => {
  theoryForm.id = ''
  theoryForm.title = ''
  theoryForm.topic = ''
  theoryForm.sub_topic = ''
  theoryForm.difficulty = 3
  theoryForm.knowledge_points_str = ''
  theoryForm.content = ''
  theoryForm.solution = ''
  theoryForm.hints = ''
  theoryForm.options_str = ''
}

const editTheoryQuestion = async (row) => {
  theoryDialogTitle.value = '编辑理论题'
  resetTheoryForm()
  try {
    const res = await getQuestionDetail(row.id)
    if (res.success) {
      const data = res.data
      theoryForm.id = data.id
      theoryForm.title = data.title || ''
      theoryForm.topic = data.topic || ''
      theoryForm.sub_topic = data.sub_topic || ''
      theoryForm.difficulty = data.difficulty || 3
      theoryForm.knowledge_points_str = parseKnowledgePoints(data.knowledge_points).join(',')
      theoryForm.content = data.content || ''
      theoryForm.solution = data.solution || ''
      theoryForm.hints = Array.isArray(data.hints) ? data.hints.join('\n') : (data.hints || '')
      theoryForm.options_str = data.options ? JSON.stringify(data.options) : ''
    }
  } catch (error) {
    console.error('获取题目详情失败:', error)
  }
  theoryDialogVisible.value = true
}

const saveTheoryQuestion = async () => {
  if (!theoryForm.title || !theoryForm.topic || !theoryForm.content) {
    ElMessage.warning('请填写必填字段')
    return
  }
  const data = {
    title: theoryForm.title,
    topic: theoryForm.topic,
    sub_topic: theoryForm.sub_topic || '',
    difficulty: theoryForm.difficulty,
    knowledge_points: theoryForm.knowledge_points_str
      ? theoryForm.knowledge_points_str.split(',').map(s => s.trim()).filter(Boolean)
      : [],
    content: theoryForm.content,
    solution: theoryForm.solution || '',
    hints: theoryForm.hints ? theoryForm.hints.split('\n').map(s => s.trim()).filter(Boolean) : [],
    metadata: { question_type: 'theory' }
  }
  if (theoryForm.options_str) {
    try {
      data.options = JSON.parse(theoryForm.options_str)
    } catch (e) {
      ElMessage.error('选项格式不正确')
      return
    }
  }
  try {
    let res
    if (theoryForm.id) {
      res = await updateTheoryQuestion(theoryForm.id, data)
    } else {
      res = await createTheoryQuestion(data)
    }
    if (res.success) {
      ElMessage.success(theoryForm.id ? '更新成功' : '创建成功')
      theoryDialogVisible.value = false
      loadTheoryQuestions()
      loadStats()
    }
  } catch (error) {
    console.error('保存理论题失败:', error)
    ElMessage.error('保存失败')
  }
}

const deleteTheoryQuestion = (row) => {
  ElMessageBox.confirm('确定要删除该题目吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await apiDeleteTheoryQuestion(row.id)
      if (res.success) {
        ElMessage.success('删除成功')
        loadTheoryQuestions()
        loadStats()
      }
    } catch (error) {
      console.error('删除理论题失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 编程题 CRUD ====================

const openPracticeDialog = () => {
  practiceDialogTitle.value = '新增编程题'
  resetPracticeForm()
  practiceDialogVisible.value = true
}

const resetPracticeForm = () => {
  practiceForm.id = ''
  practiceForm.title = ''
  practiceForm.topic = ''
  practiceForm.sub_topic = ''
  practiceForm.difficulty = 3
  practiceForm.knowledge_points_str = ''
  practiceForm.content = ''
  practiceForm.solution = ''
  practiceForm.hints = ''
}

const editPracticeQuestion = async (row) => {
  practiceDialogTitle.value = '编辑编程题'
  resetPracticeForm()
  try {
    const res = await getQuestionDetail(row.id)
    if (res.success) {
      const data = res.data
      practiceForm.id = data.id
      practiceForm.title = data.title || ''
      practiceForm.topic = data.topic || ''
      practiceForm.sub_topic = data.sub_topic || ''
      practiceForm.difficulty = data.difficulty || 3
      practiceForm.knowledge_points_str = parseKnowledgePoints(data.knowledge_points).join(',')
      practiceForm.content = data.content || ''
      practiceForm.solution = data.solution || ''
      practiceForm.hints = Array.isArray(data.hints) ? data.hints.join('\n') : (data.hints || '')
    }
  } catch (error) {
    console.error('获取题目详情失败:', error)
  }
  practiceDialogVisible.value = true
}

const savePracticeQuestion = async () => {
  if (!practiceForm.title || !practiceForm.topic || !practiceForm.content) {
    ElMessage.warning('请填写必填字段')
    return
  }
  const data = {
    title: practiceForm.title,
    topic: practiceForm.topic,
    sub_topic: practiceForm.sub_topic || '',
    difficulty: practiceForm.difficulty,
    knowledge_points: practiceForm.knowledge_points_str
      ? practiceForm.knowledge_points_str.split(',').map(s => s.trim()).filter(Boolean)
      : [],
    content: practiceForm.content,
    solution: practiceForm.solution || '',
    hints: practiceForm.hints ? practiceForm.hints.split('\n').map(s => s.trim()).filter(Boolean) : [],
    metadata: { question_type: 'practice' }
  }
  try {
    let res
    if (practiceForm.id) {
      res = await updatePracticeQuestion(practiceForm.id, data)
    } else {
      res = await createPracticeQuestion(data)
    }
    if (res.success) {
      ElMessage.success(practiceForm.id ? '更新成功' : '创建成功')
      practiceDialogVisible.value = false
      loadPracticeQuestions()
      loadStats()
    }
  } catch (error) {
    console.error('保存编程题失败:', error)
    ElMessage.error('保存失败')
  }
}

const deletePracticeQuestion = (row) => {
  ElMessageBox.confirm('确定要删除该题目吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await apiDeletePracticeQuestion(row.id)
      if (res.success) {
        ElMessage.success('删除成功')
        loadPracticeQuestions()
        loadStats()
      }
    } catch (error) {
      console.error('删除编程题失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 视频 CRUD ====================

const openVideoDialog = () => {
  videoDialogTitle.value = '新增视频'
  resetVideoForm()
  videoDialogVisible.value = true
}

const resetVideoForm = () => {
  videoForm.id = ''
  videoForm.platform = ''
  videoForm.title = ''
  videoForm.topic = ''
  videoForm.difficulty = 3
  videoForm.duration_sec = 0
  videoForm.url = ''
  videoForm.knowledge_points_str = ''
}

const editVideo = async (row) => {
  videoDialogTitle.value = '编辑视频'
  resetVideoForm()
  try {
    const res = await getVideoDetail(row.id)
    if (res.success) {
      const data = res.data
      videoForm.id = data.id
      videoForm.platform = data.platform || ''
      videoForm.title = data.title || ''
      videoForm.topic = data.topic || ''
      videoForm.difficulty = data.difficulty || 3
      videoForm.duration_sec = data.duration_sec || 0
      videoForm.url = data.url || ''
      videoForm.knowledge_points_str = parseKnowledgePoints(data.knowledge_points).join(',')
    }
  } catch (error) {
    console.error('获取视频详情失败:', error)
  }
  videoDialogVisible.value = true
}

const saveVideo = async () => {
  if (!videoForm.platform || !videoForm.title) {
    ElMessage.warning('请填写必填字段')
    return
  }
  const data = {
    platform: videoForm.platform,
    title: videoForm.title,
    topic: videoForm.topic || '',
    difficulty: videoForm.difficulty,
    duration_sec: videoForm.duration_sec || 0,
    url: videoForm.url || '',
    knowledge_points: videoForm.knowledge_points_str
      ? videoForm.knowledge_points_str.split(',').map(s => s.trim()).filter(Boolean)
      : []
  }
  try {
    let res
    if (videoForm.id) {
      res = await updateVideo(videoForm.id, data)
    } else {
      res = await createVideo(data)
    }
    if (res.success) {
      ElMessage.success(videoForm.id ? '更新成功' : '创建成功')
      videoDialogVisible.value = false
      loadVideos()
      loadStats()
    }
  } catch (error) {
    console.error('保存视频失败:', error)
    ElMessage.error('保存失败')
  }
}

const deleteVideo = (row) => {
  ElMessageBox.confirm('确定要删除该视频吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const res = await apiDeleteVideo(row.id)
      if (res.success) {
        ElMessage.success('删除成功')
        loadVideos()
        loadStats()
      }
    } catch (error) {
      console.error('删除视频失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 初始化 ====================

const loadTopics = async () => {
  try {
    const qTopics = await getQuestionTopics()
    if (qTopics.success) {
      theoryTopics.value = qTopics.data || []
      practiceTopics.value = qTopics.data || []
    }
    const vTopics = await getVideoTopics()
    if (vTopics.success) {
      videoTopics.value = vTopics.data || []
    }
  } catch (error) {
    console.error('加载知识点失败:', error)
  }
}

const loadStats = async () => {
  try {
    const tStats = await getTheoryQuestionStats()
    if (tStats.success) theoryStats.total = tStats.data.total || 0
    const pStats = await getPracticeQuestionStats()
    if (pStats.success) practiceStats.total = pStats.data.total || 0
    const vStats = await getVideoStats()
    if (vStats.success) videoStats.total = vStats.data.total || 0
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const processToolParams = async () => {
  const tool = route.query.tool

  let args = null
  try {
    args = route.query.args ? JSON.parse(route.query.args) : null
  } catch (e) {
    args = null
  }

  let result = null
  try {
    result = route.query.result ? JSON.parse(route.query.result) : null
  } catch (e) {
    result = null
  }

  await loadTopics()
  await loadStats()

  if (!tool) {
    loadTheoryQuestions()
    return
  }

  switch (tool) {
    case 'list_questions': {
      const type = args?.question_type === 'practice' ? 'practice' : 'theory'
      activeTab.value = type
      if (type === 'theory') {
        if (args?.difficulty) theorySearch.difficulty = args.difficulty
        if (args?.topic) theorySearch.topic = args.topic
        if (args?.keyword) theorySearch.keyword = args.keyword
        await loadTheoryQuestions()
      } else {
        if (args?.difficulty) practiceSearch.difficulty = args.difficulty
        if (args?.topic) practiceSearch.topic = args.topic
        if (args?.keyword) practiceSearch.keyword = args.keyword
        await loadPracticeQuestions()
      }
      break
    }
    case 'add_question': {
      const type = args?.sub_topic ? 'theory' : 'practice'
      activeTab.value = type
      if (type === 'theory') {
        await loadTheoryQuestions()
        resetTheoryForm()
        if (args) {
          if (args.title) theoryForm.title = args.title
          if (args.topic) theoryForm.topic = args.topic
          if (args.sub_topic) theoryForm.sub_topic = args.sub_topic
          if (args.difficulty) theoryForm.difficulty = args.difficulty
          if (args.content) theoryForm.content = args.content
          if (args.solution) theoryForm.solution = args.solution
          if (args.hints) theoryForm.hints = Array.isArray(args.hints) ? args.hints.join('\n') : args.hints
          if (args.knowledge_points) theoryForm.knowledge_points_str = Array.isArray(args.knowledge_points) ? args.knowledge_points.join(',') : args.knowledge_points
        }
        nextTick(() => {
          theoryDialogVisible.value = true
        })
      } else {
        await loadPracticeQuestions()
        resetPracticeForm()
        if (args) {
          if (args.title) practiceForm.title = args.title
          if (args.topic) practiceForm.topic = args.topic
          if (args.difficulty) practiceForm.difficulty = args.difficulty
          if (args.content) practiceForm.content = args.content
          if (args.solution) practiceForm.solution = args.solution
          if (args.hints) practiceForm.hints = Array.isArray(args.hints) ? args.hints.join('\n') : args.hints
          if (args.knowledge_points) practiceForm.knowledge_points_str = Array.isArray(args.knowledge_points) ? args.knowledge_points.join(',') : args.knowledge_points
        }
        nextTick(() => {
          practiceDialogVisible.value = true
        })
      }
      break
    }
    case 'delete_question': {
      const type = args?.sub_topic ? 'theory' : 'practice'
      activeTab.value = type
      if (type === 'theory') {
        await loadTheoryQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          ElMessageBox.confirm('确定要删除该题目吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }).then(async () => {
            try {
              const res = await apiDeleteTheoryQuestion(qid)
              if (res.success) {
                ElMessage.success('删除成功')
                loadTheoryQuestions()
                loadStats()
              }
            } catch (error) {
              ElMessage.error('删除失败')
            }
          }).catch(() => {})
        }
      } else {
        await loadPracticeQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          ElMessageBox.confirm('确定要删除该题目吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }).then(async () => {
            try {
              const res = await apiDeletePracticeQuestion(qid)
              if (res.success) {
                ElMessage.success('删除成功')
                loadPracticeQuestions()
                loadStats()
              }
            } catch (error) {
              ElMessage.error('删除失败')
            }
          }).catch(() => {})
        }
      }
      break
    }
    case 'get_question_detail': {
      const type = args?.sub_topic ? 'theory' : 'practice'
      activeTab.value = type
      if (type === 'theory') {
        await loadTheoryQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          editTheoryQuestion({ id: qid })
        }
      } else {
        await loadPracticeQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          editPracticeQuestion({ id: qid })
        }
      }
      break
    }
    case 'list_videos': {
      activeTab.value = 'videos'
      if (args?.difficulty) videoSearch.difficulty = args.difficulty
      if (args?.topic) videoSearch.topic = args.topic
      if (args?.keyword) videoSearch.keyword = args.keyword
      await loadVideos()
      break
    }
    case 'add_video': {
      activeTab.value = 'videos'
      await loadVideos()
      resetVideoForm()
      if (args) {
        if (args.title) videoForm.title = args.title
        if (args.topic) videoForm.topic = args.topic
        if (args.platform) videoForm.platform = args.platform
        if (args.difficulty) videoForm.difficulty = args.difficulty
        if (args.duration_sec) videoForm.duration_sec = args.duration_sec
        if (args.url) videoForm.url = args.url
        if (args.knowledge_points) videoForm.knowledge_points_str = Array.isArray(args.knowledge_points) ? args.knowledge_points.join(',') : args.knowledge_points
      }
      nextTick(() => {
        videoDialogVisible.value = true
      })
      break
    }
    case 'delete_video': {
      activeTab.value = 'videos'
      await loadVideos()
      const vid = args?.vid || args?.id
      if (vid) {
        ElMessageBox.confirm('确定要删除该视频吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }).then(async () => {
          try {
            const res = await apiDeleteVideo(vid)
            if (res.success) {
              ElMessage.success('删除成功')
              loadVideos()
              loadStats()
            }
          } catch (error) {
            ElMessage.error('删除失败')
          }
        }).catch(() => {})
      }
      break
    }
    case 'get_video_detail': {
      activeTab.value = 'videos'
      await loadVideos()
      const vid = args?.vid || args?.id
      if (vid) {
        editVideo({ id: vid })
      }
      break
    }
    case 'update_video': {
      activeTab.value = 'videos'
      await loadVideos()
      const vid = args?.vid || args?.id
      if (vid) {
        editVideo({ id: vid })
      }
      break
    }
    case 'update_question': {
      const type = args?.sub_topic ? 'theory' : 'practice'
      activeTab.value = type
      if (type === 'theory') {
        await loadTheoryQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          editTheoryQuestion({ id: qid })
        }
      } else {
        await loadPracticeQuestions()
        const qid = args?.qid || args?.id
        if (qid) {
          editPracticeQuestion({ id: qid })
        }
      }
      break
    }
    default:
      loadTheoryQuestions()
      break
  }
}

onMounted(() => {
  processToolParams()
})

watch(() => route.query, () => {
  processToolParams()
}, { deep: true })
</script>

<template>
  <div class="resource-container">
    <!-- 标签页头部 -->
    <div class="tab-header">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-item', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        <svg :viewBox="tab.icon.viewBox" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path :d="tab.icon.path" />
        </svg>
        <span>{{ tab.label }}</span>
        <span class="tab-count">{{ getTabCount(tab.key) }}</span>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="tab-content">
      <!-- 理论题 -->
      <div v-if="activeTab === 'theory'" class="content-panel">
        <div class="search-bar">
          <el-input v-model="theorySearch.keyword" placeholder="搜索题目内容" clearable class="search-input" @keyup.enter="loadTheoryQuestions" />
          <el-select v-model="theorySearch.difficulty" placeholder="选择难度" clearable class="search-select" @change="loadTheoryQuestions">
            <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
          </el-select>
          <el-button type="primary" @click="loadTheoryQuestions">搜索</el-button>
          <el-button @click="resetTheorySearch">重置</el-button>
          <el-button type="success" @click="openTheoryDialog">新增</el-button>
        </div>

        <el-table :data="theoryQuestions" border style="width: 100%" :loading="theoryLoading" stripe fit>
          <el-table-column prop="id" label="ID" width="80" align="center" />
          <el-table-column prop="title" label="标题" width="120" align="center">
            <template #default="{ row }">{{ row.title || '无标题' }}</template>
          </el-table-column>
          <el-table-column prop="topic" label="主题" width="270" align="center" />
          <el-table-column prop="sub_topic" label="题型" width="120" align="center">
            <template #default="{ row }">{{ questionType(row.sub_topic) }}</template>
          </el-table-column>
          <el-table-column prop="difficulty" label="难度" width="80" align="center">
            <template #default="{ row }">
              <span :class="['difficulty-tag', `level-${row.difficulty}`]">{{ getDifficultyLabel(row.difficulty) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="knowledge_points" label="知识点" min-width="150">
            <template #default="{ row }">
              <span v-for="(kp, idx) in parseKnowledgePoints(row.knowledge_points).slice(0, 3)" :key="idx" class="kp-tag">{{ kp }}</span>
              <span v-if="parseKnowledgePoints(row.knowledge_points).length > 3" class="kp-tag">+{{ parseKnowledgePoints(row.knowledge_points).length - 3 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" align="center">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="editTheoryQuestion(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteTheoryQuestion(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="theoryPage.page"
            v-model:page-size="theoryPage.pageSize"
            :total="theoryPage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadTheoryQuestions"
            @current-change="loadTheoryQuestions"
          />
        </div>
      </div>

      <!-- 编程题 -->
      <div v-if="activeTab === 'practice'" class="content-panel">
        <div class="search-bar">
          <el-input v-model="practiceSearch.keyword" placeholder="搜索题目内容" clearable class="search-input" @keyup.enter="loadPracticeQuestions" />
          <el-select v-model="practiceSearch.difficulty" placeholder="选择难度" clearable class="search-select" @change="loadPracticeQuestions">
            <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
          </el-select>
          <el-button type="primary" @click="loadPracticeQuestions">搜索</el-button>
          <el-button @click="resetPracticeSearch">重置</el-button>
          <el-button type="success" @click="openPracticeDialog">新增</el-button>
        </div>

        <el-table :data="practiceQuestions" border style="width: 100%" :loading="practiceLoading" stripe fit>
          <el-table-column prop="id" label="ID" width="80" align="center" />
          <el-table-column prop="title" label="标题" width="189" align="center">
            <template #default="{ row }">{{ row.title || '无标题' }}</template>
          </el-table-column>
          <el-table-column prop="topic" label="主题" width="180" align="center" />
          <el-table-column prop="sub_topic" label="题型" width="120" align="center">
            <template #default="{ row }">{{ questionType(row.sub_topic) }}</template>
          </el-table-column>
          <el-table-column prop="difficulty" label="难度" width="80" align="center">
            <template #default="{ row }">
              <span :class="['difficulty-tag', `level-${row.difficulty}`]">{{ getDifficultyLabel(row.difficulty) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="knowledge_points" label="知识点" min-width="150">
            <template #default="{ row }">
              <span v-for="(kp, idx) in parseKnowledgePoints(row.knowledge_points).slice(0, 3)" :key="idx" class="kp-tag">{{ kp }}</span>
              <span v-if="parseKnowledgePoints(row.knowledge_points).length > 3" class="kp-tag">+{{ parseKnowledgePoints(row.knowledge_points).length - 3 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" align="center">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="editPracticeQuestion(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deletePracticeQuestion(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="practicePage.page"
            v-model:page-size="practicePage.pageSize"
            :total="practicePage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadPracticeQuestions"
            @current-change="loadPracticeQuestions"
          />
        </div>
      </div>

      <!-- 视频 -->
      <div v-if="activeTab === 'videos'" class="content-panel">
        <div class="search-bar">
          <el-input v-model="videoSearch.keyword" placeholder="搜索视频标题" clearable class="search-input" @keyup.enter="loadVideos" />
          <el-select v-model="videoSearch.platform" placeholder="选择平台" clearable class="search-select" @change="loadVideos">
            <el-option label="bilibili" value="bilibili" />
            <el-option label="youtube" value="youtube" />
          </el-select>
          <el-select v-model="videoSearch.difficulty" placeholder="选择难度" clearable class="search-select" @change="loadVideos">
            <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
          </el-select>
          <el-button type="primary" @click="loadVideos">搜索</el-button>
          <el-button @click="resetVideoSearch">重置</el-button>
          <el-button type="success" @click="openVideoDialog">新增</el-button>
        </div>

        <el-table :data="videos" border style="width: 100%" :loading="videoLoading" stripe fit>
          <el-table-column prop="id" label=" ID" width="80" align="center" />
          <el-table-column prop="title" label="标题" width="275" align="center">
            <template #default="{ row }">{{ row.title || '无标题' }}</template>
          </el-table-column>
          <el-table-column prop="platform" label="平台" width="88" align="center">
            <template #default="{ row }">
              <span class="platform-tag">{{ row.platform }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="topic" label="主题" width="95" align="center" />
          <el-table-column prop="difficulty" label="难度" width="80" align="center">
            <template #default="{ row }">
              <span :class="['difficulty-tag', `level-${row.difficulty}`]">{{ getDifficultyLabel(row.difficulty) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="duration_sec" label="时长" width="60" align="center">
            <template #default="{ row }">{{ formatDuration(row.duration_sec) }}</template>
          </el-table-column>
          <el-table-column prop="knowledge_points" label="知识点" width="112">
            <template #default="{ row }">
              <span v-for="(kp, idx) in parseKnowledgePoints(row.knowledge_points).slice(0, 3)" :key="idx" class="kp-tag">{{ kp }}</span>
              <span v-if="parseKnowledgePoints(row.knowledge_points).length > 3" class="kp-tag">+{{ parseKnowledgePoints(row.knowledge_points).length - 3 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="url" label="链接" min-width="170">
            <template #default="{ row }">
              <a v-if="row.url" :href="row.url" target="_blank" class="link-text">{{ row.url }}</a>
              <span v-else class="text-gray">无</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" align="center">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="editVideo(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteVideo(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="videoPage.page"
            v-model:page-size="videoPage.pageSize"
            :total="videoPage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadVideos"
            @current-change="loadVideos"
          />
        </div>
      </div>
    </div>

    <!-- 理论题弹窗 -->
    <div v-if="theoryDialogVisible" class="custom-dialog-overlay" @click.self="theoryDialogVisible = false; resetTheoryForm()">
      <div class="custom-dialog custom-dialog-theory">
        <div class="custom-dialog-header">
          <span class="custom-dialog-title">{{ theoryDialogTitle }}</span>
          <button class="custom-dialog-close" @click="theoryDialogVisible = false; resetTheoryForm()">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="custom-dialog-body">
          <el-form :model="theoryForm" label-width="100px">
            <el-form-item label="标题" required>
              <el-input v-model="theoryForm.title" placeholder="请输入题目标题" />
            </el-form-item>
            <el-form-item label="主题" required>
              <el-select v-model="theoryForm.topic" placeholder="请选择主题">
                <el-option v-for="topic in theoryTopics" :key="topic" :label="topic" :value="topic" />
              </el-select>
            </el-form-item>
            <el-form-item label="子主题">
              <el-input v-model="theoryForm.sub_topic" placeholder="请输入子主题" />
            </el-form-item>
            <el-form-item label="难度" required>
              <el-select v-model="theoryForm.difficulty" placeholder="请选择难度">
                <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
              </el-select>
            </el-form-item>
            <el-form-item label="知识点">
              <el-input v-model="theoryForm.knowledge_points_str" placeholder="多个知识点用逗号分隔" />
            </el-form-item>
            <el-form-item label="题目内容" required>
              <el-input v-model="theoryForm.content" type="textarea" :rows="4" placeholder="请输入题目内容" />
            </el-form-item>
            <el-form-item label="答案解析">
              <el-input v-model="theoryForm.solution" type="textarea" :rows="3" placeholder="请输入答案解析" />
            </el-form-item>
            <el-form-item label="提示">
              <el-input v-model="theoryForm.hints" type="textarea" :rows="2" placeholder="请输入提示信息" />
            </el-form-item>
            <el-form-item label="选项">
              <el-input v-model="theoryForm.options_str" type="textarea" :rows="3" placeholder="JSON格式，如 [{&quot;key&quot;:&quot;A&quot;,&quot;value&quot;:&quot;选项A&quot;}]" />
            </el-form-item>
          </el-form>
        </div>
        <div class="custom-dialog-footer">
          <el-button @click="theoryDialogVisible = false; resetTheoryForm()">取消</el-button>
          <el-button type="primary" @click="saveTheoryQuestion">确定</el-button>
        </div>
      </div>
    </div>

    <!-- 编程题弹窗 -->
    <div v-if="practiceDialogVisible" class="custom-dialog-overlay" @click.self="practiceDialogVisible = false; resetPracticeForm()">
      <div class="custom-dialog custom-dialog-practice">
        <div class="custom-dialog-header">
          <span class="custom-dialog-title">{{ practiceDialogTitle }}</span>
          <button class="custom-dialog-close" @click="practiceDialogVisible = false; resetPracticeForm()">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="custom-dialog-body">
          <el-form :model="practiceForm" label-width="100px">
            <el-form-item label="标题" required>
              <el-input v-model="practiceForm.title" placeholder="请输入题目标题" />
            </el-form-item>
            <el-form-item label="主题" required>
              <el-select v-model="practiceForm.topic" placeholder="请选择主题">
                <el-option v-for="topic in practiceTopics" :key="topic" :label="topic" :value="topic" />
              </el-select>
            </el-form-item>
            <el-form-item label="子主题">
              <el-input v-model="practiceForm.sub_topic" placeholder="请输入子主题" />
            </el-form-item>
            <el-form-item label="难度" required>
              <el-select v-model="practiceForm.difficulty" placeholder="请选择难度">
                <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
              </el-select>
            </el-form-item>
            <el-form-item label="知识点">
              <el-input v-model="practiceForm.knowledge_points_str" placeholder="多个知识点用逗号分隔" />
            </el-form-item>
            <el-form-item label="题目内容" required>
              <el-input v-model="practiceForm.content" type="textarea" :rows="4" placeholder="请输入编程题内容" />
            </el-form-item>
            <el-form-item label="答案解析">
              <el-input v-model="practiceForm.solution" type="textarea" :rows="3" placeholder="请输入答案解析" />
            </el-form-item>
            <el-form-item label="提示">
              <el-input v-model="practiceForm.hints" type="textarea" :rows="2" placeholder="请输入提示信息" />
            </el-form-item>
          </el-form>
        </div>
        <div class="custom-dialog-footer">
          <el-button @click="practiceDialogVisible = false; resetPracticeForm()">取消</el-button>
          <el-button type="primary" @click="savePracticeQuestion">确定</el-button>
        </div>
      </div>
    </div>

    <!-- 视频弹窗 -->
    <div v-if="videoDialogVisible" class="custom-dialog-overlay" @click.self="videoDialogVisible = false; resetVideoForm()">
      <div class="custom-dialog custom-dialog-video">
        <div class="custom-dialog-header">
          <span class="custom-dialog-title">{{ videoDialogTitle }}</span>
          <button class="custom-dialog-close" @click="videoDialogVisible = false; resetVideoForm()">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="custom-dialog-body">
          <el-form :model="videoForm" label-width="100px">
            <el-form-item label="平台" required>
              <el-select v-model="videoForm.platform" placeholder="请选择平台">
                <el-option label="bilibili" value="bilibili" />
                <el-option label="youtube" value="youtube" />
              </el-select>
            </el-form-item>
            <el-form-item label="标题" required>
              <el-input v-model="videoForm.title" placeholder="请输入视频标题" />
            </el-form-item>
            <el-form-item label="主题" required>
              <el-select v-model="videoForm.topic" placeholder="请选择主题">
                <el-option v-for="topic in videoTopics" :key="topic" :label="topic" :value="topic" />
              </el-select>
            </el-form-item>
            <el-form-item label="难度">
              <el-select v-model="videoForm.difficulty" placeholder="请选择难度">
                <el-option v-for="d in [1,2,3,4,5]" :key="d" :label="getDifficultyLabel(d)" :value="d" />
              </el-select>
            </el-form-item>
            <el-form-item label="时长(秒)">
              <el-input-number v-model="videoForm.duration_sec" :min="0" placeholder="视频时长（秒）" />
            </el-form-item>
            <el-form-item label="视频链接">
              <el-input v-model="videoForm.url" placeholder="请输入视频链接" />
            </el-form-item>
            <el-form-item label="知识点">
              <el-input v-model="videoForm.knowledge_points_str" placeholder="多个知识点用逗号分隔" />
            </el-form-item>
          </el-form>
        </div>
        <div class="custom-dialog-footer">
          <el-button @click="videoDialogVisible = false; resetVideoForm()">取消</el-button>
          <el-button type="primary" @click="saveVideo">确定</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resource-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-page);
}

/* ===== 标签页头部 ===== */
.tab-header {
  display: flex;
  background: transparent;
  border-bottom: 1px solid var(--border-color);
  padding: 0 24px;
  gap: 6px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 22px;
  cursor: pointer;
  color: var(--text-gray);
  font-size: 14px;
  font-weight: 500;
  border-bottom: 3px solid transparent;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.tab-item::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 50%;
  width: 0;
  height: 3px;
  background: var(--grad-primary);
  border-radius: 3px 3px 0 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  transform: translateX(-50%);
}

.tab-item:hover {
  color: var(--primary);
  background-color: var(--primary-light);
}

.tab-item:hover::after {
  width: 60%;
}

.tab-item.active {
  color: var(--primary);
  border-bottom-color: transparent;
  background-color: var(--primary-light);
}

.tab-item.active::after {
  width: 100%;
}

.tab-item svg {
  transition: transform 0.25s ease;
}

.tab-item:hover svg {
  transform: scale(1.15);
}

.tab-item.active svg {
  transform: scale(1.1);
}

.tab-count {
  background: var(--grad-primary);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(45, 125, 219, 0.2);
}

.tab-item.active .tab-count {
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.35);
}

/* ===== 内容区域 ===== */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.tab-content::-webkit-scrollbar {
  width: 6px;
}

.tab-content::-webkit-scrollbar-track {
  background: transparent;
}

.tab-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}

.content-panel {
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  animation: fadeInUp 0.3s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 搜索栏 ===== */
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  padding: 16px 18px;
  background: var(--bg-page);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.search-input {
  width: 200px;
}

.search-select {
  width: 140px;
}

/* ===== 分页 ===== */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

/* ===== 难度标签 ===== */
.difficulty-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.difficulty-tag.level-1 {
  background-color: var(--pass-bg-color);
  color: var(--pass);
  border: 1px solid rgba(103, 194, 58, 0.2);
}

.difficulty-tag.level-2 {
  background-color: #f0fdf4;
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.difficulty-tag.level-3 {
  background-color: var(--coming-bg-color);
  color: var(--coming);
  border: 1px solid rgba(230, 162, 60, 0.2);
}

.difficulty-tag.level-4 {
  background-color: #fff7ed;
  color: #fb923c;
  border: 1px solid rgba(251, 146, 60, 0.2);
}

.difficulty-tag.level-5 {
  background-color: var(--main-fail-status);
  color: var(--main-delete);
  border: 1px solid rgba(245, 108, 108, 0.2);
}

/* ===== 知识点标签 ===== */
.kp-tag {
  display: inline-block;
  padding: 2px 8px;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-fade) 100%);
  color: var(--primary);
  border-radius: 4px;
  font-size: 12px;
  margin-right: 4px;
  margin-bottom: 4px;
  border: 1px solid rgba(45, 125, 219, 0.1);
}

/* ===== 平台标签 ===== */
.platform-tag {
  display: inline-block;
  padding: 3px 10px;
  background-color: var(--bgc-light);
  color: var(--text-body);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--border-color);
}

/* ===== 链接 ===== */
.link-text {
  color: var(--primary);
  text-decoration: none;
  font-size: 13px;
  transition: all 0.2s;
  border-bottom: 1px dashed var(--primary-fade);
  padding-bottom: 1px;
}

.link-text:hover {
  color: var(--primary-hv);
  border-bottom-color: var(--primary-hv);
}

.text-gray {
  color: var(--text-gray);
}

/* ===== 表格样式 ===== */
:deep(.el-table) {
  --el-table-border-color: var(--border-color);
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(45, 125, 219, 0.04);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

:deep(.el-table th.el-table__cell) {
  color: var(--text-title);
  font-weight: 600;
  font-size: 13px;
  background: linear-gradient(180deg, var(--primary-light) 0%, rgba(239, 246, 255, 0.5) 100%) !important;
  padding: 12px 0;
  border-bottom: 2px solid var(--primary-fade);
}

:deep(.el-table td.el-table__cell) {
  color: var(--text-body);
  font-size: 13px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

:deep(.el-table .el-table__row:hover > td.el-table__cell) {
  background-color: rgba(45, 125, 219, 0.04);
}

:deep(.el-table .el-table__row--striped td.el-table__cell) {
  background-color: rgba(248, 250, 252, 0.6);
}

:deep(.el-table__empty-text) {
  color: var(--text-gray);
}

/* ===== 按钮样式 ===== */
:deep(.el-button--primary) {
  background: var(--grad-primary);
  border: none;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.25);
}

:deep(.el-button--primary:hover) {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--primary:active) {
  transform: translateY(0);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, var(--main-delete) 0%, #f78a8a 100%);
  border: none;
  box-shadow: 0 2px 6px rgba(245, 108, 108, 0.25);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, #ff9999 100%);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--default) {
  border-color: var(--border-color);
  color: var(--text-body);
}

:deep(.el-button--default:hover) {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-light);
}

:deep(.el-button--small) {
  padding: 5px 12px;
  font-size: 12px;
  border-radius: 6px;
}

:deep(.el-button.is-disabled),
:deep(.el-button.is-disabled:hover),
:deep(.el-button.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
  opacity: 0.6;
  cursor: not-allowed;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--primary.is-disabled:hover),
:deep(.el-button--primary.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-button--danger.is-disabled),
:deep(.el-button--danger.is-disabled:hover),
:deep(.el-button--danger.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

/* ===== 自定义弹窗样式 ===== */
.custom-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2001;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.custom-dialog {
  position: relative;
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.custom-dialog-theory {
  width: 700px;
  max-height: 85vh;
}

.custom-dialog-practice {
  width: 700px;
  max-height: 85vh;
}

.custom-dialog-video {
  width: 650px;
  max-height: 85vh;
}

.custom-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--bg-card) 100%);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.custom-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.custom-dialog-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-gray);
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.custom-dialog-close:hover {
  color: var(--primary);
  background-color: var(--primary-light);
}

.custom-dialog-body {
  padding: 24px;
  max-height: calc(85vh - 140px);
  overflow-y: auto;
  flex: 1;
}

.custom-dialog-body::-webkit-scrollbar {
  width: 6px;
}

.custom-dialog-body::-webkit-scrollbar-track {
  background: var(--bg-page);
  border-radius: 3px;
}

.custom-dialog-body::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.custom-dialog-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}

.custom-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

:deep(.el-form-item__label) {
  color: var(--text-body);
  font-weight: 500;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

/* ===== 输入框 ===== */
:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 6px;
  transition: all 0.2s;
}

:deep(.el-input__wrapper:hover),
:deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}

:deep(.el-input__wrapper:focus-within, .el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px rgba(45, 125, 219, 0.1) !important;
}

/* ===== 分页样式 ===== */
:deep(.el-pagination) {
  --el-pagination-button-bg-color: transparent;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: var(--grad-primary);
  color: white;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.3);
}

:deep(.el-pagination .el-pager li:hover) {
  color: var(--primary);
}

/* ===== 操作列按钮 ===== */
:deep(.el-table .el-button + .el-button) {
  margin-left: 6px;
}
</style>
