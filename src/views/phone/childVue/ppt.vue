<!-- 移动端PPT组件 -->
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import { getPPTListByUserId, getTaskIdApi, getPPTProgressApi, deletePPTByIdApi } from '@/api/mainApi/resourcePPT.js'
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
        userId.value = loginUser.id
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  await getPPTList()
  // 检查是否有跳转信息需要自动打开PPT
  const skipInfo = isSkip(0)
  if (skipInfo && skipInfo.resourceId) {
    try {
      const res = await getPPTProgressApi(skipInfo.resourceId)
      if (res.code && res.data?.id) {
        openPPT(res.data.id, res.data.pptTitle, res.data.ossUrl)
      } else {
        showToast('该PPT不存在，可能已被删除')
      }
    } catch (e) {
      console.error('打开PPT失败', e)
      showToast('打开PPT失败')
    }
    removeSkip(0)
  }
  await checkCutPPTTask()
})

// =================== 数据 =====================
const allList = ref([])
const showList = ref([])
const pptData = ref({ text: '' })
const btnDisvisible = ref(false)

// =================== 预览相关 =====================
const isShowPPT = ref(false)
const previewPPTName = ref('')
const pptPreviewUrl = ref('')
const ossDownloadUrl = ref('')
const isIframeLoading = ref(true)

// =================== 进度轮询 =====================
const PPTPROGRESS = ref(null)
const PPTPROGRESSDATA = ref(null)

const getPPTProgress = async (taskId) => {
  PPTPROGRESS.value = null
  PPTPROGRESSDATA.value = null
  const result = await getPPTProgressApi(taskId)
  if (result.code) {
    if (result.data.status == 1) {
      PPTPROGRESS.value = 1
    } else if (result.data.status == 2) {
      PPTPROGRESS.value = 2
      PPTPROGRESSDATA.value = result.data
    } else {
      PPTPROGRESS.value = 3
    }
  }
}

// =================== 列表 =====================
const getPPTList = async () => {
  try {
    const result = await getPPTListByUserId(userId.value)
    if (result.code) {
      allList.value = result.data || []
      allList.value.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      showList.value = allList.value.slice(0, 20)
    } else {
      showFailToast('获取PPT列表失败')
    }
  } catch (e) {
    console.error('获取PPT列表失败', e)
    showFailToast('获取PPT列表失败')
  }
}

// =================== 生成 =====================
const submit = async () => {
  if (!pptData.value.text || !pptData.value.text.trim()) {
    showToast('请输入主题/大纲'); return
  }
  if (pptData.value.text.length > 30) {
    showToast('长度不能超过30个字符'); return
  }
  btnDisvisible.value = true
  try {
    const result = await getTaskIdApi(userId.value, pptData.value)
    if (result.code) {
      const taskId = result.data.id
      showLoadingToast({ message: '生成中...', forbidClick: true, duration: 0 })
      await getPPTList()

      let nowNum = 0; const maxNum = 100
      await getPPTProgress(taskId)

      while (PPTPROGRESS.value == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 3000))
        await getPPTProgress(taskId)
      }

      if (PPTPROGRESS.value == 2) {
        showSuccessToast('PPT生成成功！')
        await getPPTList()
      } else {
        showFailToast('PPT生成失败或超时')
        await getPPTList()
      }
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
    pptData.value = { text: '' }
    showLoadingToast({ message: '', duration: 0 })
  }
}

// =================== 预览 =====================
const openPPT = (pptId, pptTitle, ossUrl) => {
  previewPPTName.value = pptTitle
  ossDownloadUrl.value = ossUrl
  isIframeLoading.value = true
  isShowPPT.value = true
  pptPreviewUrl.value = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(ossUrl)}`
}

const closePPT = () => {
  isShowPPT.value = false
  previewPPTName.value = ''
  pptPreviewUrl.value = ''
  ossDownloadUrl.value = ''
}

// =================== 删除 =====================
const deletePPT = async (pptId) => {
  try {
    await showConfirmDialog({ title: '提示', message: '是否删除该PPT？' })
    const result = await deletePPTByIdApi(pptId)
    if (result.code) {
      showSuccessToast('删除成功')
      await getPPTList()
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      console.error('删除失败', e)
      showFailToast('删除失败')
    }
  }
}

// =================== 下载 =====================
const downloadPPT = (url) => {
  if (!url) { showToast('下载地址不存在'); return }
  const link = document.createElement('a')
  link.href = url
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// =================== 检查截断任务 =====================
const checkCutPPTTask = async () => {
  const hasCutTask = allList.value.some(item => item.status == null || item.status == 1)
  if (hasCutTask) btnDisvisible.value = true

  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i]
    if (item.status == null || item.status == 1) {
      let nowNum = 0; const maxNum = 100
      try {
        await getPPTProgress(item.id)
        if (PPTPROGRESS.value == null) continue
      } catch (e) { continue }

      while (PPTPROGRESS.value == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 3000))
        try { await getPPTProgress(item.id) } catch (e) { break }
      }

      if (PPTPROGRESS.value == 2) {
        showSuccessToast('PPT生成成功！')
        await getPPTList()
      } else {
        await getPPTList()
      }
    }
  }

  if (hasCutTask) btnDisvisible.value = false
}

// =================== 工具函数 =====================
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.replace('T', ' ').substring(0, 19)
}

const isOpenList = ref(false)
</script>

<template>
  <div class="phone-ppt">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">PPT 智能生成</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShowPPT" class="ppt-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">PPT 智能生成</h2>
        <p class="page-desc">输入学习主题，一键生成精美讲解PPT</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="pptData.text"
          placeholder="例如：人工智能的发展历史"
          maxlength="30"
          show-word-limit
          clearable
          class="ppt-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成 PPT
        </van-button>
      </div>

      <!-- 列表 -->
      <div class="list-section">
        <div v-if="allList.length > 0" class="list-wrap">
          <div
            v-for="item in (isOpenList ? allList : showList)"
            :key="item.id"
            class="list-item"
            :class="{ 'item-loading': item.status == 1 || item.status == null, 'item-fail': item.status == 3 }"
          >
            <!-- 成功状态：显示缩略图 -->
            <div v-if="item.status == 2" class="item-content" @click="openPPT(item.id, item.pptTitle, item.ossUrl)">
              <div class="item-thumb">
                <img v-if="item.imageUrl" :src="item.imageUrl" alt="PPT首图" />
                <van-icon v-else name="notes-o" size="40" color="var(--primary)" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.pptTitle }}</div>
                <div class="item-meta">
                  <span class="item-time">{{ formatTime(item.createdAt) }}</span>
                  <span class="item-pages" v-if="item.pageCount">{{ item.pageCount }}页</span>
                </div>
              </div>
              <div class="item-actions">
                <van-icon name="down" class="action-icon download-icon" @click.stop="downloadPPT(item.ossUrl)" />
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="deletePPT(item.id)" />
              </div>
            </div>

            <!-- 生成中状态 -->
            <div v-else-if="item.status == 1 || item.status == null" class="item-content item-generating">
              <div class="item-thumb generating">
                <van-icon name="loading" size="36" class="spin-icon" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.pptTitle }}</div>
                <div class="item-meta">
                  <span class="status-text">生成中...</span>
                </div>
              </div>
            </div>

            <!-- 失败状态 -->
            <div v-else-if="item.status == 3" class="item-content item-failed">
              <div class="item-thumb failed">
                <van-icon name="warning-o" size="36" color="#F56C6C" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.pptTitle }}</div>
                <div class="item-meta">
                  <span class="fail-text">生成失败</span>
                </div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="deletePPT(item.id)" />
              </div>
            </div>
          </div>
          <div v-if="allList.length > 20" class="expand-btn" @click="isOpenList = !isOpenList">
            {{ isOpenList ? '收起' : '查看更多' }}
          </div>
        </div>
        <div v-else class="empty-state">
          <van-empty description="暂无PPT" />
        </div>
      </div>
    </div>

    <!-- 横屏预览页 -->
    <div v-if="isShowPPT" class="ppt-preview-page">
      <!-- 顶部操作栏 -->
      <div class="preview-nav">
        <div class="nav-side" @click="closePPT">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ previewPPTName }}</div>
        <div class="nav-side" @click="downloadPPT(ossDownloadUrl)">
          <van-icon name="down" size="20" />
        </div>
      </div>

      <!-- iframe 预览区域 -->
      <div class="preview-area">
        <div v-if="isIframeLoading" class="iframe-loading">
          <van-loading type="spinner" color="var(--primary)" size="36" />
          <p>正在加载预览...</p>
        </div>
        <iframe
          :src="pptPreviewUrl"
          width="100%"
          height="100%"
          frameborder="0"
          allowfullscreen
          @load="isIframeLoading = false"
        ></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-ppt {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-nav, .preview-nav {
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
.ppt-list-page {
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
.ppt-input {
  margin-bottom: 12px;
}
.submit-btn {
  font-weight: 600;
}

/* 列表 */
.list-section {
  margin-top: 8px;
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
  overflow: hidden;
  transition: all 0.2s;
}
.list-item:active {
  transform: scale(0.98);
}
.item-content {
  display: flex;
  align-items: center;
  padding: 12px;
  gap: 12px;
}
.item-thumb {
  width: 80px;
  height: 56px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page, #f7f8fa);
}
.item-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.item-thumb.generating {
  background: rgba(64, 158, 255, 0.08);
}
.item-thumb.failed {
  background: rgba(245, 108, 108, 0.08);
}
.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}
.item-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
}
.item-pages {
  font-size: 12px;
  color: var(--primary, #409EFF);
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
.item-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.action-icon {
  font-size: 20px;
  padding: 4px;
}
.download-icon {
  color: var(--primary, #409EFF);
}
.delete-icon {
  color: #F56C6C;
}
.expand-btn {
  text-align: center;
  padding: 12px;
  font-size: 14px;
  color: var(--text-gray, #969799);
}
.empty-state {
  padding: 40px 0;
}

.spin-icon {
  animation: spin 1s linear infinite;
  color: var(--primary, #409EFF);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 横屏预览页 */
.ppt-preview-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.preview-nav {
  flex-shrink: 0;
}

.preview-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.preview-area iframe {
  width: 100%;
  height: 100%;
  border: none;
}
.iframe-loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 2;
  color: var(--text-gray, #969799);
}
.iframe-loading p {
  margin-top: 12px;
  font-size: 14px;
}

/* 横屏模式：竖屏时旋转预览区域 */
@media screen and (orientation: portrait) {
  .ppt-preview-page {
    transform: rotate(90deg);
    transform-origin: center center;
    position: fixed;
    top: calc(50% - 50vw);
    left: calc(50% - 50vh);
    width: 100vh;
    height: 100vw;
  }
}
</style>
