<!-- 移动端视频微课组件 -->
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import {
  getListByUserIdApi,
  searchApi,
  getProgressApi,
  deleteByIdApi,
  getVideoStreamApi,
  getVideoInfoApi,
  getVideoSummaryApi,
  getVideoMindmapApi
} from '@/api/mainApi/resourceVideo.js'
import MindmapNode from './MindmapNode.vue'
import { isSkip, removeSkip } from '@/utils/skip.js'

const router = useRouter()

// =================== 用户 =====================
let loginUser = null
const userId = ref(null)

onMounted(async () => {
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
  // 检查是否有跳转信息需要自动打开视频
  const skipInfo = isSkip(5)
  if (skipInfo && skipInfo.resourceId) {
    try {
      // 先在列表中查找
      let found = false
      for (let i = 0; i < list.value.length; i++) {
        const batch = list.value[i]
        if (batch.videos) {
          const vIdx = batch.videos.findIndex(v => v.pythonId == skipInfo.resourceId || v.id == skipInfo.resourceId)
          if (vIdx !== -1) {
            lookVideo(i, vIdx)
            found = true
            break
          }
        }
      }
      if (!found) {
        // 列表中找不到，通过API获取视频信息后用BV号打开
        const res = await getVideoInfoApi(skipInfo.resourceId)
        if (res.code && res.data) {
          const videoData = res.data.data || res.data
          const url = videoData.url || ''
          const bvidMatch = url.match(/BV[0-9A-Za-z]{10}/)
          if (bvidMatch) {
            // 构造临时数据用lookVideo流程打开
            const tempItem = { url: bvidMatch[0], title: videoData.title || '视频', author: videoData.author || '' }
            lookVideoData.value = tempItem
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
            isLookVideo.value = true
            await new Promise(resolve => setTimeout(resolve, 100))
            const infoResult = await getVideoInfoApi(bvidMatch[0], 1)
            if (infoResult.code === 1 && infoResult.data) {
              const videoInfo = infoResult.data.data || infoResult.data
              fullVideoInfo.value = videoInfo
              lookVideoData.value.title = videoInfo.title || tempItem.title
              if (videoInfo.pages && videoInfo.pages.length > 0) {
                pagesList.value = videoInfo.pages.map((p, idx) => ({
                  ...p, index: idx,
                  label: 'P' + p.page + (p.title ? ' ' + p.title : '')
                }))
              } else {
                pagesList.value = [{ page: 1, title: videoInfo.title || 'P1', cid: videoInfo.cid, index: 0, label: 'P1' }]
              }
              await loadVideoPage(0)
              fetchSummaryAndMindmap()
            }
          } else {
            showToast('无法解析视频ID')
          }
        } else {
          showToast('该视频不存在，可能已被删除')
        }
      }
    } catch (e) {
      console.error('打开视频失败', e)
      showToast('打开视频失败')
    }
    removeSkip(5)
  }
  await checkTask()
})

onUnmounted(() => {
  if (videoPlayerRef.value) {
    videoPlayerRef.value.pause()
    videoPlayerRef.value.src = ''
    videoPlayerRef.value.load()
  }
})

// =================== 搜索表单 =====================
const btnDisvisible = ref(false)
const videoData = ref({ userId: null, text: '' })
const showLoading = ref(false)
const list = ref([])
const taskProgress = ref([])

// =================== 列表 =====================
const getSearchList = async () => {
  try {
    showLoading.value = true
    const res = await getListByUserIdApi(userId.value)
    if (res.code) {
      list.value = res.data || []
      addVideos()
    } else {
      showFailToast('查询失败')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
  showLoading.value = false
}

const getProgress = async (batchId) => {
  try {
    const result = await getProgressApi(batchId)
    if (result.code) {
      taskProgress.value = result.data
    }
  } catch (e) {
    console.error('获取进度失败', e)
  }
}

const deleteItem = async (batchId, isShow = true) => {
  if (isShow) {
    await showConfirmDialog({ title: '提示', message: '是否删除该任务项？' })
  }
  try {
    const result = await deleteByIdApi(batchId)
    if (result.code) {
      showSuccessToast('删除成功')
      await getSearchList()
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      console.error('删除失败', e)
    }
  }
}

// =================== 列表交互 =====================
const openVideosList = async (index) => {
  if (list.value[index].videos == null || !list.value[index]?.videos) {
    await getProgress(list.value[index].batchId)
    try {
      if (taskProgress.value[0]?.status === 2) {
        list.value[index].videos = [...taskProgress.value]
        taskProgress.value = []
      }
    } catch (e) {
      console.error('获取进度失败', e)
      showFailToast('展开失败')
      taskProgress.value = []
    }
  } else {
    list.value[index].videos = null
  }
}

const addVideos = () => {
  for (let i = 0; i < list.value.length; i++) {
    list.value[i].videos = null
  }
}

// =================== 检查截断任务 =====================
const checkTask = async () => {
  btnDisvisible.value = true
  for (let i = 0; i < list.value.length; i++) {
    addVideos()
    const item = list.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0; const maxNum = 15
      try {
        await getProgress(item.batchId)
        if (!(taskProgress.value.length == 0)) {
          if (taskProgress.value[0].status == null) {
            item.status = 3
            await deleteItem(item.batchId, false)
            await getSearchList()
            taskProgress.value = []
            continue
          }
        }
      } catch (e) { continue }

      while (taskProgress.value.length == 0 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try { await getProgress(item.batchId) } catch (e) { break }
      }

      if (taskProgress.value[0]?.status == 2) {
        await getSearchList()
        taskProgress.value = []
      } else {
        await getSearchList()
        taskProgress.value = []
      }
    }
  }
  btnDisvisible.value = false
}

// =================== 提交搜索 =====================
const submit = async () => {
  if (!videoData.value.text || !videoData.value.text.trim()) {
    showToast('请输入主题/大纲'); return
  }
  if (videoData.value.text.length > 30) {
    showToast('长度不能超过30个字符'); return
  }
  btnDisvisible.value = true
  videoData.value.userId = userId.value

  try {
    const result = await searchApi(videoData.value)
    if (result.code) {
      showSuccessToast('提交成功')
      if (result.data.status == 1 || result.data.status == null) {
        let nowNum = 0; const maxNum = 15
        try {
          await getProgress(result.data.batchId)
          if (!(taskProgress.value.length == 0)) {
            if (taskProgress.value[0].status == null) {
              await deleteItem(result.data.batchId, false)
              await getSearchList()
              taskProgress.value = []
            }
          }
        } catch (e) {}

        await getSearchList()

        while (taskProgress.value.length == 0 && nowNum < maxNum) {
          nowNum++
          await new Promise(resolve => setTimeout(resolve, 10000))
          try { await getProgress(result.data.batchId) } catch (e) {}
        }

        if (taskProgress.value[0]?.status == 2) {
          await getSearchList()
          taskProgress.value = []
        } else {
          await getSearchList()
          taskProgress.value = []
        }
      } else if (result.data.status == 2 || result.data.status == 3) {
        await getSearchList()
        taskProgress.value = []
      }
      videoData.value = { userId: null, text: '' }
    } else {
      showFailToast('提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
  }
}

// =================== 视频播放器 =====================
const isLookVideo = ref(false)
const lookVideoData = ref({})
const videoPlayerRef = ref(null)
const isVideoLoading = ref(false)
const videoError = ref(null)

const fullVideoInfo = ref(null)
const pagesList = ref([])
const currentPageIndex = ref(0)

const isPlaying = ref(false)
const currentTime = ref(0)
const videoDuration = ref(0)
const progressPercent = ref(0)
const formattedCurrentTime = ref('0:00')
const formattedDuration = ref('0:00')
const isMuted = ref(false)

const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m + ':' + (s < 10 ? '0' : '') + s
}

const progressStyle = computed(() => ({ width: progressPercent.value + '%' }))

const currentPageTitle = computed(() => {
  if (pagesList.value.length > 0 && currentPageIndex.value < pagesList.value.length) {
    return pagesList.value[currentPageIndex.value]?.title || ''
  }
  return ''
})

// 查看视频
const lookVideo = async (index, ind) => {
  const videoDataItem = list.value[index].videos[ind]
  lookVideoData.value = videoDataItem

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

  isLookVideo.value = true

  await new Promise(resolve => setTimeout(resolve, 100))

  try {
    const url = videoDataItem.url
    const bvidMatch = url.match(/BV[0-9A-Za-z]{10}/)
    if (!bvidMatch) {
      showFailToast('无法解析视频ID')
      isVideoLoading.value = false
      return
    }
    const bvid = bvidMatch[0]

    const infoResult = await getVideoInfoApi(bvid, 1)
    if (infoResult.code !== 1 || !infoResult.data) {
      showFailToast(infoResult.msg || '获取视频信息失败')
      isVideoLoading.value = false
      return
    }

    const videoInfo = infoResult.data.data || infoResult.data
    fullVideoInfo.value = videoInfo

    lookVideoData.value.title = videoInfo.title || videoDataItem.title
    lookVideoData.value.author = videoInfo.author || videoDataItem.author

    if (videoInfo.pages && videoInfo.pages.length > 0) {
      pagesList.value = videoInfo.pages.map((p, idx) => ({
        ...p, index: idx,
        label: `P${p.page}${p.title ? ' ' + p.title : ''}`
      }))
    } else {
      pagesList.value = [{
        page: 1, title: videoInfo.title || 'P1',
        cid: videoInfo.cid, index: 0, label: 'P1'
      }]
    }

    await loadVideoPage(0)
    fetchSummaryAndMindmap()
  } catch (err) {
    console.error('加载视频失败:', err)
    showFailToast('加载视频失败')
    isVideoLoading.value = false
    videoError.value = err.message
  }
}

// 加载分集
const loadVideoPage = async (pageIndex) => {
  if (!fullVideoInfo.value) return
  isVideoLoading.value = true
  videoError.value = null
  currentPageIndex.value = pageIndex

  const page = pagesList.value[pageIndex]
  if (!page) {
    showFailToast('分集不存在')
    isVideoLoading.value = false
    return
  }

  try {
    const bvid = fullVideoInfo.value.bvid
    const pageNum = page.page

    const infoResult = await getVideoInfoApi(bvid, pageNum)
    if (infoResult.code !== 1 || !infoResult.data) {
      showFailToast('获取分集信息失败')
      isVideoLoading.value = false
      return
    }

    const videoInfo = infoResult.data.data || infoResult.data
    if (!videoInfo.streams || videoInfo.streams.length === 0) {
      showFailToast('未获取到视频流地址')
      isVideoLoading.value = false
      return
    }

    const streamUrl = videoInfo.streams[0].url
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

    const videoEl = videoPlayerRef.value
    if (!videoEl) {
      isVideoLoading.value = false
      return
    }

    videoEl.pause()
    videoEl.removeAttribute('src')
    videoEl.load()

    if (videoInfo.duration) {
      videoDuration.value = videoInfo.duration
      formattedDuration.value = formatTime(videoInfo.duration)
    }

    videoEl.currentTime = 0
    progressPercent.value = 0
    formattedCurrentTime.value = '0:00'
    currentTime.value = 0

    videoEl.src = videoSrc
    videoEl.load()

    const playVideo = () => {
      try { videoEl.play() } catch (playErr) { console.warn('自动播放被阻止:', playErr) }
    }

    if (videoEl.readyState >= 3) {
      playVideo()
      isVideoLoading.value = false
    } else {
      const onCanPlay = () => {
        videoEl.removeEventListener('canplay', onCanPlay)
        playVideo()
        isVideoLoading.value = false
      }
      videoEl.addEventListener('canplay', onCanPlay)
      setTimeout(() => {
        videoEl.removeEventListener('canplay', onCanPlay)
        if (isVideoLoading.value) isVideoLoading.value = false
      }, 15000)
    }

    bindVideoEvents(videoEl)
  } catch (err) {
    console.error('加载分集失败:', err)
    showFailToast('加载分集失败')
    isVideoLoading.value = false
    videoError.value = err.message
  }
}

// 绑定视频事件
const bindVideoEvents = (video) => {
  if (!video) return
  video.addEventListener('play', () => { isPlaying.value = true })
  video.addEventListener('pause', () => { isPlaying.value = false })
  video.addEventListener('timeupdate', () => {
    if (!video.duration || isNaN(video.duration)) return
    const cur = video.currentTime
    const dur = video.duration
    currentTime.value = cur
    videoDuration.value = dur
    progressPercent.value = (cur / dur) * 100
    formattedCurrentTime.value = formatTime(cur)
    formattedDuration.value = formatTime(dur)
  })
  video.addEventListener('ended', () => {
    isPlaying.value = false
    progressPercent.value = 100
    if (currentPageIndex.value < pagesList.value.length - 1) {
      loadVideoPage(currentPageIndex.value + 1)
    }
  })
  video.addEventListener('error', () => {
    videoError.value = '视频加载错误'
    isVideoLoading.value = false
  })
  video.addEventListener('waiting', () => { isVideoLoading.value = true })
  video.addEventListener('playing', () => { isVideoLoading.value = false })
}

// 播放控制
const togglePlay = () => {
  const video = videoPlayerRef.value
  if (!video) return
  if (video.paused) { video.play() } else { video.pause() }
}

const seekTo = (event) => {
  const video = videoPlayerRef.value
  if (!video || !video.duration) return
  const rect = event.currentTarget.getBoundingClientRect()
  const pct = (event.clientX - rect.left) / rect.width
  video.currentTime = Math.max(0, Math.min(1, pct)) * video.duration
}

const toggleMute = () => {
  const video = videoPlayerRef.value
  if (!video) return
  video.muted = !video.muted
  isMuted.value = video.muted
}

const switchPage = (index) => {
  if (index === currentPageIndex.value) return
  const video = videoPlayerRef.value
  if (video) video.pause()
  isPlaying.value = false
  isVideoLoading.value = true
  loadVideoPage(index)
  fetchSummaryAndMindmap()
}

const prevPage = () => {
  if (currentPageIndex.value > 0) switchPage(currentPageIndex.value - 1)
}

const nextPage = () => {
  if (currentPageIndex.value < pagesList.value.length - 1) switchPage(currentPageIndex.value + 1)
}

const exitLook = () => {
  const video = videoPlayerRef.value
  if (video) {
    video.pause()
    video.src = ''
    video.load()
  }
  clearAllPolls()
  isLookVideo.value = false
  lookVideoData.value = {}
  fullVideoInfo.value = null
  pagesList.value = []
  currentPageIndex.value = 0
  isVideoLoading.value = false
  videoError.value = null
  isPlaying.value = false
  mindmapData.value = null
  videoSummary.value = null
}

const isOpenList = ref(false)

// =================== 视频总结与思维导图 =====================
const mindmapData = ref(null)
const videoSummary = ref(null)
const summaryLoading = ref(false)
const mindmapLoading = ref(false)
const summaryError = ref('')
const mindmapError = ref('')

const POLL_INTERVAL = 10000
const MAX_POLL_COUNT = 100

let summaryPollTimer = null
let mindmapPollTimer = null

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

const fetchVideoSummary = async (pollCount = 0) => {
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
      const errorMsg = res.data?.error || '字幕尚未就绪，请稍后重试'
      if (pollCount < MAX_POLL_COUNT) {
        summaryError.value = errorMsg
        summaryPollTimer = setTimeout(() => {
          fetchVideoSummary(pollCount + 1)
        }, POLL_INTERVAL)
      } else {
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

const fetchVideoMindmap = async (pollCount = 0) => {
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
      const errorMsg = res.data?.error || '字幕尚未就绪，请稍后重试'
      if (pollCount < MAX_POLL_COUNT) {
        mindmapError.value = errorMsg
        mindmapPollTimer = setTimeout(() => {
          fetchVideoMindmap(pollCount + 1)
        }, POLL_INTERVAL)
      } else {
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

const fetchSummaryAndMindmap = () => {
  clearAllPolls()
  videoSummary.value = null
  mindmapData.value = null
  summaryError.value = ''
  mindmapError.value = ''
  fetchVideoSummary()
  fetchVideoMindmap()
}


</script>

<template>
  <div class="phone-video">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">视频微课</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isLookVideo" class="video-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">视频 智能搜索</h2>
        <p class="page-desc">输入学习主题，一键搜索讲解视频</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="videoData.text"
          placeholder="例如：人工智能的发展历史"
          maxlength="30"
          show-word-limit
          clearable
          class="video-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="搜索中..."
          @click="submit"
          class="submit-btn"
        >
          立即搜索
        </van-button>
      </div>

      <!-- 列表 -->
      <div class="list-section">
        <div v-if="showLoading" class="list-loading">
          <van-loading type="spinner" color="var(--primary)" />
          <span>正在加载</span>
        </div>

        <div v-else-if="list.length > 0" class="list-wrap">
          <div
            v-for="(item, index) in list"
            :key="index"
            class="list-item"
          >
            <div class="item-header">
              <div class="item-left">
                <div class="item-text">{{ item.text }}</div>
                <div class="item-time">{{ item.createTime }}</div>
              </div>
              <div class="item-mid" v-if="item.status == 1 || item.status == null">
                <van-loading type="spinner" size="20" color="var(--primary)" />
                <span class="status-text">搜索中</span>
              </div>
              <div class="item-mid" v-if="item.status == 3">
                <van-icon name="warning-o" size="20" color="#F56C6C" />
                <span class="fail-text">搜索失败</span>
              </div>
              <div class="item-right" v-if="item.status == 2 || item.status == 3">
                <van-icon name="delete-o" class="action-icon delete-icon" @click="deleteItem(item.batchId)" />
                <van-button
                  v-if="item.status == 2"
                  size="mini"
                  plain
                  type="primary"
                  @click="openVideosList(index)"
                >
                  {{ item.videos === null ? '展开' : '收起' }}
                </van-button>
              </div>
            </div>

            <!-- 视频列表 -->
            <div v-if="item.videos !== null && item?.videos" class="video-grid">
              <div
                v-for="(video, ind) in item.videos"
                :key="ind"
                class="video-card"
                @click="lookVideo(index, ind)"
              >
                <div class="video-thumb-wrap">
                  <img
                    :src="'https://images.weserv.nl?url=' + encodeURIComponent(video.thumbnail.startsWith('//') ? 'https:' + video.thumbnail : video.thumbnail)"
                    alt="视频封面"
                    class="video-thumb"
                  />
                  <div class="play-overlay">
                    <van-icon name="play-circle-o" size="36" color="#fff" />
                  </div>
                </div>
                <div class="video-title">{{ video.title }}</div>
                <div class="video-meta">
                  <span>{{ video.author }}</span>
                  <span>{{ video.playCount }}播放</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <van-empty description="暂无视频" />
        </div>
      </div>
    </div>

    <!-- 播放器页 -->
    <div v-if="isLookVideo" class="video-player-page">
      <!-- 顶部导航 -->
      <div class="player-nav">
        <div class="nav-side" @click="exitLook">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ lookVideoData.title || fullVideoInfo?.title || '' }}</div>
        <div class="nav-side"></div>
      </div>

      <!-- 视频播放器 -->
      <div class="player-wrapper">
        <!-- 加载遮罩 -->
        <div v-if="isVideoLoading" class="player-loading">
          <van-loading type="spinner" color="#fff" size="36" />
          <span>视频加载中...</span>
        </div>

        <!-- 错误遮罩 -->
        <div v-else-if="videoError" class="player-error">
          <van-icon name="warning-o" size="40" color="#ef4444" />
          <span>{{ videoError }}</span>
          <van-button size="small" type="primary" @click="loadVideoPage(currentPageIndex)">重试</van-button>
        </div>

        <video
          ref="videoPlayerRef"
          class="video-player"
          preload="metadata"
          playsinline
          webkit-playsinline
          :poster="lookVideoData.thumbnail ? 'https://images.weserv.nl?url=' + encodeURIComponent(lookVideoData.thumbnail.startsWith('//') ? 'https:' + lookVideoData.thumbnail : lookVideoData.thumbnail) : ''"
          @click="togglePlay"
        ></video>

        <!-- 自定义控制栏 -->
        <div class="custom-controls">
          <div class="controls-row">
            <van-icon
              :name="isPlaying ? 'pause-circle-o' : 'play-circle-o'"
              size="28"
              color="#fff"
              @click.stop="togglePlay"
            />
            <span class="time-display">{{ formattedCurrentTime }} / {{ formattedDuration }}</span>
            <div class="progress-bar" @click.stop="seekTo">
              <div class="progress-fill" :style="progressStyle"></div>
            </div>
            <van-icon
              :name="isMuted ? 'bullhorn-o' : 'volume-o'"
              size="20"
              color="#fff"
              @click.stop="toggleMute"
            />
          </div>
        </div>

        <!-- 分集导航 -->
        <div class="chapter-nav" v-if="pagesList.length > 1">
          <van-button size="mini" plain type="primary" :disabled="currentPageIndex === 0" @click="prevPage">
            <van-icon name="arrow-left" />
          </van-button>
          <span class="chapter-text">P{{ pagesList[currentPageIndex]?.page || 1 }} / {{ pagesList.length }}</span>
          <van-button size="mini" plain type="primary" :disabled="currentPageIndex === pagesList.length - 1" @click="nextPage">
            <van-icon name="arrow" />
          </van-button>
        </div>
      </div>

      <!-- 视频信息 -->
      <div class="video-detail-info">
        <div class="detail-title">{{ lookVideoData.title || fullVideoInfo?.title || '' }}</div>
        <div class="detail-author">UP主：{{ lookVideoData.author || fullVideoInfo?.author || '' }}</div>
      </div>

      <!-- 分集列表 -->
      <div v-if="pagesList.length > 1" class="pages-list">
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
            <van-icon v-if="idx === currentPageIndex" name="play-circle-o" class="page-play" />
          </div>
        </div>
      </div>

      <!-- 视频总结 -->
      <div class="summary-section">
        <div class="section-header">
          <van-icon name="description-o" size="18" />
          <span>视频总结</span>
        </div>
        <div class="section-content">
          <div v-if="summaryLoading" class="loading-state">
            <van-loading type="spinner" color="var(--primary)" />
            <span>加载总结中...</span>
            <span v-if="summaryError" class="polling-hint">{{ summaryError }}</span>
          </div>
          <div v-else-if="!videoSummary" class="empty-state">
            <van-icon name="description-o" size="40" color="var(--text-gray)" />
            <span v-if="summaryError">{{ summaryError }}</span>
            <span v-else>暂无视频总结</span>
          </div>
          <div v-else class="summary-wrapper">
            <div class="summary-card summary-card--highlight">
              <div class="summary-card-header">
                <van-icon name="info-o" size="16" />
                <span>内容总结</span>
              </div>
              <p class="summary-text">{{ videoSummary.summary }}</p>
            </div>

            <div v-if="videoSummary.key_points && videoSummary.key_points.length" class="summary-card">
              <div class="summary-card-header">
                <van-icon name="star-o" size="16" />
                <span>关键要点</span>
              </div>
              <ol class="key-points-list">
                <li v-for="(point, idx) in videoSummary.key_points" :key="idx" class="key-point-item">
                  <span class="key-point-badge">{{ idx + 1 }}</span>
                  <span class="key-point-text">{{ point }}</span>
                </li>
              </ol>
            </div>

            <div v-if="videoSummary.sections && videoSummary.sections.length" class="summary-card">
              <div class="summary-card-header">
                <van-icon name="orders-o" size="16" />
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

      <!-- 思维导图 -->
      <div class="mindmap-section">
        <div class="section-header">
          <van-icon name="cluster-o" size="18" />
          <span>思维导图</span>
        </div>
        <div class="section-content">
          <div v-if="mindmapLoading" class="loading-state">
            <van-loading type="spinner" color="var(--primary)" />
            <span>加载思维导图中...</span>
            <span v-if="mindmapError" class="polling-hint">{{ mindmapError }}</span>
          </div>
          <div v-else-if="!mindmapData" class="empty-state">
            <van-icon name="cluster-o" size="40" color="var(--text-gray)" />
            <span v-if="mindmapError">{{ mindmapError }}</span>
            <span v-else>暂无思维导图</span>
          </div>
          <div v-else class="mindmap-tree">
            <MindmapNode
              v-if="mindmapData"
              :node="mindmapData"
              :depth="0"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-video {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
}

/* 顶部导航 */
.page-nav, .player-nav {
  display: flex;
  align-items: center;
  padding: 12px 0;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-side {
  width: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-title {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title, #323233);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 列表页 */
.video-list-page {
  padding: 16px;
}
.page-header {
  margin-bottom: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin: 0;
}

/* 输入区 */
.input-section {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color, #eee);
}
.submit-btn {
  margin-top: 12px;
  font-weight: 600;
}

/* 列表 */
.list-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--text-gray, #969799);
  font-size: 14px;
}
.list-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.list-item {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
  padding: 12px;
}
.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-left {
  flex: 1;
  min-width: 0;
}
.item-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 2px;
}
.item-mid {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.status-text {
  font-size: 12px;
  color: var(--primary, #409EFF);
  font-weight: 500;
}
.fail-text {
  font-size: 12px;
  color: #F56C6C;
  font-weight: 500;
}
.item-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.action-icon {
  font-size: 20px;
  padding: 4px;
}
.delete-icon {
  color: #F56C6C;
}

/* 视频网格 */
.video-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color, #eee);
}
.video-card {
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-page, #f7f8fa);
}
.video-card:active {
  transform: scale(0.97);
}
.video-thumb-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
}
.video-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.25);
}
.video-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-body, #323233);
  padding: 6px 8px 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.video-meta {
  display: flex;
  justify-content: space-between;
  padding: 0 8px 6px;
  font-size: 11px;
  color: var(--text-gray, #969799);
}

.empty-state {
  padding: 40px 0;
}

/* =================== 播放器区域 =================== */
.player-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
}
.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.video-player::-webkit-media-controls {
  display: none !important;
}

.player-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  z-index: 2;
  font-size: 14px;
}
.player-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  z-index: 2;
  font-size: 14px;
}

/* 自定义控制栏 */
.custom-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  padding: 20px 12px 10px;
}
.controls-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.time-display {
  color: #ccc;
  font-size: 11px;
  min-width: 70px;
  font-variant-numeric: tabular-nums;
}
.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
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

/* 分集导航 */
.chapter-nav {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.6);
  padding: 4px 12px;
  border-radius: 16px;
  backdrop-filter: blur(8px);
}
.chapter-text {
  color: #fff;
  font-size: 12px;
  min-width: 50px;
  text-align: center;
}

/* 视频信息 */
.video-detail-info {
  padding: 12px 16px;
  background: var(--bg-card, #fff);
}
.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.detail-author {
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}

/* 分集列表 */
.pages-list {
  background: var(--bg-card, #fff);
  margin-top: 8px;
  border-radius: 12px 12px 0 0;
}
.pages-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 15px;
  color: var(--text-title, #323233);
  border-bottom: 1px solid var(--border-color, #eee);
}
.pages-count {
  font-size: 12px;
  color: var(--text-gray, #969799);
  font-weight: 400;
}
.pages-scroll {
  max-height: 200px;
  overflow-y: auto;
}
.page-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-color, #f0f0f0);
}
.page-item:active {
  background: var(--bg-page, #f7f8fa);
}
.page-item.active {
  background: var(--bg-page, #f7f8fa);
}
.page-num {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-gray, #969799);
  flex-shrink: 0;
}
.page-item.active .page-num {
  color: var(--primary, #409EFF);
}
.page-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.page-item.active .page-title {
  color: var(--text-title, #323233);
  font-weight: 500;
}
.page-play {
  color: var(--primary, #409EFF);
  font-size: 18px;
  flex-shrink: 0;
}

/* =================== 播放器页布局 =================== */
.video-player-page {
  background: var(--bg-page, #f7f8fa);
  min-height: 100vh;
  padding-bottom: 60px;
}
.player-nav {
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
}
.player-nav .nav-title {
  color: var(--text-title, #323233);
}
.player-nav .nav-side {
  color: var(--text-body, #323233);
}

/* =================== 视频总结与思维导图 =================== */
.summary-section,
.mindmap-section {
  background: var(--bg-card, #fff);
  margin-top: 8px;
  border-radius: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #323233);
  border-bottom: 1px solid var(--border-color, #eee);
}

.section-header .van-icon {
  color: var(--primary, #409EFF);
}

.section-content {
  padding: 16px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-gray, #969799);
  font-size: 14px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-gray, #969799);
  font-size: 14px;
}

.polling-hint {
  font-size: 12px;
  color: var(--warning, #E6A23C);
  text-align: center;
  max-width: 80%;
}

/* 视频总结卡片 */
.summary-wrapper {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-card {
  background: var(--bg-page, #f7f8fa);
  border: 1px solid var(--border-color, #eee);
  border-radius: 10px;
  padding: 14px;
}

.summary-card--highlight {
  background: rgba(64, 158, 255, 0.05);
  border-color: rgba(64, 158, 255, 0.2);
}

.summary-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--primary, #409EFF);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color, #eee);
}

.summary-card--highlight .summary-card-header {
  border-bottom-color: rgba(64, 158, 255, 0.2);
}

.summary-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-body, #323233);
  text-align: justify;
  margin: 0;
}

.key-points-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
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
  background: var(--primary, #409EFF);
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
  color: var(--text-body, #323233);
  flex: 1;
}

.sections-timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  position: relative;
  padding-left: 20px;
  padding-bottom: 14px;
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
  background: var(--primary, #409EFF);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15);
}

.timeline-line {
  position: absolute;
  left: 4px;
  top: 16px;
  bottom: 0;
  width: 2px;
  background: rgba(64, 158, 255, 0.2);
}

.timeline-content {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-color, #eee);
  border-radius: 8px;
  padding: 10px 12px;
}

.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title, #323233);
  margin-bottom: 4px;
}

.timeline-desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-body, #323233);
  margin: 0;
}

/* 思维导图树 */
.mindmap-tree {
  padding: 8px 0;
}
</style>
