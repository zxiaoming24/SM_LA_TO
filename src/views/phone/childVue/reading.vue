<!-- 移动端拓展阅读组件 -->
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import { getReadingListByUserId, submitReadingApi, getReadingProgressApi, getValueApi, deleteReadingByIdApi } from '@/api/mainApi/resourceReading.js'
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
  await getList()
  // 检查是否有跳转信息需要自动打开拓展阅读
  const skipInfo = isSkip(3)
  if (skipInfo && skipInfo.resourceId) {
    await getValue(skipInfo.resourceId)
    removeSkip(3)
  }
  await checkList()
})

// =================== 数据 =====================
const allList = ref([])
const showList = ref([])
const readingData = ref({ userId: null, text: '' })
const btnDisvisible = ref(false)

// =================== 预览相关 =====================
const isShow = ref(false)
const showHtmlData = ref({
  id: null, text: '', status: null, createTime: '', htmlContent: ''
})

// =================== 列表与生成 =====================
const getList = async () => {
  try {
    const result = await getReadingListByUserId(userId.value)
    if (result.code) {
      allList.value = result.data || []
      allList.value.sort((a, b) => new Date(b.createTime) - new Date(a.createTime))
      showList.value = allList.value.slice(0, 20)
    } else {
      showFailToast('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
    showFailToast('获取信息表失败')
  }
}

const getValue = async (id) => {
  try {
    const result = await getValueApi(id)
    if (result.code) {
      showHtmlData.value = result.data
      isShow.value = true
    } else if (result.code === 2) {
      showFailToast('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取信息失败', e)
    showFailToast('获取信息失败')
  }
}

const deleteItem = async (id) => {
  try {
    await showConfirmDialog({ title: '提示', message: '是否删除该拓展阅读？' })
    const result = await deleteReadingByIdApi(id)
    if (result.code) {
      showSuccessToast('删除成功')
      await getList()
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

const submit = async () => {
  if (!readingData.value.text || !readingData.value.text.trim()) {
    showToast('请输入主题/知识点'); return
  }
  if (readingData.value.text.length > 30) {
    showToast('长度不能超过30个字符'); return
  }
  btnDisvisible.value = true
  readingData.value.userId = userId.value
  try {
    const result = await submitReadingApi(readingData.value)
    if (result.code) {
      const task = result.data
      showLoadingToast({ message: '生成中...', forbidClick: true, duration: 0 })
      await getList()

      let nowNum = 0; const maxNum = 40
      let taskProgress = { status: 1 }

      while (nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          const progress = await getReadingProgressApi(task.id)
          if (progress.code) {
            taskProgress = progress.data
            if (taskProgress.status == 2) {
              showSuccessToast('生成完成')
              await getList(); await getValue(task.id); break
            } else if (taskProgress.status == 3) {
              showFailToast('生成失败')
              await getList(); break
            }
          }
        } catch (e) { console.error('轮询进度失败', e) }
      }
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
    readingData.value = { userId: null, text: '' }
    showLoadingToast({ message: '', duration: 0 })
  }
}

const checkList = async () => {
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0; const maxNum = 40
      let taskProgress = {}
      try {
        const progress = await getReadingProgressApi(item.id)
        if (progress.code) {
          taskProgress = progress.data
          if (taskProgress.status == null) {
            await deleteItem(item.id); await getList(); continue
          }
        }
      } catch (e) { continue }
      while (taskProgress.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          const progress = await getReadingProgressApi(item.id)
          if (progress.code) {
            taskProgress = progress.data
            if (taskProgress.status == 2) { await getList(); break }
            else if (taskProgress.status == 3) { await getList(); break }
          }
        } catch (e) { break }
      }
    }
  }
}

const quitShowHtml = () => {
  isShow.value = false
  showHtmlData.value = { id: null, text: '', status: null, createTime: '', htmlContent: '' }
}

const isOpenList = ref(false)
</script>

<template>
  <div class="phone-reading">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">拓展阅读</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShow" class="reading-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">拓展阅读</h2>
        <p class="page-desc">输入学习主题，一键生成拓展阅读材料</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="readingData.text"
          placeholder="例如：python基础"
          maxlength="30"
          show-word-limit
          clearable
          class="reading-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成阅读
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
            @click="getValue(item.id)"
          >
            <div class="item-info">
              <div class="item-name">{{ item.text }}</div>
              <div class="item-time">{{ item.createTime }}</div>
            </div>
            <div class="item-actions">
              <van-icon v-if="item.status == 1 || item.status == null" name="loading" class="loading-icon" />
              <span v-if="item.status == 1 || item.status == null" class="status-text">生成中</span>
              <van-icon v-if="item.status == 3" name="warning-o" class="fail-icon" />
              <van-icon
                v-if="item.status == 2 || item.status == 3"
                name="delete-o"
                class="delete-icon"
                @click.stop="deleteItem(item.id)"
              />
            </div>
          </div>
          <div v-if="allList.length > 20" class="expand-btn" @click="isOpenList = !isOpenList">
            {{ isOpenList ? '收起' : '查看更多' }}
          </div>
        </div>
        <div v-else class="empty-state">
          <van-empty description="暂无生成内容" />
        </div>
      </div>
    </div>

    <!-- 预览页 -->
    <div v-if="isShow" class="reading-detail-page">
      <div class="detail-nav">
        <div class="nav-side" @click="quitShowHtml">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ showHtmlData.text }}</div>
        <div class="nav-side" @click="quitShowHtml">
          <van-icon name="cross" size="20" />
        </div>
      </div>

      <!-- 生成中 -->
      <div v-if="showHtmlData.status == 1" class="status-page">
        <van-loading type="spinner" color="var(--primary)" size="48" />
        <p class="status-text">正在生成中，请稍候...</p>
      </div>

      <!-- 生成失败 -->
      <div v-if="showHtmlData.status == 3" class="status-page">
        <van-icon name="warning-o" size="64" color="#F56C6C" />
        <p class="status-text fail-text">生成失败</p>
      </div>

      <!-- 成功 - HTML内容 -->
      <div v-if="showHtmlData.status == 2" class="content-page">
        <div class="content-header">
          <!-- <div class="content-title">{{ showHtmlData.text }}</div> -->
          <div class="content-time">生成时间：{{ showHtmlData.createTime }}</div>
        </div>
        <div class="html-content" v-html="showHtmlData.htmlContent"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-reading {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-nav, .detail-nav {
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
.reading-list-page {
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
.reading-input {
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
  transition: all 0.2s;
}
.list-item:active {
  transform: scale(0.98);
}
.item-loading {
  opacity: 0.7;
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
.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}
.loading-icon {
  color: var(--primary, #409EFF);
  animation: spin 1s linear infinite;
}
.status-text {
  font-size: 12px;
  color: var(--primary, #409EFF);
  font-weight: 500;
}
.fail-icon {
  color: #F56C6C;
  font-size: 20px;
}
.delete-icon {
  color: #F56C6C;
  font-size: 20px;
  padding: 4px;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 预览页 */
.reading-detail-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 100;
  overflow-y: auto;
}

/* 状态页 */
.status-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
}
.status-page .status-text {
  margin-top: 20px;
  font-size: 16px;
  color: var(--text-gray, #969799);
}
.fail-text {
  color: #F56C6C !important;
  font-weight: 600;
}

/* 内容页 */
.content-page {
  padding: 16px;
}
.content-header {
  margin-bottom: 16px;
  text-align: center;
}
.content-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin-bottom: 6px;
}
.content-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
}

/* HTML 内容适配 */
.html-content {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--border-color, #eee);
  overflow: hidden;
  line-height: 1.8;
  font-size: 15px;
  color: var(--text-body, #323233);
}
.html-content :deep(h1),
.html-content :deep(h2),
.html-content :deep(h3),
.html-content :deep(h4),
.html-content :deep(h5),
.html-content :deep(h6) {
  color: var(--text-title, #323233);
  margin: 16px 0 8px;
}
.html-content :deep(h2) {
  font-size: 18px;
}
.html-content :deep(h3) {
  font-size: 16px;
}
.html-content :deep(p) {
  margin: 8px 0;
  line-height: 1.8;
}
.html-content :deep(code) {
  background: rgba(64, 158, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--primary, #409EFF);
}
.html-content :deep(a) {
  color: var(--primary, #409EFF);
}
.html-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.html-content :deep(div[style*="background:#f8f9fa"]),
.html-content :deep(div[style*="background:#fff"]),
.html-content :deep(div[style*="background:#ffffff"]) {
  background: var(--bg-page, #f7f8fa) !important;
  border-radius: 8px;
  padding: 12px;
  margin: 12px 0;
}

/* 夜间模式适配 */
:deep(.dark) .html-content {
  background: var(--bg-card);
}
:deep(.dark) .html-content * {
  color: var(--text-body) !important;
}
:deep(.dark) .html-content h1,
:deep(.dark) .html-content h2,
:deep(.dark) .html-content h3,
:deep(.dark) .html-content h4,
:deep(.dark) .html-content h5,
:deep(.dark) .html-content h6 {
  color: var(--text-title) !important;
}
:deep(.dark) .html-content a {
  color: var(--primary) !important;
}
</style>
