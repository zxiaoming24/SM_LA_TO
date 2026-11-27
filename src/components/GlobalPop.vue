<!-- 全局弹窗组件 -->
<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useActionPopStore } from '@/utils/actionPop'
import { getAiPostInfoApi, postAiApi } from '@/api/mainApi/pop.js'
import { saveSkip } from '@/utils/skip.js'//跳转
import { useRouter } from 'vue-router'
import { useRoute } from 'vue-router'
//获取当前路由
const currentRoute = useRoute()
const router = useRouter()

const popStore = useActionPopStore()

let loginUser = null
const userId = ref(null)

// 表单数据
const postForm = reactive({
  title: '',
  content: '',
  zone: '',
  tags: []
})

// 标签输入
const tagInput = ref('')

// 分区选项
const zoneOptions = ref([])
// AI识别的问题列表
const identifiedIssues = ref([])
// 加载状态
const postLoading = ref(false)
// 提交状态
const submitting = ref(false)

// 资源信息（从popStore获取）
const resourceInfo = ref({
  resourceId: null,
  resourceType: null,
  resourceTitle: '',
  resourceContent: ''
})

// 共学邀请：作答模式
const selectedMode = ref('separate')

// 获取用户信息
const getUserInfo = () => {
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
}

// 获取AI生成的帖子信息
const getPostInfo = async () => {
  if (!userId.value) {
    ElMessage.warning('请先登录')
    return
  }
  
  postLoading.value = true
  
  try {
    const res = await getAiPostInfoApi({
      userId: userId.value,
      resourceType: popStore.currentData?.rsType || null,
      resourceId: popStore.currentData?.rsId || null
    })
    
    if (res.code === 1 && res.data) {
      const draft = res.data.draft || {}
      const zones = res.data.zones || {}
      const preview = res.data.preview || {}
      
      // 填充表单
      postForm.title = draft.title || preview.title || ''
      postForm.content = draft.content || preview.content || ''
      postForm.zone = draft.zone || preview.zone || ''
      postForm.tags = draft.tags || preview.tags || []
      
      // 设置分区选项
      zoneOptions.value = Object.values(zones).map(item => ({
        id: item.id,
        name: item.name,
        description: item.description,
        tags: item.tags || []
      }))
      
      // 设置问题列表
      identifiedIssues.value = preview.identified_issues || draft.identified_issues || []
      
      // 更新资源信息
      if (popStore.currentData) {
        resourceInfo.value = {
          resourceId: popStore.currentData.rsId,
          resourceType: popStore.currentData.rsType,
          resourceTitle: popStore.currentData.resourceTitle || draft.title || '',
          resourceContent: draft.content || ''
        }
      }
      
      ElMessage.success('AI已生成帖子内容，请根据需要修改后发布')
    } else {
      ElMessage.error(res.msg || '获取AI帖子信息失败')
    }
  } catch (e) {
    console.error('获取AI规划帖子信息失败：', e)
    ElMessage.error('获取AI帖子信息失败，请重试')
  } finally {
    postLoading.value = false
  }
}

// 分区变化时更新标签建议
const onZoneChange = () => {
  const currentZone = zoneOptions.value.find(item => item.id === postForm.zone)
  if (currentZone && currentZone.tags) {
    // 将分区标签作为建议，但不自动添加
  }
}

// 获取分区描述
const getZoneDescription = (zoneId) => {
  const zone = zoneOptions.value.find(item => item.id === zoneId)
  return zone ? zone.description : ''
}

// 添加标签
const addTag = () => {
  const tag = tagInput.value.trim()
  if (!tag) {
    ElMessage.warning('请输入标签内容')
    return
  }
  if (postForm.tags.includes(tag)) {
    ElMessage.warning('标签已存在')
    return
  }
  if (postForm.tags.length >= 10) {
    ElMessage.warning('最多添加10个标签')
    return
  }
  postForm.tags.push(tag)
  tagInput.value = ''
}

// 移除标签
const removeTag = (index) => {
  postForm.tags.splice(index, 1)
}

// 提交帖子
const handleSubmitPost = async () => {
  if (!postForm.title.trim()) {
    ElMessage.warning('请输入帖子标题')
    return
  }
  if (!postForm.content.trim()) {
    ElMessage.warning('请输入帖子内容')
    return
  }
  if (!postForm.zone) {
    ElMessage.warning('请选择帖子分区')
    return
  }
  
  submitting.value = true
  
  try {
    const params = {
      user_id: userId.value,
      resource_type: resourceInfo.value.resourceType,
      resource_title: resourceInfo.value.resourceTitle || postForm.title,
      resource_content: resourceInfo.value.resourceContent || '',// 资源内容
      title: postForm.title.trim(),
      content: postForm.content.trim(),// 帖子内容
      tags: postForm.tags,
      zone: postForm.zone
    }
    
    const res = await postAiApi(params)
    
    if (res.code === 1 && res.data) {
      ElMessage.success(res.data.message)
      popStore.closePostCommunity()

      saveSkip(9,res.data.post.post_id)
      router.push('/index')
      
      resetForm()
    } else {
      ElMessage.error(res.msg || '帖子发布失败')
    }
  } catch (e) {
    console.error('发布帖子失败：', e)
    ElMessage.error('发布帖子失败，请重试')
  } finally {
    submitting.value = false
  }
}

// 重置表单
const resetForm = () => {
  postForm.title = ''
  postForm.content = ''
  postForm.zone = ''
  postForm.tags = []
  identifiedIssues.value = []
  tagInput.value = ''
}

// 关闭弹窗
const handleClose = () => {
  popStore.closePostCommunity()
  resetForm()
}

// 点击遮罩关闭
const handleCloseMask = () => {
  if (!postLoading.value && !submitting.value) {
    handleClose()
  }
}

// 打开发帖弹窗
const handleOpenPostCommunity = () => {
  getUserInfo()
  popStore.openPostCommunity()
  getPostInfo()
}

// 监听弹窗打开
watch(() => popStore.postCommunityVisible, (visible) => {
  if (visible) {
    getUserInfo()
  }
})

onMounted(() => {
  getUserInfo()
})
</script>


<template>
  <!-- 主悬浮菜单 + 从下往上动画 -->
  <transition name="pop-slide-up">
    <div
      v-if="popStore.popVisible"
      class="float-pop"
      :style="{ left: popStore.popLeft + 'px', top: popStore.popTop + 'px' }"
      @mouseenter="popStore.clearTimer()"
      @mouseleave="popStore.delayHidePop()"
    >
      <button class="pop-btn" @click="popStore.handleCollect">
        <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
        收藏
      </button>
      <button class="pop-btn" @click="popStore.openShareConfirm">
        <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>
        分享到社区
      </button>
      <button class="pop-btn" @click="popStore.openPartnerList">
        <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
        分享给学伴
      </button>
      <button class="pop-btn pop-btn-primary" @click="handleOpenPostCommunity">
        <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
        AI发帖助手
      </button>
      <button class="pop-btn" @click="popStore.openStudyInvite">
        <svg class="icon" viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        共学邀请
      </button>
    </div>
  </transition>

  <!-- 二级弹窗 -->
  <!-- 分享到社区 -->
  <Teleport to="body">
    <transition name="modal-fade">
      <div v-if="popStore.shareConfirmVisible" class="mask">
        <div class="modal" @click.stop>
          <div class="modal-header">
            <h3>分享到社区</h3>
            <button class="modal-close" @click="popStore.closeShareConfirm(0)">×</button>
          </div>
          <div class="modal-body">
            <div class="confirm-icon">
              <svg viewBox="0 0 48 48" width="48" height="48"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>
            </div>
            <p class="confirm-text">确定要将此资源分享到社区吗？</p>
            <p class="confirm-sub">分享后所有社区成员都可以看到</p>
          </div>
          <div class="btn-group">
            <button class="cancel-btn" @click="popStore.closeShareConfirm(0)">取消</button>
            <button class="confirm-btn" @click="popStore.closeShareConfirm(1)">确定分享</button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>

  <!-- 分享给学伴 -->
  <Teleport to="body">
    <transition name="modal-fade">
      <div v-if="popStore.partnerListVisible" class="mask">
        <div class="modal modal-lg" @click.stop>
          <div class="modal-header">
            <h3>选择学伴</h3>
            <button class="modal-close" @click="popStore.closePartnerList">×</button>
          </div>
          <div class="modal-body">
            <div class="partner-list">
              <div
                class="partner-item"
                v-if="popStore.partnerList.length > 0"
                v-for="item in popStore.partnerList"
                :key="item.id"
                @click="popStore.shareToPartner(item.user_id)"
              >
                <el-avatar :size="45" :src="item.avatar" style="border: 2px solid var(--border-color)">
                  {{ item.username || '学伴' }}
                </el-avatar>
                <div class="partner-info">
                  <div class="username">【ID：{{ item.user_id }}】{{ item.username || '学伴' }}</div>
                  <div class="user-desc">点击分享</div>
                </div>
                <button class="share-btn">分享</button>
              </div>
              <div class="empty" v-if="popStore.partnerList.length === 0">
                <img class="empty-img" src="@/assets/image/emptyStatus.png" alt="空"/>
                <div class="empty-text">还没有学伴，快去添加吧</div>
              </div>
            </div>
          </div>
          <div class="btn-group">
            <button class="cancel-btn" @click="popStore.closePartnerList">关闭</button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>

  <!-- 发帖到社区 -->
  <Teleport to="body">
    <transition name="modal-fade">
      <div v-if="popStore.postCommunityVisible" class="mask">
        <div class="modal post-modal" @click.stop>
          <div class="modal-header">
            <div class="header-left">
              <span class="header-icon">
                <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
              </span>
              <h3>发帖到社区</h3>
            </div>
            <button class="modal-close" @click="handleClose" :disabled="submitting || postLoading" >×</button>
          </div>
          
          <div class="modal-body">
            <!-- 加载状态 -->
            <div v-if="postLoading" class="loading-container">
              <div class="loading-spinner"></div>
              <span class="loading-title">AI 正在生成帖子内容...</span>
              <span class="loading-sub">请稍候，智能助手正在为你撰写</span>
            </div>
            
            <!-- 表单内容 -->
            <form v-else class="post-form" @submit.prevent="handleSubmitPost">
              <!-- 标题 -->
              <div class="form-group">
                <label>
                  <span class="label-text">标题</span>
                  <span class="required">*</span>
                </label>
                <input 
                  v-model="postForm.title" 
                  type="text"
                  class="form-input"
                  placeholder="输入一个吸引人的标题..."
                  maxlength="100"
                />
                <div class="char-count">{{ postForm.title.length }}/100</div>
              </div>
              
              <!-- 内容 -->
              <div class="form-group">
                <label>
                  <span class="label-text">内容</span>
                  <span class="required">*</span>
                </label>
                <textarea
                  v-model="postForm.content"
                  class="form-textarea"
                  rows="6"
                  placeholder="分享你的想法、经验或问题..."
                  maxlength="2000"
                ></textarea>
                <div class="char-count">{{ postForm.content.length }}/2000</div>
              </div>
              
              <!-- 分区 -->
              <div class="form-group">
                <label>
                  <span class="label-text">选择分区</span>
                  <span class="required">*</span>
                </label>
                <div class="select-wrapper">
                  <select v-model="postForm.zone" class="form-select" @change="onZoneChange">
                    <option value="">请选择分区</option>
                    <option
                      v-for="item in zoneOptions"
                      :key="item.id"
                      :value="item.id"
                    >
                      {{ item.name }}
                    </option>
                  </select>
                  <span class="select-arrow">▾</span>
                </div>
                <div v-if="postForm.zone" class="zone-desc">
                  {{ getZoneDescription(postForm.zone) }}
                </div>
              </div>
              
              <!-- 标签 -->
              <div class="form-group">
                <label>
                  <span class="label-text">添加标签</span>
                  <span class="label-hint">（最多10个）</span>
                </label>
                <div class="tag-input-container">
                  <div class="tag-input-wrapper">
                    <span class="tag-prefix">#</span>
                    <input
                      v-model="tagInput"
                      type="text"
                      class="form-input tag-input"
                      placeholder="输入标签，按回车添加"
                      @keydown.enter.prevent="addTag"
                      maxlength="20"
                    />
                  </div>
                  <button type="button" class="tag-add-btn" @click="addTag">
                    <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
                    添加
                  </button>
                </div>
                <div class="tag-list">
                  <span
                    v-for="(tag, index) in postForm.tags"
                    :key="index"
                    class="tag-item"
                  >
                    #{{ tag }}
                    <span class="tag-remove" @click="removeTag(index)">×</span>
                  </span>
                  <span v-if="postForm.tags.length === 0" class="tag-empty">还没有标签，添加一些吧</span>
                </div>
              </div>
              
              <!-- 问题与建议（只读展示） -->
              <div v-if="identifiedIssues.length > 0" class="form-group issues-group">
                <label>
                  <span class="label-text">AI 识别的问题与建议</span>
                </label>
                <div class="issues-list">
                  <div 
                    v-for="(issue, index) in identifiedIssues" 
                    :key="index"
                    class="issue-item"
                  >
                    <div class="issue-number">{{ index + 1 }}</div>
                    <div class="issue-content">
                      <div class="issue-title">{{ issue.issue }}</div>
                      <div class="issue-reason">
                        <span class="issue-label">原因：</span>{{ issue.reason }}
                      </div>
                      <div class="issue-suggestion">
                        <span class="issue-label">建议：</span>{{ issue.suggestion }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </form>
          </div>
          
          <!-- 操作按钮 -->
          <div class="modal-footer" v-if="!postLoading">
            <div class="footer-left">
              <span class="draft-hint">
                <svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/></svg>
                内容将自动保存
              </span>
            </div>
            <div class="btn-group">
              <button type="button" class="cancel-btn" @click="handleClose">取消</button>
              <button type="submit" class="confirm-btn" :disabled="submitting" @click="handleSubmitPost">
                <svg v-if="!submitting" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                <span v-else class="btn-loading">
                  <span class="btn-spinner"></span>
                  发布中...
                </span>
                <span v-if="!submitting">发布</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>

  <!-- 共学邀请 -->
  <Teleport to="body">
    <transition name="modal-fade">
      <div v-if="popStore.studyInviteVisible" class="mask">
        <div class="modal modal-lg" @click.stop>
          <div class="modal-header">
            <h3>发起共学邀请</h3>
            <button class="modal-close" @click="popStore.closeStudyInvite">×</button>
          </div>
          <div class="modal-body">
            <div class="invite-icon">
              <svg viewBox="0 0 48 48" width="48" height="48"><path fill="currentColor" d="M24 24c4.42 0 8-3.58 8-8s-3.58-8-8-8-8 3.58-8 8 3.58 8 8 8zm0 4c-5.33 0-16 2.67-16 8v4h32v-4c0-5.33-10.67-8-16-8z"/></svg>
            </div>
            <p class="invite-text">选择邀请对象并发送共学邀请</p>

            <div class="select-box-compact">
              <label for="myMode" class="label-compact">
                <span>作答方式</span>
              </label>

              <div class="select-wrapper-compact">
                <select id="myMode" v-model="selectedMode" class="select-compact">
                  <option value="separate">独立作答/独立查看</option>
                  <option value="pair" v-if="currentRoute.path === '/code'">结对编程</option>
                </select>
                <span class="arrow-compact">▾</span>
              </div>
            </div>

            <div class="partner-list">
              <div
                class="partner-item"
                v-if="popStore.partnerList.length > 0"
                v-for="item in popStore.partnerList"
                :key="item.id"
                @click="popStore.studyToPartner(item.user_id,selectedMode)"
              >
                <el-avatar :size="45" :src="item.avatar" style="border: 2px solid var(--border-color)">
                  {{ item.username || '学伴' }}
                </el-avatar>
                <div class="partner-info">
                  <div class="username">【ID：{{ item.user_id }}】{{ item.username || '学伴' }}</div>
                  <div class="user-desc">点击邀请</div>
                </div>
                <button class="share-btn">发送邀请</button>
              </div>
              <div class="empty" v-if="popStore.partnerList.length === 0">
                <img class="empty-img" src="@/assets/image/emptyStatus.png" alt="空"/>
                <div class="empty-text">还没有学伴，快去添加吧</div>
              </div>
            </div>
          </div>
          <!-- <div class="btn-group">
            <button class="cancel-btn" @click="popStore.closeStudyInvite">取消</button>
            <button class="confirm-btn">发送邀请</button>
          </div> -->
        </div>
      </div>

    </transition>
  </Teleport>
</template>

<style scoped>
/* ===== 主菜单 - 玻璃质感 ===== */
.float-pop {
  position: fixed;
  z-index: 4;
  display: flex;
  gap: 4px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(20px) saturate(1.6);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  transform-origin: left bottom;
}

.float-pop::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--radius-lg);
  padding: 1px;
  background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.1) 100%);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.float-pop::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--radius-lg);
  background: radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.4) 0%, transparent 60%);
  pointer-events: none;
}

.pop-slide-up-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}
.pop-slide-up-enter-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.pop-slide-up-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}
.pop-slide-up-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
.pop-slide-up-leave-active {
  transition: all 0.25s ease;
}
.pop-slide-up-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}

/* ===== 主菜单按钮 - 统一颜色 ===== */
.pop-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border: none;
  background: rgba(45, 125, 219, 0.1);
  border-radius: var(--radius-md);
  color: var(--primary);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
  font-weight: 500;
  letter-spacing: 0.3px;
  backdrop-filter: blur(4px);
}

.pop-btn .icon {
  flex-shrink: 0;
  opacity: 0.8;
}

.pop-btn:hover {
  background: var(--primary);
  color: #ffffff;
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}

.pop-btn:hover .icon {
  opacity: 1;
}

.pop-btn:active {
  transform: translateY(0px) scale(0.97);
}

/* 主要按钮 - 突出显示 */
.pop-btn-primary {
  background: var(--primary);
  color: #ffffff;
  box-shadow: var(--shadow-brand);
}

.pop-btn-primary:hover {
  background: var(--primary-hv);
  color: #ffffff;
  box-shadow: 0 6px 24px rgba(45, 125, 219, 0.4);
}

.pop-btn-primary .icon {
  opacity: 1;
}

/* ===== 遮罩层 ===== */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.01);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

/* ===== 弹窗过渡动画 ===== */
.modal-fade-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(20px);
}
.modal-fade-enter-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.modal-fade-enter-to {
  opacity: 1;
  transform: scale(1) translateY(0);
}
.modal-fade-leave-from {
  opacity: 1;
  transform: scale(1) translateY(0);
}
.modal-fade-leave-active {
  transition: all 0.25s ease;
}
.modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(20px);
}

/* ===== 弹窗容器 ===== */
.modal {
  width: 420px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.modal-lg {
  width: 520px;
  max-height: 90vh;
}

/* 发帖弹窗 - 加宽 */
.post-modal {
  width: 680px;
  max-width: 92vw;
  max-height: 90vh;
}

/* ===== 弹窗头部 ===== */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-page);
}

.modal-header .header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-header .header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--primary);
  border-radius: var(--radius-md);
  color: #ffffff;
}

.modal-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
}

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  color: var(--text-gray);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all 0.2s;
  line-height: 1;
}

.modal-close:hover:not(:disabled) {
  background: var(--bgc-light);
  color: var(--text-body);
}

.modal-close:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ===== 弹窗主体 ===== */
.modal-body {
  padding: 24px;
  max-height: calc(90vh - 140px);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-page);
}

.footer-left .draft-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-gray);
}

/* ===== 分享确认弹窗 ===== */
.confirm-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
  color: var(--primary);
}

.confirm-text {
  text-align: center;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-title);
  margin: 0 0 6px 0;
}

.confirm-sub {
  text-align: center;
  font-size: 14px;
  color: var(--text-gray);
  margin: 0;
}

/* ===== 学伴列表 ===== */
.partner-list {
  max-height: 240px;
  overflow-y: auto;
}

.partner-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.partner-item:hover {
  background: var(--primary-light);
}

.partner-item .partner-info {
  flex: 1;
}

.partner-item .username {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-title);
}

.partner-item .user-desc {
  font-size: 12px;
  color: var(--text-gray);
}

.share-btn {
  padding: 4px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.share-btn:hover {
  background: var(--primary-hv);
}

/* ===== 表单样式 ===== */
.post-form {
  margin: 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-weight: 500;
  font-size: 14px;
  color: var(--text-title);
}

.label-text {
  font-weight: 500;
}

.label-hint {
  font-size: 12px;
  color: var(--text-gray);
  font-weight: 400;
}

.required {
  color: var(--main-delete);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  box-sizing: border-box;
  transition: all 0.2s;
  background: var(--bg-page);
  color: var(--text-body);
}

.form-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.form-input::placeholder {
  color: var(--text-gray);
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  box-sizing: border-box;
  resize: vertical;
  font-family: inherit;
  transition: all 0.2s;
  background: var(--bg-page);
  color: var(--text-body);
  min-height: 120px;
}

.form-textarea:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.form-textarea::placeholder {
  color: var(--text-gray);
}

.char-count {
  text-align: right;
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* ===== 分区选择 ===== */
.select-wrapper {
  position: relative;
}

.form-select {
  width: 100%;
  padding: 10px 14px;
  padding-right: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-page);
  color: var(--text-body);
  box-sizing: border-box;
  transition: all 0.2s;
  appearance: none;
  cursor: pointer;
}

.form-select:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.select-arrow {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-gray);
  font-size: 12px;
  pointer-events: none;
}

.zone-desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-gray);
  padding: 6px 12px;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
}

/* ===== 标签 ===== */
.tag-input-container {
  display: flex;
  gap: 8px;
}

.tag-input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.tag-prefix {
  position: absolute;
  left: 12px;
  color: var(--text-gray);
  font-weight: 600;
  font-size: 16px;
}

.tag-input-wrapper .tag-input {
  padding-left: 28px;
}

.tag-add-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
}

.tag-add-btn:hover {
  background: var(--primary-hv);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--primary-light);
  border: 1px solid var(--primary-fade);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--primary);
  animation: tagIn 0.2s ease;
}

@keyframes tagIn {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.tag-remove {
  margin-left: 2px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-gray);
  line-height: 1;
  transition: all 0.2s;
}

.tag-remove:hover {
  color: var(--main-delete);
}

.tag-empty {
  font-size: 13px;
  color: var(--text-gray);
}

/* ===== 问题列表 ===== */
.issues-group {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color);
}

.issues-list {
  background: var(--bg-page);
  border-radius: var(--radius-md);
  padding: 4px 0;
  max-height: 180px;
  overflow-y: auto;
}

.issue-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
}

.issue-item:last-child {
  border-bottom: none;
}

.issue-number {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  background: var(--primary-fade);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}

.issue-content {
  flex: 1;
  min-width: 0;
}

.issue-title {
  font-weight: 600;
  color: var(--text-title);
  font-size: 14px;
  margin-bottom: 4px;
}

.issue-reason {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 3px;
}

.issue-suggestion {
  font-size: 12px;
  color: var(--primary);
}

.issue-label {
  color: var(--text-gray);
}

/* ===== 按钮 ===== */
.btn-group {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin: 25px 0;
}

.cancel-btn {
  padding: 8px 20px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-body);
  transition: all 0.2s;
  font-weight: 500;
}

.cancel-btn:hover {
  background: var(--bg-page);
  border-color: var(--text-gray);
}

.confirm-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 24px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: #ffffff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.confirm-btn:hover:not(:disabled) {
  background: var(--primary-hv);
  box-shadow: var(--shadow-brand);
  transform: translateY(-1px);
}

.confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 加载状态 ===== */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  gap: 12px;
}

.loading-spinner {
  width: 44px;
  height: 44px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spinning 0.8s linear infinite;
}

@keyframes spinning {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-title);
}

.loading-sub {
  font-size: 13px;
  color: var(--text-gray);
}

.btn-loading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spinning 0.6s linear infinite;
}

/* ===== 共学邀请 ===== */
.invite-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
  color: var(--primary);
}

.invite-text {
  text-align: center;
  font-size: 14px;
  color: var(--text-gray);
  margin: 0 0 16px 0;
}

.invite-input-group {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.invite-input-group .form-input {
  flex: 1;
}

.add-btn {
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: #ffffff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.add-btn:hover {
  background: var(--primary-hv);
}

.invite-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.invite-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-page);
  border-radius: var(--radius-md);
}

.invite-name {
  font-weight: 500;
  color: var(--text-title);
}

.invite-status {
  font-size: 12px;
  padding: 2px 12px;
  border-radius: 12px;
  font-weight: 500;
}

.invite-status.pending {
  background: #fef3c7;
  color: #92400e;
}

.invite-status.sent {
  background: #d1fae5;
  color: #065f46;
}

/* ===== 滚动条美化 ===== */
.modal-body::-webkit-scrollbar {
  width: 4px;
}

.modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 2px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}

/* ===== 空状态 ===== */
.empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 32px 0;
}

.empty .empty-img {
  width: 120px;
  opacity: 0.6;
}

.empty .empty-text {
  font-size: 14px;
  color: var(--text-gray);
}


/* 共学邀请：下拉框 */
.select-box-compact {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  background: #f8faff;
  border-radius: 10px;
  border: 1px solid #e8ecf4;
  transition: all 0.2s;
  max-width: 280px;
  margin: 0 auto;
}

.select-box-compact:hover {
  border-color: #c7d0db;
  background: #fafbff;
}

.label-compact {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a2e;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}

.label-compact span {
  background: var(--primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.select-wrapper-compact {
  position: relative;
  flex: 1;
  min-width: 100px;
}

.select-compact {
  width: 100%;
  padding: 6px 28px 6px 10px;
  font-size: 13px;
  font-weight: 500;
  color: #1a1a2e;
  background: transparent;
  border: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  font-family: inherit;
}

.select-compact:focus {
  outline: none;
}

.select-compact option {
  font-weight: 400;
  padding: 4px 8px;
}

.arrow-compact {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 30px;
  color: #94a3b8;
  pointer-events: none;
  transition: transform 0.2s;
}

.select-compact:focus ~ .arrow-compact {
  color: var(--primary);
  transform: translateY(-50%) rotate(180deg);
}
</style>