<!-- 移动端讲解文档组件 -->
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import { getListByUserIdApi, submitApi, getProgressApi, deleteByWordIdApi } from '@/api/mainApi/resourceWord.js'
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
      if (loginUser && loginUser.id) {
        userId.value = loginUser.id
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  await getWordList()
  // 检查是否有跳转信息需要自动打开讲解文档
  const skipInfo = isSkip(2)
  if (skipInfo && skipInfo.resourceId) {
    try {
      const res = await getProgressApi(skipInfo.resourceId)
      if (res.code === 1 && res.data?.ossUrl) {
        // 构造 item 数据用于打开预览
        const item = {
          id: skipInfo.resourceId,
          text: res.data.text || '讲解文档',
          status: 2,
          ossUrl: res.data.ossUrl
        }
        openWord(item)
      } else if (res.code === 2) {
        showToast('该讲解文档不存在，可能已被删除')
      }
    } catch (e) {
      console.error('打开讲解文档失败', e)
      showToast('打开讲解文档失败')
    }
    removeSkip(2)
  }
  await checkList()
})

// =================== 数据 =====================
const wordList = ref([])
const showList = ref([])
const wordData = ref({ userId: null, text: '' })
const btnDisvisible = ref(false)
const progressMsg = ref({})

// =================== 预览相关 =====================
const isShowWord = ref(false)
const previewWordName = ref('')
const wordPreviewUrl = ref('')
const ossDownloadUrl = ref('')
const isIframeLoading = ref(true)
const showWordData = ref({})

// =================== 列表 =====================
const getWordList = async () => {
  try {
    const result = await getListByUserIdApi(userId.value)
    if (result.code) {
      wordList.value = result.data || []
      wordList.value.sort((a, b) => new Date(b.createTime) - new Date(a.createTime))
      showList.value = wordList.value.slice(0, 20)
    } else {
      showFailToast('获取讲解文档列表失败')
    }
  } catch (e) {
    console.error('获取讲解文档列表失败', e)
    showFailToast('获取讲解文档列表失败')
  }
}

// =================== 生成 =====================
const submit = async () => {
  if (!wordData.value.text || !wordData.value.text.trim()) {
    showToast('请输入主题/知识点')
    return
  }
  if (wordData.value.text.length > 30) {
    showToast('长度不能超过30个字符')
    return
  }
  btnDisvisible.value = true
  wordData.value.userId = userId.value

  try {
    const result = await submitApi(wordData.value)
    if (result.code) {
      showSuccessToast('提交成功')
      const taskId = result.data.id

      if (result.data.status == 1 || result.data.status == null) {
        showLoadingToast({ message: '生成中...', forbidClick: true, duration: 0 })
        await getWordList()

        let nowNum = 0
        const maxNum = 40

        try {
          await getProgress(taskId)
          if (progressMsg.value.status == null) {
            await delWord(taskId, false)
            await getWordList()
            progressMsg.value = {}
            return
          }
        } catch (e) {
          console.error('首次查询进度失败', e)
        }

        while (progressMsg.value.status == 1 && nowNum < maxNum) {
          nowNum++
          await new Promise(resolve => setTimeout(resolve, 10000))
          try {
            await getProgress(taskId)
          } catch (e) {
            console.error('轮询进度失败', e)
            break
          }
        }

        if (progressMsg.value.status == 2) {
          showSuccessToast('讲解文档生成成功！')
          await getWordList()
          progressMsg.value = {}
        } else {
          showFailToast('讲解文档生成失败或超时')
          await getWordList()
          progressMsg.value = {}
        }
      } else if (result.data.status == 2 || result.data.status == 3) {
        await getWordList()
      }

      wordData.value = { userId: null, text: '' }
    } else {
      showFailToast('提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
    showLoadingToast({ message: '', duration: 0 })
  }
}

// =================== 进度 =====================
const getProgress = async (id) => {
  try {
    const result = await getProgressApi(id)
    if (result.code) {
      progressMsg.value = result.data
    } else {
      showFailToast('获取进度失败')
    }
  } catch (e) {
    console.error('获取进度失败', e)
  }
}

// =================== 删除 =====================
const delWord = async (id, isShow = true) => {
  if (isShow) {
    try {
      await showConfirmDialog({ title: '提示', message: '是否删除该讲解文档？' })
    } catch (e) {
      return
    }
  }

  try {
    const result = await deleteByWordIdApi(id)
    if (result.code) {
      showSuccessToast('删除成功')
      await getWordList()
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
    showFailToast('删除失败')
  }
}

// =================== 预览 =====================
const openWord = (item) => {
  if (item.status != 2) {
    showToast('该文档尚未生成完成')
    return
  }
  previewWordName.value = item.text
  ossDownloadUrl.value = item.ossUrl
  isIframeLoading.value = true
  isShowWord.value = true
  showWordData.value = item
  wordPreviewUrl.value = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(item.ossUrl)}`
}

const closeWord = () => {
  isShowWord.value = false
  previewWordName.value = ''
  wordPreviewUrl.value = ''
  ossDownloadUrl.value = ''
  showWordData.value = {}
}

// =================== 下载 =====================
const downloadWord = (url) => {
  if (!url) {
    showToast('下载地址不存在')
    return
  }
  const link = document.createElement('a')
  link.href = url
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// =================== 检查截断任务 =====================
const checkList = async () => {
  for (let i = 0; i < wordList.value.length; i++) {
    const item = wordList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      const maxNum = 40

      try {
        await getProgress(item.id)
        if (progressMsg.value.status == null) {
          item.status = 3
          await delWord(item.id, false)
          await getWordList()
          progressMsg.value = {}
          continue
        }
      } catch (e) {
        continue
      }

      while (progressMsg.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(item.id)
        } catch (e) {
          break
        }
      }

      if (progressMsg.value.status == 2) {
        showSuccessToast('讲解文档生成成功！')
        await getWordList()
        progressMsg.value = {}
      } else {
        await getWordList()
        progressMsg.value = {}
      }
    }
  }
}

// =================== 工具函数 =====================
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.replace('T', ' ').substring(0, 19)
}

const isOpenList = ref(false)
</script>

<template>
  <div class="phone-word">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">讲解文档</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShowWord" class="word-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">讲解文档 智能生成</h2>
        <p class="page-desc">输入学习主题，一键生成超详细讲解文档</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="wordData.text"
          placeholder="例如：python基础"
          maxlength="30"
          show-word-limit
          clearable
          class="word-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成
        </van-button>
      </div>

      <!-- 列表 -->
      <div class="list-section">
        <div v-if="wordList.length > 0" class="list-wrap">
          <div
            v-for="item in (isOpenList ? wordList : showList)"
            :key="item.id"
            class="list-item"
            :class="{ 'item-loading': item.status == 1 || item.status == null, 'item-fail': item.status == 3 }"
          >
            <!-- 成功状态 -->
            <div v-if="item.status == 2" class="item-content" @click="openWord(item)">
              <div class="item-icon">
                <van-icon name="chat-o" size="36" color="#00BCD4" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">{{ formatTime(item.createTime) }}</div>
              </div>
              <div class="item-actions">
                <van-icon name="down" class="action-icon download-icon" @click.stop="downloadWord(item.ossUrl)" />
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="delWord(item.id)" />
              </div>
            </div>

            <!-- 生成中状态 -->
            <div v-else-if="item.status == 1 || item.status == null" class="item-content item-generating">
              <div class="item-icon generating">
                <van-icon name="loading" size="36" class="spin-icon" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">
                  <span class="status-text">生成中...</span>
                </div>
              </div>
            </div>

            <!-- 失败状态 -->
            <div v-else-if="item.status == 3" class="item-content item-failed">
              <div class="item-icon failed">
                <van-icon name="warning-o" size="36" color="#F56C6C" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">
                  <span class="fail-text">生成失败</span>
                </div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="delWord(item.id)" />
              </div>
            </div>
          </div>
          <div v-if="wordList.length > 20" class="expand-btn" @click="isOpenList = !isOpenList">
            {{ isOpenList ? '收起' : '查看更多' }}
          </div>
        </div>
        <div v-else class="empty-state">
          <van-empty description="暂无讲解文档" />
        </div>
      </div>
    </div>

    <!-- 横屏预览页 -->
    <div v-if="isShowWord" class="word-preview-page">
      <!-- 顶部操作栏 -->
      <div class="preview-nav">
        <div class="nav-side" @click="closeWord">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ previewWordName }}</div>
        <div class="nav-side" @click="downloadWord(ossDownloadUrl)">
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
          :src="wordPreviewUrl"
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
.phone-word {
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
.word-list-page {
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
.item-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 188, 212, 0.1);
}
.item-icon.generating {
  background: rgba(0, 188, 212, 0.08);
}
.item-icon.failed {
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
.item-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}
.status-text {
  font-size: 12px;
  color: #00BCD4;
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
  color: #00BCD4;
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
  color: #00BCD4;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 横屏预览页 */
.word-preview-page {
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
  .word-preview-page {
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
