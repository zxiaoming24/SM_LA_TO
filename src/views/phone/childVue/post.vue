<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import {
  getPostsListApi,
  getPostApi,
  replyPostApi,
  deleteReplyApi,
  deletePostApi,
  getUserInfoApi,
  submitPostApi,
  uploadCommonFileApi
} from '@/api/mainApi/index.js'
import { saveSkip } from '@/utils/skip.js'

const router = useRouter()
const goBack = () => router.back()

// 当前用户
const userId = ref('')
const currentView = ref('list') // list | detail | create

// 分类
const areas = [
  { id: 0, name: '全部' },
  { id: 1, name: '学习区' },
  { id: 2, name: '生活区' },
  { id: 3, name: '资源共享' },
  { id: 4, name: '反馈建议' }
]
const choosedArea = ref(0)

// 帖子列表
const postsList = ref([])
const postsLoading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const totalPages = ref(1)

// 帖子详情
const isLookPost = ref(false)
const openPostMsg = ref({})
const openPostReply = ref([])

// 回复表单
const replyForm = ref({ userId: '', postId: '', content: '', parentReplyId: '' })
const replyLoading = ref(false)

// 发帖表单
const postForm = ref({ userId: '', title: '', content: '', tags: [], zone: 1 })
const newTag = ref('')
const postBtnDisabled = ref(false)

// 文件上传
const fileInputRef = ref(null)
const uploadedFile = ref(null)
const fileUrl = ref('')
const isUploading = ref(false)

// 回复文件上传
const replyFileInputRef = ref(null)
const replyFile = ref(null)
const replyFileUrl = ref('')
const isReplyUploading = ref(false)

// 图片预览
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// 分享资源
const shareResourceInfo = ref(null)
const resourceTypeMap = {
  'ppt': { rsType: 0, name: 'PPT', routePath: '/phone/resource/ppt' },
  'mindmap': { rsType: 1, name: '思维导图', routePath: '/phone/resource/mindmap' },
  'mindMap': { rsType: 1, name: '思维导图', routePath: '/phone/resource/mindmap' },
  'doc': { rsType: 2, name: '文档', routePath: '/phone/resource/word' },
  'docment': { rsType: 2, name: '文档', routePath: '/phone/resource/word' },
  'document': { rsType: 2, name: '文档', routePath: '/phone/resource/word' },
  'extension': { rsType: 3, name: '拓展阅读', routePath: '/phone/resource/reading' },
  'practice': { rsType: 4, name: '编程练习', routePath: '/phone/resource/code' },
  'video': { rsType: 5, name: '视频', routePath: '/phone/resource/video' },
  'animation': { rsType: 6, name: '动画', routePath: '/phone/resource/anima' },
  'question': { rsType: 7, name: '试卷', routePath: '/phone/resource/paper' },
  '动画': { rsType: 6, name: '动画', routePath: '/phone/resource/anima' },
  '视频': { rsType: 5, name: '视频', routePath: '/phone/resource/video' },
  '文档': { rsType: 2, name: '文档', routePath: '/phone/resource/word' },
  'PPT': { rsType: 0, name: 'PPT', routePath: '/phone/resource/ppt' },
  '思维导图': { rsType: 1, name: '思维导图', routePath: '/phone/resource/mindmap' },
  '拓展阅读': { rsType: 3, name: '拓展阅读', routePath: '/phone/resource/reading' },
  '编程练习': { rsType: 4, name: '编程练习', routePath: '/phone/resource/code' },
  '试卷': { rsType: 7, name: '试卷', routePath: '/phone/resource/paper' }
}

// 格式化时间
function formatTime(timeStr) {
  const d = new Date(timeStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}`
}

// 添加用户信息
const addUserInfo = async (arr) => {
  let list = Array.isArray(arr) ? arr : [arr]
  const userIdList = [...new Set(list.map(item => item.user_id))]
  try {
    const res = await getUserInfoApi({ userIdList })
    if (res.code) {
      const userMap = {}
      res.data.forEach(u => { userMap[u.userId] = u })
      list.forEach(item => {
        const user = userMap[item.user_id]
        if (user) {
          item.username = user.username
          item.avatar = user.avatar
        }
      })
    }
  } catch (e) {
    console.error('获取用户信息失败：', e)
  }
}

// 获取帖子列表
const getPostsList = async (p, ps, category) => {
  postsLoading.value = true
  try {
    const res = await getPostsListApi(p, ps, category)
    if (res.code) {
      postsList.value = res.data.posts
      await addUserInfo(postsList.value)
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    }
  } catch (error) {
    console.error('获取帖子列表失败：', error)
  } finally {
    postsLoading.value = false
  }
}

// 切换分类
const changeArea = async (area) => {
  if (choosedArea.value === area) return
  choosedArea.value = area
  page.value = 1
  await getPostsList(1, pageSize.value, area)
}

// 获取帖子详情
const getPost = async (postId) => {
  try {
    const res = await getPostApi(postId)
    if (res.code) {
      isLookPost.value = true
      openPostMsg.value = res.data.post
      await addUserInfo(openPostMsg.value)
      openPostReply.value = res.data.replies
      await addUserInfo(openPostReply.value)
      parsePostContent(openPostMsg.value.content, openPostMsg.value.tags)
      currentView.value = 'detail'
      nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    }
  } catch (error) {
    console.error('获取帖子详情失败：', error)
  }
}

// 回复帖子
const replyPost = async (postId) => {
  if (!replyForm.value.content && !replyFileUrl.value) {
    showToast('请输入回复内容')
    return
  }
  replyLoading.value = true
  try {
    replyForm.value.postId = postId
    replyForm.value.userId = userId.value
    const params = { ...replyForm.value, url: replyFileUrl.value }
    replyForm.value = { userId: '', postId: '', content: '', parentReplyId: '' }
    clearReplyFile()
    const res = await replyPostApi(params)
    if (res.code && res.data.success) {
      showToast('回复成功')
      await getPost(postId)
    } else {
      showToast('回复失败')
    }
  } catch (error) {
    console.error('回复失败：', error)
  } finally {
    replyLoading.value = false
  }
}

// 删除回复
const deleteReply = async (replyUserId, replyId) => {
  try {
    await showConfirmDialog({ title: '提示', message: '是否删除该回复？' })
    const res = await deleteReplyApi(replyUserId, replyId)
    if (res.code && res.data.success) {
      showToast('删除成功')
      await getPost(openPostMsg.value.post_id)
    }
  } catch (error) {
    if (error !== 'cancel') console.error('删除失败：', error)
  }
}

// 删除帖子
const deletePost = async (postId) => {
  try {
    await showConfirmDialog({ title: '提示', message: '是否删除该帖子？' })
    isLookPost.value = false
    currentView.value = 'list'
    const res = await deletePostApi(userId.value, postId)
    if (res.code && res.data.success) {
      showToast('删除成功')
      await getPostsList(page.value, pageSize.value, choosedArea.value)
    }
    clearPostReply()
  } catch (error) {
    if (error !== 'cancel') console.error('删除失败：', error)
  }
}

// 清除帖子详情
const clearPostReply = () => {
  openPostMsg.value = {}
  openPostReply.value = []
  replyForm.value = { userId: '', postId: '', content: '', parentReplyId: '' }
  shareResourceInfo.value = null
}

// 返回列表
const backToList = () => {
  currentView.value = 'list'
  isLookPost.value = false
  clearPostReply()
}

// 翻页
const prevPage = async () => {
  if (page.value <= 1 || postsLoading.value) return
  await getPostsList(page.value - 1, pageSize.value, choosedArea.value)
}
const nextPage = async () => {
  if (page.value >= totalPages.value || postsLoading.value) return
  await getPostsList(page.value + 1, pageSize.value, choosedArea.value)
}

// 发布帖子
const submitPost = async () => {
  if (!postForm.value.title || !postForm.value.content) {
    showToast('标题或内容是必填项')
    return
  }
  if (!postForm.value.tags || postForm.value.tags.length === 0) {
    showToast('请添加标签')
    return
  }
  postBtnDisabled.value = true
  try {
    postForm.value.userId = userId.value
    postForm.value.url = fileUrl.value
    const res = await submitPostApi(postForm.value)
    if (res.code && res.data.success) {
      showToast('发布成功')
      await getPostsList(1, pageSize.value, 0)
      postForm.value = { userId: '', title: '', content: '', tags: [], zone: 1 }
      uploadedFile.value = null
      fileUrl.value = ''
      currentView.value = 'list'
    } else {
      showToast('发布失败')
    }
  } catch (error) {
    console.error('发布帖子失败：', error)
  } finally {
    postBtnDisabled.value = false
  }
}

// 标签管理
const addTag = () => {
  const tag = newTag.value.trim()
  if (tag && !postForm.value.tags.includes(tag)) {
    postForm.value.tags.push(tag)
  }
  newTag.value = ''
}
const removeTag = (index) => {
  postForm.value.tags.splice(index, 1)
}

// 文件上传
const handleFileSelect = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  uploadedFile.value = file
  isUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadCommonFileApi(formData)
    if (res.code) {
      fileUrl.value = res.data.url
      showToast('上传成功')
    }
  } catch (e) {
    console.error('上传失败：', e)
    showToast('上传失败')
  } finally {
    isUploading.value = false
    event.target.value = ''
  }
}

const clearSelectedFile = () => {
  uploadedFile.value = null
  fileUrl.value = ''
}

// 回复文件上传
const handleReplyFileSelect = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  replyFile.value = file
  isReplyUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadCommonFileApi(formData)
    if (res.code) {
      replyFileUrl.value = res.data.url
    }
  } catch (e) {
    console.error('上传失败：', e)
  } finally {
    isReplyUploading.value = false
    event.target.value = ''
  }
}

const clearReplyFile = () => {
  replyFile.value = null
  replyFileUrl.value = ''
}

// 解析帖子内容
const processedContent = ref({ paragraphs: [] })

const parsePostContent = (content, tags = []) => {
  if (!content) {
    processedContent.value = { paragraphs: [] }
    shareResourceInfo.value = null
    return
  }
  shareResourceInfo.value = null
  const isSharePost = content.startsWith('分享者')
  if (isSharePost && tags && tags.length > 0) {
    const resourceIdMatch = content.match(/资源ID[：:]\s*([^\s\n]+)/)
    if (resourceIdMatch) {
      const resourceId = resourceIdMatch[1].trim()
      for (const tag of tags) {
        if (resourceTypeMap[tag]) {
          shareResourceInfo.value = { resourceId, ...resourceTypeMap[tag] }
          break
        }
      }
    }
  }
  const urlRegex = /(https?:\/\/[^\s`\n]+)/g
  const lines = content.split(/\n/)
  const paragraphs = []
  lines.forEach(line => {
    if (!line.trim()) { paragraphs.push({ type: 'empty' }); return }
    const parts = line.split(urlRegex)
    const paragraphParts = []
    parts.forEach(part => {
      const urlMatch = part.match(urlRegex)
      if (urlMatch) {
        const url = part.trim()
        const linkInfo = classifyLink(url)
        paragraphParts.push({ type: 'link', url, ...linkInfo })
      } else {
        paragraphParts.push({ type: 'text', content: part })
      }
    })
    paragraphs.push({ type: 'paragraph', parts: paragraphParts })
  })
  processedContent.value = { paragraphs }
}

const classifyLink = (url) => {
  const lowerUrl = url.toLowerCase()
  const fileName = extractFileName(url)
  if (lowerUrl.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/)) return { type: 'image', label: fileName || '图片' }
  if (lowerUrl.match(/\.(pdf)$/)) return { type: 'pdf', label: fileName || 'PDF' }
  if (lowerUrl.match(/\.(doc|docx)$/)) return { type: 'word', label: fileName || 'Word' }
  if (lowerUrl.match(/\.(ppt|pptx)$/)) return { type: 'ppt', label: fileName || 'PPT' }
  if (lowerUrl.match(/\.(xls|xlsx)$/)) return { type: 'excel', label: fileName || 'Excel' }
  if (lowerUrl.includes('bilibili.com') || lowerUrl.includes('.mp4')) return { type: 'video', label: fileName || '视频' }
  return { type: 'other', label: fileName || '链接' }
}

const extractFileName = (url) => {
  try {
    const cleanUrl = url.split('?')[0].split('#')[0]
    const fileName = cleanUrl.split('/').pop()
    if (fileName && fileName.includes('.')) return decodeURIComponent(fileName)
    return null
  } catch (e) { return null }
}

const parseReplyContent = (content) => {
  if (!content) return []
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const parts = []
  let lastIndex = 0
  let match
  while ((match = urlRegex.exec(content)) !== null) {
    if (match.index > lastIndex) parts.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    const url = match[0]
    const linkInfo = classifyLink(url)
    parts.push({ type: 'link', url, ...linkInfo })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) parts.push({ type: 'text', content: content.slice(lastIndex) })
  return parts
}

// 图片预览
const openImagePreviewFn = (url) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

// 文件预览
const previewFileUrl = ref('')
const previewFileType = ref('')

const getOfficePreviewUrl = (url) => {
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`
}

const toggleFilePreview = (part) => {
  if (previewFileUrl.value === part.url) {
    // 点击同一个文件，关闭预览
    previewFileUrl.value = ''
    previewFileType.value = ''
  } else {
    // 打开预览
    previewFileUrl.value = part.url
    previewFileType.value = part.type
  }
}

// 跳转到分享资源页面
const jumpToResource = () => {
  if (!shareResourceInfo.value) return
  const { resourceId, rsType, routePath } = shareResourceInfo.value
  // 使用 saveSkip 保存跳转信息
  saveSkip(rsType, resourceId)
  // 路由跳转
  router.push(routePath)
}

// 下载
const handleDownload = (url) => {
  window.open(url, '_blank')
}

onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser) userId.value = loginUser.id || loginUser.userId || ''
    } catch (e) { console.error('用户信息解析失败', e) }
  }
  getPostsList(1, pageSize.value, 0)
})
</script>

<template>
  <div class="phone-post">
    <!-- 顶部导航栏 -->
    <div class="mobile-header">
      <div class="header-left" @click="currentView === 'detail' ? backToList() : goBack()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="header-title">{{ currentView === 'detail' ? '帖子详情' : currentView === 'create' ? '发布帖子' : '帖子社区' }}</div>
      <div class="header-right">
        <van-icon v-if="currentView === 'list'" name="edit" size="20" @click="currentView = 'create'" />
      </div>
    </div>

    <!-- ========== 帖子列表视图 ========== -->
    <div v-if="currentView === 'list'" class="list-view">
      <!-- 分类标签 -->
      <div class="area-tabs">
        <div
          v-for="area in areas" :key="area.id"
          class="area-tab"
          :class="{ active: choosedArea === area.id }"
          @click="changeArea(area.id)"
        >{{ area.name }}</div>
      </div>

      <!-- 帖子列表 -->
      <van-loading v-if="postsLoading && postsList.length === 0" class="loading" size="24px" vertical>加载中...</van-loading>

      <div v-else-if="postsList.length" class="post-list">
        <div
          v-for="item in postsList" :key="item.post_id"
          class="post-card"
          :class="{ 'my-post': userId === item.user_id }"
          @click="getPost(item.post_id)"
        >
          <div class="post-header">
            <div class="post-avatar" :style="{ background: 'var(--primary-light)' }">
              <img v-if="item.avatar" :src="item.avatar" class="avatar-img" />
              <span v-else class="avatar-text">{{ (item.username || '用').charAt(0) }}</span>
            </div>
            <div class="post-meta">
              <span class="post-username">{{ item.username || '用户' }}</span>
              <span class="post-time">{{ formatTime(item.created_at) }}</span>
            </div>
            <div class="post-zone-reply">
              <div class="post-zone-tag">{{ item.zone_name }}</div>
              <div class="post-reply-count">
                <van-icon name="comment-o" size="14" />
                <span>{{ item.reply_count }}</span>
              </div>
            </div>
          </div>
          <div class="post-title">{{ item.title }}</div>
          <div class="post-tags" v-if="item.tags && item.tags.length">
            <span class="tag" v-for="tag in item.tags" :key="tag">{{ tag }}</span>
          </div>
        </div>

        <!-- 翻页 -->
        <div class="pagination">
          <van-button size="small" :disabled="page <= 1" :loading="postsLoading" @click="prevPage">上一页</van-button>
          <span class="page-info">{{ page }}/{{ totalPages }}</span>
          <van-button size="small" :disabled="page >= totalPages" :loading="postsLoading" @click="nextPage">下一页</van-button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <van-icon name="forum-o" size="64" color="var(--text-gray)" />
        <p>暂无帖子</p>
      </div>
    </div>

    <!-- ========== 帖子详情视图 ========== -->
    <div v-else-if="currentView === 'detail'" class="detail-view">
      <!-- 帖子头部 -->
      <div class="detail-header">
        <div class="post-avatar" :style="{ background: 'var(--primary-light)' }">
          <img v-if="openPostMsg.avatar" :src="openPostMsg.avatar" class="avatar-img" />
          <span v-else class="avatar-text">{{ (openPostMsg.username || '用').charAt(0) }}</span>
        </div>
        <div class="detail-meta">
          <span class="post-username">{{ openPostMsg.username || '用户' }}</span>
          <div class="detail-sub">
            <span>{{ openPostMsg.zone_name }}</span>
            <span>{{ formatTime(openPostMsg.created_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 帖子标题 -->
      <h3 class="detail-title">{{ openPostMsg.title }}</h3>

      <!-- 分享资源提示 -->
      <div v-if="shareResourceInfo" class="share-resource-bar" @click="jumpToResource">
        <div class="resource-info-left">
          <van-icon name="link-o" size="16" />
          <span>{{ shareResourceInfo.name }} · ID: {{ shareResourceInfo.resourceId }}</span>
        </div>
        <van-button size="mini" type="primary" plain>前往查看</van-button>
      </div>

      <!-- 帖子内容 -->
      <div class="detail-content">
        <template v-for="(paragraph, pIndex) in processedContent.paragraphs" :key="pIndex">
          <br v-if="paragraph.type === 'empty'" />
          <div v-else class="content-paragraph">
            <template v-for="(part, idx) in paragraph.parts" :key="idx">
              <span v-if="part.type === 'text'" class="content-text">{{ part.content }}</span>
              <img v-else-if="part.type === 'image'" :src="part.url" class="content-image" @click="openImagePreviewFn(part.url)" />
              <!-- PDF 文件 -->
              <div v-else-if="part.type === 'pdf'" class="file-card">
                <div class="file-card-icon">
                  <van-icon name="description" size="24" />
                </div>
                <div class="file-card-info">
                  <div class="file-card-name">{{ part.label }}</div>
                  <div class="file-card-type">PDF 文件</div>
                </div>
                <a :href="part.url" target="_blank" class="file-card-download">
                  <van-icon name="down" size="18" />
                </a>
              </div>
              <!-- Office 文件（Word/PPT/Excel）-->
              <div v-else-if="['word', 'ppt', 'excel'].includes(part.type)" class="file-card-wrapper">
                <div class="file-card" @click="toggleFilePreview(part)">
                  <div class="file-card-icon">
                    <van-icon :name="part.type === 'ppt' ? 'notes-o' : part.type === 'word' ? 'description' : 'orders-o'" size="24" />
                  </div>
                  <div class="file-card-info">
                    <div class="file-card-name">{{ part.label }}</div>
                    <div class="file-card-type">{{ part.type.toUpperCase() }} 文件 · 点击预览</div>
                  </div>
                  <a :href="part.url" target="_blank" class="file-card-download" @click.stop>
                    <van-icon name="down" size="18" />
                  </a>
                </div>
                <!-- 展开预览 -->
                <div v-if="previewFileUrl === part.url" class="file-preview-area">
                  <iframe :src="getOfficePreviewUrl(part.url)" class="file-preview-iframe" frameborder="0" allowfullscreen></iframe>
                  <div class="file-preview-actions">
                    <van-button size="small" plain @click="toggleFilePreview(part)">
                      <van-icon name="cross" /> 关闭预览
                    </van-button>
                    <van-button size="small" type="primary" plain @click="handleDownload(part.url)">
                      <van-icon name="down" /> 下载文件
                    </van-button>
                  </div>
                </div>
              </div>
              <a v-else-if="part.type === 'video'" :href="part.url" target="_blank" class="content-link video-link">
                <van-icon name="video-o" /> {{ part.label }}
              </a>
              <a v-else-if="part.url" :href="part.url" target="_blank" class="content-link">
                <van-icon name="down" /> {{ part.label }}
              </a>
            </template>
          </div>
        </template>
      </div>

      <!-- 帖子标签 -->
      <div class="detail-tags" v-if="openPostMsg.tags && openPostMsg.tags.length">
        <span class="tag" v-for="tag in openPostMsg.tags" :key="tag">{{ tag }}</span>
      </div>

      <!-- 操作按钮 -->
      <div class="detail-actions" v-if="userId === openPostMsg.user_id">
        <van-button size="small" type="danger" plain @click="deletePost(openPostMsg.post_id)">
          <van-icon name="delete-o" /> 删除帖子
        </van-button>
      </div>

      <!-- 回复列表 -->
      <div class="reply-section">
        <div class="reply-header">
          <span class="reply-title">回复 ({{ openPostReply.length }})</span>
          <van-button size="mini" plain @click="getPost(openPostMsg.post_id)">
            <van-icon name="replay" /> 刷新
          </van-button>
        </div>

        <div v-if="openPostReply.length === 0" class="no-reply">暂无回复</div>

        <div
          v-for="(item, index) in openPostReply" :key="index"
          class="chat-item"
          :class="{ 'chat-mine': String(item.user_id) === String(userId) }"
        >
          <!-- 对方头像在左 -->
          <div class="chat-avatar" :style="{ background: 'var(--primary-light)' }">
            <img v-if="item.avatar" :src="item.avatar" class="avatar-img" />
            <span v-else class="avatar-text">{{ (item.username || '用').charAt(0) }}</span>
          </div>
          <!-- 消息主体 -->
          <div class="chat-body">
            <div class="chat-name">
              {{ item.username || '用户' }}
            </div>
            <div class="chat-bubble">
              <div class="chat-content">
                <template v-for="(part, idx) in parseReplyContent(item.content)" :key="idx">
                  <span v-if="part.type === 'text'">{{ part.content }}</span>
                  <img v-else-if="part.type === 'image'" :src="part.url" class="chat-image" @click="openImagePreviewFn(part.url)" />
                  <a v-else-if="part.type === 'video'" :href="part.url" target="_blank" class="chat-link video-link">
                    <van-icon name="video-o" /> {{ part.label }}
                  </a>
                  <a v-else-if="part.url" :href="part.url" target="_blank" class="chat-link">
                    <van-icon name="link-o" /> {{ part.label }}
                  </a>
                </template>
              </div>
              <div class="chat-footer">
                <span class="chat-time">{{ formatTime(item.created_at) }}</span>
                <span class="delete-btn" v-if="String(item.user_id) === String(userId) || String(openPostMsg.user_id) === String(userId)" @click="deleteReply(item.user_id, item.reply_id)">删除</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 回复输入框 -->
      <div class="reply-input-bar">
        <input
          class="reply-input"
          v-model="replyForm.content"
          placeholder="输入回复内容..."
          @keyup.enter="replyPost(openPostMsg.post_id)"
        />
        <van-button size="small" type="primary" :loading="replyLoading" @click="replyPost(openPostMsg.post_id)">发送</van-button>
      </div>
    </div>

    <!-- ========== 发帖视图 ========== -->
    <div v-else-if="currentView === 'create'" class="create-view">
      <div class="form-group">
        <label>标题</label>
        <input class="form-input" v-model="postForm.title" placeholder="请输入帖子标题" />
      </div>

      <div class="form-group">
        <label>分区</label>
        <div class="zone-select">
          <div
            v-for="area in areas.slice(1)" :key="area.id"
            class="zone-option"
            :class="{ active: postForm.zone === area.id }"
            @click="postForm.zone = area.id"
          >{{ area.name }}</div>
        </div>
      </div>

      <div class="form-group">
        <label>内容</label>
        <textarea class="form-textarea" v-model="postForm.content" placeholder="请输入帖子内容" rows="6"></textarea>
      </div>

      <div class="form-group">
        <label>标签</label>
        <div class="tags-input">
          <span class="tag" v-for="(tag, index) in postForm.tags" :key="tag">
            {{ tag }}
            <van-icon name="cross" size="12" @click="removeTag(index)" />
          </span>
          <input class="tag-input" v-model="newTag" placeholder="添加标签" @keyup.enter="addTag" @blur="addTag" />
        </div>
      </div>

      <div class="form-group">
        <label>附件（可选）</label>
        <div class="file-upload" v-if="!uploadedFile" @click="fileInputRef?.click()">
          <van-icon name="plus" size="24" color="var(--text-gray)" />
          <span>选择文件</span>
          <input ref="fileInputRef" type="file" @change="handleFileSelect" style="display:none" />
        </div>
        <div v-else class="file-info">
          <van-icon name="description" />
          <span>{{ uploadedFile.name }}</span>
          <van-icon name="cross" @click="clearSelectedFile" />
        </div>
        <van-loading v-if="isUploading" size="20px">上传中...</van-loading>
      </div>

      <van-button type="primary" block :loading="postBtnDisabled" :disabled="postBtnDisabled" @click="submitPost">
        发布帖子
      </van-button>
    </div>

    <!-- 图片预览 -->
    <van-image-preview v-model:show="showImagePreview" :images="[previewImageUrl]" />
  </div>
</template>

<style scoped>
.phone-post {
  padding: 16px;
  padding-top: 73px;
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
}

/* 顶部导航 */
.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 8px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left,
.header-right {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}

.header-left:active,
.header-right:active {
  background: var(--bg-hover);
}

.header-title {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 分类标签 */
.area-tabs {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 4px 0 12px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.area-tabs::-webkit-scrollbar {
  display: none;
}

.area-tab {
  padding: 6px 10px;
  border-radius: 16px;
  font-size: 13px;
  color: var(--text-body);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.area-tab.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

/* 帖子列表 */
.post-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.post-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.post-card:active {
  background: var(--bg-hover);
  transform: scale(0.99);
}

.post-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.post-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
}

.post-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.post-username {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
}

.post-time {
  font-size: 11px;
  color: var(--text-gray);
}

.post-reply-count {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-gray);
}

.post-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
  line-height: 1.4;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-zone-reply {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.post-zone-tag {
  display: inline-block;
  font-size: 11px;
  color: var(--primary);
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: 8px;
}

.post-tags, .detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--text-body);
  background: var(--bg-hover);
  border-radius: 8px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 16px 0;
}

.page-info {
  font-size: 13px;
  color: var(--text-gray);
}

/* 帖子详情 */
.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.detail-meta {
  flex: 1;
}

.detail-sub {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
}

.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin: 0 0 12px;
  line-height: 1.4;
}

.share-resource-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  background: var(--primary-light);
  border: 1px solid var(--primary);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--primary);
  cursor: pointer;
}

.resource-info-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.detail-content {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 14px;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-body);
  word-break: break-word;
}

.content-paragraph {
  margin-bottom: 4px;
}

.content-image {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
  cursor: pointer;
}

.content-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  font-size: 13px;
  padding: 4px 8px;
  background: var(--primary-light);
  border-radius: 6px;
  margin: 4px 0;
  text-decoration: none;
}

.video-link {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

/* 文件预览样式 */
.file-card-wrapper {
  margin: 12px 0;
}

.file-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.file-card:active {
  background: var(--bg-hover);
}

.file-card-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-light);
  border-radius: 8px;
  color: var(--primary);
  flex-shrink: 0;
}

.file-card-info {
  flex: 1;
  min-width: 0;
}

.file-card-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-card-type {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
}

.file-card-download {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #fff;
  border-radius: 50%;
  text-decoration: none;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.file-card-download:active {
  opacity: 0.8;
}

.file-preview-area {
  margin-top: 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.file-preview-iframe {
  width: 100%;
  height: 400px;
  border: none;
  background: #f5f5f5;
}

.file-preview-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}

.detail-actions {
  margin-bottom: 16px;
}

/* 回复区 */
.reply-section {
  margin-top: 20px;
  margin-bottom: 70px;
}

.reply-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.reply-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}

.no-reply {
  text-align: center;
  padding: 20px;
  color: var(--text-gray);
  font-size: 13px;
}

/* 聊天样式回复 */
.chat-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  align-items: flex-start;
}

.chat-item.chat-mine {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.chat-body {
  max-width: calc(100% - 56px);
  display: flex;
  flex-direction: column;
}

.chat-mine .chat-body {
  align-items: flex-end;
}

.chat-name {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 4px;
  padding: 0 4px;
}

.chat-bubble {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  border-top-left-radius: 4px;
  padding: 10px 12px;
  position: relative;
}

.chat-mine .chat-bubble {
  background: var(--primary-light);
  border-color: var(--primary);
  border-top-left-radius: 12px;
  border-top-right-radius: 4px;
}

.chat-content {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
  word-break: break-word;
}

.chat-image {
  max-width: 180px;
  border-radius: 6px;
  margin: 4px 0;
  cursor: pointer;
  display: block;
}

.chat-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  font-size: 13px;
  padding: 4px 8px;
  background: rgba(45, 125, 219, 0.1);
  border-radius: 6px;
  margin: 4px 0;
  text-decoration: none;
}

.chat-link.video-link {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.chat-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
}

.chat-time {
  color: var(--text-gray);
}

.delete-btn {
  font-size: 11px;
  color: #f56c6c;
  cursor: pointer;
}

/* 回复输入框 */
.reply-input-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  z-index: 99;
}

.reply-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-hover);
  font-size: 16px;
  color: var(--text-body);
  outline: none;
}

.reply-input:focus {
  border-color: var(--primary);
}

/* 发帖表单 */
.create-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}

.form-input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-card);
  font-size: 16px;
  color: var(--text-body);
  outline: none;
}

.form-input:focus {
  border-color: var(--primary);
}

.form-textarea {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-card);
  font-size: 16px;
  color: var(--text-body);
  outline: none;
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
}

.form-textarea:focus {
  border-color: var(--primary);
}

.zone-select {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.zone-option {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  color: var(--text-body);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
}

.zone-option.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.tags-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tag-input {
  flex: 1;
  min-width: 80px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-card);
  font-size: 16px;
  color: var(--text-body);
  outline: none;
}

.tag-input:focus {
  border-color: var(--primary);
}

.file-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-gray);
  font-size: 13px;
  transition: border-color 0.2s;
}

.file-upload:active {
  border-color: var(--primary);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-hover);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-body);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-gray);
  font-size: 14px;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.my-post {
  border-color: var(--primary);
}
</style>
