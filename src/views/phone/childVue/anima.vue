<!-- 移动端动画组件 -->
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import { getAnimaListApi, generateAnimaApi, pollAnimaApi, deleteAnimaApi } from '@/api/mainApi/resourceAnima.js'
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
  await getList()
  // 检查是否有跳转信息需要自动打开动画
  const skipInfo = isSkip(6)
  if (skipInfo && skipInfo.resourceId) {
    await getValue(skipInfo.resourceId)
    removeSkip(6)
  }
  await checkList()
})

// =================== 数据 =====================
const animaData = ref({
  userId: null,
  text: '',
  enableTts: true
})
const btnDisvisible = ref(false)
const task = ref({})
const taskProgress = ref({})

// =================== 列表 =====================
const allList = ref([])
const showList = ref([])
const isOpenList = ref(false)

// =================== 预览 =====================
const isShow = ref(false)
const showHtmlData = ref({
  id: null,
  text: '',
  status: null,
  createTime: '',
  htmlContent: ''
})
const previewHtmlContent = ref('')
const iframeRef = ref(null)

// 生成中HTML
const ingHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#fff; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1); min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center;">
  <div style="width:60px; height:60px; border:4px solid #DBEAFE; border-top-color:#2D7DDB; border-radius:50%; animation:spin 1s linear infinite; margin-bottom:20px;"></div>
  <h2 style="color:#2D7DDB; border-left:4px solid #2D7DDB; padding-left:12px; font-size:20px;">正在生成动画中，请稍候...</h2>
  <p style="color:#64748B; font-size:14px; margin-top:10px;">系统正在处理你的数据，请稍等片刻</p>
  <style>@keyframes spin { to { transform:rotate(360deg); } }</style>
</div>`

// 失败HTML
const failHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#ffffff; min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.08);">
  <div style="font-size:70px; color:#E53E3E; margin-bottom:24px; animation: shake 0.5s ease-in-out infinite alternate;">✕</div>
  <h2 style="color:#E53E3E; border-left:4px solid #E53E3E; padding-left:12px; font-size:22px; font-weight:bold; margin-bottom:16px;">生成失败</h2>
  <p style="color:#64748B; font-size:15px; text-align:center;">动画生成过程中出现异常，请删除重试</p>
  <style>@keyframes shake{0%{transform:scale(1);opacity:0.8;}100%{transform:scale(1.1);opacity:1;}}</style>
</div>`

// =================== 接口 =====================
const getList = async () => {
  try {
    const result = await getAnimaListApi(userId.value)
    if (result.code) {
      allList.value = result.data || []
      showList.value = allList.value.slice(0, 20)
    } else {
      showFailToast('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}

const getValue = async (id) => {
  try {
    const result = await pollAnimaApi(id)
    if (result.code && result.data) {
      showHtmlData.value = {
        id: result.data.id,
        text: result.data.text || '',
        status: result.data.status,
        createTime: result.data.createTime || '',
        htmlContent: result.data.html || ''
      }
      if (result.data.html && result.data.status === 2) {
        displayHtmlContent(result.data.html)
      } else {
        previewHtmlContent.value = ''
      }
      isShow.value = true
    } else if (result.code === 2) {
      showToast('未找到对应资源，可能已被删除')
    } else {
      if (result.data === null && result.code === 0) {
        showHtmlData.value = {
          id: id,
          text: '',
          status: 3,
          createTime: '',
          htmlContent: ''
        }
        isShow.value = true
      } else {
        showFailToast(result.msg || '获取信息失败')
      }
    }
  } catch (e) {
    console.error('获取信息失败', e)
    showFailToast('获取信息失败')
  }
}

const deleteItem = async (id, isTip = true) => {
  if (isTip) {
    try {
      await showConfirmDialog({ title: '提示', message: '是否删除该信息？' })
    } catch (e) {
      return
    }
  }
  try {
    const result = await deleteAnimaApi(id)
    if (result.code) {
      showSuccessToast('删除成功')
      await getList()
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
    showFailToast('删除失败')
  }
}

const createTask = async () => {
  try {
    const result = await generateAnimaApi(animaData.value)
    if (result.code) {
      task.value = result.data
      taskProgress.value = { status: 1, id: result.data.id }
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  }
}

const getProgress = async (id) => {
  try {
    const result = await pollAnimaApi(id)
    if (result.code && result.data) {
      taskProgress.value = result.data
    } else {
      if (result.code === 0) {
        taskProgress.value = { status: 3, id: id }
      } else {
        taskProgress.value = { status: 1, id: id }
      }
    }
  } catch (e) {
    console.error('查询进度失败', e)
    taskProgress.value = { status: 1, id: id }
  }
}

// =================== 提交 =====================
const submit = async () => {
  if (!animaData.value.text || !animaData.value.text.trim()) {
    showToast('请输入动画主题/知识点')
    return
  }
  if (animaData.value.text.length > 30) {
    showToast('长度不能超过30个字符')
    return
  }

  btnDisvisible.value = true
  animaData.value.userId = userId.value

  try {
    await createTask()
    if (taskProgress.value.status == 1 || taskProgress.value.status == null) {
      let nowNum = 0
      const maxNum = 40

      try {
        await getProgress(task.value.id)
        if (taskProgress.value.status == null) {
          await deleteItem(task.value.id, false)
          await getList()
          task.value = {}
          taskProgress.value = {}
          return
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
      }

      await getList()
      await getValue(task.value.id)

      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(task.value.id)
        } catch (e) {
          console.error('轮询进度失败', e)
        }
      }

      if (taskProgress.value.status == 2) {
        showSuccessToast('动画生成成功！')
        await getList()
        await getValue(task.value.id)
        task.value = {}
        taskProgress.value = {}
      } else {
        await getList()
        await getValue(task.value.id)
        task.value = {}
        taskProgress.value = {}
      }
    } else if (taskProgress.value.status == 2 || taskProgress.value.status == 3) {
      await getList()
      await getValue(task.value.id)
      task.value = {}
      taskProgress.value = {}
    }
  } finally {
    btnDisvisible.value = false
    animaData.value = { userId: null, text: '', enableTts: true }
  }
}

// =================== 预览 =====================
const displayHtmlContent = (htmlString) => {
  if (!htmlString) {
    previewHtmlContent.value = ''
    return
  }
  previewHtmlContent.value = htmlString
  setTimeout(() => {
    if (iframeRef.value) {
      const iframeDoc = iframeRef.value.contentDocument || iframeRef.value.contentWindow.document
      iframeDoc.open()
      iframeDoc.write(htmlString)
      iframeDoc.close()
    }
  }, 0)
}

const quitShowHtml = () => {
  isShow.value = false
  previewHtmlContent.value = ''
  showHtmlData.value = {
    id: null,
    text: '',
    status: null,
    createTime: '',
    htmlContent: ''
  }
}

// =================== 检查截断任务 =====================
const checkList = async () => {
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      const maxNum = 40

      try {
        await getProgress(item.id)
        if (taskProgress.value.status == null) {
          await deleteItem(item.id, false)
          await getList()
          taskProgress.value = {}
          continue
        }
      } catch (e) {
        continue
      }

      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(item.id)
        } catch (e) {
          break
        }
      }

      if (taskProgress.value.status == 2) {
        showSuccessToast('动画生成成功！')
        await getList()
        taskProgress.value = {}
      } else {
        await getList()
        taskProgress.value = {}
      }
    }
  }
}

// =================== 工具函数 =====================
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.replace('T', ' ').substring(0, 19)
}
</script>

<template>
  <div class="phone-anima">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">动画</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShow" class="anima-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">智能动画 一键生成</h2>
        <p class="page-desc">输入学习主题，AI为你生成生动有趣的动画演示</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="animaData.text"
          placeholder="例如：二叉树遍历、冒泡排序、太阳系"
          maxlength="30"
          show-word-limit
          clearable
          class="anima-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成动画
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
            <!-- 成功状态 -->
            <div v-if="item.status == 2" class="item-content" @click="getValue(item.id)">
              <div class="item-icon">
                <van-icon name="video-o" size="36" color="#FF9800" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text || '无标题' }}</div>
                <div class="item-time">{{ formatTime(item.createTime) }}</div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="deleteItem(item.id)" />
              </div>
            </div>

            <!-- 生成中状态 -->
            <div v-else-if="item.status == 1 || item.status == null" class="item-content item-generating" @click="getValue(item.id)">
              <div class="item-icon generating">
                <van-icon name="loading" size="36" class="spin-icon" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text || '生成中...' }}</div>
                <div class="item-time">
                  <span class="status-text">生成中...</span>
                </div>
              </div>
            </div>

            <!-- 失败状态 -->
            <div v-else-if="item.status == 3" class="item-content item-failed" @click="getValue(item.id)">
              <div class="item-icon failed">
                <van-icon name="warning-o" size="36" color="#F56C6C" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text || '生成失败' }}</div>
                <div class="item-time">
                  <span class="fail-text">生成失败</span>
                </div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="deleteItem(item.id)" />
              </div>
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
    <div v-if="isShow" class="anima-preview-page">
      <!-- 顶部操作栏 -->
      <div class="preview-nav">
        <div class="nav-side" @click="quitShowHtml">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ showHtmlData.text || '动画预览' }}</div>
        <div class="nav-side"></div>
      </div>

      <!-- 预览内容 -->
      <div class="preview-content">
        <div class="content-header">
          <div class="content-title">{{ showHtmlData.text }}</div>
          <div class="content-time">生成时间：{{ showHtmlData.createTime }}</div>
        </div>

        <!-- 成功项 - iframe 显示 HTML -->
        <div v-if="showHtmlData.status == 2 && showHtmlData.htmlContent" class="iframe-wrapper">
          <iframe
            ref="iframeRef"
            :srcdoc="previewHtmlContent"
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals"
            style="width: 100%; min-height: 600px; border: none; border-radius: 8px; background: #fff;"
            title="动画预览"
          ></iframe>
        </div>

        <!-- 生成中 -->
        <div v-else-if="showHtmlData.status == 1" class="html-preview" v-html="ingHtml"></div>

        <!-- 失败 -->
        <div v-else-if="showHtmlData.status == 3" class="html-preview" v-html="failHtml"></div>

        <!-- 成功但无内容 -->
        <div v-else-if="showHtmlData.status == 2 && !showHtmlData.htmlContent" class="html-preview" v-html="ingHtml"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-anima {
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
.anima-list-page {
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
  background: rgba(255, 152, 0, 0.1);
}
.item-icon.generating {
  background: rgba(255, 152, 0, 0.08);
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
  color: #FF9800;
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
  color: #FF9800;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 预览页 */
.anima-preview-page {
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

.preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.content-header {
  text-align: center;
  margin-bottom: 16px;
}
.content-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.content-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}

.iframe-wrapper {
  width: 100%;
  min-height: 600px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.html-preview {
  width: 100%;
  overflow: hidden;
}

.html-preview :deep(div) {
  max-width: 100% !important;
}
</style>
