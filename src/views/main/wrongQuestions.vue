<script setup>
import { ref, onMounted, computed, onUnmounted, watch, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox,ElNotification } from 'element-plus'
import { useRouter } from 'vue-router'
//跳转做编程题
import { saveSkip } from '@/utils/skip.js'
import emitter from '@/utils/emitter'
// 引入封装的图表方法
import { renderAnswerChart, destroyAnswerChart, highlightAttempt } from '@/views/main/mapJs/lineDiagram.js'
import { getSummaryApi, getPendingListApi,
  getOkListApi, deleteQuestionApi, getInfoApi, getAiRecommendApi,
  submitSingleQuestionApi,getFrequentlyListApi,getFrequentlyMesApi } from '@/api/mainApi/wrongQuestions.js'
import KnowledgePoints from '@/components/KnowledgePoints.vue'

const router = useRouter()
let loginUser = null
const userId = ref('')// 用户ID
const showTopBtn = ref(false)// 是否显示回到顶部按钮

// 滚动监听
const scrollHandler = () => {
  // 滚动大于80px显示按钮，可自定义高度
  showTopBtn.value = window.scrollY > 80
}
// 回到顶部
const backTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(async () => {

  // 页面初始置顶
  window.scrollTo(0, 0)
  window.addEventListener('scroll', scrollHandler)

  const userStr = localStorage.getItem('loginUser')
  if (userStr) {

    //获取用户id
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        // 判断登录用户类型
        if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
          ElMessage.warning('请进行画像构建~')
          router.push('/aiAnswer')
        }
        // 已是字符串直接赋值，否则转字符串
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }

  }

  // 获取错题数据
  await getSummary()

  // 切换导航到待巩固
  await changeNav(1)
})



// ====================数据====================
const summary = ref({})
const page = ref(1)//页码
const pageSize = ref(10)//每页帖子数量
const totalPages = ref(1)//总页数
const qType = ref(0)//资源类型下拉框
const showPopup = ref(false)//弹窗：重练非编程题+学习资料推荐
const showSituation = ref(false)//弹窗：查看学习趋势
const questionList = ref([])
const okList = ref([])

// 待巩固该题弹窗信息表
const showQuestion = reactive({})// 当前弹窗展示的题目数据

// 答题绑定变量
const answer = ref('')          // 填空、简答题 文本答案
const answerIndex = ref(null)   // 单选题 选中下标
const multipleIndex = ref([])   // 多选题 选中下标数组
const judgeAnswer = ref('')     // 判断题 答案：正确 / 错误

// 分析结果
const analysisResult = ref(null) // 提交后的分析结果
const isSubmitting = ref(false)  // 是否正在提交
const hasSubmitted = ref(false)  // 是否已提交分析

// 推荐材料信息
const recommend = ref([])
// 当前正在查看的推荐题目详情（理论题弹窗）
const showRecommendDetail = ref(false)
const recommendDetailData = ref(null)

// 推荐材料加载状态
const isLoadingRecommend = ref(false)

// 已掌握数据
const okData = ref({})//已掌握的展开信息

// 易错题数据
const frequentlyList = ref([])
const frequentlyStats = ref({})

// 推荐题目详情弹窗的变量
const recommendDetailAnswerIndex = ref(null)
const recommendDetailMultipleIndex = ref([])
const recommendDetailJudgeAnswer = ref('')
const recommendDetailTextAnswer = ref('')
const recommendDetailResult = ref(null)
const recommendDetailSubmitting = ref(false)

// 打开普通题目详情（弹窗/新页面）
const openQuestionDetail = (item) => {
  console.log('查看题目详情', item)
  // 直接使用传入的数据，已经包含了完整的题目信息
  recommendDetailData.value = item
  showRecommendDetail.value = true
}

// 关闭推荐题目详情弹窗
const closeRecommendDetail = () => {
  showRecommendDetail.value = false
  recommendDetailData.value = null
  resetRecommendDetail()
}

// 重置推荐题目详情弹窗状态
const resetRecommendDetail = () => {
  recommendDetailAnswerIndex.value = null
  recommendDetailMultipleIndex.value = []
  recommendDetailJudgeAnswer.value = ''
  recommendDetailTextAnswer.value = ''
  recommendDetailResult.value = null
}

// 推荐题目详情弹窗中，多选题：选中/取消切换
const toggleRecommendMultiple = (index) => {
  const findIndex = recommendDetailMultipleIndex.value.indexOf(index)
  if (findIndex > -1) {
    recommendDetailMultipleIndex.value.splice(findIndex, 1)
  } else {
    recommendDetailMultipleIndex.value.push(index)
  }
}

// 提取选项字母（支持 "A. xxx" 或 "xxx" 格式）
const extractOptionLetter = (optionText, index) => {
  if (!optionText) return String.fromCharCode(65 + index)
  // 尝试匹配 "A. xxx" 格式
  const match = optionText.match(/^([A-D])\./)
  if (match) return match[1]
  // 尝试匹配 "A" 格式
  if (/^[A-D]$/i.test(optionText.trim())) return optionText.trim().toUpperCase()
  // 否则返回字母
  return String.fromCharCode(65 + index)
}

// 提交推荐题目（理论题）
const submitRecommendQuestion = async () => {
  if (!recommendDetailData.value) return
  
  // 获取用户选择的答案
  let userAnswer = ''
  const qData = recommendDetailData.value
  
  if (qData.sub_topic === 'single_choice') {
    // 单选题
    const selectedIndex = recommendDetailAnswerIndex.value
    if (selectedIndex === null || selectedIndex === undefined) {
      ElMessage.warning('请选择一个选项')
      return
    }
    // 提取选项字母
    const optionText = qData.options[selectedIndex] || ''
    userAnswer = extractOptionLetter(optionText, selectedIndex)
  } else if (qData.sub_topic === 'multiple_choice') {
    // 多选题
    if (!recommendDetailMultipleIndex.value || recommendDetailMultipleIndex.value.length === 0) {
      ElMessage.warning('请至少选择一个选项')
      return
    }
    const selectedOptions = recommendDetailMultipleIndex.value.map(idx => {
      const optionText = qData.options[idx] || ''
      return extractOptionLetter(optionText, idx)
    })
    userAnswer = selectedOptions.join(',')
  } else if (qData.sub_topic === 'judge') {
    // 判断题
    if (!recommendDetailJudgeAnswer.value) {
      ElMessage.warning('请选择正确或错误')
      return
    }
    userAnswer = recommendDetailJudgeAnswer.value
  } else if (qData.sub_topic === 'fill_blank' || qData.sub_topic === 'short_answer') {
    // 填空题/简答题
    if (!recommendDetailTextAnswer.value || recommendDetailTextAnswer.value.trim() === '') {
      ElMessage.warning('请输入您的答案')
      return
    }
    userAnswer = recommendDetailTextAnswer.value.trim()
  } else {
    ElMessage.warning('未知题型')
    return
  }

  // 构建提交数据
  const submitData = {
    user_id: userId.value,
    question_type: qData.sub_topic || 'single_choice',
    question: {
      question: qData.content || qData.title || qData.question || '',
      options: qData.options || [],
      answer: qData.answer || ''
    },
    user_answer: userAnswer,
    knowledge_points: qData.knowledge_points || [],
  }

  try {
    recommendDetailSubmitting.value = true
    const res = await submitSingleQuestionApi(submitData)
    if (res.code === 1) {
      recommendDetailResult.value = res.data
      ElMessage.success(res.data.message || '提交成功')
      // 刷新待巩固列表
      await getPendingList(page.value)
      await getSummary()
    } else {
      ElMessage.error(res.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交推荐题目失败', e)
    ElMessage.error('提交失败，请稍后重试')
  } finally {
    recommendDetailSubmitting.value = false
  }
}

// 已掌握
// 切换作答
const activeIdx = ref(-1)//选中展示重练的下标
const curAnswer = ref('')//该次的用户回答
const curScore = ref('')//该次分数
const curVerdict = ref('')//该次状态

//监听下拉框
watch(qType, async (newValue) => {
  console.log('qType 改变', newValue)
  page.value = 1
  await getPendingList(1)
})

// ===================函数====================
// 导航栏切换
const navOption = ref(0)
const changeNav = async (choose) => {
  if (navOption.value === choose) {
    console.log('已选分类不切换')
    return
  }
  switch (choose) {
    case 1:
      console.log('切换到 待巩固')
      page.value = 1
      await getPendingList(1)
      navOption.value = 1
      break
    case 2:
      console.log('切换到 已掌握')
      page.value = 1
      await getOkList(1)
      navOption.value = 2
      break
    case 3:
      console.log('切换到 易错题')
      page.value = 1
      await getFrequentlyList(1)
      await getFrequentlyStats()
      navOption.value = 3
      break
    case 4:
      console.log('切换到 知识点盘问')
      navOption.value = 4
      break
    default:
      console.log('错误：无效的选择')
  }

}

//格式化后端 T分隔时间 2026-06-04T10:35:21.923784 → yyyy-MM-dd HH:mm:ss
function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}:${s}`
}

// 获取题型函数
const questionType = (type) => {
  switch (type) {
    case 'fill_blank':
      return '填空题'
    case 'programming':
      return '编程题'
    case 'single_choice':
      return '单选题'
    case 'multiple_choice':
      return '多选题'
    case 'judge':
      return '判断题'
    case 'short_answer':
      return '简答题'
    default:
      return '未知题型'
  }
}

//上一页
const prevPage = async () => {
  console.log('上一页')
  if (page.value > 1) {
    page.value--
    switch (navOption.value) {
      case 1:
        await getPendingList(page.value)
        break
      case 2:
        await getOkList(page.value)
        break
      case 3:
        await getFrequentlyList(page.value)
        break
      default:
        console.log('错误：无效的选择')
    }
  }
}
//下一页
const nextPage = async () => {
  console.log('下一页')
  if (page.value < totalPages.value) {
    page.value++
    switch (navOption.value) {
      case 1:
        await getPendingList(page.value)
        break
      case 2:
        await getOkList(page.value)
        break
      case 3:
        await getFrequentlyList(page.value)
        break
      default:
        console.log('错误：无效的选择')
    }
  }
}

// 待巩固：打开弹窗
// 易错题页：打开弹窗（使用 frequentlyList）
const openFrequentlyPopup = async (index) => {
  // 禁止页面滚动
  document.body.style.overflow = 'hidden'

  // 展示信息
  const item = frequentlyList.value[index]
  // 赋值当前题目
  Object.assign(showQuestion, item)
  
  // 上报错题上下文给智能球
  if (item) {
    emitter.emit('contextDetail', {
      page: 'wrongQuestions',
      title: '错题重练',
      action: 'reviewing',
      detail: `错题ID: ${item.record_id || item.id}, 题目: ${item.question_data?.title || item.question || '未知题目'}, 知识点: ${item.knowledge_point || ''}`
    })
  }
  
  // 重置答题状态，避免不同题目数据污染
  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  analysisResult.value = null
  hasSubmitted.value = false
  recommend.value = []
  
  showPopup.value = true

  // 调用获取推荐材料接口
  await fetchRecommendMaterials(item.record_id)
}

const openPopup = async (index) => {
  // 禁止页面滚动
  document.body.style.overflow = 'hidden'

  // 展示信息
  const item = questionList.value[index]
  // 赋值当前题目
  Object.assign(showQuestion, item)
  
  // 上报错题上下文给智能球
  if (item) {
    emitter.emit('contextDetail', {
      page: 'wrongQuestions',
      title: '错题重练',
      action: 'reviewing',
      detail: `错题ID: ${item.record_id || item.id}, 题目: ${item.question || '未知题目'}, 知识点: ${item.knowledge_point || ''}`
    })
  }
  
  // 重置答题状态，避免不同题目数据污染
  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  analysisResult.value = null
  hasSubmitted.value = false
  recommend.value = []
  
  showPopup.value = true

  // 调用获取推荐材料接口
  await fetchRecommendMaterials(item.record_id)
}

// 获取推荐材料
const fetchRecommendMaterials = async (recordId) => {
  try {
    isLoadingRecommend.value = true
    const notificationInstance = ElNotification({
      title: '小提示',
      message: '正在获取/生成推荐材料...',
      position: 'bottom-left',
      duration: 0,
      showClose: false, // 隐藏关闭按钮
    });
    const res = await getInfoApi(userId.value, recordId)
    if (res.code === 1 && res.data.success) {
      // 显示推荐材料列表
      // 提取 materials 中的 question 列表
      const materials = res.data.materials || {}
      const questionList = materials.question || []
      // 过滤掉空数据
      recommend.value = questionList.filter(item => item && item.id !== undefined && item.sub_topic !== 'code_practice')
      
      // 如果 should_recommend 为 false 或 attempt_count < 3，显示提示
      if (!res.data.should_recommend) {
        ElNotification({
          title: '小提示',
          message: '该题错误次数较少，暂无推荐材料',
          position: 'bottom-left',
          duration: 4000,
          showClose: false,
        });
        // 关闭提示
        notificationInstance.close()
      } else {
        ElNotification({
          title: '小提示',
          message: `已为您推荐 ${recommend.value.length} 个相关题目`,
          position: 'bottom-left',
          duration: 4000,
          showClose: false,
        });
        // 关闭提示
        notificationInstance.close()
      }
    } else {
      recommend.value = []
      ElNotification({
        title: '小提示',
        message: '暂无推荐材料',
        position: 'bottom-left',
        duration: 4000,
        showClose: false,
      });
      // 关闭提示
      notificationInstance.close()
    }
    // 关闭提示
    notificationInstance.close()
  } catch (e) {
    console.error('获取推荐材料失败', e)
    recommend.value = []
  } finally {
    isLoadingRecommend.value = false
  }
}

// 配套：关闭弹窗（必须加，恢复滚动）
const closePopup = () => {
  showPopup.value = false
  recommend.value = []
  analysisResult.value = null
  hasSubmitted.value = false
  // 恢复页面滚动
  document.body.style.overflow = ''
}

//popup中，多选题：选中/取消切换
const toggleMultiple = (index) => {
  const findIndex = multipleIndex.value.indexOf(index)
  if (findIndex > -1) {
    // 已选中则取消
    multipleIndex.value.splice(findIndex, 1)
  } else {
    // 未选中则添加
    multipleIndex.value.push(index)
  }
}

// 获取当前题目的用户答案
const getUserAnswer = () => {
  const qType = showQuestion.question_type
  let userAnswer = ''

  switch (qType) {
    case 'single_choice':
      if (answerIndex.value === null || answerIndex.value === undefined) {
        ElMessage.warning('请选择一个选项')
        return null
      }
      const optionText = showQuestion.question_data.options[answerIndex.value] || ''
      userAnswer = extractOptionLetter(optionText, answerIndex.value)
      break

    case 'multiple_choice':
      if (!multipleIndex.value || multipleIndex.value.length === 0) {
        ElMessage.warning('请至少选择一个选项')
        return null
      }
      const selectedOptions = multipleIndex.value.map(idx => {
        const optText = showQuestion.question_data.options[idx] || ''
        return extractOptionLetter(optText, idx)
      })
      userAnswer = selectedOptions.join(',')
      break

    case 'judge':
      if (!judgeAnswer.value) {
        ElMessage.warning('请选择正确或错误')
        return null
      }
      userAnswer = judgeAnswer.value
      break

    case 'fill_blank':
    case 'short_answer':
      if (!answer.value || answer.value.trim() === '') {
        ElMessage.warning('请输入您的答案')
        return null
      }
      userAnswer = answer.value.trim()
      break

    default:
      ElMessage.warning('未知题型')
      return null
  }

  return userAnswer
}

// 提交重做分析
const handleSubmitAnalysis = async () => {
  if (isSubmitting.value) return

  const userAnswer = getUserAnswer()
  if (userAnswer === null) return

  // 构建提交数据
  const submitData = {
    user_id: userId.value,
    question_type: showQuestion.question_type,
    question: {
      question: showQuestion.question_data.question || showQuestion.question_data.title || '',
      options: showQuestion.question_data.options || null,
      answer: showQuestion.question_data.answer || showQuestion.correct_answer || ''
    },
    user_answer: userAnswer,
    knowledge_points: showQuestion.knowledge_points.join(',') || []
  }

  try {
    isSubmitting.value = true
    const res = await submitSingleQuestionApi(submitData)
    if (res.code === 1) {
      analysisResult.value = res.data
      hasSubmitted.value = true
      ElMessage.success(res.data.message || '提交成功')
      
      // 刷新待巩固列表和统计信息
      await getPendingList(page.value)
      await getSummary()
      
      // 重新获取推荐材料
      await fetchRecommendMaterials(showQuestion.record_id)
    } else {
      ElMessage.error(res.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交分析失败', e)
    ElMessage.error('提交失败，请稍后重试')
  } finally {
    isSubmitting.value = false
  }
}

// 重新练习（清空分析和作答）
const handleResetPractice = () => {
  // 清空分析结果
  analysisResult.value = null
  hasSubmitted.value = false
  
  // 清空作答
  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  
  ElMessage.info('已重置，请重新作答')
}

// 判断提交按钮是否禁用
const isSubmitDisabled = computed(() => {
  return isSubmitting.value || hasSubmitted.value
})

// 获取提交按钮文本
const submitBtnText = computed(() => {
  if (isSubmitting.value) return '提交中...'
  if (hasSubmitted.value) return '已提交'
  return '重做分析'
})

// 已掌握：打开弹窗
const openSituation = async (index) => {
  document.body.style.overflow = 'hidden'// 禁止页面滚动

  okData.value = okList.value[index]

  //第一个重练显示
  const item = okList.value[index].attempts[0]
  activeIdx.value = 0
  curAnswer.value = item.user_answer
  curScore.value = item.score
  curVerdict.value = item.verdict

  //展示信息
  showSituation.value = true

  // 异步等待 0.5 秒
  await new Promise(resolve => setTimeout(resolve, 500))

  //折线图
  renderAnswerChart('answerChart', okList.value[index])

}

// 配套：关闭弹窗（必须加，恢复滚动）
const closeSituation = () => {
  destroyAnswerChart('answerChart')
  showSituation.value = false

  okData.value = []
  activeIdx.value = -1
  curAnswer.value = ''
  curScore.value = ''
  curVerdict.value = ''

  // 恢复页面滚动
  document.body.style.overflow = ''
}

// 判断是否为编程题
// 推荐材料中的编程题通过 resource_type 或 _content_type 判断
const isProgrammingResource = (item) => {
  if (!item) return false
  // 优先通过 sub_topic 判断
  if (item.sub_topic === 'programming') return true
  // 其次通过 topic 判断
  if (item.topic === 'programming') return true
  // 最后通过 resource_id 以 P 或 p 开头判断（兼容旧数据）
  // if (item.resource_id && /^[Pp]/.test(item.resource_id)) return true
  return false
}

// 跳转编程题作答
const goAnswer = async (rsType = 4, resourceId, recordId = '') => {
  console.log('跳转作答', rsType, resourceId, recordId)
  saveSkip(rsType, resourceId, recordId)
  // 跳转到/code
  router.push('/code')
}

// 处理推荐材料中的跳转
const handleRecommendJump = (item) => {
  if (!item) {
    ElMessage.warning('推荐数据不存在')
    return
  }
  
  console.log('推荐项数据:', item)
  
  // 判断是否为编程题
  const isProgramming = isProgrammingResource(item)
  
  if (isProgramming) {
    // 编程题：跳转作答
    const problemId = item.resource_id || item.id
    goAnswer(4, problemId, showQuestion.record_id || '')
  } else {
    // 理论题：直接使用推荐数据中的信息弹出详情
    // 推荐数据中已经包含了完整的题目信息
    
    // 确定题型
    let subTopic = item.sub_topic || item._type || item.resource_type || 'single_choice'
    
    // 如果题型是 'question' 或其他非具体类型，尝试推断
    if (subTopic === 'question' || subTopic === '' || subTopic === 'theory') {
      if (item.options && item.options.length > 0) {
        // 有选项，判断单选/多选
        if (item.answer && item.answer.length === 1 && /^[A-D]$/i.test(item.answer)) {
          subTopic = 'single_choice'
        } else if (item.answer && item.answer.includes(',')) {
          subTopic = 'multiple_choice'
        } else {
          subTopic = 'single_choice'
        }
      } else {
        // 没有选项，可能是填空或简答
        subTopic = 'short_answer'
      }
    }
    
    const questionData = {
      ...item,
      // 题目内容（优先使用 content，其次 title，最后 metadata.title）
      question: item.content || item.title || item.metadata?.title || '',
      // 选项列表（已经是完整格式，如 "A. xxx" 或 "xxx"）
      options: item.options || [],
      // 正确答案
      answer: item.answer || '',
      // 解析
      explanation: item.explanation || '',
      // 题型
      sub_topic: subTopic
    }
    
    console.log('打开推荐题目详情:', questionData)
    openQuestionDetail(questionData)
    resetRecommendDetail()
  }
}

// AI生成更多推荐材料
const handleAiGenerate = async () => {
  if (!showQuestion.record_id) {
    ElMessage.warning('记录ID不存在')
    return
  }

  isLoadingRecommend.value = true

  // 提取知识点
  let knowledgePoints = []
  if (showQuestion.knowledge_points && showQuestion.knowledge_points.length > 0) {
    knowledgePoints = showQuestion.knowledge_points
  } else if (showQuestion.question_data && showQuestion.question_data.knowledge_points) {
    knowledgePoints = showQuestion.question_data.knowledge_points
  }

  // 确定难度
  let difficulty = '中等'
  if (showQuestion.question_data && showQuestion.question_data.difficulty) {
    const diff = showQuestion.question_data.difficulty
    if (diff.includes('简单') || diff === '简单') difficulty = '简单'
    else if (diff.includes('中等') || diff === '中等') difficulty = '中等'
    else if (diff.includes('困难') || diff === '困难') difficulty = '困难'
  }

  const requestData = {
    user_id: userId.value,
    record_id: showQuestion.record_id,
    knowledge_points: knowledgePoints.length > 0 ? knowledgePoints : ['编程基础'],
    resource_types: ['question', 'practice'],
    difficulty: difficulty
  }

  try {
    // 显示加载提示
    const loadingMsg = ElNotification({
      title: '小提示',
      message: 'AI正在生成推荐材料，请稍候...',
      position: 'bottom-left',
      duration: 0,
      showClose: false,
    });

    const res = await getAiRecommendApi(requestData)
    loadingMsg.close()

    if (res.code === 1 && res.data && res.data.success) {
      ElMessage.success('AI生成推荐材料成功')
      // 重新获取推荐材料
      await fetchRecommendMaterials(showQuestion.record_id)
    } else {
      ElMessage.error(res.msg || 'AI生成失败')
    }
  } catch (e) {
    console.error('AI生成推荐材料失败', e)
    ElNotification({
      title: '小提示',
      message: 'AI生成失败，请稍后重试',
      position: 'bottom-left',
      duration: 4000,
      showClose: false,
    });
  } finally {
    isLoadingRecommend.value = false
  }
}

// ===================接口====================
//获取统计信息
const getSummary = async () => {
  try {
    const res = await getSummaryApi(userId.value)
    if (res.code && res.data.success === true) {
      summary.value = res.data
    }
  } catch (e) {
    console.error('获取统计信息失败', e)
  }
}

//获取待巩固列表
const getPendingList = async (optionPage) => {
  try {
    const res = await getPendingListApi(optionPage, pageSize.value, qType.value, userId.value)
    if (res.code && res.data.success === true) {
      questionList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages

    } else {
      ElMessage.error('查询失败', res.data)
    }
  } catch (e) {
    console.error('获取待巩固列表失败', e)
  }
}

//获取已掌握列表
const getOkList = async (optionPage) => {
  try {
    const res = await getOkListApi(optionPage, pageSize.value, userId.value)
    if (res.code && res.data.success === true) {
      okList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages

    }
  } catch (e) {
    console.error('获取已掌握列表失败', e)
  }
}

//获取易错题列表
const getFrequentlyList = async (optionPage) => {
  try {
    const res = await getFrequentlyListApi(optionPage, pageSize.value, userId.value)
    if (res.code && res.data.success === true) {
      frequentlyList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    } else {
      ElMessage.error('获取易错题列表失败', res.data)
    }
  } catch (e) {
    console.error('获取易错题列表失败', e)
  }
}

//获取易错题统计信息
const getFrequentlyStats = async () => {
  try {
    const res = await getFrequentlyMesApi(userId.value)
    if (res.code && res.data.success === true) {
      frequentlyStats.value = res.data
    }
  } catch (e) {
    console.error('获取易错题统计失败', e)
  }
}

//删除错题本待巩固列表问题
const deleteQuestion = async (recordId) => {
  try {
    const res = await deleteQuestionApi(userId.value, recordId)
    if (res.code && res.data.success === true) {
      ElMessage.success('删除成功')
      await getPendingList(page.value)
      await getSummary()
    } else {
      ElMessage.error('删除失败', res.data)
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}


onUnmounted(() => {
  window.removeEventListener('scroll', scrollHandler)
})
</script>

<template>
  <!-- 回顶按钮 -->
  <div v-if="showTopBtn" class="back-top" @click="backTop">↑</div>
  <div class="container">

    <!-- 标题 -->
    <div class="title">
      <h1>错题本</h1>
      <p class="subtitle">自动记录所有错题信息，帮助快速回顾学习</p>
    </div>

    <!-- 主体 -->
    <div class="main">

      <!-- 左侧固定 错题统计 -->
      <div class="summary">
        <div class="BigTitle">错题统计</div>
        <!-- 总数 -->
        <div class="total">
          <div class="count">{{ summary.total || 0 }}</div>
          <div class="title">所有错题</div>
        </div>
        <!-- 待巩固 -->
        <div class="pending" :class="{ show: navOption === 1 }" @click="changeNav(1)">
          <div class="count">{{ summary.pending || 0 }}</div>
          <div class="title">待巩固</div>
        </div>
        <!-- 已掌握 -->
        <div class="resolved" :class="{ show: navOption === 2 }" @click="changeNav(2)">
          <div class="count">{{ summary.resolved || 0 }}</div>
          <div class="title">已掌握</div>
        </div>
        <!-- 易错题 -->
        <div class="frequently" :class="{ show: navOption === 3 }" @click="changeNav(3)">
          <div class="count">{{ summary.frequently_wrong || 0 }}</div>
          <div class="title">易错题</div>
        </div>
      </div>

      <!-- 左侧 -->

      <!-- 内容部分 -->
      <div class="content">

        <!-- 导航栏 -->
        <div class="nav">
          <div class="pendingPage" :class="{ active: navOption === 1 }" @click="changeNav(1)">
            待巩固
          </div>
          <div class="resolvedPage" :class="{ active: navOption === 2 }" @click="changeNav(2)">
            已掌握
          </div>
          <div class="frequentlyPage" :class="{ active: navOption === 3 }" @click="changeNav(3)">
            易错题
          </div>
          <div class="knowledgesPage" :class="{ active: navOption === 4 }" @click="changeNav(4)">
            <svg t="1785382768566" class="icon" viewBox="0 0 3185 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6635" width="55" height="55"><path d="M113.777778 984.177778v-108.088889h34.133333c11.377778 0 17.066667 0 22.755556-5.688889s11.377778-11.377778 17.066666-22.755556l91.022223-290.133333H113.777778v-113.777778h170.666666V204.8h-11.377777l-22.755556 45.511111c-11.377778 17.066667-22.755556 28.444444-34.133333 39.822222s-28.444444 11.377778-51.2 11.377778h-56.888889V193.422222h22.755555c11.377778 0 22.755556-11.377778 34.133334-39.822222L199.111111 56.888889h119.466667l-11.377778 39.822222h244.622222v113.777778H409.6v238.933333h170.666667v108.088889H398.222222l-11.377778 51.2H455.111111l85.333333 221.866667c5.688889 11.377778 11.377778 17.066667 17.066667 28.444444s11.377778 11.377778 17.066667 11.377778h17.066666v108.088889h-51.2c-28.444444 0-51.2-5.688889-68.266666-11.377778s-22.755556-28.444444-34.133334-56.888889l-79.644444-187.733333L295.822222 910.222222c-11.377778 34.133333-28.444444 51.2-45.511111 56.888889s-39.822222 11.377778-68.266667 11.377778H113.777778z m489.244444-910.222222h415.288889V853.333333c0 22.755556 0 45.511111-5.688889 62.577778s-17.066667 28.444444-34.133333 39.822222-34.133333 17.066667-51.2 17.066667h-324.266667V73.955556z m278.755556 119.466666H739.555556v654.222222h119.466666c5.688889 0 11.377778-5.688889 17.066667-11.377777 5.688889-5.688889 5.688889-11.377778 5.688889-17.066667v-625.777778zM1143.466667 358.4h204.8v443.733333c0 28.444444 0 45.511111 5.688889 51.2s11.377778 5.688889 17.066666 5.688889h28.444445v119.466667H1308.444444c-34.133333 0-56.888889-5.688889-68.266666-22.755556s-22.755556-45.511111-22.755556-79.644444v-398.222222h-73.955555V358.4z m0-295.822222h250.311111v125.155555h-250.311111V62.577778z m318.577777 796.444444h28.444445c11.377778 0 17.066667 0 22.755555-5.688889s5.688889-11.377778 11.377778-28.444444l34.133334-199.111111h136.533333l-39.822222 250.311111c-5.688889 28.444444-11.377778 45.511111-17.066667 56.888889-5.688889 11.377778-17.066667 22.755556-28.444444 28.444444-11.377778 5.688889-34.133333 11.377778-62.577778 11.377778h-79.644445v-113.777778z m17.066667-284.444444v-512h574.577778v352.711111c0 56.888889 0 91.022222-5.688889 108.088889s-11.377778 28.444444-28.444444 34.133333c-17.066667 11.377778-51.2 11.377778-102.4 11.377778H1479.111111z m449.422222-392.533334h-318.577777v278.755556H1877.333333c22.755556 0 34.133333 0 39.822223-5.688889 5.688889-5.688889 11.377778-22.755556 11.377777-62.577778V182.044444z m39.822223 443.733334l28.444444 187.733333c5.688889 22.755556 5.688889 34.133333 11.377778 39.822222 5.688889 5.688889 11.377778 11.377778 17.066666 11.377778h28.444445v113.777778H1991.111111c-28.444444 0-51.2 0-68.266667-5.688889s-22.755556-11.377778-34.133333-28.444444c-5.688889-17.066667-11.377778-34.133333-17.066667-56.888889l-34.133333-261.688889h130.844445zM2161.777778 972.8v-108.088889h39.822222c5.688889 0 11.377778 0 11.377778-5.688889 5.688889-5.688889 11.377778-17.066667 11.377778-39.822222l11.377777-68.266667h130.844445l-28.444445 130.844445c-5.688889 28.444444-17.066667 51.2-34.133333 68.266666-17.066667 17.066667-39.822222 22.755556-73.955556 22.755556H2161.777778z m5.688889-671.288889h210.488889V51.2h142.222222v51.2h540.444444v113.777778h-540.444444v91.022222h540.444444V568.888889c0 17.066667 0 39.822222-5.688889 56.888889 0 17.066667-11.377778 34.133333-28.444444 51.2-17.066667 17.066667-51.2 28.444444-102.4 28.444444H2167.466667V301.511111z m762.311111 119.466667H2309.688889v170.666666h585.955555c11.377778 0 22.755556 0 28.444445-5.688888 5.688889-5.688889 5.688889-11.377778 5.688889-28.444445V420.977778z m-409.6 324.266666l17.066666 79.644445c5.688889 17.066667 5.688889 28.444444 11.377778 28.444444s5.688889 5.688889 11.377778 5.688889h56.888889V967.111111h-56.888889c-39.822222 0-68.266667 0-79.644444-5.688889s-22.755556-11.377778-34.133334-22.755555c-5.688889-11.377778-11.377778-28.444444-17.066666-45.511111l-34.133334-147.911112h125.155556z m102.4 0h125.155555l17.066667 62.577778c5.688889 28.444444 11.377778 45.511111 22.755556 51.2 5.688889 5.688889 17.066667 5.688889 28.444444 5.688889h39.822222v108.088889h-73.955555c-22.755556 0-39.822222 0-51.2-5.688889s-22.755556-11.377778-34.133334-22.755555c-11.377778-11.377778-22.755556-28.444444-28.444444-51.2l-45.511111-147.911112z m438.044444 113.777778V967.111111h-62.577778c-56.888889 0-91.022222-17.066667-96.711111-51.2l-51.2-170.666667h119.466667l28.444444 85.333334c5.688889 11.377778 5.688889 17.066667 11.377778 22.755555s17.066667 5.688889 34.133334 5.688889h17.066666z" fill="#FFA44C" p-id="6636"></path></svg>
            盘问
          </div>
        </div>

        <!-- 筛选题目类型 -->
        <div class="filter" v-if="navOption === 1">
          <div class="filter-title">题型：</div>
          <select v-model="qType">
            <option value="0">全部类型</option>
            <option value="1">编程题</option>
            <option value="2">单选题</option>
            <option value="3">多选题</option>
            <option value="4">判断题</option>
            <option value="5">填空题</option>
            <option value="6">简答题</option>
          </select>
        </div>

        <!-- 知识点盘问 -->
        <div v-if="navOption === 4">
          <KnowledgePoints :userId="userId" />
        </div>

        <!-- 列表部分 -->

        <!-- 待巩固 -->
        <Transition name="slide" mode="out-in">
          <div class="list" v-if="navOption === 1 && questionList.length !== 0">
            <!-- 列表项(待巩固) -->
            <div class="questionItem pending-card" v-for="(item, index) in questionList" :key="index" v-if="navOption === 1">

              <!-- 编程题 -->
              <div class="question" v-if="item.question_type === 'programming'">
                <!-- 分数 -->
                <div class="qscore">{{ item.score }} 分</div>

                <!-- 标题 -->
                <div class="qheader">
                  <div class="qtype">编程题</div>
                  <div class="qtitle">{{ item.question_data.title }}</div>
                </div>

                <!-- 描述 -->
                <div class="qdescription">{{ item.question_data.description }}</div>
                <!-- 知识点 -->
                <div class="qtags">
                  <div v-if="Array.isArray(item.question_data.knowledge_points)" v-for="tag in item.question_data.knowledge_points" :key="tag">
                    {{ tag }}
                  </div>
                  <div v-else>
                    {{ item.question_data.knowledge_points }}
                  </div>
                </div>

                <!-- 内容 -->
                <div class="qcontent">
                  <!-- 代码区 -->
                  <div class="code-editor-container">
                    <div class="line-numbers">
                      <div>原</div>
                      <div>答</div>
                      <div>案</div>
                      <div>代</div>
                      <div>码</div>
                      <div>预</div>
                      <div>览</div>
                      <div>区</div>
                    </div>
                    <textarea v-model="item.user_answer" placeholder="// 此处为原代码展示块" class="code-textarea" spellcheck="false" disabled></textarea>
                  </div>
                </div>

                <!-- 底部 -->
                <div class="qfooter">
                  <!-- 左侧信息 -->
                  <div class="qfLeft">
                    <div class="qcreatTime">
                      <span>创建时间：</span>
                      <span>{{ formatTime(item.created_at) }}</span>
                    </div>
                    <div class="qattemptCount">
                      <span>重练次数：</span>
                      <span>{{ item.attempt_count }}</span>
                    </div>
                    <div class="qdifficulty">
                      <span>本题难度：</span>
                      <span>{{ item.question_data.difficulty || "无" }}</span>
                    </div>
                  </div>
                  <!-- 右侧按钮 -->
                  <div class="qfRight">
                    <div class="reStartBtn" @click="openPopup(index)">重新练习</div>
                    <div class="deleteBtn" @click="deleteQuestion(item.record_id)">删除</div>
                  </div>
                </div>
              </div>

              <!-- 非编程题：单选 / 多选 / 判断 / 填空 / 简答 -->
              <div class="question" v-else>
                <!-- 分数 -->
                <div class="qscore">{{ item.score }} 分</div>

                <!-- 题型 + 题目标题区域 -->
                <div class="qheader">
                  <div class="qtype">
                    <span v-if="item.question_type === 'single_choice'">单选题</span>
                    <span v-else-if="item.question_type === 'multiple_choice'">多选题</span>
                    <span v-else-if="item.question_type === 'judge'">判断题</span>
                    <span v-else-if="item.question_type === 'fill_blank'">填空题</span>
                    <span v-else-if="item.question_type === 'short_answer'">简答题</span>
                  </div>
                  <div class="qtitle">{{ item.question_data.question }}</div>
                </div>

                <!-- 题干 -->
                <div class="qcontent otherContent">

                  <!-- 单选、多选：渲染选项 -->
                  <div class="qoptions" v-if="item.question_type === 'single_choice' || item.question_type === 'multiple_choice'">
                    <div class="option-item" v-for="opt in item.question_data.options" :key="opt">
                      {{ opt }}
                    </div>
                  </div>

                  <!-- 判断题：不单独展示对错选项 -->
                </div>

                <!-- 知识点 -->
                <div class="qtags" v-if="item.knowledge_points && item.knowledge_points.length">
                  <div v-if="Array.isArray(item.knowledge_points)" v-for="tag in item.knowledge_points" :key="tag">
                    {{ tag }}
                  </div>
                  <div v-else>
                    {{ item.knowledge_points }}
                  </div>
                </div>

                <!-- 作答 & 正确答案 区域 -->
                <div class="answer-box">
                  <div class="ans-row">
                    <span class="ans-label">我的答案：</span>
                    <span class="ans-text">{{ item.user_answer || "未作答" }}</span>
                  </div>
                  <div class="ans-row">
                    <span class="ans-label">正确答案：</span>
                    <span class="ans-text">{{ item.correct_answer }}</span>
                  </div>
                  <!-- 解析 -->
                  <div class="ans-row" v-if="item.question_data.explanation">
                    <span class="ans-label">题目解析：</span>
                    <span class="ans-text">{{ item.question_data.explanation }}</span>
                  </div>
                </div>

                <!-- 底部信息栏（时间、次数、难度 + 操作按钮） -->
                <div class="qfooter">
                  <div class="qfLeft">
                    <div class="qcreatTime">
                      <span>创建时间：</span>
                      <span>{{ formatTime(item.created_at) }}</span>
                    </div>
                    <div class="qattemptCount">
                      <span>作答次数：</span>
                      <span>{{ item.attempt_count }}</span>
                    </div>
                    <div class="qdifficulty">
                      <span>本题难度：</span>
                      <span>{{ item.difficulty || "无" }}</span>
                    </div>
                  </div>
                  <div class="qfRight">
                    <div class="reStartBtn" @click="openPopup(index)">重新练习</div>
                    <div class="deleteBtn" @click="deleteQuestion(item.record_id)">删除</div>
                  </div>
                </div>
              </div>

            </div>

            <!-- 翻页 -->
            <div class="pageCt">
              <div class="upPage pageBtn" @click="prevPage()" :class="page === 1 ? 'disabled' : ''">上一页</div>
              <div class="pageCount">{{ page }}/{{ totalPages }}</div>
              <div class="downPage pageBtn" @click="nextPage()" :class="page === totalPages ? 'disabled' : ''">下一页</div>
            </div>
          </div>
        </Transition>

        <!-- 已掌握 -->
        <Transition name="slide" mode="out-in">
          <div class="list" v-if="navOption === 2 && okList.length !== 0">

            <!-- 列表项(已掌握) -->
            <div class="questionItem ok-card" v-for="(item, index) in okList" :key="index" v-if="navOption === 2">

              <div class="question">

                <!-- 掌握提示 -->
                <div class="qscore qok">
                  <svg t="1780924134455" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5719" width="35" height="35"><path d="M512.07379 0a511.973799 511.973799 0 1 0 361.995592 149.978207A511.973799 511.973799 0 0 0 512.07379 0z m-35.537005 710.137775a45.174159 45.174159 0 0 1-66.255433 0L219.345241 519.803987a47.282286 47.282286 0 1 1 66.857755-66.857755l157.808394 158.410716 298.149448-297.547125a47.282286 47.282286 0 1 1 66.857755 66.857755z" fill="#00CC7B" p-id="5720"></path></svg>
                  <div>已掌握</div>
                </div>

                <!-- 标题 -->
                <div class="qheader">
                  <div class="qtype">
                    {{ questionType(item.question_type) }}
                  </div>
                  <div class="qtitle">{{ item.question_data.title || item.question_data.question }}</div>
                </div>

                <!-- 描述 -->
                <div class="qdescription">{{ item.question_data.description || item.question_data.content }}</div>
                <div class="qdescription" v-for="i in item.question_data.options">
                  {{ i }}<br>
                </div>
                <div class="qdescription" v-if="item.question_type === 'judge'">正确&nbsp;&nbsp;错误</div>
                <!-- 知识点 -->
                <div class="qtags">
                  <div v-for="tag in item.question_data.knowledge_points" :key="tag">{{ tag }}</div>
                </div>

                <!-- 底部 -->
                <div class="qfooter">
                  <div class="qfLeft">
                    <div class="qcreatTime">
                      <span>创建时间：</span>
                      <span>{{ formatTime(item.created_at) }}</span>
                    </div>
                    <div class="qattemptCount">
                      <span>重练次数：</span>
                      <span>{{ item.attempt_count }}</span>
                    </div>
                    <div class="qdifficulty">
                      <span>本题难度：</span>
                      <span>{{ item.question_data.difficulty || "无" }}</span>
                    </div>
                  </div>

                  <div class="qfRight">
                    <div class="reStartBtn" @click="openSituation(index)">
                      查看得分趋势
                    </div>
                  </div>
                </div>
              </div>

            </div>

            <!-- 翻页 -->
            <div class="pageCt">
              <div class="upPage pageBtn" @click="prevPage()" :class="page === 1 ? 'disabled' : ''">
                上一页
              </div>
              <div class="pageCount">
                {{ page }}/{{ totalPages }}
              </div>
              <div class="downPage pageBtn" @click="nextPage()" :class="page === totalPages ? 'disabled' : ''">
                下一页
              </div>
            </div>
          </div>
        </Transition>

        <!-- 易错题 -->
        <Transition name="slide" mode="out-in">
          <div class="frequentlyPage-wrap" v-if="navOption === 3 && frequentlyList.length !== 0">

            <!-- 易错题统计卡片 -->
            <div class="fw-stats-row" v-if="frequentlyStats && frequentlyStats.total">
              <div class="fw-stat-card">
                <div class="fw-stat-num">{{ frequentlyStats.total || 0 }}</div>
                <div class="fw-stat-label">易错题总数</div>
              </div>
              <div class="fw-stat-card">
                <div class="fw-stat-num">{{ frequentlyStats.threshold || 0 }}</div>
                <div class="fw-stat-label">易错阈值</div>
              </div>
              <div class="fw-stat-card">
                <div class="fw-stat-num">{{ frequentlyStats.max_attempts || 0 }}</div>
                <div class="fw-stat-label">最多错误次数</div>
              </div>
              <div class="fw-stat-card">
                <div class="fw-stat-num">{{ frequentlyStats.avg_attempts || 0 }}</div>
                <div class="fw-stat-label">平均错误次数</div>
              </div>
            </div>

            <!-- 薄弱知识点 -->
            <div class="fw-kp-area" v-if="frequentlyStats.weak_knowledge_points && frequentlyStats.weak_knowledge_points.length">
              <span class="fw-kp-title">薄弱知识点：</span>
              <span class="fw-kp-tag" v-for="kp in frequentlyStats.weak_knowledge_points" :key="kp.knowledge_point">
                {{ kp.knowledge_point }}({{ kp.count }})
              </span>
            </div>

            <!-- 易错题列表 -->
            <div class="list">
              <div class="questionItem fw-card" v-for="(item, index) in frequentlyList" :key="item.record_id || index">

                <!-- 左侧环形进度 -->
                <div class="fw-ring-wrap">
                  <svg class="fw-ring" viewBox="0 0 80 80">
                    <circle class="fw-ring-bg" cx="40" cy="40" r="34"></circle>
                    <circle class="fw-ring-fg" cx="40" cy="40" r="34"
                      :style="{ strokeDasharray: 213.628, strokeDashoffset: 213.628 - Math.min(item.fw_attempt_count || item.attempt_count || 0, 20) / 20 * 213.628 }">
                    </circle>
                  </svg>
                  <div class="fw-ring-center">
                    <span class="fw-ring-num">{{ item.fw_attempt_count || item.attempt_count || 0 }}</span>
                    <span class="fw-ring-label">错误次数</span>
                  </div>
                </div>

                <!-- 右侧内容 -->
                <div class="fw-body">
                  <!-- 题型徽章 + 标题 -->
                  <div class="fw-header">
                    <span class="fw-badge">{{ questionType(item.question_type) }}</span>
                    <span class="fw-score">{{ item.score || 0 }} 分</span>
                    <span class="fw-frequent-badge">🔥 易错题</span>
                  </div>

                  <!-- 题目内容 -->
                  <div class="fw-question">
                    {{ item.question_data.title || item.question_data.question || item.question_data.description || '无题目内容' }}
                  </div>

                  <!-- 题目描述/选项 -->
                  <!-- <div class="fw-description" v-if="item.question_type === 'programming' && item.question_data.description">
                    {{ item.question_data.description }}
                  </div> -->
                  <div class="fw-options" v-if="item.question_type !== 'programming' && item.question_data.options && item.question_data.options.length">
                    <div class="fw-option-item" v-for="(opt, oi) in item.question_data.options" :key="oi">{{ opt }}</div>
                  </div>

                  <!-- 知识点标签 -->
                  <div class="fw-kp-tags" v-if="item.knowledge_points && item.knowledge_points.length">
                    <span class="fw-kp-tag" v-for="kp in (Array.isArray(item.knowledge_points) ? item.knowledge_points : [item.knowledge_points])" :key="kp">{{ kp }}</span>
                  </div>

                  <!-- 错误次数进度条 -->
                  <div class="fw-attempt-bar">
                    <span class="fw-attempt-label">错误 {{ item.attempt_count || 0 }} 次</span>
                    <div class="fw-bar-bg">
                      <div class="fw-bar-fill" :style="{ width: Math.min((item.attempt_count || 0) / 20 * 100, 100) + '%' }"></div>
                    </div>
                    <span class="fw-attempt-count">共 {{ (item.attempts && item.attempts.length) || 0 }} 次尝试</span>
                  </div>

                  <!-- 底部操作 -->
                  <div class="fw-footer">
                    <div class="fw-time">{{ formatTime(item.created_at) }}</div>
                    <div class="fw-actions">
                      <div class="fw-retry-btn" @click="openFrequentlyPopup(index)">✏️ 重新练习</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 翻页 -->
              <div class="pageCt">
                <div class="upPage pageBtn" @click="prevPage()" :class="page === 1 ? 'disabled' : ''">上一页</div>
                <div class="pageCount">{{ page }}/{{ totalPages }}</div>
                <div class="downPage pageBtn" @click="nextPage()" :class="page === totalPages ? 'disabled' : ''">下一页</div>
              </div>
            </div>
          </div>
        </Transition>

        <!-- 空列表 -->
        <div class="emptyList" v-if="navOption !== 4 && ((navOption === 1 && questionList.length === 0) || (navOption === 2 && okList.length === 0) || (navOption === 3 && frequentlyList.length === 0))">
          <div class="nullPost">
            <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
          </div>
          <div>暂无信息</div>
        </div>

      </div>
    </div>

  </div>

  <!-- 弹窗：重练非编程题+学习资料推荐 -->
  <div class="popup" v-if="showPopup">
    <!-- 关闭按钮 -->
    <div class="quit" @click="closePopup()">
      <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5824" width="40" height="40"><path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" p-id="5825" fill="#ffffff"></path><path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" p-id="5826" fill="#ffffff"></path></svg>
      <div>退出</div>
    </div>
    <div class="cardArea">
      <!-- 左右分栏布局 -->
      <div class="content-wrap">
        <!-- 左侧：编程题跳转按钮 -->
        <div class="left-box programming" v-if="showQuestion.question_type === 'programming'">
          <!-- 编程题 -->
          <div class="submit-btn jumpBtn" @click="goAnswer(4,(showQuestion.question_data.id?.length ? showQuestion.question_data.id : showQuestion.question_data.problem_id),showQuestion.record_id)">
            跳转编程题页重练 >
          </div>
        </div>
        <!-- 左侧：重新练习答题区域 -->
        <div class="left-box" v-else>
          <div class="topTitle">
            <div class="type">
              {{ questionType(showQuestion.question_type) }}
            </div>
            <div class="Q">{{ showQuestion.question_data.question }}</div>
          </div>

          <!-- 1. 单选题 -->
          <div class="question-card" v-if="showQuestion.question_type === 'single_choice'">
            <div class="options-grid">
              <div v-for="(option, index) in showQuestion.question_data.options" :key="index" class="option-card" :class="{ 'radio-selected': answerIndex === index }" @click="!hasSubmitted && (answerIndex = index)">
                <div class="option-letter">{{ String.fromCharCode(65 + index) }}</div>
                <div class="option-text">{{ option }}</div>
                <div class="radio-icon"></div>
              </div>
            </div>
          </div>

          <!-- 2. 多选题 -->
          <div class="question-card" v-if="showQuestion.question_type === 'multiple_choice'">
            <div class="options-grid">
              <div v-for="(option, index) in showQuestion.question_data.options" :key="index" class="option-card" :class="{ 'checkbox-selected': multipleIndex.includes(index) }" @click="!hasSubmitted && toggleMultiple(index)">
                <div class="option-letter">{{ String.fromCharCode(65 + index) }}</div>
                <div class="option-text">{{ option }}</div>
                <div class="checkbox-icon"></div>
              </div>
            </div>
            <div v-if="multipleIndex.length > 0" class="tip-text">
              已选择 {{ multipleIndex.length }} 项
            </div>
          </div>

          <!-- 3. 判断题 -->
          <div class="question-card" v-if="showQuestion.question_type === 'judge'">
            <div class="judge-grid">
              <div class="option-card" :class="{ 'radio-selected': judgeAnswer === '正确' }" @click="!hasSubmitted && (judgeAnswer = '正确')">
                <div class="option-letter">√</div>
                <div class="option-text">正确</div>
                <div class="radio-icon"></div>
              </div>
              <div class="option-card" :class="{ 'radio-selected': judgeAnswer === '错误' }" @click="!hasSubmitted && (judgeAnswer = '错误')">
                <div class="option-letter">×</div>
                <div class="option-text">错误</div>
                <div class="radio-icon"></div>
              </div>
            </div>
          </div>

          <!-- 4. 填空题 / 简答题：文本框作答 -->
          <div class="A" v-if="showQuestion.question_type === 'fill_blank' || showQuestion.question_type === 'short_answer'">
            <textarea rows="4" placeholder="请输入您的答案..." class="answer-textarea" v-model="answer" :disabled="hasSubmitted"></textarea>
          </div>

          <!-- 分析结果展示 -->
          <div class="analysis-result" v-if="analysisResult">
            <div class="result-header">
              <span class="result-icon" :class="analysisResult.is_correct ? 'correct' : 'wrong'">
                {{ analysisResult.is_correct ? '✓' : '✗' }}
              </span>
              <span class="result-text">
                {{ analysisResult.is_correct ? '回答正确！' : '回答错误' }}
              </span>
              <span class="result-score">得分：{{ analysisResult.score || 0 }} 分</span>
            </div>
            <div class="result-body" v-if="analysisResult.message">
              <p>{{ analysisResult.message }}</p>
            </div>
            <div class="result-body" v-if="analysisResult.correct_answer">
              <p><strong>正确答案：</strong>{{ analysisResult.correct_answer }}</p>
            </div>
            <div class="result-body" v-if="analysisResult.user_answer">
              <p><strong>你的答案：</strong>{{ analysisResult.user_answer }}</p>
            </div>
          </div>

          <!-- 提交按钮 / 重新练习按钮 -->
          <div class="submit-btn" v-if="!hasSubmitted" @click="handleSubmitAnalysis" :class="{ 'disabled': isSubmitting }">
            {{ submitBtnText }}
          </div>
          <div class="submit-btn reset-btn" v-else @click="handleResetPractice">
            重新练习
          </div>
        </div>

        <!-- 右侧：题目&文档详情面板 -->
        <!-- 右侧区域：有推荐题目 / 空状态 -->
        <div class="right-box" v-if="recommend && recommend.length">
          <div class="tab-content">
            <el-scrollbar height="100%" width="100%">
              <div class="scroll">
                <!-- 提示信息 -->
                <div class="recommend-tip">
                  <span class="tip-icon">💡</span>
                  <span>该题已错多次，为您推荐以下相关材料</span>
                </div>
                <!-- 遍历推荐题目列表（缩略展示） -->
                <div class="detail-item" v-for="(item, idx) in recommend" :key="idx"> 
                  <!-- 标题 + 基础信息 -->
                  <h4>【{{ questionType(item.sub_topic) || questionType(item.topic) || '通用' }}】 - {{ item.title || '推荐补救题目' }}</h4>
                  <p class="label">
                    难度：{{ (item.difficulty === 1 ? '简单' : (item.difficulty === 2 ? '中等' : (item.difficulty === 3 ? '困难' : item.difficulty))) || '无' }}&nbsp;&nbsp;|&nbsp;
                    知识点：{{ Array.isArray(item.knowledge_points) ? item.knowledge_points.join('、') : ((item.knowledge_points) || '无') }}
                  </p>
                  <!-- 按钮区分：编程题 / 普通题 -->
                  <div class="btn-group">
                    <button class="operate-btn jump-btn" @click="handleRecommendJump(item)">
                      {{ isProgrammingResource(item) ? '【编程题】跳转作答 >' : '<【理论题】查看题目' }}
                    </button>
                  </div>
                </div>

                <!-- AI生成更多推荐资料 -->
                <div class="aiGet" @click="handleAiGenerate" v-if="!isLoadingRecommend">
                  AI生成更多推荐资料
                </div>
                <div class="aiGet loading" v-else>
                  AI生成中，请稍候...
                </div>
              </div>
            </el-scrollbar>

          </div>
        </div>

        <div class="right-box" v-else>
          <div class="popupNull">
            <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
            <div class="popupNullText">{{ isLoadingRecommend ? '加载中...' : '暂无推荐材料' }}</div>
            <!-- AI生成按钮（空状态时也显示） -->
            <div class="aiGet empty-ai" @click="handleAiGenerate" v-if="!isLoadingRecommend">
              AI生成推荐材料
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- 弹窗：查看学习趋势 -->
  <div class="popup" v-if="showSituation">
    <!-- 关闭按钮 -->
    <div class="quit" @click="closeSituation()">
      <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" width="40" height="40">
        <path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" fill="#ffffff"></path>
        <path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" fill="#ffffff"></path>
      </svg>
      <div>退出</div>
    </div>
    <div class="cardArea okArea">
      <!-- 左侧：折线图 -->
      <div class="left-box">
        <div id="answerChart" style="width: 100%; height: 100%; border-radius: 12px;"></div>
      </div>

      <!-- 右侧：从 okData 渲染答题详情 -->
      <div class="right-box">
        <!-- 题目基础信息 -->
        <div class="q-base">
          <h2 class="q-title">{{ okData.question_data?.title || okData.question_data?.question }}</h2>
          <div class="q-meta">
            <span class="tag easy">{{ okData.question_data?.difficulty || okData?.question_type }}</span>
            <span>
              知识点：{{
                (() => {
                  const points = okData.question_data?.knowledge_points || okData?.knowledge_points;
                  if (Array.isArray(points)) {
                    return points.join('、');
                  }
                  return points || '无知识点';
                })()
              }}
            </span>
          </div>
          <div class="q-stat">
            <div>作答次数：{{ okData.attempt_count }} 次</div>
            <div>最终得分：{{ okData.mastered_score }} 分</div>
          </div>
        </div>

        <div class="divider"></div>

        <!-- 作答次数列表（点击切换） -->
        <div class="attempt-list">
          <div class="attempt-item" :class="{ active: activeIdx === idx }" v-for="(item, idx) in okData.attempts" :key="idx" @click="
            activeIdx = idx;
            curAnswer = item.user_answer;
            curScore = item.score;
            curVerdict = item.verdict;
            highlightAttempt('answerChart', idx)
          ">
            <span>第{{ item.attempt_number }}次</span>&nbsp;
            <span class="score" :class="item.verdict === 'Accepted' ? 'ok' : 'err'">
              {{ item.score }} 分
            </span>
          </div>
        </div>

        <!-- 本次作答内容 -->
        <div class="answer-panel" v-if="curAnswer">
          <div class="panel-head">
            <span>本次作答</span>
            <span class="mini-score" :class="curVerdict === 'Accepted' ? 'ok' : 'err'">
              {{ curScore }} 分 · {{ curVerdict }}
            </span>
          </div>
          <pre class="answer-code">{{ curAnswer }}</pre>
        </div>
      </div>
    </div>
  </div>

  <!-- 推荐题目详情弹窗（理论题） -->
  <div class="popup" v-if="showRecommendDetail && recommendDetailData">
    <div class="quit" @click="closeRecommendDetail">
      <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5824" width="40" height="40"><path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" p-id="5825" fill="#ffffff"></path><path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" p-id="5826" fill="#ffffff"></path></svg>
      <div>退出</div>
    </div>
    <div class="cardArea recommend-detail">
      <div class="recommend-detail-content">
        <div class="detail-header">
          <span class="type-badge">
            {{ 
              recommendDetailData.sub_topic === 'single_choice' ? '单选题' :
              recommendDetailData.sub_topic === 'multiple_choice' ? '多选题' :
              recommendDetailData.sub_topic === 'judge' ? '判断题' :
              recommendDetailData.sub_topic === 'fill_blank' ? '填空题' :
              recommendDetailData.sub_topic === 'short_answer' ? '简答题' :
              '理论题'
            }}
          </span>
          <h3 class="detail-title">{{ recommendDetailData.question || recommendDetailData.content || recommendDetailData.title }}</h3>
        </div>

        <!-- 选项展示 -->
        <div v-if="recommendDetailData.options && recommendDetailData.options.length > 0">
          <!-- 单选题 -->
          <div v-if="recommendDetailData.sub_topic === 'single_choice'">
            <div class="options-grid">
              <div v-for="(option, index) in recommendDetailData.options" :key="index" 
                   class="option-card" 
                   :class="{ 'radio-selected': recommendDetailAnswerIndex === index }" 
                   @click="!recommendDetailResult && (recommendDetailAnswerIndex = index)">
                <div class="option-letter">{{ String.fromCharCode(65 + index) }}</div>
                <div class="option-text">{{ option }}</div>
                <div class="radio-icon"></div>
              </div>
            </div>
          </div>
          
          <!-- 多选题 -->
          <div v-if="recommendDetailData.sub_topic === 'multiple_choice'">
            <div class="options-grid">
              <div v-for="(option, index) in recommendDetailData.options" :key="index" 
                   class="option-card" 
                   :class="{ 'checkbox-selected': recommendDetailMultipleIndex.includes(index) }" 
                   @click="!recommendDetailResult && toggleRecommendMultiple(index)">
                <div class="option-letter">{{ String.fromCharCode(65 + index) }}</div>
                <div class="option-text">{{ option }}</div>
                <div class="checkbox-icon"></div>
              </div>
            </div>
            <div v-if="recommendDetailMultipleIndex.length > 0" class="tip-text">
              已选择 {{ recommendDetailMultipleIndex.length }} 项
            </div>
          </div>
        </div>

        <!-- 判断题 -->
        <div v-if="recommendDetailData.sub_topic === 'judge'">
          <div class="judge-grid">
            <div class="option-card" :class="{ 'radio-selected': recommendDetailJudgeAnswer === '正确' }" 
                 @click="!recommendDetailResult && (recommendDetailJudgeAnswer = '正确')">
              <div class="option-letter">√</div>
              <div class="option-text">正确</div>
              <div class="radio-icon"></div>
            </div>
            <div class="option-card" :class="{ 'radio-selected': recommendDetailJudgeAnswer === '错误' }" 
                 @click="!recommendDetailResult && (recommendDetailJudgeAnswer = '错误')">
              <div class="option-letter">×</div>
              <div class="option-text">错误</div>
              <div class="radio-icon"></div>
            </div>
          </div>
        </div>

        <!-- 填空题/简答题 -->
        <div v-if="recommendDetailData.sub_topic === 'fill_blank' || recommendDetailData.sub_topic === 'short_answer'">
          <textarea rows="4" placeholder="请输入您的答案..." class="answer-textarea" 
                    v-model="recommendDetailTextAnswer" :disabled="!!recommendDetailResult"></textarea>
        </div>

        <!-- 分析结果 -->
        <div class="analysis-result" v-if="recommendDetailResult">
          <div class="result-header">
            <span class="result-icon" :class="recommendDetailResult.is_correct ? 'correct' : 'wrong'">
              {{ recommendDetailResult.is_correct ? '✓' : '✗' }}
            </span>
            <span class="result-text">
              {{ recommendDetailResult.is_correct ? '回答正确！' : '回答错误' }}
            </span>
            <span class="result-score">得分：{{ recommendDetailResult.score || 0 }} 分</span>
          </div>
          <div class="result-body" v-if="recommendDetailResult.message">
            <p>{{ recommendDetailResult.message }}</p>
          </div>
          <div class="result-body" v-if="recommendDetailResult.correct_answer">
            <p><strong>正确答案：</strong>{{ recommendDetailResult.correct_answer }}</p>
          </div>
          <div class="result-body" v-if="recommendDetailResult.user_answer">
            <p><strong>你的答案：</strong>{{ recommendDetailResult.user_answer }}</p>
          </div>
        </div>

        <!-- 提交按钮 -->
        <div class="submit-btn" v-if="!recommendDetailResult" @click="submitRecommendQuestion" :class="{ 'disabled': recommendDetailSubmitting }">
          {{ recommendDetailSubmitting ? '提交中...' : '提交答案' }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 侧滑动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease-in-out;
}

.slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.slide-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
/* 回顶按钮 */
.back-top {
  z-index: 1;
  position: fixed;
  right: 30px;
  bottom: 50px;
  width: 50px;
  height: 50px;
  background: var(--primary);
  color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border-radius: 50%;
  text-align: center;
  line-height: 45px;
  font-size: 30px;
  cursor: pointer;
  transition: all 0.3s ease;
  transform: scale(1);
}
.back-top:hover {
  box-shadow: var(--shadow-brand);
  transform: scale(1.15);
}

/* ====================== 编码输入区美化 (IDE 风格) ====================== */
.code-editor-container {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 400px;
  border: 1px solid #3e3e42;
  border-radius: 6px;
  overflow: hidden;
  background-color: #1e1e1e;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 行号区域 */
.line-numbers {
  width: 40px;
  background-color: #1e1e1e;
  color: #858585;
  text-align: right;
  padding: 15px 8px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  user-select: none;
  border-right: 1px solid #333;
  overflow: hidden;
}

/* 文本输入区域 */
.code-textarea {
  flex: 1;
  background-color: transparent;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  padding: 15px;
  border: none;
  resize: vertical;
  outline: none;
  white-space: pre;
  overflow-x: auto;
}
.code-textarea::placeholder {
  color: #6a6a6a;
  font-style: italic;
}

.code-editor-container:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary) inset, 0 4px 12px rgba(45, 125, 219, 0.1);
}

.container {
  padding-top: 10px;
  min-width: 1314px;
  width: 100%;
  height: 100%;
  background: transparent;
}
.title {
  text-align: center;
  margin-bottom: 20px;
}
.title h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
}
.subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

.main {
  width: 100%;
  min-height: 75vh;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
  background: transparent;
}
.main .summary {
  position: absolute;
  top: 0;
  left: 0;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border-radius: 20px;
  padding: 20px 10px;
  padding-top: 45px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.summary .count {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-title);
}
.summary .title {
  font-size: 16px;
  color: var(--text-gray);
  margin: 0;
}
.summary .BigTitle {
  position: absolute;
  top: 0px;
  font-size: 18px;
  font-weight: 700;
  color: var(--main-delete-hover);
  text-align: center;
  border: none;
}
.summary>div {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 1px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 10px;
  transition: all 0.3s ease-in-out;
}
.summary>div:not(:nth-child(2)) {
  cursor: pointer;
}

.summary .total {
  border: 1px solid var(--main-delete);
}
.total>div:first-child {
  color: var(--main-delete-hover);
}
.total>div:last-child {
  color: var(--main-delete);
}

.summary .pending {
  border: 1px solid var(--coming);
}
.pending>div:first-child {
  color: var(--coming-hover);
}
.pending>div:last-child {
  color: var(--coming);
}

.summary .resolved {
  border: 1px solid var(--pass);
}
.resolved>div:first-child {
  color: var(--pass-hover);
}
.resolved>div:last-child {
  color: var(--pass);
}

.summary .frequently {
  border: 1px solid var(--main-delete);
}
.frequently>div:first-child {
  color: var(--main-delete-hover);
}
.frequently>div:last-child {
  color: var(--main-delete);
}

.summary>div:nth-child(2):hover {
  background-color: var(--main-fail-status);
}
.summary>div:nth-child(3).show,
.summary>div:nth-child(3):hover {
  background-color: var(--coming-bg-color);
}
.summary>div:nth-child(4).show,
.summary>div:nth-child(4):hover {
  background-color: var(--pass-bg-color);
}
.summary>div:last-child.show,
.summary>div:last-child:hover {
  background-color: var(--main-fail-status);
}

.main .content {
  margin-left: 125px;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  width: 90%;
  min-height: 75vh;
  padding: 24px;
  position: relative;
  overflow: hidden;
}
.main .content::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary));
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}

.content .filter {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.filter-title {
  font-size: 18px;
  font-weight: bold;
  white-space: nowrap;
}
.filter select {
  padding: 6px 5px;
  border: 1px solid var(--text-gray);
  border-radius: 6px;
  outline: none;
  font-size: 14px;
  min-width: 110px;
  transition: border 0.2s;
}
.filter select:focus {
  border-color: var(--primary);
}

.content .nav {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  background: transparent;
  backdrop-filter: blur(10px);
  padding: 0 20px;
  height: 56px;
  align-items: center;
  justify-content: center;
}

.content .emptyList {
  width: 100%;
  height: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.emptyList img {
  width: 200px;
}
.emptyList>div:last-child {
  color: var(--text-gray);
  font-size: 16px;
}

.pendingPage,
.resolvedPage {
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-body);
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  margin-bottom: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  letter-spacing: 0;
  height: 36px;
  display: flex;
  align-items: center;
}

.pendingPage:hover {
  color: var(--coming);
  border-color: var(--coming);
  box-shadow: 0 4px 16px rgba(230, 162, 60, 0.15);
  transform: translateY(-2px);
}
.resolvedPage:hover {
  color: var(--pass);
  border-color: var(--pass);
  box-shadow: 0 4px 16px rgba(103, 194, 58, 0.15);
  transform: translateY(-2px);
}

.pendingPage.active {
  color: #fff;
  background-color: var(--coming);
  border-color: var(--coming);
  box-shadow: 0 4px 16px rgba(230, 162, 60, 0.2);
}
.resolvedPage.active {
  color: #fff;
  background-color: var(--pass);
  border-color: var(--pass);
  box-shadow: 0 4px 16px rgba(103, 194, 58, 0.2);
}

.pendingPage::after,
.resolvedPage::after {
  display: none;
}

.list .pageCt {
  font-size: 14px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  padding: 20px 0;
}

.pageCt .pageBtn {
  color: var(--primary);
  border: 1px solid var(--border-color);
  padding: 8px 20px;
  border-radius: 24px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  background: var(--bg-card);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.pageCt .pageBtn:not(.disabled):hover {
  color: #fff;
  background-color: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
  transform: translateY(-1px);
}
.pageCt .pageBtn.disabled {
  color: var(--text-gray);
  border-color: var(--border-color);
  cursor: not-allowed;
}
.pageCt .pageBtn.disabled:hover {
  color: var(--text-gray);
  border-color: var(--border-color);
  background: var(--bg-card);
  transform: none;
}

.pageCt .pageCount {
  padding: 8px 20px;
  background: var(--bg-hover);
  border-radius: 24px;
  color: var(--text-body);
  font-weight: 500;
  min-width: 80px;
  text-align: center;
}

.list {
  padding: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.list .questionItem {
  width: 100%;
  min-height: 200px;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 20px;
  border-radius: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}
.list .questionItem::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--primary), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}
.questionItem:hover {
  box-shadow: 0 12px 40px rgba(45, 125, 219, 0.18);
  border-color: var(--primary);
  transform: translateY(-4px) scale(1.005);
}
.questionItem:hover::before {
  opacity: 1;
}
.questionItem .question {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.question .qscore {
  position: absolute;
  right: 10px;
  top: 0;
  font-size: 20px;
  color: var(--text-gray);
  font-weight: 700;
}
.questionItem .qok {
  top: -10px;
  font-size: 25px;
  color: var(--pass);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.question .qheader {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
.qheader .qtype {
  padding: 0 10px;
  font-size: 16px;
  border: 1px solid var(--primary);
  border-radius: 20px;
  color: var(--primary);
  font-weight: 700;
}
.qheader .qtitle {
  max-width: 1100px;
  font-size: 18px;
  font-weight: 700;
}
.question .qdescription {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-gray);
}
.question .qtags {
  padding: 0 10px;
  padding-bottom: 10px;
  display: flex;
  gap: 10px;
  border-bottom: 1px solid var(--border-color);
}
.qtags>div {
  padding: 0 10px;
  font-size: 14px;
  border: 1px solid var(--pass);
  border-radius: 20px;
  color: var(--pass);
  font-weight: 500;
}

.question .qcontent {
  padding: 10px 150px;
}

.question .qfooter {
  color: var(--text-gray);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.qfooter .qfLeft,
.qfooter .qfRight {
  display: flex;
  align-items: center;
  gap: 20px;
}

.qfLeft>div>span:first-child {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}

.qfRight>div {
  font-size: 14px;
  padding: 6px 16px;
  color: var(--primary);
  border: 1px solid var(--primary);
  border-radius: 10px;
  transition: all 0.2s ease-in-out;
  font-weight: 500;
}
.qfRight>div:first-child:hover {
  cursor: pointer;
  background-color: var(--primary);
  color: #fff;
}
.qfRight>div:last-child {
  color: var(--main-delete);
  border-color: var(--main-delete);
}
.qfRight>div:last-child:hover {
  cursor: pointer;
  background-color: var(--main-delete);
  color: #fff;
}

.qoptions {
  font-size: 18px;
  color: var(--text-gray)
}
.option-item {
  margin: 4px 0;
  line-height: 1.5;
}
.question .otherContent {
  padding: 0 90px;
}
.answer-box {
  margin: 12px 0;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
}
.dark .answer-box {
  background: var(--bg-card);
}
.ans-row {
  margin: 6px 0;
  line-height: 1.5;
}
.ans-label {
  font-weight: bold;
  color: #666;
}
.dark .ans-label {
  color: var(--text-gray);
}

.popup {
  z-index: 2;
  position: fixed;
  bottom: 0;
  left: 0;
  min-width: 1500px;
  width: 100%;
  min-height: 100vh;
  background: rgba(0, 0, 0, 0.5);
}
.popup .cardArea {
  margin: 100px auto;
  margin-bottom: 0;
  width: 1500px;
  min-height: 785px;
  max-height: 785px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
  border-radius: 10px;
}

.popup .type {
  display: inline-block;
  padding: 6px 14px;
  background: var(--grad-primary);
  color: var(--bg-page);
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-lg);
  letter-spacing: 0.5px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-brand);
}

.popup .Q {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-title);
  line-height: 1.6;
  margin-bottom: 20px;
}

.popup .A {
  margin-top: 20px;
  position: relative;
}

.popup .answer-textarea {
  width: 100%;
  padding: 16px 18px;
  font-size: 15px;
  font-family: inherit;
  line-height: 1.6;
  color: var(--text-body);
  background: var(--bg-card);
  border: 1.5px solid var(--border-color);
  border-radius: var(--radius-lg);
  outline: none;
  resize: vertical;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  box-shadow: 0 1px 2px var(--shadow-color);
}

.popup .answer-textarea:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.1);
}

.popup .answer-textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-fade);
  background: var(--bg-card);
}

.popup .answer-textarea::placeholder {
  color: var(--text-gray);
  font-size: 14px;
  opacity: 0.7;
  transition: opacity 0.3s ease;
}

.popup .answer-textarea:focus::placeholder {
  opacity: 0.4;
}

.popup .A::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  width: 0;
  height: 2px;
  background: var(--grad-primary);
  transition: all 0.4s ease;
  border-radius: 2px;
  transform: translateX(-50%);
}

.popup .A:focus-within::after {
  width: 60px;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.answer-textarea::-webkit-scrollbar {
  width: 6px;
}
.answer-textarea::-webkit-scrollbar-track {
  background: var(--bgc-light);
  border-radius: 3px;
}
.answer-textarea::-webkit-scrollbar-thumb {
  background: var(--primary);
  border-radius: 3px;
  opacity: 0.6;
}
.answer-textarea::-webkit-scrollbar-thumb:hover {
  background: var(--primary-hv);
}

.popup .question-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.popup .type-badge {
  display: inline-block;
  padding: 6px 14px;
  background: var(--grad-primary);
  color: var(--bg-card);
  font-size: 12px;
  font-weight: 600;
  border-radius: 20px;
  margin-bottom: 16px;
}
.popup .question-text {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-title);
  line-height: 1.5;
  margin-bottom: 24px;
}
.options-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.option-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.3s ease;
}
.option-card:hover {
  border-color: var(--primary);
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}
.option-card.radio-selected {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-brand);
}
.option-card.checkbox-selected {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-brand);
}
.option-letter {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bgc-light);
  border-radius: var(--radius-lg);
  font-size: 20px;
  font-weight: 700;
  color: var(--text-gray);
  transition: all 0.3s ease;
  flex-shrink: 0;
}
.option-card.radio-selected .option-letter {
  background: var(--primary);
  color: var(--bg-card);
  box-shadow: var(--shadow-brand);
}
.option-card.checkbox-selected .option-letter {
  background: var(--primary);
  color: var(--bg-card);
  box-shadow: var(--shadow-brand);
}
.option-text {
  flex: 1;
  font-size: 16px;
  color: var(--text-body);
  line-height: 1.4;
}
.option-card.radio-selected .option-text,
.option-card.checkbox-selected .option-text {
  color: var(--text-title);
  font-weight: 500;
}
.radio-icon {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
  transition: all 0.2s ease;
}
.option-card:hover .radio-icon {
  border-color: var(--primary);
}
.option-card.radio-selected .radio-icon {
  border-color: var(--primary);
  background: var(--primary);
}
.option-card.radio-selected .radio-icon::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 8px;
  height: 8px;
  background: var(--bg-card);
  border-radius: 50%;
}
.checkbox-icon {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-radius: 6px;
  position: relative;
  flex-shrink: 0;
  transition: all 0.2s ease;
  background: var(--bg-card);
}
.option-card:hover .checkbox-icon {
  border-color: var(--primary);
}
.option-card.checkbox-selected .checkbox-icon {
  border-color: var(--primary);
  background: var(--primary);
}
.option-card.checkbox-selected .checkbox-icon::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--bg-card);
  font-size: 12px;
  font-weight: bold;
}

.popup .submit-btn {
  display: block;
  width: 200px;
  margin: 20px auto 0;
  padding: 14px 24px;
  background: var(--grad-primary);
  color: var(--bg-card);
  border: none;
  border-radius: var(--radius-lg);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: var(--shadow-brand);
  text-align: center;
}
.popup .submit-btn:hover:not(.disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(45, 125, 219, 0.4);
}
.popup .submit-btn.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.popup .submit-btn.reset-btn {
  background: var(--pass);
  box-shadow: 0 4px 12px rgba(0, 204, 123, 0.3);
}
.popup .submit-btn.reset-btn:hover {
  background: var(--pass-hover);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 204, 123, 0.4);
}

.content-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  gap: 30px;
  padding: 20px;
  animation: fadeInUp 0.5s ease-out;
}
.left-box {
  flex: 1;
  min-width: 700px;
  max-height: 720px;
  overflow-y: auto;
  padding-right: 10px;
}

.judge-grid {
  display: flex;
  gap: 20px;
  margin-top: 10px;
}
.judge-grid .option-card {
  flex: 1;
  justify-content: flex-start;
}

.tip-text {
  margin-top: 16px;
  padding: 8px 12px;
  background: var(--primary-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--primary);
  text-align: center;
}

.popup .left-box.programming {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
.programming .jumpBtn {
  margin: 0 auto;
  width: 300px;
}

.right-box {
  width: 600px;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  color: var(--text-body);
  overflow: hidden;
}
.tab-content {
  max-height: 720px;
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}
.tab-content .scroll {
  width: 100%;
  height: 100%;
  padding: 20px;
}
.tab-content::-webkit-scrollbar {
  width: 6px;
}
.tab-content::-webkit-scrollbar-thumb {
  background: var(--text-gray);
  border-radius: 3px;
}
.tab-content::-webkit-scrollbar-track {
  background: var(--bgc-light);
}

.recommend-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--primary-light);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
  border-left: 4px solid var(--primary);
}
.recommend-tip .tip-icon {
  font-size: 20px;
}
.recommend-tip span {
  font-size: 14px;
  color: var(--text-title);
  font-weight: 500;
}

.detail-item {
  position: relative;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
.detail-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}
.detail-item h4 {
  font-size: 16px;
  color: var(--text-title);
  margin-bottom: 6px;
  padding-right: 160px;
}
.label {
  font-size: 13px;
  color: var(--text-gray);
}

.btn-group {
  position: absolute;
  top: 0;
  right: 0;
  gap: 10px;
}
.operate-btn {
  padding: 4px 12px;
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s ease;
}
.jump-btn {
  background: var(--primary);
  color: var(--bg-card);
}
.jump-btn:hover {
  background: var(--primary-hv);
  transform: scale(1.02);
}

.aiGet {
  padding: 14px 20px;
  text-align: center;
  background: var(--grad-primary);
  color: var(--bg-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  font-weight: 600;
  font-size: 15px;
  transition: all 0.3s ease;
  margin-top: 16px;
  box-shadow: var(--shadow-brand);
}
.aiGet:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.4);
}
.aiGet.loading {
  background: var(--text-gray);
  cursor: not-allowed;
  opacity: 0.7;
}
.aiGet.empty-ai {
  margin-top: 20px;
  width: 100%;
}

.popupNull {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}
.popupNull img {
  width: 120px;
  margin-bottom: 16px;
}
.popupNullText {
  color: var(--text-gray);
  font-size: 14px;
}

.analysis-result {
  margin-top: 20px;
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
}
.analysis-result .result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.analysis-result .result-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 18px;
  font-weight: 700;
  color: var(--bg-card);
}
.analysis-result .result-icon.correct {
  background: var(--pass);
}
.analysis-result .result-icon.wrong {
  background: var(--main-delete);
}
.analysis-result .result-text {
  font-size: 16px;
  font-weight: 600;
}
.analysis-result .result-score {
  margin-left: auto;
  font-size: 14px;
  color: var(--text-gray);
}
.analysis-result .result-body {
  padding: 8px 0;
  font-size: 14px;
  color: var(--text-body);
  border-top: 1px solid var(--border-color);
}
.analysis-result .result-body:first-of-type {
  border-top: none;
}
.analysis-result .result-body p {
  margin: 4px 0;
}
.analysis-result .result-body strong {
  color: var(--text-title);
}

.popup .quit {
  z-index: 2;
  position: absolute;
  top: 90px;
  right: 40px;
}
.popup .quit:hover {
  cursor: pointer;
}
.popup .quit svg path {
  fill: var(--bg-card) !important;
}
.popup .quit:hover svg path {
  fill: var(--main-delete) !important;
}
.popup .quit>div {
  color: var(--bg-card);
}
.popup .quit:hover>div {
  color: var(--main-delete);
}

.popup .right-box .popupNull {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.popupNull img {
  width: 160px;
  margin-bottom: 20px;
}
.popupNull .popupNullText {
  font-size: 16px;
  color: var(--text-gray);
}

.popup .okArea {
  padding: 20px;
  height: 760px;
  display: flex;
  gap: 20px;
}
.okArea .left-box {
  height: 100%;
}

.okArea .right-box {
  width: 420px;
  height: 100%;
  padding: 20px;
  overflow-y: auto;
  border: 1px dotted var(--text-gray);
}

.okArea .q-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 8px;
}
.okArea .q-meta {
  font-size: 14px;
  color: var(--text-gray);
  margin-bottom: 6px;
}
.okArea .tag.easy {
  background: var(--primary-fade);
  color: var(--primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 8px;
}
.okArea .q-stat {
  font-size: 14px;
  color: var(--text-gray);
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.okArea .divider {
  height: 1px;
  background: var(--border-color);
  margin: 16px 0;
}
.okArea .attempt-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.okArea .attempt-item {
  padding: 6px 12px;
  border: 1px solid var(--primary-disa-bgc);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.okArea .attempt-item.active {
  background: var(--primary-fade);
  border-color: var(--primary);
}
.okArea .score.err,
.mini-score.err {
  color: var(--main-delete);
}
.okArea .score.ok,
.mini-score.ok {
  color: var(--pass);
}
.okArea .answer-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}
.okArea .panel-head {
  padding: 10px 14px;
  background: var(--bg-hover);
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  border-bottom: 1px solid var(--border-color);
}
.okArea .answer-code {
  margin: 0;
  padding: 14px;
  font-size: 13px;
  background: var(--bg-card);
  color: var(--text-body);
  white-space: pre-wrap;
  max-height: 460px;
  overflow-y: auto;
}

.recommend-detail {
  padding: 30px !important;
  max-height: 90vh !important;
  overflow-y: auto;
}
.recommend-detail-content {
  max-width: 800px;
  margin: 0 auto;
}
.detail-header {
  margin-bottom: 24px;
}
.detail-header .type-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--grad-primary);
  color: var(--bg-card);
  font-size: 12px;
  font-weight: 600;
  border-radius: 20px;
  margin-bottom: 12px;
}
.detail-header .detail-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-title);
  line-height: 1.6;
}

/* ==================== 易错题样式 ==================== */
.frequentlyPage-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 统计卡片 */
.fw-stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}

.fw-stat-card {
  background: var(--main-fail-status);
  border: 1px solid var(--main-delete);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  transition: all 0.3s ease;
}

.fw-stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.2);
}

.fw-stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--main-delete-hover);
}

.fw-stat-label {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* 薄弱知识点 */
.fw-kp-area {
  padding: 10px 16px;
  background: var(--bg-hover);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-body);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.fw-kp-title {
  font-weight: 600;
  color: var(--main-delete-hover);
  margin-right: 6px;
}

.fw-kp-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  background: var(--main-fail-status);
  color: var(--main-delete);
  font-weight: 500;
  margin: 2px;
}

/* 易错题卡片 */
.fw-card {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.fw-card:hover {
  box-shadow: 0 12px 40px rgba(245, 108, 108, 0.18) !important;
  border-color: var(--main-delete) !important;
}

.fw-card::before {
  background: linear-gradient(90deg, transparent, var(--main-delete), transparent) !important;
}

.fw-ring-wrap {
  flex-shrink: 0;
  position: relative;
  width: 80px;
  height: 80px;
}

.fw-ring {
  display: block;
  width: 80px;
  height: 80px;
  transform: rotate(-90deg);
}

.fw-ring-bg {
  fill: none;
  stroke: var(--border-color);
  stroke-width: 6;
}

.fw-ring-fg {
  fill: none;
  stroke: var(--main-delete);
  stroke-width: 6;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.6s ease;
}

.fw-ring-center {
  position: absolute;
  top: 0;
  left: 0;
  width: 80px;
  height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.fw-ring-num {
  font-size: 22px;
  font-weight: 800;
  color: var(--main-delete-hover);
  line-height: 1;
}

.fw-ring-label {
  font-size: 9px;
  color: var(--text-gray);
  margin-top: 2px;
}

.fw-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fw-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fw-badge {
  padding: 3px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.fw-score {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-gray);
}

.fw-frequent-badge {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--main-delete), var(--main-delete-hover));
  color: #fff;
  margin-left: auto;
}

.fw-question {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-title);
  font-weight: 600;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fw-description {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding: 8px 12px;
  background: var(--bgc-light);
  border-radius: 8px;
}

.fw-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  color: var(--text-body);
}

.fw-option-item {
  padding: 4px 8px;
  background: var(--bgc-light);
  border-radius: 6px;
}

.fw-kp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 错误次数进度条 */
.fw-attempt-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}

.fw-attempt-label {
  font-size: 12px;
  color: var(--text-gray);
  white-space: nowrap;
}

.fw-bar-bg {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.fw-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--main-delete), var(--main-delete-hover));
  transition: width 0.5s ease;
}

.fw-attempt-count {
  font-size: 12px;
  color: var(--text-gray);
  white-space: nowrap;
}

.fw-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--border-color);
  padding-top: 10px;
}

.fw-time {
  font-size: 12px;
  color: var(--text-gray);
}

.fw-actions {
  display: flex;
  gap: 10px;
}

.fw-retry-btn {
  padding: 6px 16px;
  border-radius: 8px;
  background: var(--main-delete);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  font-weight: 500;
}

.fw-retry-btn:hover {
  background: var(--main-delete-hover);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.3);
  transform: translateY(-1px);
}

/* 易错题页签激活状态 */
.frequentlyPage {
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-body);
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  margin-bottom: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  letter-spacing: 0;
  height: 36px;
  display: flex;
  align-items: center;
}

.frequentlyPage:hover {
  color: var(--main-delete);
  border-color: var(--main-delete);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.15);
  transform: translateY(-2px);
}

.frequentlyPage.active {
  color: #fff;
  background-color: var(--main-delete);
  border-color: var(--main-delete);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
}

.frequentlyPage::after {
  display: none;
}

.knowledgesPage {
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-body);
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  margin-bottom: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  letter-spacing: 0;
  height: 36px;
  display: flex;
  align-items: center;
}

.knowledgesPage:hover {
  color: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.15);
  transform: translateY(-2px);
}

.knowledgesPage.active {
  color: #fff;
  background-color: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.3);
}

.knowledgesPage::after {
  display: none;
}

/* 暗色模式适配 */
.dark .fw-stat-card {
  background: rgba(245, 108, 108, 0.15);
  border-color: var(--main-delete);
}

.dark .fw-stat-card:hover {
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
}

.dark .fw-kp-tag {
  background: rgba(245, 108, 108, 0.15);
  color: var(--main-delete);
}

.dark .fw-badge {
  background: rgba(245, 108, 108, 0.15);
  color: var(--main-delete);
}

.dark .fw-description {
  background: var(--bgc-light);
}

.dark .fw-option-item {
  background: var(--bgc-light);
}

.dark .frequentlyPage:hover {
  color: var(--main-delete);
  border-color: var(--main-delete);
}

.dark .frequentlyPage.active {
  background-color: var(--main-delete);
  border-color: var(--main-delete);
}

.dark .knowledgesPage:hover {
  color: var(--primary-hv);
  border-color: var(--primary-hv);
}

.dark .knowledgesPage.active {
  background-color: var(--primary);
  border-color: var(--primary);
}

.dark .frequently {
  border-color: var(--main-delete);
}

.dark .frequently>div:first-child {
  color: var(--main-delete);
}

.dark .frequently>div:last-child {
  color: var(--main-delete);
}

.dark .summary>div:last-child.show,
.dark .summary>div:last-child:hover {
  background-color: rgba(245, 108, 108, 0.15);
}

/* ==================== 已掌握卡片绿色样式 ==================== */
.ok-card::before {
  background: linear-gradient(90deg, transparent, var(--pass), transparent) !important;
}

.ok-card:hover {
  box-shadow: 0 12px 40px rgba(103, 194, 58, 0.18) !important;
  border-color: var(--pass) !important;
}

.ok-card .qtype {
  border-color: var(--pass) !important;
  color: var(--pass) !important;
}

.ok-card .qfLeft>div>span:first-child {
  color: var(--pass) !important;
}

.ok-card .qfRight .reStartBtn {
  color: var(--pass) !important;
  border-color: var(--pass) !important;
}

.ok-card .qfRight .reStartBtn:hover {
  background-color: var(--pass) !important;
  color: #fff !important;
}

.ok-card .qscore.qok svg path {
  fill: var(--pass) !important;
}

/* 暗色模式适配 - 已掌握 */
.dark .ok-card:hover {
  box-shadow: 0 12px 40px rgba(74, 222, 128, 0.25) !important;
}

.dark .ok-card .qfRight .reStartBtn:hover {
  background-color: var(--pass) !important;
}

/* ==================== 待巩固卡片橘色样式 ==================== */
.pending-card::before {
  background: linear-gradient(90deg, transparent, var(--coming), transparent) !important;
}

.pending-card:hover {
  box-shadow: 0 12px 40px rgba(230, 162, 60, 0.18) !important;
  border-color: var(--coming) !important;
}

.pending-card .qtype {
  border-color: var(--coming) !important;
  color: var(--coming) !important;
}

.pending-card .qfLeft>div>span:first-child {
  color: var(--coming) !important;
}

.pending-card .qfRight .reStartBtn {
  color: var(--coming) !important;
  border-color: var(--coming) !important;
}

.pending-card .qfRight .reStartBtn:hover {
  background-color: var(--coming) !important;
  color: #fff !important;
}

.pending-card .qfRight .deleteBtn {
  color: var(--main-delete) !important;
  border-color: var(--main-delete) !important;
}

.pending-card .qfRight .deleteBtn:hover {
  background-color: var(--main-delete) !important;
  color: #fff !important;
}

/* 暗色模式适配 - 待巩固 */
.dark .pending-card:hover {
  box-shadow: 0 12px 40px rgba(251, 146, 60, 0.25) !important;
}

.dark .pending-card .qfRight .reStartBtn:hover {
  background-color: var(--coming) !important;
}
</style>