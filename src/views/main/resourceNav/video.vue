<script setup>
// ============================================================
// 1. 导入依赖
// ============================================================
import { ref, onMounted, computed, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { saveSkip, isSkip, removeSkip } from '@/utils/skip.js'//跳转查看
import emitter from '@/utils/emitter'
import { 
  getListByUserIdApi,
  searchApi,
  getProgressApi,
  deleteByIdApi,
  getVideoStreamApi,
  getVideoInfoApi,
  getUserBehaviourApi,
  postRewindApi,
  getVideoInfoByPythonIdApi,
  generatePaperApi,
  getVideoSummaryApi,
  getVideoMindmapApi
} from '@/api/mainApi/resourceVideo.js'//接口
import Mermaid from '@/components/Mermaid.vue'
//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
const itemRef = ref([])// 循环ref 必须初始化为空数组
const popStore = useActionPopStore()
const router = useRouter()
// 添加设置 ref 的函数
const setItemRef = (element, rowIndex, colIndex) => {
  if (!element) return
  
  if (!itemRef.value[rowIndex]) {
    itemRef.value[rowIndex] = []
  }
  
  itemRef.value[rowIndex][colIndex] = element
}
// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index1, index2, rsId, type='video') => {
  await nextTick()

  const targetEl = itemRef.value?.[index1]?.[index2]
  if (!targetEl) {
    console.warn(`元素 [${index1}][${index2}] 不存在`)
    return
  }

  const rect = targetEl.getBoundingClientRect()
  let left = rect.left - 65
  let top = rect.top - 55 // 元素上方55px

  // 顶部越界则改为下方展示
  if (top < 0) {
    top = rect.bottom + 10
  }

  // 每个item对应自身坐标弹出
  popStore.showPop(left, top, { groupId: index1, id: index2, title: `第${index1+1}个条目下的第${index2+1}个子条目}`, rsId: rsId, rsType: type, userId: userId.value })
}
// ============================================================
// 2. 全局变量
// ============================================================
let loginUser = null
const userId = ref(null)
const skipInfo = ref()//跳转信息

// ============================================================
// 3. 组件生命周期
// ============================================================
onMounted(async() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  await getSearchList()

  if(isSkip(5) === false){
    console.log('没有视频需要提前打开')
  }else{
    skipInfo.value = isSkip(5)
    console.log('跳转信息:', skipInfo.value)
    
    // 判断是否为评论区跳转/ai对话搜索跳转
    if(startsWithVideo(skipInfo.value.resourceId)){
      // 评论区跳转
      const res = await getVideoInfoByPythonIdApi(skipInfo.value.resourceId)
      if(res.code){
        lookVideo(-1, -1,res.data)
      }else{
        ElMessage.error('该视频不存在，可能已经被删除了')
      }
    }else{
      // ai对话搜索
      for(let i = 0; i < list.value.length; i++){
        if(list.value[i].batchId == skipInfo.value.resourceId || skipInfo.value.resourceId === list.value[i].id){
          openVideosList(i)
          ElMessage.success('已展开视频框')
          break
        }
        if(i == list.value.length - 1){
          ElMessage.error('Ai搜索的该套视频资源不存在，可能已经被删除了')
        }
      } 
    }
    
    removeSkip(5)
  }

  await checkTask()
  
  document.addEventListener('keydown', handleKeydown)
  
  emitter.on('videoWarning', (data) => {
    if (data.visible && isLookVideo.value) {
      const video = videoPlayerRef.value
      if (video && !video.paused) {
        video.pause()
      }
    }
  })
})

// 区分跳转事件（ai生成跳转/评论区跳转）
const startsWithVideo = (str)  => {
    // 参数校验：确保输入为字符串
    if (typeof str !== 'string') {
        return false;
    }
    // 转为小写后比较前5个字符
    return str.toLowerCase().startsWith('video');
}

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  emitter.off('videoWarning')
  if (monitor.value.timerInterval) {
    clearInterval(monitor.value.timerInterval)
  }
  const video = videoPlayerRef.value
  if (video) {
    video.pause()
    video.src = ''
    video.load()
  }
})

// ============================================================
// 4. 搜索表单相关
// ============================================================
const videoRef = ref(null)
const btnDisvisible = ref(false)
const videoData = ref({
  userId: null,
  text: ''
})

const Rules = {
  text: [
    { required: true, message: '请输入主题/大纲', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}

const showLoading = ref(false)
const list = ref([])//视频列表

// ============================================================
// 5. 核心API接口调用
// ============================================================

/** 获取用户的所有视频生成任务列表 */
const getSearchList = async () => { 
  console.log('查询搜索记录列表')
  try {
    itemRef.value = []
    showLoading.value = true
    const res = await getListByUserIdApi(userId.value)
    if(res.code){
      list.value = res.data
      addVideos()
      showLoading.value = false
    }else{
      ElMessage.error('查询失败',res.msg)
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
  showLoading.value = false
}

/** 轮询获取视频生成进度 */
const taskProgress = ref([])
const getProgress = async (batchId) => { 
  try {
    const result = await getProgressApi(batchId)
    if(result.code){
      console.log('获取进度成功')
      taskProgress.value = result.data
    }else{
      ElMessage.error('获取进度失败')
    }
  } catch (e) {
    console.error('获取进度失败', e)
  }
}

/** 删除视频任务 */
const deleteItem = async (batchId, isShow = true) => { 
  if(isShow == true){
    await ElMessageBox.confirm('是否删除该任务项？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }

  try {
    const result = await deleteByIdApi(batchId)
    if(result.code){
      ElMessage.success('删除成功')
      await getSearchList()
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

// ============================================================
// 6. 列表UI交互函数
// ============================================================

/** 展开/收起视频列表 */
const openVideosList = async (index) => { 
  if(list.value[index].videos == null || !(list.value[index]?.videos)){
    await getProgress(list.value[index].batchId)
    try{
      if(taskProgress.value[0].status === 2){
        list.value[index].videos = [...taskProgress.value]
        taskProgress.value = []
      }
    }catch(e){
      console.error('获取进度失败', e)
      ElMessage.error('展开失败')
      taskProgress.value = []
    }
  }else{
    list.value[index].videos = null
  }
}

/** 为每个任务项添加videos属性 */
const addVideos = () => { 
  for (let i = 0; i < list.value.length; i++) {
    list.value[i].videos = null
  }
}

/** 检查未完成的任务（断点续传） */
const checkTask = async() => { 
  console.log('检查截断')
  btnDisvisible.value = true
  for (let i = 0; i < list.value.length; i++) {
    addVideos()
    const item = list.value[i];
    if(item.status == 1 || item.status == null){
      let nowNum = 0
      let maxNum = 15

      try {
        console.log('第一次查询进度')
        await getProgress(item.batchId)
        if(!(taskProgress.value.length == 0)){
          if(taskProgress.value[0].status == null){
            item.status = 3
            await deleteItem(item.batchId, false)
            await getSearchList()
            taskProgress.value = []
            continue
          }
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      while (taskProgress.value.length == 0 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.batchId} 生成中... 第 ${nowNum} 次轮询`)
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          console.log('获取进度次数：', nowNum)
          await getProgress(item.batchId)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      if (taskProgress.value[0]?.status == 2) {
        console.log(` ${item.batchId} 任务完成`)
        await getSearchList()
        taskProgress.value = []
      } else {
        console.log(` ${item.batchId} 未完成`)
        await getSearchList()
        taskProgress.value = []
      }
    }
  }
  btnDisvisible.value = false
  console.log('检查截断结束')
}

/** 提交搜索任务 */
const submit = async () => { 
  videoRef.value.validate(async(valid) => { 
    if (valid) { 
      console.log('表单校验通过，提交中')
      btnDisvisible.value = true
      videoData.value.userId = userId.value

      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        const result = await searchApi(videoData.value)
        if(result.code){
          ElMessage.success('提交成功')
          if(result.data.status == 1 || result.data.status == null){
            let nowNum = 0
            let maxNum = 15

            try {
              console.log('第一次查询进度')
              await getProgress(result.data.batchId)
              if(!(taskProgress.value.length == 0)){
                if(taskProgress.value[0].status == null){
                  await deleteItem(result.data.batchId, false)
                  await getSearchList()
                  taskProgress.value = []
                }
              }
            } catch (e) {
              console.error('首次查询进度失败', e)
            }

            await getSearchList()

            while (taskProgress.value.length == 0 && nowNum < maxNum) {
              nowNum++
              console.log(`任务 ${result.data.batchId} 生成中... 第 ${nowNum} 次轮询`)
              await new Promise(resolve => setTimeout(resolve, 10000))

              try {
                console.log('获取进度次数：', nowNum)
                await getProgress(result.data.batchId)
              } catch (e) {
                console.error('轮询进度失败', e)
              }
            }
        
            if (taskProgress.value[0]?.status == 2) {
              console.log(` ${result.data.batchId} 任务完成`)
              await getSearchList()
              taskProgress.value = []
            } else {
              console.log(` ${result.data.batchId} 未完成`)
              await getSearchList()
              taskProgress.value = []
            }
          } else if(result.data.status == 2 || result.data.status == 3){
            await getSearchList()
            taskProgress.value = []
          }
          btnDisvisible.value = false
          videoData.value = {userId: null, text: ''}
          
        }else{
          ElMessage.error('提交失败')
        }
      } finally {
        clearTimeout(gameInvitationTimer)
      }
    } else {
      console.log('校验失败')
      return false
    }
  })
}

// ============================================================
// 7. 视频播放器相关（合集播放器）
// ============================================================
const isLookVideo = ref(false)
const lookVideoData = ref({})
const videoPlayerRef = ref(null)
const isVideoLoading = ref(false)
const videoError = ref(null)

// 合集数据
const fullVideoInfo = ref(null)
const pagesList = ref([])
const currentPageIndex = ref(0)

// 播放控制状态
const isPlaying = ref(false)
const currentTime = ref(0)
const videoDuration = ref(0)
const progressPercent = ref(0)
const formattedCurrentTime = ref('0:00')
const formattedDuration = ref('0:00')
const isMuted = ref(false)
const isFullscreen = ref(false)

// 是否已绑定事件
const isEventsBound = ref(false)

// 防止重复弹出题目生成提示
let isShowingQuizDialog = false

// 控制栏显示状态
const showControls = ref(true)
let controlsTimer = null

// ============================================================
// 8. 观看行为监控
// ============================================================
const monitor = ref({
  playing: false,
  started: false,
  currentTime: 0,
  duration: 0,
  rewindCount: 0,// 回溯次数
  pauseCount: 0,// 暂停次数
  watchTime: 0,
  rewindEvents: [],
  seekThreshold: 5,
  initDuration: 0,
  completionPosted: false,
  lastReportTime: 0,
  timerInterval: null,
  switchingChapter: false,
  _confusionAsked: false  // 当前视频是否已问过疑惑
})

const currentVideoInfo = ref(null)

// ============================================================
// 9. 工具函数
// ============================================================

/** 格式化时间（分:秒） */
const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m + ':' + (s < 10 ? '0' : '') + s
}

/** 格式化时间（中文） */
const formatTimeFull = (seconds) => {
  if (!seconds || isNaN(seconds) || seconds < 0) return '0秒'
  if (seconds < 60) return Math.floor(seconds) + '秒'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m + '分' + s + '秒'
}

// ============================================================
// 10. 核心播放逻辑（合集播放器）
// ============================================================

/** 控制栏自动隐藏 */
const resetControlsTimer = () => {
  if (controlsTimer) {
    clearTimeout(controlsTimer)
    controlsTimer = null
  }
  if (isPlaying.value) {
    controlsTimer = setTimeout(() => {
      showControls.value = false
    }, 3000)
  }
}

/** 显示控制栏 */
const showControlsTemporarily = () => {
  showControls.value = true
  resetControlsTimer()
}

/** 查看视频 - 入口函数 */
const lookVideo = async (index = -1, ind = -1,openVideo = {}) => {
  let videoDataItem = null
  if(index < 0 || ind < 0){
    videoDataItem = openVideo
  }else{
    videoDataItem = list.value[index].videos[ind]
  }
  
  lookVideoData.value = videoDataItem
  
  resetMonitor()
  isPlaying.value = false
  currentTime.value = 0
  videoDuration.value = 0
  progressPercent.value = 0
  formattedCurrentTime.value = '0:00'
  formattedDuration.value = '0:00'
  videoError.value = null
  isVideoLoading.value = true
  pagesList.value = []
  currentPageIndex.value = 0
  fullVideoInfo.value = null
  monitor.value.switchingChapter = false
  isEventsBound.value = false
  showControls.value = true
  
  isLookVideo.value = true
  
  // video页面特殊处理：展开右侧悬浮窗并自动开始监控
  emitter.emit('expandCameraWindow', { autoStartMonitor: true })
  
  await nextTick()
  
  try {
    const url = videoDataItem.url
    const bvidMatch = url.match(/BV[0-9A-Za-z]{10}/)
    if (!bvidMatch) {
      ElMessage.error('无法解析视频ID')
      isVideoLoading.value = false
      return
    }
    const bvid = bvidMatch[0]
    
    const infoResult = await getVideoInfoApi(bvid, 1)
    console.log('获取视频信息结果:', infoResult)
    
    if (infoResult.code !== 1 || !infoResult.data) {
      ElMessage.error(infoResult.msg || '获取视频信息失败')
      isVideoLoading.value = false
      return
    }
    
    const videoInfo = infoResult.data.data || infoResult.data
    console.log('视频信息:', videoInfo)
    
    fullVideoInfo.value = videoInfo
    
    // 更新标题
    lookVideoData.value.title = videoInfo.title || videoDataItem.title
    lookVideoData.value.author = videoInfo.author || videoDataItem.author
    
    // 构建分集列表
    if (videoInfo.pages && videoInfo.pages.length > 0) {
      pagesList.value = videoInfo.pages.map((p, idx) => ({
        ...p,
        index: idx,
        label: `P${p.page}${p.title ? ' ' + p.title : ''}`
      }))
    } else {
      pagesList.value = [{
        page: 1,
        title: videoInfo.title || 'P1',
        cid: videoInfo.cid,
        index: 0,
        label: 'P1'
      }]
    }
    
    currentVideoInfo.value = {
      title: videoInfo.title || videoDataItem.title,
      author: videoInfo.author || videoDataItem.author,
      url: videoDataItem.url,
      bvid: bvid,
      duration: videoInfo.duration || 0
    }

    // 获取视频总结和思维导图
    fetchSummaryAndMindmap()

    await loadVideoPage(0)
    
  } catch (err) {
    console.error('加载视频失败:', err)
    ElMessage.error('加载视频失败: ' + (err.message || '未知错误'))
    isVideoLoading.value = false
    videoError.value = err.message
  }
}

/** 加载指定分集 */
const loadVideoPage = async (pageIndex) => {
  if (!fullVideoInfo.value) return
  
  // ★★★ 标记切换中，抑制回溯检测 ★★★
  monitor.value.switchingChapter = true
  
  // ★★★ 重置疑惑标记，允许新分集重新触发疑惑弹窗 ★★★
  monitor.value._confusionAsked = false
  
  // 重置题目弹窗标志，允许新分集播放完成后再次弹窗
  isShowingQuizDialog = false
  
  isVideoLoading.value = true
  videoError.value = null
  currentPageIndex.value = pageIndex
  
  const page = pagesList.value[pageIndex]
  if (!page) {
    ElMessage.error('分集不存在')
    isVideoLoading.value = false
    monitor.value.switchingChapter = false
    return
  }
  
  // 上报视频上下文给智能球
  emitter.emit('contextDetail', {
    page: 'video',
    title: fullVideoInfo.value.title || '视频学习',
    action: 'watching',
    detail: `视频标题: ${fullVideoInfo.value.title || ''}, 分集: P${page.page} ${page.title || ''}`
  })
  
  try {
    const bvid = fullVideoInfo.value.bvid
    const pageNum = page.page
    
    const infoResult = await getVideoInfoApi(bvid, pageNum)
    if (infoResult.code !== 1 || !infoResult.data) {
      ElMessage.error('获取分集信息失败')
      isVideoLoading.value = false
      monitor.value.switchingChapter = false
      return
    }
    
    const videoInfo = infoResult.data.data || infoResult.data
    
    if (!videoInfo.streams || videoInfo.streams.length === 0) {
      ElMessage.error('未获取到视频流地址')
      isVideoLoading.value = false
      monitor.value.switchingChapter = false
      return
    }
    
    const streamUrl = videoInfo.streams[0].url
    console.log(`加载 P${pageNum} 流地址:`, streamUrl.substring(0, 80) + '...')
    
    // 通过python后端代理获取视频流
    const proxyResult = await getVideoStreamApi(encodeURIComponent(streamUrl))
    let videoSrc = ''
    if (proxyResult instanceof Blob) {
      videoSrc = URL.createObjectURL(proxyResult)
    } else if (typeof proxyResult === 'string') {
      videoSrc = proxyResult
    } else if (proxyResult.data) {
      videoSrc = proxyResult.data
    } else {
      videoSrc = streamUrl
    }
    
    // ★★★ 获取video元素 ★★★
    const videoEl = videoPlayerRef.value
    if (!videoEl) {
      ElMessage.error('播放器初始化失败')
      isVideoLoading.value = false
      monitor.value.switchingChapter = false
      return
    }
    
    // ★★★ 暂停并清空当前播放 ★★★
    videoEl.pause()
    videoEl.removeAttribute('src')
    videoEl.load()
    
    // 更新时长
    if (videoInfo.duration) {
      videoDuration.value = videoInfo.duration
      formattedDuration.value = formatTime(videoInfo.duration)
    }
    
    // 重置播放器状态
    videoEl.currentTime = 0
    progressPercent.value = 0
    formattedCurrentTime.value = '0:00'
    currentTime.value = 0
    monitor.value.currentTime = 0
    monitor.value.duration = 0
    
    // ★★★ 设置新视频源 ★★★
    videoEl.src = videoSrc
    videoEl.load()
    
    // ★★★ 重置事件绑定标记，强制重新绑定 ★★★
    isEventsBound.value = false
    
    // ★★★ 绑定事件（每次重新绑定） ★★★
    bindVideoEvents(videoEl)
    startMonitorTimer()
    
    // 等待视频加载完成后自动播放
    const playVideo = () => {
      try {
        videoEl.play()
      } catch (playErr) {
        console.warn('自动播放被阻止:', playErr)
      }
    }
    
    // 如果已经可以播放，直接播放
    if (videoEl.readyState >= 3) {
      playVideo()
      isVideoLoading.value = false
      // 延迟解除切换标记
      setTimeout(() => {
        monitor.value.switchingChapter = false
      }, 1500)
    } else {
      // 等待 canplay 事件
      const onCanPlay = () => {
        videoEl.removeEventListener('canplay', onCanPlay)
        playVideo()
        isVideoLoading.value = false
        setTimeout(() => {
          monitor.value.switchingChapter = false
        }, 1500)
      }
      videoEl.addEventListener('canplay', onCanPlay)
      
      // 超时处理
      setTimeout(() => {
        videoEl.removeEventListener('canplay', onCanPlay)
        if (isVideoLoading.value) {
          isVideoLoading.value = false
          monitor.value.switchingChapter = false
        }
      }, 15000)
    }
    
    // ★★★ 更新当前分集标题显示 ★★★
    console.log(`✅ 切换到 P${pageNum}: ${page.title || ''}`)
    
  } catch (err) {
    console.error('加载分集失败:', err)
    ElMessage.error('加载分集失败: ' + (err.message || '未知错误'))
    isVideoLoading.value = false
    videoError.value = err.message
    monitor.value.switchingChapter = false
  }
}

/** 切换分集 */
const switchPage = (index) => {
  if (index === currentPageIndex.value) return
  // 上报当前观看数据
  reportWatchData('switch_page')
  // 立即暂停视频并显示加载遮罩
  const video = videoPlayerRef.value
  if (video) {
    video.pause()
  }
  isPlaying.value = false
  isVideoLoading.value = true

  // 换集时重新获取总结和思维导图
  fetchSummaryAndMindmap()

  loadVideoPage(index)
}

/** 上一集 */
const prevPage = () => {
  if (currentPageIndex.value > 0) {
    switchPage(currentPageIndex.value - 1)
  }
}

/** 下一集 */
const nextPage = () => {
  if (currentPageIndex.value < pagesList.value.length - 1) {
    switchPage(currentPageIndex.value + 1)
  }
}

// ============================================================
// 11. 视频事件绑定
// ============================================================

/** 绑定视频DOM事件 */
const bindVideoEvents = (video) => {
  if (!video) return
  
  // ★★★ 如果已经绑定过事件，先移除旧的监听 ★★★
  if (isEventsBound.value) {
    try {
      // 克隆节点替换，移除所有事件监听
      const parent = video.parentNode
      if (parent) {
        const newVideo = video.cloneNode(true)
        parent.replaceChild(newVideo, video)
        video = newVideo
        videoPlayerRef.value = video
        console.log('🔄 已替换视频节点，移除旧事件')
      }
    } catch (e) {
      console.warn('替换视频节点失败，使用原节点', e)
    }
  }
  
  // ★★★ 标记已绑定 ★★★
  isEventsBound.value = true
  const v = videoPlayerRef.value || video
  
  // ★★★ 移除可能存在的重复监听（使用标志防止多次绑定） ★★★
  // 播放事件
  v.addEventListener('play', function onPlay() {
    isPlaying.value = true
    monitor.value.playing = true
    showControls.value = true
    resetControlsTimer()
    if (!monitor.value.started) {
      monitor.value.started = true
      monitor.value.lastReportTime = Date.now()
      console.log('▶️ 开始播放')
    }
  })
  
  // 暂停事件
  v.addEventListener('pause', function onPause() {
    if (monitor.value.playing) {
      monitor.value.pauseCount++
      monitor.value.playing = false
      console.log('⏸️ 暂停 (累计 ' + monitor.value.pauseCount + ' 次)')
    }
    isPlaying.value = false
    showControls.value = true
    if (controlsTimer) {
      clearTimeout(controlsTimer)
      controlsTimer = null
    }
  })
  
  // 点击切换播放
  v.addEventListener('click', function onClick() {
    togglePlay()
  })
  
  // 鼠标移动显示控制栏
  v.addEventListener('mousemove', function onMouseMove() {
    showControlsTemporarily()
  })
  
  // ★★★ 时间更新 - 核心监控逻辑 ★★★
  v.addEventListener('timeupdate', function onTimeUpdate() {
    if (!v.duration || isNaN(v.duration)) return
    
    const cur = v.currentTime
    const dur = v.duration
    const prev = monitor.value.currentTime
    
    monitor.value.currentTime = cur
    monitor.value.duration = dur
    
    currentTime.value = cur
    videoDuration.value = dur
    progressPercent.value = (cur / dur) * 100
    formattedCurrentTime.value = formatTime(cur)
    formattedDuration.value = formatTime(dur)
    
    const pct = Math.round((cur / dur) * 100)
    if (pct > monitor.value.initDuration) {
      monitor.value.initDuration = pct
    }
    
    // ★★★ 回溯检测：仅在非切换章节时触发 ★★★
    if (!monitor.value.switchingChapter && prev > 0 && cur < prev - monitor.value.seekThreshold) {
      monitor.value.rewindCount++
      const rewindEvent = {
        index: monitor.value.rewindCount,
        from: prev,
        to: cur,
        gap: prev - cur,
        time: new Date().toISOString(),
        page: pagesList.value[currentPageIndex.value]?.page || 1
      }
      monitor.value.rewindEvents.push(rewindEvent)
      console.log('↩ 回溯 #' + monitor.value.rewindCount + ': ' + 
        formatTime(prev) + ' → ' + formatTime(cur) + 
        ' (倒退 ' + formatTimeFull(prev - cur) + ')')
      
      // ★★★ 触发疑惑弹窗 - 每次都弹，不限制次数 ★★★
      // 但同一次回溯只弹一次（通过 _lastRewindTime 控制频率）
      const now = Date.now()
      if (!monitor.value._lastRewindTime || (now - monitor.value._lastRewindTime) > 5000) {
        monitor.value._lastRewindTime = now
        showConfusionDialog(
          fullVideoInfo.value?.bvid || '',
          fullVideoInfo.value?.title || '',
          rewindEvent
        )
      }
    }
  })
  
  // 拖动进度条
  v.addEventListener('seeked', function onSeeked() {
    if (!v.duration) return
    const cur = v.currentTime
    const prev = monitor.value.currentTime
    
    if (!monitor.value.switchingChapter && prev > 0 && cur < prev - monitor.value.seekThreshold) {
      monitor.value.rewindCount++
      const rewindEvent = {
        index: monitor.value.rewindCount,
        from: prev,
        to: cur,
        gap: prev - cur,
        time: new Date().toISOString(),
        page: pagesList.value[currentPageIndex.value]?.page || 1,
        source: 'seek'
      }
      monitor.value.rewindEvents.push(rewindEvent)
      console.log('↩ 拖动回溯 #' + monitor.value.rewindCount)
      
      // 触发疑惑弹窗
      const now = Date.now()
      if (!monitor.value._lastRewindTime || (now - monitor.value._lastRewindTime) > 5000) {
        monitor.value._lastRewindTime = now
        showConfusionDialog(
          fullVideoInfo.value?.bvid || '',
          fullVideoInfo.value?.title || '',
          rewindEvent
        )
      }
    }
    monitor.value.currentTime = cur
    showControlsTemporarily()
  })
  
  // 播放结束
  v.addEventListener('ended', function onEnded() {
    isPlaying.value = false
    monitor.value.playing = false
    monitor.value.initDuration = 100
    console.log('✅ 播放完成!')
    reportWatchData('ended')
    
    // 防止重复弹窗
    if (isShowingQuizDialog) return
    isShowingQuizDialog = true
    
    // 弹出提示框询问是否生成本集相关题目
    ElMessageBox.confirm(
      '本集视频播放完成，是否生成本集相关的测试题目？',
      '生成测试题',
      {
        confirmButtonText: '生成题目',
        cancelButtonText: '继续播放',
        type: 'question'
      }
    ).then(async () => {
      // 用户选择生成题目
      const currentPage = pagesList.value[currentPageIndex.value]
      const videoTitle = fullVideoInfo.value?.title || ''
      const bvid = fullVideoInfo.value?.bvid || ''
      const pageNum = currentPage?.page || 1
      let loadingInstance = ''
      try {
        loadingInstance = ElLoading.service({
          fullscreen: true,
          text: '题目生成中...',
          background: 'rgba(255, 255, 255, 0.9)'
        })
        
        const res = await generatePaperApi({
          user_id: userId.value,
          video_title: `${videoTitle} P${pageNum}`,
          bvid: `${bvid}-p${pageNum}`
        })
        
        if (res.code === 1 && res.data?.paperId) {
          saveSkip(7, res.data.paperId)
          router.push('/paper')
        } else {
          ElMessage.error('题目生成失败')
          if (currentPageIndex.value < pagesList.value.length - 1) {
            nextPage()
          }
        }
      } catch (e) {
        console.error('生成题目失败:', e)
        ElMessage.error('生成题目失败')
        if (currentPageIndex.value < pagesList.value.length - 1) {
          nextPage()
        }
      } finally {
        loadingInstance.close()
        isShowingQuizDialog = false
      }
    }).catch(() => {
      // 用户选择继续播放下一集
      isShowingQuizDialog = false
      if (currentPageIndex.value < pagesList.value.length - 1) {
        setTimeout(() => {
          nextPage()
        }, 3000)
      }
    })
  })
  
  // 错误事件
  v.addEventListener('error', function onError() {
    console.error('视频错误:', v.error)
    videoError.value = v.error ? v.error.message : '视频加载错误'
    // ElMessage.error('视频播放错误')
    isVideoLoading.value = false
  })
  
  // 可以播放
  v.addEventListener('canplay', function onCanPlay() {
    console.log('✅ 可播放')
    isVideoLoading.value = false
  })
  
  // 缓冲
  v.addEventListener('waiting', function onWaiting() {
    console.log('⏳ 缓冲中...')
    isVideoLoading.value = true
  })
  
  v.addEventListener('playing', function onPlaying() {
    isVideoLoading.value = false
  })
}

// ============================================================
// 12. 播放控制函数
// ============================================================

/** 切换播放/暂停 */
const togglePlay = () => {
  const video = videoPlayerRef.value
  if (!video) return
  if (video.paused) {
    video.play()
  } else {
    video.pause()
  }
  showControlsTemporarily()
}

/** 点击进度条跳转 */
const seekTo = (event) => {
  const video = videoPlayerRef.value
  if (!video || !video.duration) return
  const rect = event.currentTarget.getBoundingClientRect()
  const pct = (event.clientX - rect.left) / rect.width
  video.currentTime = pct * video.duration
  showControlsTemporarily()
}

/** 切换静音 */
const toggleMute = () => {
  const video = videoPlayerRef.value
  if (!video) return
  video.muted = !video.muted
  isMuted.value = video.muted
  showControlsTemporarily()
}

/** 全屏 */
const toggleFullscreen = () => {
  const wrapper = document.querySelector('.video-player-wrapper')
  if (wrapper) {
    if (!document.fullscreenElement) {
      wrapper.requestFullscreen()
      isFullscreen.value = true
    } else {
      document.exitFullscreen()
      isFullscreen.value = false
    }
  }
  showControlsTemporarily()
}

// ============================================================
// 13. 监控与上报
// ============================================================

/** 启动监控定时器 */
const startMonitorTimer = () => {
  if (monitor.value.timerInterval) {
    clearInterval(monitor.value.timerInterval)
  }
  monitor.value.timerInterval = setInterval(() => {
    const video = videoPlayerRef.value
    if (!video || !video.duration) return
    
    if (!video.paused && !video.ended) {
      monitor.value.watchTime++
    }
    
    if (video.duration && video.currentTime > 0) {
      const remaining = video.duration - video.currentTime
      if (remaining < 1 && !monitor.value.completionPosted && video.currentTime > 0) {
        monitor.value.completionPosted = true
        monitor.value.initDuration = 100
        console.log('✅ 接近完播')
      }
    }
    
    if (monitor.value.started && Date.now() - monitor.value.lastReportTime > 30000) {
      reportWatchData('auto')
    }
  }, 1000)
  monitor.value.lastReportTime = Date.now()
}

/** 重置监控数据 */
const resetMonitor = () => {
  if (monitor.value.timerInterval) {
    clearInterval(monitor.value.timerInterval)
    monitor.value.timerInterval = null
  }
  if (controlsTimer) {
    clearTimeout(controlsTimer)
    controlsTimer = null
  }
  monitor.value = {
    playing: false,
    started: false,
    currentTime: 0,
    duration: 0,
    rewindCount: 0,
    pauseCount: 0,
    watchTime: 0,
    rewindEvents: [],
    seekThreshold: 5,
    initDuration: 0,
    completionPosted: false,
    lastReportTime: 0,
    timerInterval: null,
    switchingChapter: false,
    _confusionAsked: false,
    _lastRewindTime: 0
  }
  isEventsBound.value = false
  isMuted.value = false
  isFullscreen.value = false
  showControls.value = true
}

/** 监控数据显示 */
const monitorDisplay = computed(() => {
  const m = monitor.value
  return {
    state: m.playing ? '播放中' : '已暂停',
    progress: m.initDuration + '%',
    watchTime: formatTimeFull(m.watchTime),
    rewindCount: m.rewindCount,
    pauseCount: m.pauseCount,
    completion: m.initDuration + '%'
  }
})

/** 上报观看行为数据 */
const reportWatchData = async (reason) => {
  if (!monitor.value.started || !userId.value) return
  
  monitor.value.lastReportTime = Date.now()
  
  const videoInfo = currentVideoInfo.value
  if (!videoInfo) return
  
  const reportData = {
    userId: userId.value,
    videoInfo: {
      title: videoInfo.title || lookVideoData.value.title || '',
      author: videoInfo.author || lookVideoData.value.author || '',
      url: lookVideoData.value.url || '',
      bvid: videoInfo.bvid || ''
    },
    watchData: {
      watchDuration: Math.round(monitor.value.watchTime) + 's',
      totalDuration: Math.round(monitor.value.duration) + 's',
      completionRate: monitor.value.initDuration + '%',
      pauseCount: monitor.value.pauseCount,
      rewindCount: monitor.value.rewindCount,
      rewindEvents: monitor.value.rewindEvents.slice(-10),
      engagementSignals: {
        significantRewinds: monitor.value.rewindCount,
        totalRewinds: monitor.value.rewindCount,
        userActive: true,
        watchProgress: monitor.value.initDuration + '%'
      }
    }
  }
  
  console.log('📤 上报观看数据 (原因: ' + reason + '):', reportData)
  
  try {
    const result = await getUserBehaviourApi(reportData)
    if (result.code === 1) {
      console.log('✅ 上报成功')
    }
  } catch (e) {
    console.warn('上报失败:', e.message)
  }
}

/** 疑惑弹窗 */
const showConfusionDialog = (bvid, title, rewindEvent) => {
  togglePlay()// 暂停
  ElMessageBox.confirm(
    `检测到您回看了视频内容（${formatTime(rewindEvent.from)} → ${formatTime(rewindEvent.to)}），是否对当前内容存在疑惑？`,
    '确认疑惑',
    {
      confirmButtonText: '是的，有疑惑',
      cancelButtonText: '没有，只是复习',
      type: 'warning',
      distinguishCancelAndClose: true
    }
  ).then(() => {
    ElMessage.success({
      message: '已记录您的疑惑，下次对话时可为您解答',
      duration: 3000,
    });
    togglePlay()// 播放
    reportConfusion(bvid, title, rewindEvent, true)
  }).catch((action) => {
    if (action === 'cancel') {
      ElMessage.info({
        message: '好的，继续学习吧！',
        duration: 2000,
      });
      togglePlay()// 播放
      reportConfusion(bvid, title, rewindEvent, false)
    }
  })
  
}

/** 上报疑惑到后端 */
const reportConfusion = async (bvid, title, rewindEvent, isConfused) => {
  try {
    const page = pagesList.value[currentPageIndex.value]?.page || 1
    const res = await postRewindApi({
      userId: userId.value,
      bvid: bvid,
      videoTitle: title,
      rewindFrom: rewindEvent.from,
      rewindTo: rewindEvent.to,
      rewindGap: Math.round(rewindEvent.gap),
      isConfused: isConfused,
      page: page
    })
    // const result = await res.json()
    if (res.code) {
      console.log('✅ 疑惑上报成功')
    }
  } catch (e) {
    console.warn('⚠️ 疑惑上报失败:', e.message)
  }
}

/** 退出播放器 */
const exitLook = () => {
  if (monitor.value.started) {
    reportWatchData('exit')
  }
  
  if (monitor.value.timerInterval) {
    clearInterval(monitor.value.timerInterval)
    monitor.value.timerInterval = null
  }
  if (controlsTimer) {
    clearTimeout(controlsTimer)
    controlsTimer = null
  }
  
  const video = videoPlayerRef.value
  if (video) {
    video.pause()
    video.src = ''
    video.load()
  }
  
  isLookVideo.value = false
  lookVideoData.value = {}
  currentVideoInfo.value = null
  fullVideoInfo.value = null
  pagesList.value = []
  currentPageIndex.value = 0
  isVideoLoading.value = false
  videoError.value = null
  isPlaying.value = false
  isEventsBound.value = false
  mindmapData.value = null
  videoSummary.value = null
  resetMonitor()
}

// ============================================================
// 14. 键盘快捷键
// ============================================================

const handleKeydown = (e) => {
  if (!isLookVideo.value) return
  const video = videoPlayerRef.value
  if (!video) return
  
  switch (e.key) {
    case ' ':
    case 'k':
      e.preventDefault()
      togglePlay()
      break
    case 'ArrowRight':
      e.preventDefault()
      video.currentTime = Math.min(video.currentTime + 5, video.duration || 0)
      break
    case 'ArrowLeft':
      e.preventDefault()
      video.currentTime = Math.max(video.currentTime - 5, 0)
      break
    case 'f':
      e.preventDefault()
      toggleFullscreen()
      break
  }
}

const progressStyle = computed(() => ({
  width: progressPercent.value + '%'
}))

// 当前分集标题
const currentPageTitle = computed(() => {
  if (pagesList.value.length > 0 && currentPageIndex.value < pagesList.value.length) {
    return pagesList.value[currentPageIndex.value]?.title || ''
  }
  return ''
})

// ============================================================
// 15. 视频总结与思维导图
// ============================================================
const mindmapRef = ref(null)
const mindmapData = ref(null)
const videoSummary = ref(null)
const summaryLoading = ref(false)
const mindmapLoading = ref(false)
const summaryError = ref('')
const mindmapError = ref('')

// 轮询配置
const POLL_INTERVAL = 10000 // 轮询间隔 10秒
const MAX_POLL_COUNT = 100 // 最多轮询 100 次（共约 16 分钟）

// 轮询定时器
let summaryPollTimer = null
let mindmapPollTimer = null

// 清除轮询
const clearSummaryPoll = () => {
  if (summaryPollTimer) {
    clearTimeout(summaryPollTimer)
    summaryPollTimer = null
  }
}

const clearMindmapPoll = () => {
  if (mindmapPollTimer) {
    clearTimeout(mindmapPollTimer)
    mindmapPollTimer = null
  }
}

const clearAllPolls = () => {
  clearSummaryPoll()
  clearMindmapPoll()
}

// 获取视频总结（支持轮询）
const fetchVideoSummary = async (pollCount = 0) => {
  console.log('获取视频总结...', pollCount > 0 ? `(轮询 ${pollCount}/${MAX_POLL_COUNT})` : '')
  const bvid = fullVideoInfo.value?.bvid
  const page = pagesList.value[currentPageIndex.value]?.page || 1
  if (!bvid) return

  if (pollCount === 0) {
    summaryLoading.value = true
    summaryError.value = ''
  }

  try {
    const res = await getVideoSummaryApi({ bvid, page })
    if (res.code === 1 && res.data?.success) {
      videoSummary.value = res.data.data
      summaryLoading.value = false
      summaryError.value = ''
    } else if (res.code === 1 && res.data?.success === false) {
      // 字幕尚未就绪，轮询重试
      const errorMsg = res.data?.error || '字幕尚未就绪，请稍后重试'
      if (pollCount < MAX_POLL_COUNT) {
        summaryError.value = errorMsg
        summaryPollTimer = setTimeout(() => {
          fetchVideoSummary(pollCount + 1)
        }, POLL_INTERVAL)
      } else {
        // 超过最大轮询次数
        videoSummary.value = null
        summaryLoading.value = false
        summaryError.value = errorMsg
      }
    } else {
      videoSummary.value = null
      summaryLoading.value = false
    }
  } catch (e) {
    console.error('获取视频总结失败:', e)
    videoSummary.value = null
    summaryLoading.value = false
  }
}

// 获取思维导图（支持轮询）
const fetchVideoMindmap = async (pollCount = 0) => {
  console.log('获取思维导图...', pollCount > 0 ? `(轮询 ${pollCount}/${MAX_POLL_COUNT})` : '')
  const bvid = fullVideoInfo.value?.bvid
  const page = pagesList.value[currentPageIndex.value]?.page || 1
  if (!bvid) return

  if (pollCount === 0) {
    mindmapLoading.value = true
    mindmapError.value = ''
  }

  try {
    const res = await getVideoMindmapApi({ bvid, page })
    if (res.code === 1 && res.data?.success) {
      mindmapData.value = res.data.data.mindmap
      mindmapLoading.value = false
      mindmapError.value = ''
    } else if (res.code === 1 && res.data?.success === false) {
      // 字幕尚未就绪，轮询重试
      const errorMsg = res.data?.error || '字幕尚未就绪，请稍后重试'
      if (pollCount < MAX_POLL_COUNT) {
        mindmapError.value = errorMsg
        mindmapPollTimer = setTimeout(() => {
          fetchVideoMindmap(pollCount + 1)
        }, POLL_INTERVAL)
      } else {
        // 超过最大轮询次数
        mindmapData.value = null
        mindmapLoading.value = false
        mindmapError.value = errorMsg
      }
    } else {
      mindmapData.value = null
      mindmapLoading.value = false
    }
  } catch (e) {
    console.error('获取思维导图失败:', e)
    mindmapData.value = null
    mindmapLoading.value = false
  }
}

// 同时获取总结和思维导图
const fetchSummaryAndMindmap = () => {
  // 先清除之前的轮询
  clearAllPolls()
  // 重置数据
  videoSummary.value = null
  mindmapData.value = null
  summaryError.value = ''
  mindmapError.value = ''
  // 开始获取
  fetchVideoSummary()
  fetchVideoMindmap()
}

// Mermaid 渲染完成回调
const handleRendered = (svg) => {
  console.log('思维导图渲染完成')
}

// Mermaid 渲染错误回调
const handleError = (err) => {
  console.error('思维导图渲染错误:', err)
}
</script>

<template>
  <!-- 模板部分保持不变 -->
  <div class="container">
    <div class="title" v-if="!(isLookVideo)">
      <h1>视频 智能搜索</h1>
      <p class="subtitle">输入学习主题，一键搜索讲解视频</p>
    </div>
    
    <Transition name="fade-slide" mode="out-in">
      <div class="inputBox" v-if="!isLookVideo">
        <!-- 左侧列表 -->
        <div class="left">

          <!-- 加载中 -->
          <div class="list-loading" v-if="showLoading"> 
            <el-icon class="is-loading" :size="60" color="var(--primary)"><Loading /></el-icon>
            <span class="loading-text">正在加载</span>
          </div>

          <!-- 列表为空 -->
          <div class="preview-placeholder" v-if="list.length === 0 && !showLoading">
            <img src="@/assets/image/emptyStatus.png" alt="" style="width: 170px; margin-bottom: 10px;">
            <p>暂无视频</p>
          </div>

          <!-- 列表不为空 -->
          <div class="list" v-if="list.length !== 0">
            <el-scrollbar height="100%" width="100%">
              <div class="scroll">
                <div class="itemBox" 
                  v-for="(item,index) in list" 
                  :key="index" 
                  :ref="itemRef[index]"
                >
                  <div class="topHead">
                    <div class="itemLeft">
                      <div class="text">{{ item.text }}</div>
                      <div class="ct">{{ item.createTime }}</div>
                    </div>

                    <div class="itemMid" v-if="item.status == 1">
                      <div class="loadingIcon">
                        <el-icon class="is-loading" :size="40" color="#2D7DDB"><Loading /></el-icon>
                      </div>
                      <div class="loadingText">搜索中</div>
                    </div>

                    <div class="itemMid" v-if="item.status == 3">
                      <div class="fail">
                        <el-icon class="shake-icon" :size="40"><CloseBold /></el-icon>
                        <div class="fail-text">搜索失败</div>
                      </div>
                    </div>
                    
                    <div class="itemRight" v-if="item.status == 2 || item.status == 3">
                      <div class="delete" @click="deleteItem(item.batchId)">删除</div>
                      <div class="isOpen" @click="openVideosList(index)" :class="item.videos === null ? '' : 'close'" v-if="item.status == 2">
                        {{ item.videos === null ? '展开' : '收起' }}
                      </div>
                    </div>
                  </div>

                  <TransitionGroup name="expand-down">
                    <div class="itemContent" 
                      v-if="item.videos !== null && item?.videos"
                    >
                      <el-scrollbar always>
                        <div class="scrollbar-flex-content">
                          <div
                            @click="lookVideo(index, ind)" 
                            v-for="(video,ind) in item.videos" 
                            :key="ind" 
                            class="scrollbar-demo-item"
                            :ref="(el) => setItemRef(el, index, ind)"
                            @mouseenter="handleEnter(index,ind,video.id)"
                            @mouseleave="popStore.delayHidePop"
                          >
                            <img 
                              :src="'https://images.weserv.nl?url=' + encodeURIComponent(video.thumbnail.startsWith('//') ? 'https:' + video.thumbnail : video.thumbnail)" 
                              alt="视频封面" 
                              class="video-thumb"
                            />
                            <div class="video-info">
                              <div class="icon-play">
                                <svg viewBox="0 0 1024 1024" width="60" height="60">
                                  <path d="M826.820379 900.364673a1.688226 1.688226 0 0 0 0-3.376452 1.688226 1.688226 0 0 0 0 3.376452z" fill="#ffffff"></path>
                                  <path d="M512 1023.999088A512.09521 512.09521 0 0 1 312.710552 40.247307a512.122222 512.122222 0 0 1 398.590151 943.504474 508.808797 508.808797 0 0 1-199.300703 40.247307z m0-984.595894a472.703271 472.703271 0 0 0-183.949101 908.062984A472.731408 472.731408 0 0 0 695.960356 76.521656 469.6307 469.6307 0 0 0 512 39.391939z" fill="#ffffff"></path>
                                  <path d="M357.651127 753.579053V270.420036l418.432434 241.573881z m39.391939-414.932179v346.70534l300.256616-173.324533z" fill="#ffffff"></path>
                                </svg>
                              </div>
                              <div class="video-title" :title="video.title">{{ video.title }}</div>
                              <div class="other-info">
                                <div class="video-author">UP主：{{ video.author }}</div>
                                <div class="video-playCount">播放量：{{ video.playCount }}</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </el-scrollbar>
                    </div>
                  </TransitionGroup>
                </div>
              </div>
            </el-scrollbar>
          </div>
        </div>

        <!-- 右侧表单 -->
        <div class="right">
          <el-form 
            :rules="Rules" 
            ref="videoRef" 
            :model="videoData" 
            label-position="top"
            class="video-form"
          >
            <el-form-item label="主题/知识点" prop="text">
              <el-input 
                v-model="videoData.text"
                size="large" 
                show-word-limit 
                maxlength="30" 
                placeholder="例如：人工智能的发展历史"
                clearable
              />
            </el-form-item>

            <el-form-item class="btn-item">
              <el-button 
                type="primary" 
                size="large" 
                class="submit-btn"
                @click="submit()"
                :disabled="btnDisvisible"
              >
                立即搜索
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </Transition>

    <!-- 播放器 -->
    <Transition name="fade-slide" mode="out-in">
      <div class="lookVideo" v-if="isLookVideo">
        <div class="lookHeader">
          <div class="lookBtn" @click="exitLook()">◀ 返回</div>
          <div class="video-title-header">
            <h1>{{ lookVideoData.title || fullVideoInfo?.title || '' }}</h1>
            <p class="subtitle">UP主：{{ lookVideoData.author || fullVideoInfo?.author || '' }}</p>
          </div>
        </div>

        <div class="player-with-pages">
          <div class="video-player-wrapper" @mousemove="showControlsTemporarily">
            <!-- 章节导航 -->
            <div class="chapter-nav-overlay" v-if="pagesList.length >= 1">
              <button class="chapter-nav-btn" @click="prevPage" :disabled="currentPageIndex === 0">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
              </button>
              <span class="chapter-indicator">{{ currentPageIndex + 1 }} / {{ pagesList.length }}</span>
              <button class="chapter-nav-btn" @click="nextPage" :disabled="currentPageIndex === pagesList.length - 1">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
              </button>
            </div>

            <!-- 加载遮罩 -->
            <div class="video-loading-overlay" v-if="isVideoLoading">
              <div class="loading-spinner"></div>
              <span>视频加载中...</span>
            </div>
            
            <!-- 错误遮罩 -->
            <div class="video-error-overlay" v-else-if="videoError">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="#ef4444"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
              <span>播放出错：{{ videoError }}</span>
              <button class="retry-btn" @click="loadVideoPage(currentPageIndex)">重试</button>
            </div>
            
            <video 
              ref="videoPlayerRef"
              class="video-player"
              preload="metadata"
              playsinline
              :poster="lookVideoData.thumbnail ? 'https://images.weserv.nl?url=' + encodeURIComponent(lookVideoData.thumbnail.startsWith('//') ? 'https:' + lookVideoData.thumbnail : lookVideoData.thumbnail) : ''"
            ></video>

            <!-- 自定义控制栏 -->
            <div class="custom-controls" :class="{ show: showControls }">
              <div class="controls-row">
                <button class="ctrl-btn" @click="togglePlay">
                  <svg v-if="!isPlaying" viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                </button>
                
                <div class="chapter-group" v-if="pagesList.length >= 1">
                  <button class="chapter-btn" @click="prevPage" :disabled="currentPageIndex === 0">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
                  </button>
                  <span class="chapter-indicator-small">{{ currentPageIndex + 1 }}/{{ pagesList.length }}</span>
                  <button class="chapter-btn" @click="nextPage" :disabled="currentPageIndex === pagesList.length - 1">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
                  </button>
                </div>
                
                <span class="time-display">{{ formattedCurrentTime }} / {{ formattedDuration }}</span>
                
                <div class="progress-bar" @click="seekTo">
                  <div class="progress-fill" :style="progressStyle"></div>
                  <div class="progress-thumb" :style="{ left: progressPercent + '%' }"></div>
                </div>
                
                <button class="ctrl-btn" @click="toggleMute">
                  <svg v-if="!isMuted" viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
                  <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/></svg>
                </button>
                
                <button class="ctrl-btn" @click="toggleFullscreen">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>
                </button>
              </div>
            </div>

            <!-- 底部当前分集信息 -->
            <div class="player-bottom-info" v-if="pagesList.length >= 1">
              <span class="current-page-label">当前播放：</span>
              <span class="current-page-title">P{{ pagesList[currentPageIndex]?.page || currentPageIndex + 1 }} {{ currentPageTitle }}</span>
            </div>
          </div>

          <!-- 分集列表 -->
          <div class="pages-sidebar" v-if="pagesList.length >= 1">
            <div class="pages-header">
              <span>分集列表</span>
              <span class="pages-count">共 {{ pagesList.length }} 集</span>
            </div>
            <div class="pages-scroll">
              <div 
                v-for="(page, idx) in pagesList" 
                :key="idx"
                class="page-item"
                :class="{ active: idx === currentPageIndex }"
                @click="switchPage(idx)"
              >
                <span class="page-num">P{{ page.page }}</span>
                <span class="page-title">{{ page.title || '未命名' }}</span>
                <span class="page-play" v-if="idx === currentPageIndex">▶</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 监控面板 -->
        <div class="monitor-panel">
          <div class="monitor-header">
            <span class="monitor-title">观看行为监控</span>
            <span class="monitor-status" :class="monitorDisplay.state.includes('播放') ? 'playing' : 'paused'">
              {{ monitorDisplay.state }}
            </span>
          </div>
          <div class="monitor-grid">
            <div class="monitor-item">
              <span class="label">本集播放进度</span>
              <span class="value">{{ monitorDisplay.progress }}</span>
            </div>
            <div class="monitor-item">
              <span class="label">已观看时长</span>
              <span class="value">{{ monitorDisplay.watchTime }}</span>
            </div>
            <div class="monitor-item">
              <span class="label">回溯次数（倒退次数）</span>
              <span class="value" :class="monitorDisplay.rewindCount > 0 ? 'danger' : ''">
                {{ monitorDisplay.rewindCount }}
              </span>
            </div>
            <div class="monitor-item">
              <span class="label">暂停次数</span>
              <span class="value">{{ monitorDisplay.pauseCount }}</span>
            </div>
            <div class="monitor-item">
              <span class="label">完播率</span>
              <span class="value success">{{ monitorDisplay.completion }}</span>
            </div>
          </div>
          
          <div class="rewind-detail" v-if="monitor.rewindEvents.length > 0">
            <h4>↩ 回溯详情 ({{ monitor.rewindEvents.length }}次)</h4>
            <div class="rewind-list">
              <div v-for="(evt, idx) in monitor.rewindEvents.slice(-5).reverse()" :key="idx" class="rewind-item">
                #{{ evt.index }}: {{ formatTime(evt.from) }} → {{ formatTime(evt.to) }} 
                (倒退 {{ formatTimeFull(evt.gap) }}) {{ evt.page ? 'P' + evt.page : '' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 视频总结和视频思维导图 -->
        <div class="summary-mindmap-section">
          <el-splitter class="summary-splitter">
            <!-- 左侧：思维导图 -->
            <el-splitter-panel min="300px" default="50%">
              <div class="panel-container">
                <div class="panel-header">
                  <el-icon><Connection /></el-icon>
                  <span>思维导图</span>
                </div>
                <div class="panel-content">
                  <div v-if="mindmapLoading" class="loading-state">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>加载思维导图中...</span>
                    <span v-if="mindmapError" class="polling-hint">Agent正在读取视频内容总结中，请稍后......</span>
                  </div>
                  <div v-else-if="!mindmapData" class="empty-state">
                    <el-icon><PictureFilled /></el-icon>
                    <span v-if="mindmapError">{{ mindmapError }}</span>
                    <span v-else>暂无思维导图</span>
                  </div>
                  <Mermaid
                    v-else
                    ref="mindmapRef"
                    :mindmap-data="mindmapData"
                    @rendered="handleRendered"
                    @error="handleError"
                  />
                </div>
              </div>
            </el-splitter-panel>

            <!-- 右侧：视频总结 -->
            <el-splitter-panel min="300px">
              <div class="panel-container">
                <div class="panel-header">
                  <el-icon><Document /></el-icon>
                  <span>视频总结</span>
                </div>
                <div class="panel-content summary-content">
                  <div v-if="summaryLoading" class="loading-state">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>加载总结中...</span>
                    <span v-if="summaryError" class="polling-hint">Agent正在读取视频内容总结中，请稍后......</span>
                  </div>
                  <div v-else-if="!videoSummary" class="empty-state">
                    <el-icon><Document /></el-icon>
                    <span v-if="summaryError">{{ summaryError }}</span>
                    <span v-else>暂无视频总结</span>
                  </div>
                  <div v-else class="summary-wrapper">
                    <!-- 内容总结 -->
                    <div class="summary-card summary-card--highlight">
                      <div class="summary-card-header">
                        <el-icon><InfoFilled /></el-icon>
                        <span>内容总结</span>
                      </div>
                      <p class="summary-text">{{ videoSummary.summary }}</p>
                    </div>

                    <!-- 关键要点 -->
                    <div v-if="videoSummary.key_points && videoSummary.key_points.length" class="summary-card">
                      <div class="summary-card-header">
                        <el-icon><Star /></el-icon>
                        <span>关键要点</span>
                      </div>
                      <ol class="key-points-list">
                        <li v-for="(point, idx) in videoSummary.key_points" :key="idx" class="key-point-item">
                          <span class="key-point-badge">{{ idx + 1 }}</span>
                          <span class="key-point-text">{{ point }}</span>
                        </li>
                      </ol>
                    </div>

                    <!-- 章节详述 -->
                    <div v-if="videoSummary.sections && videoSummary.sections.length" class="summary-card">
                      <div class="summary-card-header">
                        <el-icon><List /></el-icon>
                        <span>章节详述</span>
                      </div>
                      <div class="sections-timeline">
                        <div v-for="(section, idx) in videoSummary.sections" :key="idx" class="timeline-item">
                          <div class="timeline-dot"></div>
                          <div class="timeline-line" v-if="idx < videoSummary.sections.length - 1"></div>
                          <div class="timeline-content">
                            <div class="timeline-title">{{ section.title }}</div>
                            <p class="timeline-desc">{{ section.content }}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </el-splitter-panel>
          </el-splitter>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ================= 页面过渡动画 ================= */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.5s ease-in-out;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.98);
}

.expand-down-enter-active,
.expand-down-leave-active {
  transition: all 0.5s ease-in-out;
  overflow: hidden;
}
.expand-down-enter-from {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}
.expand-down-enter-to {
  max-height: 500px;
  opacity: 1;
  transform: translateY(0);
}
.expand-down-leave-from {
  max-height: 500px;
  opacity: 1;
  transform: translateY(0);
}
.expand-down-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}

/* ================= 容器 ================= */
.container {
  position: relative;
  width: 100%;
  height: 85vh;
  padding: 0 30px;
  box-sizing: border-box;
  background: transparent;
  overflow: hidden;
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

.inputBox {
  width: 100%;
  height: 85%;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}
.inputBox .left {
  position: relative;
  flex: 1;
  min-height: 400px;
  max-width: 70%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.preview-placeholder {
  text-align: center;
  color: var(--text-gray);
}
.inputBox .right {
  width: 400px;
  height: 200px;
  background-color: var(--bg-card);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);
  padding: 30px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.video-form {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: end;
}
.btn-item {
  margin-bottom: 0;
  margin-top: 10px;
}
.submit-btn {
  width: 100%;
  font-weight: bold;
  letter-spacing: 1px;
  transition: all 0.3s;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--primary-hv);
}

/* ================= 列表 ================= */
.list-loading {
  position: absolute;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  color: var(--text-gray);
  background-color: var(--bg-page);
}
.loading-text {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out;
}
.loading-text::after {
  content: '...';
  animation: dots 1.5s steps(5, end) infinite;
}
.el-icon.is-loading {
  animation: rotating 2s linear infinite;
}
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}

.left .list {
  width: 100%;
  height: 100%;
}
.list .scroll {
  width: 100%;
  height: 100%;
  padding: 20px;
}
.list .scroll .itemBox {
  padding: 10px 20px;
  width: 100%;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  border-radius: 12px;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  transition: all 0.3s;
  box-shadow: var(--shadow-normal);
}
.itemBox.showVideo {
  height: 300px;
}


.itemBox .topHead {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.topHead .itemLeft .text {
  max-width: 700px;
  /* 溢出隐藏 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}
.topHead .itemLeft .ct {
  font-size: 14px;
  color: var(--text-gray);
}
.topHead .itemRight {
  display: flex;
  gap: 10px;
}
.topHead .itemRight .delete {
  font-size: 14px;
  color: var(--main-delete);
  border: 1px solid var(--main-delete);
  padding: 6px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
}
.topHead .itemRight .delete:hover {
  background-color: var(--main-delete);
  color: var(--bg-card);
}
.topHead .itemRight .isOpen {
  font-size: 14px;
  color: var(--primary);
  border: 1px solid var(--primary);
  padding: 6px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
}
.topHead .itemRight .isOpen:hover {
  background-color: var(--primary);
  color: var(--bg-card);
}
.topHead .itemRight .isOpen.close {
  color: var(--coming);
  border-color: var(--coming);
}
.topHead .itemRight .isOpen.close:hover {
  background-color: var(--coming);
  color: var(--bg-card);
}

.itemMid {
  display: flex;
  justify-content: center;
  align-items: center;
}
.loadingIcon {
  width: 100px;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.loadingText {
  color: var(--primary);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out;
}
.loadingText::after {
  content: '...';
  animation: dots 1.5s steps(5, end) infinite;
}
.fail {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--main-delete);
}
.fail .shake-icon {
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
}
.fail .fail-text {
  font-size: 14px;
  font-weight: 500;
  opacity: 0;
  animation: fade-in-up 0.5s ease-out forwards;
  animation-delay: 0.3s;
}
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.itemBox .itemContent {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.itemContent .scrollbar-flex-content {
  padding: 10px;
  display: flex;
}

.scrollbar-demo-item {
  flex-shrink: 0;
  position: relative;
  width: 290px;
  height: 180px;
  margin: 10px;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  box-shadow: var(--shadow-normal);
}
.video-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-info {
  position: absolute;
  inset: 0;
  color: #fff;
  background: rgba(0,0,0,0.7);
  opacity: 0;
  visibility: hidden;
  transform: translateY(8px);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 12px;
}
.scrollbar-demo-item:hover .video-info {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.video-info .icon-play {
  text-align: center;
  margin-bottom: 10px;
}
.video-info .video-title {
  font-size: 14px;
  font-weight: 700;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.video-info .other-info {
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  opacity: 0.8;
}

/* ================= 播放器 ================= */
.lookVideo {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  background: transparent;
  padding: 10px 30px 20px;
  box-sizing: border-box;
  overflow-y: auto;
}

.lookHeader {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 12px;
}
.lookBtn {
  font-size: 20px;
  color: var(--text-body);
  cursor: pointer;
  transition: color 0.3s;
}
.lookBtn:hover {
  color: var(--primary);
}
.video-title-header {
  flex: 1;
  min-width: 0;
}
.video-title-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.video-title-header .subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

.player-with-pages {
  display: flex;
  gap: 16px;
  max-width: 1400px;
  margin: 0 auto;
  height: calc(100% - 80px);
  min-height: 400px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.video-player-wrapper {
  flex: 1;
  position: relative;
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  /* height: 100%;
  min-height: 400px;
  max-height: 600px; */
  max-width: 1100px;
  aspect-ratio: 16 / 9;
  
}

.video-player {
  width: 100%;
  height: 100%;
  display: block;
  background: #000;
  object-fit: contain;
}
/* 隐藏原生控制栏 */
.video-player::-webkit-media-controls {
  display: none !important;
}
.video-player::-webkit-media-controls-enclosure {
  display: none !important;
}
.video-player::-webkit-media-controls-panel {
  display: none !important;
}

/* 章节导航 */
.chapter-nav-overlay {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(0,0,0,0.6);
  padding: 6px 16px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.1);
}
.chapter-nav-btn {
  background: rgba(255,255,255,0.15);
  border: none;
  color: #fff;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 12px;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chapter-nav-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.3);
}
.chapter-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.chapter-indicator {
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  min-width: 50px;
  text-align: center;
}

/* 加载遮罩 */
.video-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  background: rgba(0,0,0,0.7);
  color: #fff;
  /* 15 */
  z-index: 2;
  border-radius: 12px;
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #fb7299;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.video-error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  background: rgba(0,0,0,0.8);
  color: #ef4444;
  /* 15 */
  z-index: 2;
  border-radius: 12px;
}
.video-error-overlay span {
  color: #fff;
  font-size: 14px;
}
.retry-btn {
  margin-top: 12px;
  padding: 8px 24px;
  background: #fb7299;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.3s;
}
.retry-btn:hover {
  background: #e66080;
}

/* 自定义控制栏 */
.custom-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  /* 25 */
  z-index: 2;
  background: linear-gradient(transparent, rgba(0,0,0,0.85));
  padding: 30px 16px 12px;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.video-player-wrapper:hover .custom-controls,
.custom-controls.show {
  opacity: 1;
}
.controls-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ctrl-btn {
  background: none;
  border: none;
  color: #fff;
  cursor: pointer;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: background 0.2s;
}
.ctrl-btn:hover {
  background: rgba(255,255,255,0.1);
}

.chapter-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.chapter-btn {
  background: none;
  border: none;
  color: #aaa;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.chapter-btn:hover:not(:disabled) {
  color: #fff;
  background: rgba(255,255,255,0.1);
}
.chapter-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.chapter-indicator-small {
  color: #aaa;
  font-size: 11px;
  min-width: 36px;
  text-align: center;
}

.time-display {
  color: #ccc;
  font-size: 12px;
  min-width: 80px;
  font-variant-numeric: tabular-nums;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.3);
  border-radius: 2px;
  cursor: pointer;
  position: relative;
}
.progress-fill {
  height: 100%;
  background: #fb7299;
  border-radius: 2px;
  transition: width 0.1s;
}
.progress-thumb {
  position: absolute;
  top: 50%;
  width: 12px;
  height: 12px;
  background: #fb7299;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.2s;
}
.progress-bar:hover .progress-thumb {
  opacity: 1;
}

/* 底部信息 */
.player-bottom-info {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1;
  background: rgba(0,0,0,0.7);
  padding: 4px 16px;
  border-radius: 16px;
  backdrop-filter: blur(4px);
  color: #fff;
  font-size: 13px;
  max-width: 80%;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.current-page-label {
  color: rgba(255,255,255,0.6);
}
.current-page-title {
  font-weight: 500;
}

/* 分集列表 */
.pages-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 600px;
  overflow: hidden;
}
.pages-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: var(--text-title);
  flex-shrink: 0;
}
.pages-count {
  font-size: 12px;
  color: var(--text-gray);
  font-weight: 400;
}
.pages-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.pages-scroll::-webkit-scrollbar {
  width: 4px;
}
.pages-scroll::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 2px;
}
.pages-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--primary);
}

.page-item {
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}
.page-item:hover {
  background: var(--bg-page);
}
.page-item.active {
  background: var(--bg-page);
  border-left-color: var(--primary);
}
.page-item .page-num {
  font-weight: 600;
  color: var(--text-gray);
  font-size: 13px;
  flex-shrink: 0;
}
.page-item.active .page-num {
  color: var(--primary);
}
.page-item .page-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-body);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.page-item.active .page-title {
  color: var(--text-title);
}
.page-item .page-play {
  color: var(--primary);
  font-size: 14px;
}

/* 监控面板 */
.monitor-panel {
  max-width: 1400px;
  margin: 12px auto 0;
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid var(--border-color);
}
.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.monitor-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}
.monitor-status {
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.monitor-status.playing {
  background: #d5f5e3;
  color: #065f46;
}
.monitor-status.paused {
  background: #dbeafe;
  color: #1e40af;
}
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}
.monitor-item {
  background: var(--bg-page);
  padding: 8px 12px;
  border-radius: 8px;
  text-align: center;
}
.monitor-item .label {
  font-size: 12px;
  color: var(--text-gray);
  display: block;
  margin-bottom: 2px;
}
.monitor-item .value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}
.monitor-item .value.danger {
  color: #ef4444;
}
.monitor-item .value.success {
  color: #10b981;
}

.rewind-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}
.rewind-detail h4 {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 6px;
}
.rewind-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.rewind-item {
  font-size: 12px;
  color: var(--text-body);
  background: var(--bg-page);
  padding: 2px 10px;
  border-radius: 12px;
  font-family: monospace;
}

/* ================= 响应式 ================= */
@media (max-width: 900px) {
  .player-with-pages {
    flex-direction: column;
    height: auto;
    min-height: auto;
  }
  .video-player-wrapper {
    max-height: 400px;
    min-height: 250px;
    width: 100%;
  }
  .pages-sidebar {
    width: 100%;
    max-height: 150px;
    flex-direction: row;
  }
  .pages-scroll {
    display: flex;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 8px 12px;
  }
  .pages-scroll::-webkit-scrollbar {
    height: 4px;
    width: 0;
  }
  .page-item {
    white-space: nowrap;
    border-left: none;
    border-bottom: 3px solid transparent;
    padding: 8px 14px;
    flex-shrink: 0;
  }
  .page-item.active {
    border-bottom-color: var(--primary);
    border-left-color: transparent;
  }
  .pages-header {
    flex-shrink: 0;
  }
  .chapter-nav-overlay {
    top: 10px;
    padding: 4px 12px;
    gap: 8px;
  }
  .chapter-nav-btn {
    font-size: 14px;
    padding: 2px 8px;
  }
  .chapter-indicator {
    font-size: 11px;
    min-width: 40px;
  }
  .player-bottom-info {
    bottom: 50px;
    font-size: 11px;
    padding: 2px 12px;
  }
  .controls-row {
    gap: 6px;
  }
  .ctrl-btn {
    padding: 2px 4px;
  }
  .ctrl-btn svg {
    width: 18px;
    height: 18px;
  }
  .time-display {
    font-size: 10px;
    min-width: 60px;
  }
}

/* Element Plus 覆盖 */
:deep(.el-form-item) {
  margin-bottom: 10px;
}
:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-gray);
}
:deep(.el-button--primary) {
  --el-button-bg-color: var(--primary);
  --el-button-border-color: var(--primary);
  --el-button-hover-bg-color: var(--primary-hv);
  --el-button-hover-border-color: var(--primary-hv);
  --el-button-active-color: var(--primary-act);
  --el-button-active-bg-color: var(--primary-act);
  --el-button-active-border-color: var(--primary-act);
  --el-button-disabled-bg-color: var(--primary-disa-bgc);
  --el-button-disabled-border-color: var(--primary-disa-border);
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}

/* ================= 视频总结与思维导图 ================= */
.summary-mindmap-section {
  width: 100%;
  max-width: 1400px;
  margin: 20px auto;
  height: 600px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-card);
}

.summary-splitter {
  width: 100%;
  height: 100%;
}

.panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border-color);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}

.panel-header .el-icon {
  color: var(--primary);
}

.panel-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--text-gray);
  font-size: 14px;
}

.loading-state .el-icon,
.empty-state .el-icon {
  font-size: 48px;
  color: var(--primary);
}

.polling-hint {
  font-size: 12px;
  color: var(--warning);
  text-align: center;
  max-width: 80%;
}

.summary-content {
  padding: 20px;
}

.summary-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.summary-card {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
}

.summary-card--highlight {
  background: var(--primary-light);
  border-color: var(--primary-fade);
}

.summary-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.summary-card--highlight .summary-card-header {
  border-bottom-color: var(--primary-fade);
}

.summary-card-header .el-icon {
  font-size: 16px;
}

.summary-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-body);
  text-align: justify;
  margin: 0;
}

.key-points-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.key-point-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.key-point-badge {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  background: var(--primary);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.key-point-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-body);
  flex: 1;
}

.sections-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  position: relative;
  padding-left: 24px;
  padding-bottom: 16px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: 0;
  top: 4px;
  width: 10px;
  height: 10px;
  background: var(--primary);
  border: 2px solid var(--bg-card);
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--primary-fade);
}

.timeline-line {
  position: absolute;
  left: 4px;
  top: 16px;
  bottom: 0;
  width: 2px;
  background: var(--primary-fade);
}

.timeline-content {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 6px;
}

.timeline-desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-body);
  margin: 0;
}

/* 滚动条美化 */
.panel-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.panel-content::-webkit-scrollbar-track {
  background: var(--bg-hover);
  border-radius: 3px;
}

.panel-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.panel-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}

/* 夜间模式适配 */
:deep(.dark) .summary-mindmap-section {
  background: var(--bg-card);
  border-color: var(--border-color);
}

:deep(.dark) .panel-header {
  background: var(--bg-hover);
  border-bottom-color: var(--border-color);
}

:deep(.dark) .section-item {
  background: var(--bg-hover);
}
</style>