<script setup>
import { ref, computed, onMounted, nextTick, onUnmounted, watch, inject } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showSuccessToast, showFailToast, showToast, showConfirmDialog } from 'vant'
import { saveSkip } from '@/utils/skip.js'
import MobileRadarScanner from '@/views/phone/components/MobileRadarScanner.vue'
import { getUserInfoApi } from '@/api/mainApi/index.js'
import {
  searchApi, inviteApi, partnersListApi, getInvitedApi, isAcceptApi, otherSharedRsApi,
  getSTListApi, getPostSTApi, isSTApi, getSTDialogApi, postDialogMsgApi, delSTApi,
  compareScoreApi, getMyInvitationApi, getPairDialogApi, updatePairCodeApi, submitPairCodeApi,
  createGroupApi, getMyGroupsApi, getAllGroupsApi, joinGroupApi, getGroupDetailApi,
  getGroupMessagesApi, sendGroupMessageApi, uploadGroupImageApi, leaveGroupApi, dissolveGroupApi,
  getPendingGroupInvitesApi, inviteToGroupApi, respondGroupInviteApi, getGroupCompetitionsApi,
  getCompetitionDetailApi, createCompetitionApi, generateProblemsApi, startCompetitionApi,
  endCompetitionApi, deleteCompetitionApi, submitAnswerApi, getRankingApi
} from '@/api/mainApi/partners.js'

const router = useRouter()
const route = useRoute()
let loginUser = null
const userId = ref('')

// =============================== 语音通话（inject layout 提供的） ===============================
const startVoiceCall = inject('startVoiceCall', (targetId) => {
  showToast('通话功能暂不可用')
})

// =============================== 响应式变量声明 ===============================
// 共同学习数据
const studyList = ref([])
const pendingCount = ref(0)

// 讨论相关
const currentDiscussItem = ref(null)
const discussMessages = ref([])
const discussInput = ref('')
const discussDialogVisible = ref(false)
const isSending = ref(false)
const messageListRef = ref(null)
let discussPollingTimer = null
let lastMessageCount = 0

// 结对编程相关
const pairDialogVisible = ref(false)
const pairItem = ref(null)
const pairProblem = ref(null)
const pairCodeContent = ref('')
const pairLanguage = ref('python')
const submittingPair = ref(false)
const pairSubmitResult = ref(null)
let pairPollingTimer = null
let isUpdatingFromPolling = false

// 对比成绩相关
const compareDialogVisible = ref(false)
const compareData = ref(null)

// 我的学伴搜索关键词
const partnerSearchKeyword = ref('')

// 其他变量
const isSeeRadar = ref(false)
const radarRef = ref(null)
const isScanning = ref(false)
const allPartnerList = ref([])
const myPartnerList = ref([])
const inviteList = ref([])
const invitedNum = ref(0)
const sharedList = ref([])

// 小组自定义弹窗状态
const groupDialogType = ref('') // create | invite | pending | competition | confirm
const groupDialogData = ref({})
const groupDialogLoading = ref(false)

// 小组相关
const myGroups = ref([])
const pendingGroupInvites = ref([])
const currentGroupView = ref('list') // list / detail / discover
const currentGroupId = ref(null)
const currentGroupDetail = ref(null)
const currentGroupMessages = ref([])
const currentGroupCompetitions = ref([])
const groupChatInput = ref('')
const groupImageInputRef = ref(null)
const discoverGroups = ref([])
let chatPollTimer = null
const showRankingPanel = ref(false)

// 用户信息缓存（userId -> { username, avatar }）
const userInfoMap = ref({})

// 批量获取用户信息
const fetchUserInfos = async (userIds) => {
  if (!userIds || userIds.length === 0) return
  const needFetch = [...new Set(userIds)].filter(id => id && !userInfoMap.value[id])
  if (needFetch.length === 0) return
  try {
    const res = await getUserInfoApi({ userIdList: needFetch })
    if (res.code && res.data) {
      const newMap = { ...userInfoMap.value }
      res.data.forEach(u => {
        newMap[u.userId] = { username: u.username, avatar: u.avatar }
      })
      userInfoMap.value = newMap
    }
  } catch (e) {
    console.error('获取用户信息失败:', e)
  }
}

const getUserName = (uid) => {
  if (!uid) return ''
  if (uid === userId.value) return '我'
  const info = userInfoMap.value[uid]
  return info ? info.username : uid
}

const getUserInitial = (uid) => {
  if (!uid) return '?'
  const info = userInfoMap.value[uid]
  if (info && info.username) {
    return info.username.charAt(0).toUpperCase()
  }
  return uid.slice(-2).toUpperCase()
}

const getUserAvatar = (uid) => {
  if (!uid) return ''
  const info = userInfoMap.value[uid]
  return info && info.avatar ? info.avatar : ''
}

const canInviteMember = computed(() => {
  if (!currentGroupDetail.value) return false
  const group = currentGroupDetail.value
  const isOwner = userId.value === group.creator_id
  return group.is_public || isOwner || group.role === 'admin'
})

// 导航
const navItems = [
  { label: '匹配学伴', value: 'find-partner' },
  { label: '我的学伴', value: 'my-partner' },
  { label: '邀请', value: 'invited' },
  { label: '共享', value: 'shared' },
  { label: '共学', value: 'tg-study' },
  { label: '小组', value: 'group' }
]
const currentNav = ref('find-partner')

// =============================== 弹窗滚动控制 ===============================
function lockScroll(lock) {
  document.body.style.overflow = lock ? 'hidden' : ''
  const phoneContent = document.querySelector('.phone-content')
  if (phoneContent) phoneContent.style.overflow = lock ? 'hidden' : ''
}

watch(discussDialogVisible, (val) => {
  lockScroll(val)
})

watch(pairDialogVisible, (val) => {
  lockScroll(val)
})

watch(compareDialogVisible, (val) => {
  lockScroll(val)
})

watch(groupDialogType, (val) => {
  lockScroll(!!val)
})

// =============================== 计算属性 ===============================
const filteredPartnerList = computed(() => {
  const keyword = partnerSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return myPartnerList.value
  return myPartnerList.value.filter(item => {
    const name = (item.username || '').toLowerCase()
    const id = (item.user_id || '').toLowerCase()
    return name.includes(keyword) || id.includes(keyword)
  })
})

// =============================== 用户信息获取 ===============================
const addUserInfo = async (arr, idFields = ['user_id', 'invited_by', 'inviter_id', 'invitee_id', 'sharer_id']) => {
  let list = Array.isArray(arr) ? arr : [arr]
  if (!list.length) return

  const userIdSet = new Set()
  const fields = Array.isArray(idFields) ? idFields : [idFields]

  list.forEach(item => {
    fields.forEach(field => {
      const id = item[field]
      if (id !== undefined && id !== null && id !== '') {
        userIdSet.add(String(id))
      }
    })
  })

  const userIdList = [...userIdSet]
  if (!userIdList.length) return

  try {
    const res = await getUserInfoApi({ userIdList })

    if (res.code === 1 && Array.isArray(res.data)) {
      const userMap = {}
      res.data.forEach(u => {
        if (u.userId) {
          userMap[String(u.userId)] = {
            username: u.username || '用户',
            avatar: u.avatar || ''
          }
        }
      })

      list.forEach(item => {
        fields.forEach(field => {
          const id = item[field]
          if (id !== undefined && id !== null && id !== '') {
            const userInfo = userMap[String(id)]
            if (userInfo) {
              if (field === 'user_id') {
                item.username = userInfo.username
                item.avatar = userInfo.avatar
              } else if (field === 'invited_by') {
                item.username = userInfo.username
                item.avatar = userInfo.avatar
              } else if (field === 'inviter_id') {
                item.inviter_name = userInfo.username
                item.inviter_avatar = userInfo.avatar
              } else if (field === 'invitee_id') {
                item.invitee_name = userInfo.username
                item.invitee_avatar = userInfo.avatar
              } else if (field === 'sharer_id') {
                item.sharer_name = userInfo.username
                item.sharer_avatar = userInfo.avatar
              } else {
                const nameKey = field + '_name'
                const avatarKey = field + '_avatar'
                item[nameKey] = userInfo.username
                item[avatarKey] = userInfo.avatar
              }
            } else {
              if (field === 'user_id' || field === 'invited_by') {
                if (!item.username) item.username = '用户'
                if (!item.avatar) item.avatar = ''
              } else if (field === 'sharer_id') {
                if (!item.sharer_name) item.sharer_name = String(id)
                if (!item.sharer_avatar) item.sharer_avatar = ''
              } else {
                const nameKey = field + '_name'
                if (!item[nameKey]) item[nameKey] = String(id)
              }
            }
          }
        })
      })
    } else {
      list.forEach(item => {
        fields.forEach(field => {
          const id = item[field]
          if (id !== undefined && id !== null && id !== '') {
            if (field === 'user_id' || field === 'invited_by') {
              if (!item.username) item.username = '用户'
            } else if (field === 'sharer_id') {
              if (!item.sharer_name) item.sharer_name = String(id)
            } else {
              const nameKey = field + '_name'
              if (!item[nameKey]) item[nameKey] = String(id)
            }
          }
        })
      })
    }
  } catch (e) {
    console.error('获取用户信息失败：', e)
    list.forEach(item => {
      fields.forEach(field => {
        const id = item[field]
        if (id !== undefined && id !== null && id !== '') {
          if (field === 'user_id' || field === 'invited_by') {
            if (!item.username) item.username = '用户'
          } else if (field === 'sharer_id') {
            if (!item.sharer_name) item.sharer_name = String(id)
          } else {
            const nameKey = field + '_name'
            if (!item[nameKey]) item[nameKey] = String(id)
          }
        }
      })
    })
  }
}

const addUserInfoForStudy = async (list, ...idFields) => {
  if (!list || !list.length) return
  return addUserInfo(list, idFields)
}

// =============================== 工具函数 ===============================
function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  if (isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}:${s}`
}

// ============================== 搜索学伴 ===============================
const addX = (x) => {
  for (let i = 0; i < x; i++) {
    radarRef.value?.addTarget()
  }
}
const resetRadar = () => {
  radarRef.value?.reset()
}
const setStatusText = (text) => {
  radarRef.value?.setStatus(text)
}

const searchPartner = async () => {
  allPartnerList.value = []
  isSeeRadar.value = true
  await new Promise(resolve => setTimeout(resolve, 100))
  resetRadar()
  isScanning.value = true
  setStatusText('扫描中...')
  try {
    const res = await searchApi(userId.value)
    if (res.code && !res.data?.error) {
      const rawMatches = res.data?.matches ?? []
      const filteredMatches = rawMatches.filter(
        item => item?.relationship_status !== 'accepted'
      )
      allPartnerList.value = filteredMatches
      await addUserInfo(allPartnerList.value, ['user_id'])
      addX(allPartnerList.value.length)
      setStatusText('扫描完成')
      isScanning.value = false
    } else if (res.data?.error) {
      showFailToast(res.data.error)
      isScanning.value = false
    } else {
      showFailToast('获取数据失败，请稍后重试')
      isScanning.value = false
    }
  } catch (e) {
    console.error('搜索学伴失败：', e)
    isScanning.value = false
    showFailToast('搜索失败，请重试')
  }
}

const invite = async (otherId) => {
  try {
    const res = await inviteApi({
      fromUser: userId.value,
      toUser: otherId
    })
    if (res.code) {
      showSuccessToast('邀请发送成功')
      await searchPartner()
    } else {
      showFailToast(res.msg || '邀请失败')
    }
  } catch (e) {
    console.error('邀请失败：', e)
    showFailToast('邀请失败，请重试')
  }
}

// =============================== 我的学伴 ===============================
const getMyPartnerList = async () => {
  myPartnerList.value = []
  try {
    const res = await partnersListApi(userId.value)
    if (res.code) {
      const companions = res.data?.companions ?? []
      myPartnerList.value = companions
      await addUserInfo(myPartnerList.value, ['user_id'])
    }
  } catch (e) {
    console.error('获取我的学伴列表失败：', e)
  }
}

const handleViewProfile = (item) => {
  if (item.user_id) {
    startVoiceCall(String(item.user_id))
  } else {
    showToast('无法发起语音通话')
  }
}

// =============================== 邀请 ===============================
const getNumInvited = () => {
  invitedNum.value = 0
  for (let i = 0; i < inviteList.value.length; i++) {
    if (inviteList.value[i].status === 'pending') {
      invitedNum.value++
    }
  }
}

const getInvitedList = async () => {
  inviteList.value = []
  try {
    const res = await getInvitedApi(userId.value)
    if (res.code) {
      const invites = res.data?.invites ?? []
      inviteList.value = invites
      await addUserInfo(inviteList.value, ['invited_by'])
    }
    getNumInvited()
  } catch (e) {
    console.error('获取邀请列表失败：', e)
  }
}

const isAccept = async (inviteId, accept) => {
  try {
    const res = await isAcceptApi({
      userId: userId.value,
      companionId: inviteId,
      accept: accept
    })
    if (res.code) {
      showSuccessToast(res.data.message)
      await getInvitedList()
      await getMyPartnerList()
      await fetchStudyList()
    }
  } catch (e) {
    console.error('通过/拒绝邀请失败：', e)
  }
}

// =============================== 共享 ===============================
const getSharedList = async () => {
  sharedList.value = []
  try {
    const res = await otherSharedRsApi(userId.value)
    if (res.code) {
      const shared = res.data?.shared || []
      sharedList.value = shared
      await addUserInfo(sharedList.value, ['sharer_id'])
    }
  } catch (e) {
    console.error('获取共享列表失败：', e)
  }
}

const viewRs = async (rsType, rsId) => {
  const typeMap = {
    'ppt': 0,
    'mindmap': 1,
    'doc': 2,
    'extension': 3,
    'practice': 4,
    'video': 5,
    'animation': 6,
    'question': 7
  }
  saveSkip(typeMap[rsType] || 0, rsId)
  const routeMap = {
    'ppt': '/phone/resource/ppt',
    'mindmap': '/phone/resource/mindmap',
    'doc': '/phone/resource/word',
    'extension': '/phone/resource/reading',
    'practice': '/phone/resource/code',
    'video': '/phone/resource/video',
    'animation': '/phone/resource/anima',
    'question': '/phone/resource/paper'
  }
  const path = routeMap[rsType]
  if (path) {
    router.push(path)
  } else {
    showToast('不存在该资源，无法跳转')
  }
}

// =============================== 共同学习功能 ===============================
const fetchStudyList = async () => {
  studyList.value = []
  pendingCount.value = 0

  try {
    const [pendingRes, sentRes, recordsRes] = await Promise.all([
      getPostSTApi(userId.value),
      getMyInvitationApi(userId.value),
      getSTListApi(userId.value)
    ])

    const allItems = []

    // 1. 待处理邀请（别人发给我的）
    if (pendingRes.code) {
      const invites = pendingRes.data?.invites ?? []
      await addUserInfoForStudy(invites, 'inviter_id')
      invites.forEach(item => {
        if (item.status === 'pending') {
          item._type = 'pending'
          allItems.push(item)
          pendingCount.value++
        }
      })
    }

    // 2. 已发送邀请（我发给别人的，过滤掉 accepted）
    if (sentRes.code) {
      const invites = sentRes.data?.invites ?? []
      await addUserInfoForStudy(invites, 'invitee_id')
      invites.forEach(item => {
        if (item.status !== 'accepted') {
          item._type = 'sent'
          allItems.push(item)
        }
      })
    }

    // 3. 已建立的共学记录
    if (recordsRes.code) {
      const sessions = recordsRes.data?.sessions ?? []
      await addUserInfoForStudy(sessions, 'inviter_id', 'invitee_id')
      sessions.forEach(item => {
        item._type = 'record'
        allItems.push(item)
      })
    }

    allItems.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    studyList.value = allItems

  } catch (e) {
    console.error('获取共学列表失败：', e)
  }
}

const handleAccept = async (inviteId, accept) => {
  try {
    const res = await isSTApi({ inviteId, accept })
    if (res.code) {
      showSuccessToast(res.data?.message || (accept ? '已接受' : '已拒绝'))
      await fetchStudyList()
      await getInvitedList()
      await getMyPartnerList()
    }
  } catch (e) {
    console.error('操作失败：', e)
    showFailToast('操作失败，请重试')
  }
}

const handleDelete = async (inviteId) => {
  try {
    await showConfirmDialog({
      title: '提示',
      message: '确定要删除此记录吗？'
    })
    const res = await delSTApi({ invitationId: inviteId, userId: userId.value })
    if (res.code) {
      showSuccessToast(res.data?.message || '删除成功')
      await fetchStudyList()
    }
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      console.error('删除失败：', e)
      showFailToast('删除失败，请重试')
    }
  }
}

// =============================== 讨论功能 ===============================
const handleDiscuss = async (item) => {
  currentDiscussItem.value = item
  discussMessages.value = []
  discussInput.value = ''
  lastMessageCount = 0
  discussDialogVisible.value = true
  await fetchDiscussMessages(item.id)
  startDiscussPolling(item.id)
}

const closeDiscussDialog = () => {
  stopDiscussPolling()
  discussDialogVisible.value = false
  currentDiscussItem.value = null
  discussMessages.value = []
  lastMessageCount = 0
}

const fetchDiscussMessages = async (invitationId) => {
  try {
    const res = await getSTDialogApi(invitationId)
    if (res.code) {
      let messages = res.data?.messages ?? []
      if (messages.length > lastMessageCount || messages.length < lastMessageCount) {
        const senderIds = [...new Set(messages.map(m => m.sender_id).filter(Boolean))]
        if (senderIds.length > 0) {
          try {
            const userRes = await getUserInfoApi({ userIdList: senderIds })
            if (userRes.code === 1 && Array.isArray(userRes.data)) {
              const userMap = {}
              userRes.data.forEach(u => {
                if (u.userId) {
                  userMap[String(u.userId)] = {
                    username: u.username || '用户',
                    avatar: u.avatar || ''
                  }
                }
              })
              messages.forEach(msg => {
                if (msg.sender_id && userMap[String(msg.sender_id)]) {
                  msg.sender_name = userMap[String(msg.sender_id)].username
                  msg.sender_avatar = userMap[String(msg.sender_id)].avatar
                }
              })
            }
          } catch (e) {
            console.error('获取消息发送者信息失败：', e)
          }
        }
        messages.forEach(msg => {
          if (msg.sender_id === userId.value) {
            msg.sender_name = '我'
            msg.sender_avatar = loginUser?.avatar || ''
          } else {
            msg.sender_name = msg.sender_name || msg.sender_id || '用户'
            msg.sender_avatar = msg.sender_avatar || ''
          }
        })
        discussMessages.value = messages
        lastMessageCount = messages.length
        await nextTick()
        if (messageListRef.value) {
          messageListRef.value.scrollTop = messageListRef.value.scrollHeight
        }
      }
    }
  } catch (e) {
    console.error('获取消息失败：', e)
  }
}

const startDiscussPolling = (invitationId) => {
  if (discussPollingTimer) clearInterval(discussPollingTimer)
  discussPollingTimer = setInterval(() => {
    fetchDiscussMessages(invitationId)
  }, 2000)
}

const stopDiscussPolling = () => {
  if (discussPollingTimer) {
    clearInterval(discussPollingTimer)
    discussPollingTimer = null
  }
}

const sendDiscussMessage = async () => {
  const content = discussInput.value.trim()
  if (!content) return
  if (isSending.value) return
  isSending.value = true
  try {
    const res = await postDialogMsgApi({
      invitationId: currentDiscussItem.value.id,
      senderId: userId.value,
      content
    })
    if (res.code) {
      discussInput.value = ''
      await fetchDiscussMessages(currentDiscussItem.value.id)
    }
  } catch (e) {
    console.error('发送消息失败：', e)
    showFailToast('发送失败，请重试')
  } finally {
    isSending.value = false
  }
}

// =============================== 结对编程功能 ===============================
const handlePairProgramming = async (item) => {
  pairItem.value = item
  pairCodeContent.value = ''
  pairSubmitResult.value = null
  pairDialogVisible.value = true

  try {
    const res = await getPairDialogApi(item.id)
    if (res.code) {
      const session = res.data?.session
      if (session) {
        pairProblem.value = session.problem_data
        pairCodeContent.value = session.code_content || ''
        pairLanguage.value = session.language || 'python'
        startPairPolling(item.id)
      }
    }
  } catch (e) {
    console.error('获取结对编程会话失败：', e)
    showFailToast('获取会话数据失败')
  }
}

const startPairPolling = (invitationId) => {
  if (pairPollingTimer) clearInterval(pairPollingTimer)
  pairPollingTimer = setInterval(async () => {
    try {
      const res = await getPairDialogApi(invitationId)
      if (res.code) {
        const session = res.data?.session
        if (session) {
          if (session.code_content !== pairCodeContent.value) {
            isUpdatingFromPolling = true
            pairCodeContent.value = session.code_content || ''
            if (session.language && session.language !== pairLanguage.value) {
              pairLanguage.value = session.language
            }
            isUpdatingFromPolling = false
          }
        }
      }
    } catch (e) {
      console.error('轮询获取代码失败：', e)
    }
  }, 3000)
}

const stopPairPolling = () => {
  if (pairPollingTimer) {
    clearInterval(pairPollingTimer)
    pairPollingTimer = null
  }
}

const onCodeChange = (event) => {
  const val = event.target?.value || ''
  if (isUpdatingFromPolling) return
  if (!pairItem.value) return

  pairCodeContent.value = val

  updatePairCodeApi({
    invitationId: pairItem.value.id,
    userId: userId.value,
    codeContent: val,
    language: pairLanguage.value
  }).catch(e => {
    console.error('更新代码失败：', e)
  })
}

const onLanguageChange = async () => {
  if (!pairItem.value) return
  try {
    await updatePairCodeApi({
      invitationId: pairItem.value.id,
      userId: userId.value,
      codeContent: pairCodeContent.value || '',
      language: pairLanguage.value
    })
  } catch (e) {
    console.error('更新语言失败：', e)
  }
}

const submitPairCode = async () => {
  if (!pairItem.value) return
  if (!pairCodeContent.value.trim()) {
    showToast('请先编写代码')
    return
  }

  submittingPair.value = true

  try {
    const res = await submitPairCodeApi({
      invitationId: pairItem.value.id,
      submitterId: userId.value,
      language: pairLanguage.value
    })

    if (res.code) {
      const data = res.data

      if (data?.success === false && data?.error === '已提交过') {
        showToast('您已提交过代码，不能重复提交')
        submittingPair.value = false
        return
      }

      const result = data?.result
      if (result) {
        pairSubmitResult.value = result
        showSuccessToast('代码提交成功')
      } else {
        showSuccessToast(data?.message || '代码提交成功')
        try {
          const refreshRes = await getPairDialogApi(pairItem.value.id)
          if (refreshRes.code) {
            const session = refreshRes.data?.session
            if (session?.submit_result) {
              pairSubmitResult.value = session.submit_result
            }
          }
        } catch (e) {
          console.error('获取提交结果失败：', e)
        }
      }
    } else {
      showFailToast(res.msg || '提交失败，请重试')
    }
  } catch (e) {
    console.error('提交代码失败：', e)
    const errorMsg = e?.response?.data?.data?.error || e?.message || ''
    if (errorMsg.includes('已提交过')) {
      showToast('您已提交过代码，不能重复提交')
    } else {
      showFailToast('提交失败，请重试')
    }
  } finally {
    submittingPair.value = false
  }
}

const closePairDialog = () => {
  stopPairPolling()
  pairDialogVisible.value = false
  pairItem.value = null
  pairProblem.value = null
  pairSubmitResult.value = null
  pairCodeContent.value = ''
}

const getDifficultyClass = (difficulty) => {
  const map = {
    '简单': 'diff-easy',
    '中等': 'diff-medium',
    '困难': 'diff-hard'
  }
  return map[difficulty] || 'diff-easy'
}

// =============================== 对比成绩功能 ===============================
const handleCompareScore = async (item) => {
  try {
    const res = await compareScoreApi(item.resource_id, item.inviter_id, item.invitee_id)
    if (res.code) {
      const data = res.data

      const userIds = []
      if (data.user_a) userIds.push(data.user_a)
      if (data.user_b) userIds.push(data.user_b)

      if (userIds.length > 0) {
        try {
          const userRes = await getUserInfoApi({ userIdList: userIds })
          if (userRes.code === 1 && Array.isArray(userRes.data)) {
            const userMap = {}
            userRes.data.forEach(u => {
              if (u.userId) {
                userMap[u.userId] = {
                  username: u.username || '用户',
                  avatar: u.avatar || ''
                }
              }
            })

            if (data.user_a && userMap[data.user_a]) {
              data.user_a_name = userMap[data.user_a].username
              data.user_a_avatar = userMap[data.user_a].avatar
            } else {
              data.user_a_name = data.user_a || '用户A'
              data.user_a_avatar = ''
            }

            if (data.user_b && userMap[data.user_b]) {
              data.user_b_name = userMap[data.user_b].username
              data.user_b_avatar = userMap[data.user_b].avatar
            } else {
              data.user_b_name = data.user_b || '用户B'
              data.user_b_avatar = ''
            }
          }
        } catch (e) {
          console.error('获取对比用户信息失败：', e)
          data.user_a_name = data.user_a || '用户A'
          data.user_a_avatar = ''
          data.user_b_name = data.user_b || '用户B'
          data.user_b_avatar = ''
        }
      }

      compareData.value = data
      compareDialogVisible.value = true
    }
  } catch (e) {
    console.error('对比成绩失败：', e)
    showFailToast('获取对比数据失败')
  }
}

const closeCompareDialog = () => {
  compareDialogVisible.value = false
  compareData.value = null
}

const getWinnerClass = (userKey) => {
  if (!compareData.value) return ''
  const winner = compareData.value.winner
  if (winner === '平局') return 'tie'
  if (winner === userKey) return 'winner'
  return 'loser'
}

const getWinnerLabel = (userKey) => {
  if (!compareData.value) return ''
  const winner = compareData.value.winner
  if (winner === '平局') return '平局'
  if (winner === userKey) return '获胜'
  return '失败'
}

const getScoreClass = (score) => {
  if (score === undefined || score === null) return ''
  if (score >= 80) return 'score-high'
  if (score >= 60) return 'score-medium'
  if (score > 0) return 'score-low'
  return 'score-zero'
}

const getVerdictClass = (verdict) => {
  const map = {
    'Accepted': 'verdict-pass',
    'Wrong Answer': 'verdict-fail',
    'Compilation Error': 'verdict-error',
    'Runtime Error': 'verdict-error',
    'Time Limit Exceeded': 'verdict-error',
    '未作答': 'verdict-empty'
  }
  return map[verdict] || 'verdict-empty'
}

const getResultBannerClass = () => {
  if (!compareData.value) return ''
  const winner = compareData.value.winner
  if (winner === '平局') return 'banner-tie'
  return 'banner-win'
}

const getResultText = () => {
  if (!compareData.value) return ''
  const winner = compareData.value.winner
  if (winner === '平局') return '势均力敌，平局！'
  const winnerName = winner === compareData.value.user_a
    ? compareData.value.user_a_name
    : compareData.value.user_b_name
  return `${winnerName || winner} 获胜！`
}

// =============================== 其他操作 ===============================
const handleView = (item) => {
  viewRs(item.resource_type, item.resource_id)
}

const handleGoAnswer = (item) => {
  viewRs(item.resource_type, item.resource_id)
}

// =============================== markdown渲染 ===============================
const markdownToHtml = (content) => {
  if (!content) return ''
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  html = html.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="md-link">$1</a>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1 class="md-h1">$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/((?:<li class="md-li">.*?<\/li>\n?)+)/g, '<ul class="md-ul">$1</ul>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote class="md-blockquote">$1</blockquote>')

  const lines = html.split('\n')
  const out = []
  for (const line of lines) {
    const t = line.trim()
    if (!t) {
      out.push('<br>')
      continue
    }
    if (/^<(h[1-3]|ul|\/ul|li|blockquote|\/blockquote|code|a|span)/.test(t)) {
      out.push(t)
    } else {
      out.push('<p class="md-p">' + t + '</p>')
    }
  }
  html = out.join('')
  html = html.replace(/<p class="md-p"><ul/g, '<ul')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p class="md-p"><li/g, '<li')
  html = html.replace(/<\/li><\/p>/g, '</li>')

  return html
}

// =============================== 资源类型相关 ===============================
const getResourceTypeLabel = (type) => {
  const map = {
    'doc': '讲解文档',
    'document': '讲解文档',
    'practice': '编程题',
    'mindmap': '思维导图',
    'extension': '拓展阅读',
    'video': '视频',
    'animation': '动画',
    'ppt': 'PPT',
    'question': '试卷'
  }
  return map[type] || type || '未知'
}

const getResourceIconClass = (type) => {
  const map = {
    'doc': 'icon-doc',
    'practice': 'icon-practice',
    'mindmap': 'icon-mindmap',
    'extension': 'icon-extension',
    'video': 'icon-video',
    'animation': 'icon-animation',
    'ppt': 'icon-ppt',
    'question': 'icon-question'
  }
  return map[type] || 'icon-default'
}

const getResourceIconEmoji = (type) => {
  const map = {
    'doc': '📄',
    'practice': '✏️',
    'mindmap': '🔗',
    'extension': '📖',
    'video': '🎬',
    'animation': '🖼️',
    'ppt': '📊',
    'question': '📋'
  }
  return map[type] || '📄'
}

const getStatusLabel = (status) => {
  const map = {
    'pending': '待处理',
    'accepted': '已接受',
    'rejected': '已拒绝'
  }
  return map[status] || status || '未知'
}

// =============================== 小组相关方法 ===============================
const createGroupNameRef = ref(null)
const inviteUserIdRef = ref(null)
let _confirmCallback = null

const closeGroupDialog = () => {
  groupDialogType.value = ''
  groupDialogData.value = {}
  groupDialogLoading.value = false
  _confirmCallback = null
}

const showCreateGroupDialog = () => {
  groupDialogData.value = { name: '', description: '', is_public: true }
  groupDialogType.value = 'create'
  nextTick(() => createGroupNameRef.value?.focus())
}

const doCreateGroup = async () => {
  const name = groupDialogData.value.name?.trim()
  if (!name) { showToast('请输入小组名称'); return }
  groupDialogLoading.value = true
  try {
    const res = await createGroupApi({
      name,
      creator_id: userId.value,
      description: groupDialogData.value.description?.trim() || '',
      is_public: groupDialogData.value.is_public
    })
    if (res.success) {
      showSuccessToast('小组创建成功！')
      closeGroupDialog()
      loadMyGroups()
    } else {
      showFailToast(res.error || '创建失败')
    }
  } catch (e) {
    showFailToast('创建失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const loadMyGroups = async () => {
  currentGroupView.value = 'list'
  try {
    const pendingRes = await getPendingGroupInvitesApi(userId.value)
    if (pendingRes.success) {
      pendingGroupInvites.value = pendingRes.invites || []
    }
    const res = await getMyGroupsApi(userId.value)
    if (res.success) {
      myGroups.value = res.groups || []
    } else {
      showFailToast(res.detail || '获取小组列表失败')
    }
    const inviterIds = (pendingGroupInvites.value || []).map(inv => inv.inviter_id)
    if (inviterIds.length > 0) {
      await fetchUserInfos(inviterIds)
    }
  } catch (e) {
    showFailToast('获取小组列表失败: ' + e.message)
  }
}

const showDiscoverGroups = async () => {
  currentGroupView.value = 'discover'
  try {
    const res = await getAllGroupsApi()
    if (res.success) {
      discoverGroups.value = res.groups || []
      const creatorIds = (res.groups || []).map(g => g.creator_id)
      if (creatorIds.length > 0) {
        await fetchUserInfos(creatorIds)
      }
    } else {
      showFailToast(res.detail || '获取小组列表失败')
    }
  } catch (e) {
    showFailToast('获取小组列表失败: ' + e.message)
  }
}

const quickJoinGroup = async (groupId, groupName) => {
  try {
    const res = await joinGroupApi({ group_id: groupId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('已加入 ' + groupName)
      loadMyGroups()
    } else {
      showFailToast(res.error || '加入失败')
    }
  } catch (e) {
    showFailToast('加入失败: ' + e.message)
  }
}

const openGroupDetail = async (groupId) => {
  currentGroupView.value = 'detail'
  currentGroupId.value = groupId
  try {
    const [detailRes, msgRes] = await Promise.all([
      getGroupDetailApi(groupId),
      getGroupMessagesApi(groupId, 50)
    ])
    if (!detailRes.success) throw new Error(detailRes.detail)
    currentGroupDetail.value = detailRes.group
    currentGroupMessages.value = msgRes.success ? (msgRes.messages || []) : []
    const uIds = []
    if (detailRes.group?.members) {
      detailRes.group.members.forEach(m => uIds.push(m.user_id))
    }
    if (msgRes.messages) {
      msgRes.messages.forEach(m => uIds.push(m.sender_id))
    }
    await fetchUserInfos(uIds)
    try {
      const compRes = await getGroupCompetitionsApi(groupId)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } catch (e) {}
    startGroupChatPolling(groupId)
  } catch (e) {
    showFailToast('获取小组详情失败: ' + e.message)
  }
}

const backToGroupList = () => {
  if (chatPollTimer) clearInterval(chatPollTimer)
  currentGroupView.value = 'list'
  currentGroupDetail.value = null
  currentGroupId.value = null
  currentGroupMessages.value = []
  currentGroupCompetitions.value = []
}

const startGroupChatPolling = (groupId) => {
  if (chatPollTimer) clearInterval(chatPollTimer)
  chatPollTimer = setInterval(() => refreshGroupChat(groupId), 3000)
}

const refreshGroupChat = async (groupId) => {
  try {
    const res = await getGroupMessagesApi(groupId, 50)
    if (res.success) {
      currentGroupMessages.value = res.messages || []
      if (res.messages) {
        const uIds = res.messages.map(m => m.sender_id)
        await fetchUserInfos(uIds)
      }
    }
  } catch (e) {}
}

const sendGroupMessage = async () => {
  if (!groupChatInput.value.trim() || !currentGroupId.value) return
  const content = groupChatInput.value.trim()
  groupChatInput.value = ''
  try {
    await sendGroupMessageApi({
      group_id: currentGroupId.value,
      sender_id: userId.value,
      content,
      msg_type: 'text'
    })
    refreshGroupChat(currentGroupId.value)
  } catch (e) {
    showFailToast('发送失败')
  }
}

const uploadGroupImage = async (event) => {
  const file = event.target.files[0]
  if (!file || !currentGroupId.value) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('sender_id', userId.value)
  formData.append('group_id', currentGroupId.value)
  try {
    const res = await uploadGroupImageApi(formData)
    if (res.success) {
      refreshGroupChat(currentGroupId.value)
    } else {
      showFailToast(res.error || '上传失败')
    }
  } catch (e) {
    showFailToast('上传失败: ' + e.message)
  }
  event.target.value = ''
}

const leaveGroupWithConfirm = (groupId) => {
  groupDialogData.value = {
    title: '退出小组',
    message: '确定退出这个小组？',
    confirmText: '确定退出',
    action: () => doLeaveGroup(groupId)
  }
  groupDialogType.value = 'confirm'
}

const doLeaveGroup = async (groupId) => {
  groupDialogLoading.value = true
  try {
    const res = await leaveGroupApi({ group_id: groupId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('已退出')
      closeGroupDialog()
      backToGroupList()
      loadMyGroups()
    } else {
      showFailToast(res.error || '退出失败')
    }
  } catch (e) {
    showFailToast('退出失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const dissolveGroup = async (groupId) => {
  groupDialogData.value = {
    title: '解散小组',
    message: '确定解散这个小组？此操作不可恢复并会删除所有数据和比赛！',
    confirmText: '确定解散',
    action: () => doDissolveGroup(groupId)
  }
  groupDialogType.value = 'confirm'
}

const doDissolveGroup = async (groupId) => {
  groupDialogLoading.value = true
  try {
    const res = await dissolveGroupApi({ group_id: groupId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('小组已解散')
      closeGroupDialog()
      backToGroupList()
      loadMyGroups()
    } else {
      showFailToast(res.error || '解散失败')
    }
  } catch (e) {
    showFailToast('解散失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const showInviteMemberDialog = () => {
  groupDialogData.value = { invitee_id: '' }
  groupDialogType.value = 'invite'
  nextTick(() => inviteUserIdRef.value?.focus())
}

const doInviteToGroup = async () => {
  const inviteeId = groupDialogData.value.invitee_id?.trim()
  if (!inviteeId) { showToast('请输入用户ID'); return }
  groupDialogLoading.value = true
  try {
    const res = await inviteToGroupApi({
      group_id: currentGroupId.value,
      inviter_id: userId.value,
      invitee_id: inviteeId
    })
    if (res.success) {
      showSuccessToast('邀请已发送')
      closeGroupDialog()
    } else {
      showFailToast(res.error || '邀请失败')
    }
  } catch (e) {
    showFailToast('邀请失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const showPendingInvitesDialog = () => {
  groupDialogType.value = 'pending'
}

const respondGroupInvite = async (invitationId, accept) => {
  try {
    const res = await respondGroupInviteApi({
      invitation_id: invitationId,
      invitee_id: userId.value,
      accept
    })
    if (res.success) {
      showSuccessToast(accept ? '已加入小组' : '已拒绝')
      const pendingRes = await getPendingGroupInvitesApi(userId.value)
      if (pendingRes.success) {
        pendingGroupInvites.value = pendingRes.invites || []
      }
      closeGroupDialog()
      loadMyGroups()
    } else {
      showFailToast(res.error || '操作失败')
    }
  } catch (e) {
    showFailToast('操作失败: ' + e.message)
  }
}

const showCreateCompetitionDialog = () => {
  const defaultStart = new Date(Date.now() + 5 * 60000).toISOString().slice(0, 16)
  const defaultEnd = new Date(Date.now() + 2 * 3600000).toISOString().slice(0, 16)
  groupDialogData.value = {
    title: '',
    description: '',
    topic: '编程算法',
    problem_count: 3,
    start_at: defaultStart,
    end_at: defaultEnd
  }
  groupDialogType.value = 'competition'
}

const doCreateCompetition = async () => {
  const title = groupDialogData.value.title?.trim()
  if (!title) { showToast('请输入比赛名称'); return }
  const problemCount = parseInt(groupDialogData.value.problem_count)
  if (!problemCount || problemCount < 1) { showToast('题目数量必须是一个大于 0 的整数'); return }
  groupDialogLoading.value = true
  try {
    const res = await createCompetitionApi({
      group_id: currentGroupId.value,
      created_by: userId.value,
      title,
      description: groupDialogData.value.description?.trim() || '',
      topic: groupDialogData.value.topic?.trim() || '编程算法',
      problem_count: problemCount,
      start_at: groupDialogData.value.start_at ? new Date(groupDialogData.value.start_at).toISOString() : null,
      end_at: groupDialogData.value.end_at ? new Date(groupDialogData.value.end_at).toISOString() : null
    })
    if (!res.success) {
      showFailToast(res.error || '创建失败')
      return
    }
    const compId = res.competition_id

    showToast('比赛创建成功，正在生成赛题...')
    const topic = groupDialogData.value.topic?.trim() || '编程算法'
    const genRes = await generateProblemsApi({
      competition_id: compId,
      user_id: userId.value,
      input_text: topic,
      problem_count: problemCount
    })
    if (genRes.success) {
      showSuccessToast(`已生成 ${genRes.count || problemCount} 道赛题！`)
      closeGroupDialog()
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      showToast('比赛创建成功，但赛题生成失败: ' + (genRes.error || ''))
    }
  } catch (e) {
    showFailToast('创建失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const openCompetition = async (compId) => {
  try {
    const res = await getCompetitionDetailApi(compId)
    if (!res.success || !res.competition) {
      showFailToast('比赛不存在')
      return
    }
    openCompetitionArena(res.competition)
  } catch (e) {
    showFailToast('加载比赛失败: ' + e.message)
  }
}

// =============================== 全屏竞技场（移动端单列 DOM 覆盖层） ===============================
let arenaOverlay = null
let arenaData = null
let arenaCurrentIdx = 0
let arenaProblemStatus = {}
let arenaRankTimer = null
let arenaTimerInterval = null
let arenaShowRanking = false

const openCompetitionArena = async (comp) => {
  arenaData = comp
  arenaCurrentIdx = 0
  arenaProblemStatus = {}
  arenaShowRanking = false

  arenaOverlay = document.createElement('div')
  arenaOverlay.id = 'arenaOverlay'
  arenaOverlay.style.cssText = 'position:fixed;inset:0;z-index:10000;background:#0f172a;display:flex;flex-direction:column;overflow:hidden;'

  arenaOverlay.innerHTML = `
    <!-- 顶栏 -->
    <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#1e293b;border-bottom:1px solid #334155;flex-shrink:0;">
      <div style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;">
        <button id="arenaCloseBtn" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:18px;padding:4px;">✕</button>
        <span style="color:#e2e8f0;font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">⭐ ${comp.title}</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
        <span id="arenaTimer" style="color:#22c55e;font-size:12px;font-weight:600;font-family:monospace;"></span>
        <span id="arenaSolvedCount" style="color:#94a3b8;font-size:11px;">0/${comp.problems?.length || 0}</span>
        <button id="arenaRankBtn" style="background:#334155;color:#e2e8f0;border:none;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:11px;">🏆 榜</button>
      </div>
    </div>
    <!-- 题目导航（横向滚动） -->
    <div id="arenaNav" style="display:flex;gap:6px;overflow-x:auto;background:#1e293b;padding:8px 10px;border-bottom:1px solid #334155;flex-shrink:0;-webkit-overflow-scrolling:touch;"></div>
    <!-- 主体（题目 + 编辑器） -->
    <div id="arenaMain" style="flex:1;overflow-y:auto;display:flex;flex-direction:column;-webkit-overflow-scrolling:touch;">
      <div id="arenaProblemArea" style="padding:12px;flex-shrink:0;"></div>
      <!-- 判分结果 -->
      <div id="arenaJudgeResult" style="display:none;padding:10px 12px;flex-shrink:0;"></div>
      <!-- 编辑器区 -->
      <div style="border-top:1px solid #334155;background:#1e293b;padding:10px 12px;flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <select id="arenaLang" style="padding:5px 8px;border:1px solid #334155;border-radius:6px;background:#0f172a;color:#e2e8f0;font-size:12px;cursor:pointer;">
            <option value="python">Python</option>
            <option value="cpp">C++</option>
            <option value="java">Java</option>
            <option value="javascript">JavaScript</option>
            <option value="c">C</option>
          </select>
          <div style="flex:1;"></div>
          <button id="arenaPrevBtn" style="padding:5px 10px;background:#334155;color:#e2e8f0;border:none;border-radius:6px;cursor:pointer;font-size:12px;">‹</button>
          <button id="arenaSubmitBtn" style="padding:5px 14px;background:#22c55e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;">提交</button>
          <button id="arenaNextBtn" style="padding:5px 10px;background:#334155;color:#e2e8f0;border:none;border-radius:6px;cursor:pointer;font-size:12px;">›</button>
        </div>
        <textarea id="arenaCodeEditor" placeholder="# 在此编写代码..." style="width:100%;height:160px;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:10px;font-family:monospace;font-size:12px;resize:none;box-sizing:border-box;"></textarea>
      </div>
    </div>
    <!-- 排行榜面板（覆盖层） -->
    <div id="arenaRanking" style="position:absolute;top:0;right:0;bottom:0;width:80%;max-width:300px;background:#1e293b;border-left:1px solid #334155;overflow-y:auto;padding:12px;transform:translateX(100%);transition:transform 0.25s ease;z-index:10;display:none;-webkit-overflow-scrolling:touch;"></div>
    <div id="arenaRankMask" style="position:absolute;inset:0;background:rgba(0,0,0,0.4);z-index:9;display:none;"></div>
  `

  document.body.appendChild(arenaOverlay)
  document.body.style.overflow = 'hidden'

  document.getElementById('arenaCloseBtn').onclick = closeCompetitionArena
  document.getElementById('arenaPrevBtn').onclick = arenaPrevProblem
  document.getElementById('arenaNextBtn').onclick = arenaNextProblem
  document.getElementById('arenaSubmitBtn').onclick = arenaSubmit
  document.getElementById('arenaRankBtn').onclick = toggleArenaRanking
  document.getElementById('arenaRankMask').onclick = toggleArenaRanking

  renderArenaNav()
  arenaShowProblem(0)
  if (comp.status === 'running' || comp.status === 'finished') {
    arenaLoadRanking()
    if (comp.status === 'running') {
      arenaRankTimer = setInterval(arenaLoadRanking, 5000)
      arenaStartTimer()
    }
  }
}

const toggleArenaRanking = () => {
  arenaShowRanking = !arenaShowRanking
  const panel = document.getElementById('arenaRanking')
  const mask = document.getElementById('arenaRankMask')
  if (!panel || !mask) return
  if (arenaShowRanking) {
    panel.style.display = 'block'
    mask.style.display = 'block'
    setTimeout(() => { panel.style.transform = 'translateX(0)' }, 10)
    arenaLoadRanking()
  } else {
    panel.style.transform = 'translateX(100%)'
    mask.style.display = 'none'
  }
}

const closeCompetitionArena = () => {
  if (arenaRankTimer) clearInterval(arenaRankTimer)
  if (arenaTimerInterval) clearInterval(arenaTimerInterval)
  arenaRankTimer = null
  arenaTimerInterval = null
  if (arenaOverlay) {
    arenaOverlay.remove()
    arenaOverlay = null
  }
  document.body.style.overflow = ''
  arenaData = null
  arenaShowRanking = false
}

const renderArenaNav = () => {
  const nav = document.getElementById('arenaNav')
  if (!nav || !arenaData) return
  const problems = arenaData.problems || []
  let html = ''
  problems.forEach((p, idx) => {
    const status = arenaProblemStatus[p.id]
    let icon = '○', color = '#64748b'
    if (status === 'accepted') { icon = '●'; color = '#22c55e' }
    else if (status === 'wrong') { icon = '●'; color = '#ef4444' }
    else if (status === 'partial') { icon = '●'; color = '#f59e0b' }
    const isActive = idx === arenaCurrentIdx
    html += `<div onclick="window.__arenaShowProblem(${idx})" style="flex-shrink:0;padding:6px 12px;border-radius:8px;cursor:pointer;background:${isActive ? '#334155' : '#0f172a'};border:1px solid ${isActive ? '#6366f1' : '#334155'};display:flex;align-items:center;gap:4px;">
      <span style="color:${color};font-size:14px;">${icon}</span>
      <span style="color:#e2e8f0;font-size:12px;font-weight:${isActive ? '600' : '400'};">${getLetter(idx)}</span>
    </div>`
  })
  nav.innerHTML = html
}

window.__arenaShowProblem = (idx) => {
  arenaShowProblem(idx)
}

const arenaShowProblem = (idx) => {
  if (!arenaData) return
  const problems = arenaData.problems || []
  if (idx < 0 || idx >= problems.length) return
  arenaCurrentIdx = idx
  const p = problems[idx]
  const diffColor = p.difficulty === '简单' ? '#22c55e' : p.difficulty === '困难' ? '#ef4444' : '#f59e0b'

  const area = document.getElementById('arenaProblemArea')
  area.innerHTML = `
    <div style="background:#1e293b;border-radius:10px;padding:14px;border:1px solid #334155;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:10px;">
        <div style="font-size:15px;font-weight:700;color:#e2e8f0;flex:1;">${getLetter(idx)}. ${p.title}</div>
        <span style="font-size:11px;color:${diffColor};background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:4px;white-space:nowrap;flex-shrink:0;">${p.difficulty} · ${p.score}分</span>
      </div>
      <div style="font-size:13px;color:#cbd5e1;line-height:1.7;white-space:pre-wrap;">${p.description}</div>
    </div>
  `

  const editor = document.getElementById('arenaCodeEditor')
  const savedCode = localStorage.getItem('arena_code_' + arenaData.id + '_' + p.id) || ''
  if (editor) {
    editor.value = savedCode
  }

  renderArenaNav()
  updateSolvedCount()
  // 滚动到顶部
  const main = document.getElementById('arenaMain')
  if (main) main.scrollTop = 0
}

const arenaNextProblem = () => {
  const problems = arenaData ? (arenaData.problems || []) : []
  if (arenaCurrentIdx < problems.length - 1) arenaShowProblem(arenaCurrentIdx + 1)
}

const arenaPrevProblem = () => {
  if (arenaCurrentIdx > 0) arenaShowProblem(arenaCurrentIdx - 1)
}

const arenaSubmit = async () => {
  if (!arenaData) return
  const problems = arenaData.problems || []
  const p = problems[arenaCurrentIdx]
  if (!p) return
  const editor = document.getElementById('arenaCodeEditor')
  if (!editor) return
  const code = editor.value.trim()
  if (!code) {
    showToast('请先编写代码')
    return
  }

  localStorage.setItem('arena_code_' + arenaData.id + '_' + p.id, code)

  const resultDiv = document.getElementById('arenaJudgeResult')
  resultDiv.style.display = 'block'
  resultDiv.innerHTML = '<div style="color:#94a3b8;font-size:12px;">⏳ 评判中...</div>'

  try {
    const res = await submitAnswerApi({
      competition_id: arenaData.id,
      problem_id: p.id,
      user_id: userId.value,
      answer_text: code
    })
    if (res.success) {
      const statusText = res.status === 'accepted' ? 'Accepted' : res.status === 'partial' ? 'Partial' : 'Wrong Answer'
      const passText = `通过: ${res.passed}/${res.total}`
      arenaProblemStatus[p.id] = res.status
      resultDiv.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <div style="min-width:0;flex:1;"><span style="font-size:14px;font-weight:700;color:${res.status === 'accepted' ? '#22c55e' : res.status === 'partial' ? '#f59e0b' : '#ef4444'};">${statusText}</span>
        <span style="color:#94a3b8;font-size:11px;margin-left:8px;">得分: ${res.score} · ${passText}</span></div>
        <button onclick="document.getElementById('arenaJudgeResult').style.display='none'" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:12px;flex-shrink:0;">✕</button>
      </div>`
      renderArenaNav()
      updateSolvedCount()
      arenaLoadRanking()
    } else {
      resultDiv.innerHTML = `<div style="color:#ef4444;font-size:12px;">${res.error || '提交失败'}</div>`
    }
  } catch (e) {
    resultDiv.innerHTML = `<div style="color:#ef4444;font-size:12px;">提交失败: ${e.message}</div>`
  }
}

const updateSolvedCount = () => {
  const solved = Object.values(arenaProblemStatus).filter(s => s === 'accepted').length
  const total = (arenaData && arenaData.problems) ? arenaData.problems.length : 0
  const el = document.getElementById('arenaSolvedCount')
  if (el) el.textContent = `${solved}/${total}`
}

const arenaStartTimer = () => {
  if (!arenaData || !arenaData.end_at) return
  const endTime = new Date(arenaData.end_at).getTime()
  arenaTimerInterval = setInterval(() => {
    const now = Date.now()
    const diff = Math.max(0, endTime - now)
    const el = document.getElementById('arenaTimer')
    if (!el) {
      clearInterval(arenaTimerInterval)
      return
    }
    if (diff <= 0) {
      el.textContent = '⏱ 已结束'
      el.style.color = '#ef4444'
      clearInterval(arenaTimerInterval)
    } else {
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      el.textContent = `⏱ ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    }
  }, 1000)
}

const arenaLoadRanking = async () => {
  const container = document.getElementById('arenaRanking')
  if (!container || !arenaData) return
  try {
    const res = await getRankingApi(arenaData.id)
    if (res.success) {
      const ranking = res.ranking || []
      const uIds = ranking.map(r => r.user_id)
      await fetchUserInfos(uIds)
      let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><div style="font-size:13px;font-weight:600;color:#94a3b8;">实时排行</div><button onclick="window.__arenaToggleRank()" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;">✕</button></div>'
      if (ranking.length === 0) {
        html += '<div style="text-align:center;color:#64748b;padding:20px;font-size:12px;">暂无排行</div>'
      } else {
        ranking.forEach((rank, idx) => {
          const isMe = rank.user_id === userId.value
          const displayName = rank.user_id === userId.value ? '我' : (userInfoMap.value[rank.user_id]?.username || rank.user_id)
          const medalBg = idx === 0 ? 'linear-gradient(135deg,#fbbf24,#f59e0b)' : idx === 1 ? 'linear-gradient(135deg,#94a3b8,#64748b)' : idx === 2 ? 'linear-gradient(135deg,#fb923c,#ea580c)' : 'linear-gradient(135deg,#667eea,#764ba2)'
          html += `<div style="display:flex;align-items:center;padding:8px 10px;border-radius:8px;margin-bottom:6px;background:${isMe ? 'rgba(96,165,250,0.15)' : '#0f172a'};border:1px solid ${isMe ? 'rgba(96,165,250,0.4)' : 'transparent'};">
            <div style="width:26px;height:26px;border-radius:50%;background:${medalBg};color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;">${idx + 1}</div>
            <div style="flex:1;margin-left:8px;font-size:12px;font-weight:600;color:#e2e8f0;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${displayName}</div>
            <div style="font-size:12px;font-weight:700;color:#22c55e;margin-right:6px;flex-shrink:0;">${rank.total_score || 0}</div>
            <div style="font-size:10px;color:#64748b;flex-shrink:0;">${rank.solved || 0}/${arenaData.problems?.length || 0}</div>
          </div>`
        })
      }
      container.innerHTML = html
    }
  } catch (e) {
    console.error('加载排行榜失败:', e)
  }
}

window.__arenaToggleRank = () => {
  toggleArenaRanking()
}

const startCompetition = async (compId) => {
  try {
    const res = await startCompetitionApi({ group_id: compId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('比赛已开始！')
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      showFailToast(res.error || '开始失败')
    }
  } catch (e) {
    showFailToast('开始失败: ' + e.message)
  }
}

const endCompetition = async (compId) => {
  groupDialogData.value = {
    title: '结束比赛',
    message: '确定结束比赛？',
    confirmText: '确定结束',
    action: () => doEndCompetition(compId)
  }
  groupDialogType.value = 'confirm'
}

const doEndCompetition = async (compId) => {
  groupDialogLoading.value = true
  try {
    const res = await endCompetitionApi({ group_id: compId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('比赛已结束')
      closeGroupDialog()
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      showFailToast(res.error || '结束失败')
    }
  } catch (e) {
    showFailToast('结束失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const deleteCompetition = (compId) => {
  groupDialogData.value = {
    title: '删除比赛',
    message: '确定删除这个比赛？不可恢复！',
    confirmText: '确定删除',
    action: () => doDeleteCompetition(compId)
  }
  groupDialogType.value = 'confirm'
}

const doDeleteCompetition = async (compId) => {
  groupDialogLoading.value = true
  try {
    const res = await deleteCompetitionApi({ group_id: compId, user_id: userId.value })
    if (res.success) {
      showSuccessToast('比赛已删除')
      closeGroupDialog()
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      showFailToast(res.error || '删除失败')
    }
  } catch (e) {
    showFailToast('删除失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const doConfirmAction = () => {
  if (_confirmCallback) {
    _confirmCallback()
  } else if (groupDialogData.value.action) {
    groupDialogData.value.action()
  }
}

const formatCompTime = (timeStr) => {
  if (!timeStr) return ''
  return new Date(timeStr).toLocaleString()
}

const getLetter = (idx) => {
  return String.fromCharCode(65 + idx)
}

const changeNav = async (value) => {
  if (currentNav.value === value) return
  if (value === 'my-partner') await getMyPartnerList()
  if (value === 'invited') await getInvitedList()
  if (value === 'shared') {
    await getSharedList()
  }
  if (value === 'tg-study') {
    await fetchStudyList()
  }
  if (value === 'group') {
    await loadMyGroups()
  }
  currentNav.value = value
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// =============================== 生命周期 ===============================
onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        if (loginUser.isNew == false && loginUser.isBuildProfile == 0) {
          showToast('请进行画像构建~')
          router.push('/aiAnswer')
        }
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  await getInvitedList()
  await getMyPartnerList()
  await fetchStudyList()
  await getSharedList()

  const tabParam = route.query.tab
  if (tabParam && navItems.some(item => item.value === tabParam)) {
    currentNav.value = tabParam
  }
})

onUnmounted(() => {
  document.body.style.overflow = ''
  stopDiscussPolling()
  stopPairPolling()
  if (chatPollTimer) clearInterval(chatPollTimer)
  closeCompetitionArena()
})
</script>

<template>
  <div class="phone-partners">
    <!-- 顶部 Tab 栏 -->
    <div class="tab-bar">
      <div
        v-for="item in navItems"
        :key="item.value"
        class="tab-item"
        :class="{ active: currentNav === item.value }"
        @click="changeNav(item.value)"
      >
        <span class="tab-label">{{ item.label }}</span>
        <span v-if="item.value === 'invited' && invitedNum" class="badge">{{ invitedNum }}</span>
        <span v-if="item.value === 'tg-study' && pendingCount" class="badge">{{ pendingCount }}</span>
        <span v-if="item.value === 'group' && pendingGroupInvites.length" class="badge">{{ pendingGroupInvites.length }}</span>
      </div>
    </div>

    <!-- 1. 找学伴 -->
    <div v-if="currentNav === 'find-partner'" class="tab-content">
      <div class="search-section">
        <div class="search-header">
          <div class="search-icon-wrapper">🔍</div>
          <div class="search-info">
            <h3 class="search-title">发现学习伙伴</h3>
            <p class="search-desc">根据学习特征智能匹配</p>
          </div>
        </div>

        <div class="radar-wrapper" :class="{ 'has-result': allPartnerList?.length }">
          <MobileRadarScanner
            v-if="isSeeRadar"
            ref="radarRef"
            :scanning="isScanning"
          />
          <div class="radar-placeholder" v-else>
            <div class="placeholder-icon">👤</div>
            <div class="placeholder-text">
              <p class="placeholder-title">准备扫描</p>
              <p class="placeholder-desc">点击下方按钮开始寻找</p>
            </div>
          </div>
        </div>

        <button
          @click="searchPartner()"
          class="search-btn"
          :disabled="isScanning"
        >
          <span v-if="isScanning" class="btn-spinner"></span>
          {{ isScanning ? '扫描中...' : '搜索相似学伴' }}
        </button>
      </div>

      <div class="result-section" v-if="allPartnerList?.length">
        <div class="result-header">
          <span class="result-count">找到 {{ allPartnerList.length }} 位学伴</span>
        </div>
        <div class="partner-list">
          <div
            class="partner-card"
            v-for="(item, index) in allPartnerList"
            :key="item.user_id"
            :style="{ animationDelay: (index * 0.04) + 's' }"
          >
            <div class="card-main">
              <div class="avatar-wrapper">
                <img v-if="item.avatar" :src="item.avatar" class="partner-avatar" />
                <div v-else class="partner-avatar avatar-text">{{ item.username?.[0] || '用' }}</div>
                <!-- <div class="online-dot"></div> -->
              </div>
              <div class="user-info">
                <div class="user-name">{{ item.username || '用户' }}</div>
                <div class="user-id">ID：{{ item.user_id }}</div>
              </div>
              <div class="similarity-tag">
                <div class="similarity-score">{{ item.similarity }}</div>
                <div class="similarity-label">匹配度</div>
              </div>
            </div>
            <div class="card-reason">
              <span class="reason-icon">💡</span>
              <span>{{ item.reason || '根据学习特征匹配' }}</span>
            </div>
            <button
              @click="invite(item.user_id)"
              class="action-btn"
              :class="item.relationship_status === 'pending' ? 'btn-invited' : 'btn-invite'"
              :disabled="item.relationship_status === 'pending'"
              style="margin-top: 10px;"
            >
              {{ item.relationship_status === 'pending' ? '已邀请' : '+ 邀请' }}
            </button>
          </div>
        </div>
      </div>

      <div class="empty-result" v-if="isSeeRadar && !isScanning && !allPartnerList?.length">
        <div class="empty-icon">📭</div>
        <p class="empty-text">暂无匹配的学伴，稍后再试试吧</p>
      </div>
    </div>

    <!-- 2. 我的学伴 -->
    <div v-else-if="currentNav === 'my-partner'" class="tab-content">
      <van-search
        v-model="partnerSearchKeyword"
        placeholder="搜索学伴..."
        shape="round"
        class="partner-search"
      />
      <div class="partner-list" v-if="filteredPartnerList?.length">
        <div
          class="partner-card partner-card-my"
          v-for="(item, index) in filteredPartnerList"
          :key="item.companion_id"
          :style="{ animationDelay: (index * 0.03) + 's' }"
        >
          <div class="card-main">
            <div class="avatar-wrapper">
              <img v-if="item.avatar" :src="item.avatar" class="partner-avatar" />
              <div v-else class="partner-avatar avatar-text">{{ item.username?.[0] || '用' }}</div>
            </div>
            <div class="user-info">
              <div class="user-name">{{ item.username || '用户' }}</div>
              <div class="user-id">ID：{{ item.user_id }}</div>
            </div>
          </div>
          <div class="card-meta">
            <span class="phase-tag">
              <span class="phase-label">当前阶段</span>
              <span class="phase-value">{{ item.current_phase || '学习中' }}</span>
            </span>
            <span class="time-tag">
              <span class="time-icon">🕐</span>
              <span>{{ formatTime(item.established_at) }}</span>
            </span>
          </div>
          <button class="action-btn btn-call" @click="handleViewProfile(item)" :disabled="isInCall">
            📞 通话
          </button>
        </div>
      </div>
      <div class="empty-state" v-else>
        <div class="empty-icon">👥</div>
        <p class="empty-title">还没有学伴</p>
        <p class="empty-desc">去「找学伴」发现学习伙伴</p>
        <button class="action-btn btn-invite" @click="changeNav('find-partner')">去发现学伴 →</button>
      </div>
    </div>

    <!-- 3. 邀请 -->
    <div v-else-if="currentNav === 'invited'" class="tab-content">
      <div class="section-tip">待处理的学伴邀请</div>
      <div class="partner-list" v-if="inviteList?.length">
        <div class="invite-card" v-for="item in inviteList" :key="item.id">
          <div class="card-main">
            <div class="avatar-wrapper">
              <img v-if="item.avatar" :src="item.avatar" class="partner-avatar" />
              <div v-else class="partner-avatar avatar-text">{{ item.username?.[0] || '用' }}</div>
            </div>
            <div class="user-info">
              <div class="user-name">{{ item.username || '用户' }}</div>
              <div class="user-id">ID：{{ item.invited_by }}</div>
            </div>
            <span class="status-pill" :class="item.status === 'pending' ? 'pill-pending' : 'pill-done'">
              {{ item.status === 'pending' ? '待处理' : '已处理' }}
            </span>
          </div>
          <div class="card-meta">
            <span class="time-tag">
              <span class="time-icon">🕐</span>
              <span>{{ formatTime(item.created_at) }}</span>
            </span>
          </div>
          <div class="card-actions" v-if="item.status === 'pending'">
            <button @click="isAccept(item.id, false)" class="action-btn btn-reject">拒绝</button>
            <button @click="isAccept(item.id, true)" class="action-btn btn-accept">通过</button>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <div class="empty-icon">📭</div>
        <p class="empty-title">暂无学伴邀请</p>
      </div>
    </div>

    <!-- 4. 共享 -->
    <div v-else-if="currentNav === 'shared'" class="tab-content">
      <div class="section-tip">学伴共享的资料库</div>
      <div class="partner-list" v-if="sharedList?.length">
        <div class="shared-card" v-for="item in sharedList" :key="item.resource_id">
          <div class="card-main">
            <div class="resource-icon" :class="getResourceIconClass(item.resource_type)">
              {{ getResourceIconEmoji(item.resource_type) }}
            </div>
            <div class="user-info">
              <div class="user-name">
                <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                {{ item.title || '未命名资源' }}
              </div>
              <div class="user-id">
                分享人：{{ item.sharer_name || item.sharer_id || '用户' }}
              </div>
            </div>
          </div>
          <div class="card-meta">
            <span class="time-tag">
              <span class="time-icon">🕐</span>
              <span>{{ formatTime(item.created_at) }}</span>
            </span>
            <button @click="viewRs(item.resource_type, item.resource_id)" class="action-btn btn-view">查看</button>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <div class="empty-icon">📭</div>
        <p class="empty-title">暂无学伴分享的资料</p>
      </div>
    </div>

    <!-- 5. 共同学习 -->
    <div v-else-if="currentNav === 'tg-study'" class="tab-content">
      <div class="section-tip">
        共学记录
        <span v-if="pendingCount > 0" class="pending-hint">（有 {{ pendingCount }} 条待处理）</span>
      </div>
      <div class="partner-list" v-if="studyList?.length">
        <div class="study-card" v-for="item in studyList" :key="item.id + '_' + (item._type || 'record')">
          <div class="card-main">
            <div class="resource-icon" :class="getResourceIconClass(item.resource_type)">
              {{ getResourceIconEmoji(item.resource_type) }}
            </div>
            <div class="user-info">
              <div class="user-name study-title">
                <template v-if="item._type === 'pending'">
                  <span class="inviter-name">{{ item.inviter_name || item.inviter_id }}</span>
                  邀请你共学
                  <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                  <span class="status-pill pill-pending">待处理</span>
                </template>
                <template v-else-if="item._type === 'sent'">
                  你邀请 <span class="inviter-name">{{ item.invitee_name || item.invitee_id }}</span>
                  共学 <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                  <span class="status-pill" :class="item.status === 'pending' ? 'pill-pending' : 'pill-done'">
                    {{ item.status === 'pending' ? '等待响应' : '已接受' }}
                  </span>
                </template>
                <template v-else>
                  <span class="inviter-name">{{ item.inviter_name || item.inviter_id }}</span>
                  与 <span class="inviter-name">{{ item.invitee_name || item.invitee_id }}</span>
                  共学 <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                  <span class="status-pill" :class="item.status === 'accepted' ? 'pill-done' : 'pill-rejected'">
                    {{ getStatusLabel(item.status) }}
                  </span>
                  <span v-if="item.mode === 'pair'" class="mode-tag pair">结对编程</span>
                  <span v-else class="mode-tag separate">独立作答</span>
                </template>
              </div>
              <div class="user-id resource-title">{{ item.title || '未命名资源' }}</div>
              <div class="user-id">
                <template v-if="item._type === 'pending' || item._type === 'sent'">
                  模式：{{ item.mode === 'pair' ? '结对编程' : '独立作答' }}
                  <span class="partner-time">· {{ formatTime(item.created_at) }}</span>
                </template>
                <template v-else>
                  创建：{{ formatTime(item.created_at) }}
                  <span v-if="item.responded_at">响应：{{ formatTime(item.responded_at) }}</span>
                </template>
              </div>
            </div>
          </div>
          <div class="card-actions" v-if="item._type === 'pending'">
            <button @click="handleAccept(item.id, false)" class="action-btn btn-reject">拒绝</button>
            <button @click="handleAccept(item.id, true)" class="action-btn btn-accept">接受</button>
          </div>
          <div class="card-actions" v-else-if="item._type === 'sent' && item.status === 'pending'">
            <button @click="handleDelete(item.id)" class="action-btn btn-delete">删除</button>
          </div>
          <div class="card-actions" v-else>
            <button @click="handleDiscuss(item)" class="action-btn btn-invite">讨论</button>
            <template v-if="item.resource_type === 'practice'">
              <button v-if="item.mode === 'pair'" @click="handlePairProgramming(item)" class="action-btn btn-accept">结对编程</button>
              <button v-else @click="handleCompareScore(item)" class="action-btn btn-warn">对比成绩</button>
              <button v-if="item.mode !== 'pair'" @click="handleGoAnswer(item)" class="action-btn btn-view">去作答</button>
            </template>
            <template v-else>
              <button @click="handleView(item)" class="action-btn btn-view">查看</button>
            </template>
            <button @click="handleDelete(item.id)" class="action-btn btn-delete">删除</button>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <div class="empty-icon">📭</div>
        <p class="empty-title">暂无共学记录</p>
      </div>
    </div>

    <!-- 6. 小组 -->
    <div v-else-if="currentNav === 'group'" class="tab-content">
      <div class="section-tip">创建或加入学习小组，与成员一起学习和比赛</div>
      <div class="group-actions-bar">
        <button @click="showCreateGroupDialog" class="action-btn btn-invite">+ 创建小组</button>
        <button @click="showDiscoverGroups" class="action-btn btn-accept">🔍 发现小组</button>
        <button @click="loadMyGroups" class="action-btn btn-warn">我的小组</button>
      </div>

      <div v-if="pendingGroupInvites.length > 0" class="group-invite-banner" @click="showPendingInvitesDialog">
        <span>📨 你有 {{ pendingGroupInvites.length }} 条小组邀请待处理</span>
        <span class="banner-arrow">查看 →</span>
      </div>

      <!-- 小组列表视图 -->
      <div v-if="currentGroupView === 'list'" class="group-content">
        <div v-if="myGroups.length === 0 && pendingGroupInvites.length === 0" class="empty-state">
          <div class="empty-icon">👥</div>
          <p class="empty-title">还没有加入任何小组</p>
          <button @click="showDiscoverGroups" class="action-btn btn-accept">🔍 发现小组</button>
        </div>
        <div v-else class="group-list">
          <div v-for="group in myGroups" :key="group.id" class="group-card" @click="openGroupDetail(group.id)">
            <div class="group-avatar">{{ group.name.charAt(0).toUpperCase() }}</div>
            <div class="group-info">
              <div class="group-name">
                {{ group.name }}
                <span class="role-tag">{{ group.role === 'owner' ? '创建者' : group.role === 'admin' ? '管理员' : '成员' }}</span>
              </div>
              <div class="group-meta">{{ group.description || '暂无描述' }} · {{ group.member_count || 0 }} 人</div>
            </div>
            <span class="arrow-icon">›</span>
          </div>
        </div>
      </div>

      <!-- 小组详情视图 -->
      <div v-else-if="currentGroupView === 'detail' && currentGroupDetail" class="group-detail-view">
        <div class="group-back-bar">
          <button @click="backToGroupList" class="group-back-btn">‹ 返回小组列表</button>
        </div>

        <!-- 小组信息卡 -->
        <div class="group-detail-card">
          <div class="group-detail-header">
            <div class="group-avatar">{{ currentGroupDetail.name.charAt(0).toUpperCase() }}</div>
            <div>
              <div class="group-name strong">{{ currentGroupDetail.name }}</div>
              <div class="group-meta">{{ currentGroupDetail.members?.length || 0 }} 人</div>
            </div>
          </div>
          <div class="members-label">成员</div>
          <div class="members-list">
            <span v-for="member in currentGroupDetail.members" :key="member.user_id" class="group-member-tag">
              {{ getUserName(member.user_id) }}
              <span v-if="member.role === 'owner'" class="role-mark">👑</span>
              <span v-else-if="member.role === 'admin'" class="role-mark">🛡️</span>
            </span>
          </div>
          <div class="group-detail-actions">
            <button v-if="canInviteMember" @click="showInviteMemberDialog" class="action-btn btn-invite">邀请成员</button>
            <button v-if="currentGroupDetail.creator_id === userId" @click="showCreateCompetitionDialog" class="action-btn btn-warn">🏆 发布比赛</button>
            <button v-if="currentGroupDetail.creator_id === userId" @click="dissolveGroup(currentGroupId)" class="action-btn btn-delete">解散小组</button>
            <button v-else @click="leaveGroupWithConfirm(currentGroupId)" class="action-btn btn-reject">退出小组</button>
          </div>
        </div>

        <!-- 比赛列表 -->
        <div class="comp-section">
          <div class="comp-section-title">🏆 比赛</div>
          <div v-if="currentGroupCompetitions.length === 0" class="empty-mini">暂无比赛</div>
          <div v-else class="comp-list">
            <div v-for="comp in currentGroupCompetitions" :key="comp.id" class="comp-card">
              <div class="comp-header">
                <div class="comp-title">🏆 {{ comp.title }}</div>
                <span class="comp-status" :class="comp.status">
                  {{ comp.status === 'pending' ? '待开始' : comp.status === 'running' ? '进行中' : '已结束' }}
                </span>
              </div>
              <div class="comp-meta">
                {{ comp.problem_count || 0 }} 道题 · {{ formatCompTime(comp.start_at) }}
              </div>
              <div class="comp-actions">
                <button v-if="comp.status === 'pending' || comp.status === 'running'" @click="openCompetition(comp.id)" class="action-btn btn-invite">
                  {{ comp.status === 'pending' ? '管理赛题' : '进入比赛' }}
                </button>
                <button v-if="comp.status === 'finished'" @click="openCompetition(comp.id)" class="action-btn btn-view">查看排行</button>
                <button v-if="comp.created_by === userId && comp.status === 'pending'" @click="startCompetition(comp.id)" class="action-btn btn-accept">开始</button>
                <button v-if="comp.created_by === userId && comp.status === 'running'" @click="endCompetition(comp.id)" class="action-btn btn-reject">结束</button>
                <button v-if="comp.created_by === userId" @click="deleteCompetition(comp.id)" class="action-btn btn-delete">🗑</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 群聊 -->
        <div class="group-chat-card">
          <div class="comp-section-title">💬 群聊</div>
          <div class="group-chat-messages" ref="messageListRef">
            <div
              v-for="msg in currentGroupMessages"
              :key="msg.id"
              class="group-msg"
              :class="{ self: msg.sender_id === userId }"
            >
              <div class="msg-avatar">
                <img v-if="getUserAvatar(msg.sender_id)" :src="getUserAvatar(msg.sender_id)" class="msg-avatar-img" />
                <span v-else>{{ getUserInitial(msg.sender_id) }}</span>
              </div>
              <div class="msg-body">
                <div class="msg-sender">{{ getUserName(msg.sender_id) }}</div>
                <div class="msg-bubble">
                  <img v-if="msg.msg_type === 'image'" :src="msg.content" alt="图片" class="msg-image" />
                  <span v-else>{{ msg.content }}</span>
                </div>
                <div class="msg-time">{{ (msg.created_at || '').slice(11, 19) }}</div>
              </div>
            </div>
            <div v-if="currentGroupMessages.length === 0" class="empty-mini">暂无消息</div>
          </div>
          <div class="group-chat-input-area">
            <input v-model="groupChatInput" type="text" placeholder="输入消息..." class="group-chat-input" @keydown.enter="sendGroupMessage" />
            <button @click="sendGroupMessage" class="action-btn btn-invite chat-send">发送</button>
            <input type="file" ref="groupImageInputRef" accept="image/*" style="display:none" @change="uploadGroupImage" />
            <button @click="$refs.groupImageInputRef.click()" class="action-btn btn-view chat-img">📷</button>
          </div>
        </div>
      </div>

      <!-- 发现小组视图 -->
      <div v-else-if="currentGroupView === 'discover'" class="group-content">
        <div class="group-back-bar">
          <button @click="currentGroupView = 'list'" class="group-back-btn">‹ 返回我的小组</button>
        </div>
        <div class="section-tip">🔍 发现公开小组</div>
        <div v-if="discoverGroups.length === 0" class="empty-state">
          <div class="empty-icon">🔍</div>
          <p class="empty-title">暂无公开小组，创建一个吧</p>
        </div>
        <div v-else class="group-list">
          <div v-for="group in discoverGroups" :key="group.id" class="group-card">
            <div class="group-avatar">{{ group.name.charAt(0).toUpperCase() }}</div>
            <div class="group-info">
              <div class="group-name">{{ group.name }} <span class="role-tag">公开</span></div>
              <div class="group-meta">创建者: {{ getUserName(group.creator_id) }} · {{ group.member_count || 0 }} 人</div>
            </div>
            <button @click.stop="quickJoinGroup(group.id, group.name)" class="action-btn btn-accept">加入</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ===================== 自定义弹窗 ===================== -->

    <!-- 创建小组弹窗 -->
    <div v-if="groupDialogType === 'create'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog">
        <div class="dialog-header">
          <span class="dialog-title">创建学习小组</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-item">
            <label class="form-label">小组名称 *</label>
            <input v-model="groupDialogData.name" type="text" placeholder="取一个响亮的名字" class="form-input" ref="createGroupNameRef">
          </div>
          <div class="form-item">
            <label class="form-label">小组描述</label>
            <textarea v-model="groupDialogData.description" placeholder="介绍一下你们小组..." class="form-textarea"></textarea>
          </div>
          <div class="form-item">
            <label class="form-label">小组类型</label>
            <div class="type-cards">
              <label class="type-card" :class="{ active: groupDialogData.is_public }" @click="groupDialogData.is_public = true">
                <div class="type-icon">☀️</div>
                <div class="type-name">公开小组</div>
                <div class="type-desc">任何人可加入</div>
              </label>
              <label class="type-card" :class="{ active: !groupDialogData.is_public }" @click="groupDialogData.is_public = false">
                <div class="type-icon">🔒</div>
                <div class="type-name">私密小组</div>
                <div class="type-desc">需邀请才能加入</div>
              </label>
            </div>
          </div>
          <div class="dialog-btns">
            <button @click="doCreateGroup" class="action-btn btn-invite" :disabled="groupDialogLoading">
              {{ groupDialogLoading ? '创建中...' : '创建' }}
            </button>
            <button @click="closeGroupDialog" class="action-btn btn-reject">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 邀请成员弹窗 -->
    <div v-if="groupDialogType === 'invite'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog">
        <div class="dialog-header">
          <span class="dialog-title">邀请成员</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-item">
            <label class="form-label">输入用户ID</label>
            <input v-model="groupDialogData.invitee_id" type="text" placeholder="例如: user_002" class="form-input" ref="inviteUserIdRef">
          </div>
          <div class="dialog-btns">
            <button @click="doInviteToGroup" class="action-btn btn-invite" :disabled="groupDialogLoading">发送邀请</button>
            <button @click="closeGroupDialog" class="action-btn btn-reject">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 待处理邀请弹窗 -->
    <div v-if="groupDialogType === 'pending'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog">
        <div class="dialog-header">
          <span class="dialog-title">小组邀请 ({{ pendingGroupInvites.length }})</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div v-if="pendingGroupInvites.length === 0" class="empty-mini">暂无待处理的邀请</div>
          <div v-for="inv in pendingGroupInvites" :key="inv.id" class="invite-item">
            <div class="invite-item-title">🔒 {{ inv.group_name }}</div>
            <div class="invite-item-meta">邀请人: {{ getUserName(inv.inviter_id) }} · {{ inv.member_count || 0 }} 人</div>
            <div class="invite-item-actions">
              <button @click="respondGroupInvite(inv.id, true)" class="action-btn btn-accept">接受</button>
              <button @click="respondGroupInvite(inv.id, false)" class="action-btn btn-reject">拒绝</button>
            </div>
          </div>
          <button @click="closeGroupDialog" class="action-btn btn-reject full-width">关闭</button>
        </div>
      </div>
    </div>

    <!-- 发布比赛弹窗 -->
    <div v-if="groupDialogType === 'competition'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog">
        <div class="dialog-header">
          <span class="dialog-title">🏆 发布比赛</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-item">
            <label class="form-label">比赛名称 *</label>
            <input v-model="groupDialogData.title" type="text" placeholder="例如：算法挑战赛" class="form-input">
          </div>
          <div class="form-item">
            <label class="form-label">比赛描述</label>
            <textarea v-model="groupDialogData.description" placeholder="描述一下比赛内容..." class="form-textarea"></textarea>
          </div>
          <div class="form-item">
            <label class="form-label">比赛主题（用于生成赛题）</label>
            <textarea v-model="groupDialogData.topic" placeholder="输入比赛主题/知识点..." class="form-textarea"></textarea>
          </div>
          <div class="form-item">
            <label class="form-label">题目数量</label>
            <input v-model="groupDialogData.problem_count" type="number" min="1" max="20" class="form-input">
          </div>
          <div class="form-row">
            <div class="form-item">
              <label class="form-label">开始时间</label>
              <input v-model="groupDialogData.start_at" type="datetime-local" class="form-input">
            </div>
            <div class="form-item">
              <label class="form-label">结束时间</label>
              <input v-model="groupDialogData.end_at" type="datetime-local" class="form-input">
            </div>
          </div>
          <div class="dialog-btns">
            <button @click="doCreateCompetition" class="action-btn btn-invite" :disabled="groupDialogLoading">
              {{ groupDialogLoading ? '创建中...' : '创建并生成赛题' }}
            </button>
            <button @click="closeGroupDialog" class="action-btn btn-reject">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="groupDialogType === 'confirm'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog small">
        <div class="dialog-header">
          <span class="dialog-title">{{ groupDialogData.title || '确认' }}</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <p class="confirm-message">{{ groupDialogData.message }}</p>
          <div class="dialog-btns">
            <button @click="doConfirmAction" class="action-btn btn-delete" :disabled="groupDialogLoading">
              {{ groupDialogLoading ? '处理中...' : (groupDialogData.confirmText || '确定') }}
            </button>
            <button @click="closeGroupDialog" class="action-btn btn-reject">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 讨论弹窗（近全屏） -->
    <div v-if="discussDialogVisible" class="custom-overlay discuss-overlay" @click.self="closeDiscussDialog">
      <div class="custom-dialog discuss-dialog">
        <div class="dialog-header">
          <div class="dialog-header-left">
            <span class="dialog-title">讨论</span>
            <span class="dialog-subtitle">{{ currentDiscussItem?.title || '' }}</span>
          </div>
          <button class="dialog-close" @click="closeDiscussDialog">×</button>
        </div>
        <div class="dialog-body discuss-body">
          <div class="message-list" ref="messageListRef">
            <div
              v-for="msg in discussMessages"
              :key="msg.id"
              class="message-item"
              :class="{ self: msg.sender_id === userId }"
            >
              <div class="message-avatar">
                <img v-if="msg.sender_avatar" :src="msg.sender_avatar" class="msg-avatar-img" />
                <span v-else>{{ msg.sender_name?.[0] || 'U' }}</span>
              </div>
              <div class="message-wrapper">
                <div class="message-sender">{{ msg.sender_name }}</div>
                <div class="message-bubble">{{ msg.content }}</div>
                <div class="message-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>
            <div v-if="!discussMessages.length" class="empty-mini">暂无消息，开始交流吧</div>
          </div>
        </div>
        <div class="dialog-footer">
          <input
            v-model="discussInput"
            class="message-input"
            placeholder="输入消息..."
            @keyup.enter="sendDiscussMessage"
            :disabled="isSending"
          />
          <button class="action-btn btn-invite" @click="sendDiscussMessage" :disabled="isSending">
            {{ isSending ? '...' : '发送' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 结对编程弹窗（单列） -->
    <div v-if="pairDialogVisible" class="custom-overlay pair-overlay" @click.self="closePairDialog">
      <div class="custom-dialog pair-dialog">
        <div class="dialog-header">
          <span class="dialog-title">结对编程</span>
          <button class="dialog-close" @click="closePairDialog">×</button>
        </div>
        <div class="dialog-body pair-body">
          <!-- 题目描述（上方可滚动） -->
          <div class="pair-problem">
            <div class="pair-problem-title">{{ pairProblem?.title || '题目' }}</div>
            <div class="pair-problem-meta">
              <span class="difficulty" :class="getDifficultyClass(pairProblem?.difficulty)">
                {{ pairProblem?.difficulty || '简单' }}
              </span>
              <span class="pair-mode-tag">{{ pairItem?.mode === 'pair' ? '结对编程' : '独立作答' }}</span>
            </div>
            <div class="pair-problem-desc" v-html="markdownToHtml(pairProblem?.description)"></div>
            <div v-if="pairProblem?.examples" class="pair-examples">
              <div class="example-title">示例：</div>
              <div v-for="(ex, idx) in pairProblem.examples" :key="idx" class="example-item">
                <div><strong>输入：</strong>{{ ex.input }}</div>
                <div><strong>输出：</strong>{{ ex.output }}</div>
                <div v-if="ex.explanation" class="example-explain">{{ ex.explanation }}</div>
              </div>
            </div>
            <div v-if="pairProblem?.hints" class="pair-hints">
              <div class="hints-title">提示：</div>
              <ul>
                <li v-for="(hint, idx) in pairProblem.hints" :key="idx">{{ hint }}</li>
              </ul>
            </div>
          </div>
          <!-- 编辑器（下方） -->
          <div class="pair-editor-section">
            <div class="pair-editor-header">
              <span class="pair-users">
                {{ pairItem?.inviter_name || pairItem?.inviter_id }}
                <span class="pair-link">⟷</span>
                {{ pairItem?.invitee_name || pairItem?.invitee_id }}
              </span>
              <select v-model="pairLanguage" class="language-select" @change="onLanguageChange">
                <option value="python">Python</option>
                <option value="java">Java</option>
                <option value="cpp">C++</option>
                <option value="c">C</option>
                <option value="javascript">JavaScript</option>
                <option value="go">Go</option>
                <option value="rust">Rust</option>
              </select>
            </div>
            <textarea
              :value="pairCodeContent"
              class="code-textarea"
              placeholder="在这里编写代码..."
              @input="onCodeChange"
            ></textarea>
            <div class="pair-actions">
              <button class="action-btn btn-reject" @click="closePairDialog">关闭</button>
              <button
                class="action-btn btn-warn"
                @click="submitPairCode"
                :disabled="submittingPair"
              >
                {{ submittingPair ? '提交中...' : '提交代码' }}
              </button>
            </div>
            <div v-if="pairSubmitResult" class="pair-result">
              <div class="result-header" :class="pairSubmitResult.verdict === 'Accepted' ? 'result-pass' : 'result-fail'">
                {{ pairSubmitResult.verdict || '评测结果' }}
                <span class="result-score">得分：{{ pairSubmitResult.score || 0 }}</span>
              </div>
              <div v-if="pairSubmitResult.analysis" class="result-analysis">
                <div><strong>分析：</strong>{{ pairSubmitResult.analysis?.correctness || '' }}</div>
                <div v-if="pairSubmitResult.suggestions?.length">
                  <strong>建议：</strong>
                  <ul>
                    <li v-for="(s, idx) in pairSubmitResult.suggestions" :key="idx">{{ s }}</li>
                  </ul>
                </div>
                <div v-if="pairSubmitResult.reference_solution" class="reference-solution">
                  <strong>参考解法：</strong>{{ pairSubmitResult.reference_solution }}
                </div>
              </div>
              <div v-if="pairSubmitResult.encouragement" class="encouragement">
                {{ pairSubmitResult.encouragement }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 对比成绩弹窗（垂直堆叠 + VS 分隔） -->
    <div v-if="compareDialogVisible" class="custom-overlay" @click.self="closeCompareDialog">
      <div class="custom-dialog compare-dialog">
        <div class="dialog-header">
          <span class="dialog-title">成绩对比</span>
          <button class="dialog-close" @click="closeCompareDialog">×</button>
        </div>
        <div class="dialog-body compare-body">
          <div class="compare-arena">
            <div class="compare-user-card">
              <div class="user-card-header">
                <div class="user-avatar">
                  <img v-if="compareData?.user_a_avatar" :src="compareData?.user_a_avatar" class="msg-avatar-img" />
                  <span v-else>{{ compareData?.user_a_name?.[0] || 'A' }}</span>
                </div>
                <div class="user-name">{{ compareData?.user_a_name || '用户A' }}</div>
                <span class="user-badge" :class="getWinnerClass(compareData?.user_a)">
                  {{ getWinnerLabel(compareData?.user_a) }}
                </span>
              </div>
              <div class="user-card-body">
                <div class="score-item">
                  <span class="score-label">得分</span>
                  <span class="score-value" :class="getScoreClass(compareData?.a_result?.score)">
                    {{ compareData?.a_result?.score ?? 0 }}
                  </span>
                </div>
                <div class="score-item">
                  <span class="score-label">状态</span>
                  <span class="status-value" :class="getVerdictClass(compareData?.a_result?.verdict)">
                    {{ compareData?.a_result?.verdict || '未作答' }}
                  </span>
                </div>
                <div class="score-item">
                  <span class="score-label">通过测试</span>
                  <span class="passed-value">{{ compareData?.a_result?.passed || '0/0' }}</span>
                </div>
              </div>
            </div>

            <div class="vs-divider">
              <span class="vs-text">VS</span>
            </div>

            <div class="compare-user-card">
              <div class="user-card-header">
                <div class="user-avatar">
                  <img v-if="compareData?.user_b_avatar" :src="compareData?.user_b_avatar" class="msg-avatar-img" />
                  <span v-else>{{ compareData?.user_b_name?.[0] || 'B' }}</span>
                </div>
                <div class="user-name">{{ compareData?.user_b_name || '用户B' }}</div>
                <span class="user-badge" :class="getWinnerClass(compareData?.user_b)">
                  {{ getWinnerLabel(compareData?.user_b) }}
                </span>
              </div>
              <div class="user-card-body">
                <div class="score-item">
                  <span class="score-label">得分</span>
                  <span class="score-value" :class="getScoreClass(compareData?.b_result?.score)">
                    {{ compareData?.b_result?.score ?? 0 }}
                  </span>
                </div>
                <div class="score-item">
                  <span class="score-label">状态</span>
                  <span class="status-value" :class="getVerdictClass(compareData?.b_result?.verdict)">
                    {{ compareData?.b_result?.verdict || '未作答' }}
                  </span>
                </div>
                <div class="score-item">
                  <span class="score-label">通过测试</span>
                  <span class="passed-value">{{ compareData?.b_result?.passed || '0/0' }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="compare-result-banner" :class="getResultBannerClass()">
            <span class="result-text">{{ getResultText() }}</span>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="action-btn btn-reject full-width" @click="closeCompareDialog">关闭</button>
        </div>
      </div>
    </div>


  </div>
</template>

<style scoped>
/* ===================== 主容器 ===================== */
.phone-partners {
  padding: 12px;
  padding-bottom: 60px;
  min-height: 100vh;
  background: var(--bg-page);
  box-sizing: border-box;
}

/* ===================== Tab 栏 ===================== */
.tab-bar {
  display: flex;
  gap: 2px;
  overflow: hidden;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 12px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tab-bar::-webkit-scrollbar {
  display: none;
}

.tab-item {
  flex: 1;
  min-width: 0;
  padding: 8px 4px;
  font-size: 13px;
  color: var(--text-gray);
  border-radius: var(--radius-md);
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1.4;
}
.tab-label {
  max-width: 2.2em;
  word-break: break-all;
  text-align: center;
}

.tab-item.active {
  color: #fff;
  background: var(--grad-primary);
  font-weight: 600;
}

.tab-item:not(.active):active {
  background: var(--bg-hover);
}

.badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  padding: 0 4px;
  background: var(--main-delete);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
  text-align: center;
}

/* ===================== 通用内容 ===================== */
.tab-content {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.section-tip {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 10px;
  padding: 0 2px;
}

.pending-hint {
  color: var(--coming);
  font-weight: 600;
}

/* ===================== 卡片 ===================== */
.partner-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.partner-card,
.invite-card,
.shared-card,
.study-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  animation: fadeSlideUp 0.4s ease forwards;
  opacity: 0;
}

@keyframes fadeSlideUp {
  0% { opacity: 0; transform: translateY(16px); }
  100% { opacity: 1; transform: translateY(0); }
}

.card-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.partner-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--primary-fade);
}

.avatar-text {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  font-weight: 600;
  font-size: 16px;
}

.online-dot {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background: var(--pass);
  border: 2px solid var(--bg-card);
  border-radius: 50%;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-id {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
  align-items: center;
  justify-content: space-between;
}

.phase-tag,
.time-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-gray);
}

.phase-label {
  color: var(--text-gray);
}

.phase-value {
  color: var(--primary);
  font-weight: 600;
}

.time-icon {
  font-size: 12px;
}

.card-reason {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.5;
}

.reason-icon {
  flex-shrink: 0;
}

/* 匹配度标签 */
.similarity-tag {
  text-align: center;
  flex-shrink: 0;
}

.similarity-score {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1;
}

.similarity-label {
  font-size: 10px;
  color: var(--text-gray);
  margin-top: 2px;
}

/* 资源图标 */
.resource-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.resource-icon.icon-doc { background: #dbeafe; }
.resource-icon.icon-practice { background: #dcfce7; }
.resource-icon.icon-mindmap { background: #fef3c7; }
.resource-icon.icon-extension { background: #fce7f3; }
.resource-icon.icon-video { background: #f3e8ff; }
.resource-icon.icon-animation { background: #ffedd5; }
.resource-icon.icon-ppt { background: #fee2e2; }
.resource-icon.icon-question { background: #e0e7ff; }
.resource-icon.icon-default { background: var(--bg-hover); }

.resource-tag {
  display: inline-block;
  padding: 1px 6px;
  background: var(--primary-fade);
  color: var(--primary);
  font-size: 11px;
  border-radius: var(--radius-sm);
  margin-right: 4px;
  font-weight: 500;
}

/* 状态标签 */
.status-pill {
  display: inline-block;
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 10px;
  font-weight: 500;
}

.pill-pending {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.pill-done {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.pill-rejected {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.mode-tag {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: var(--radius-sm);
  margin-left: 4px;
}

.mode-tag.pair {
  background: #fef3c7;
  color: #d97706;
}

.mode-tag.separate {
  background: #e0e7ff;
  color: #4f46e5;
}

.inviter-name {
  color: var(--primary);
  font-weight: 600;
}

.study-title {
  line-height: 1.6;
}

.resource-title {
  margin-top: 4px;
  font-weight: 500;
  color: var(--text-body);
  display: -webkit-box;
  line-clamp: 1;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.partner-time {
  color: var(--text-gray);
}

/* ===================== 按钮区 ===================== */
.partner-card > .action-btn {
  display: block;
  margin-left: auto;
}
.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.action-btn {
  min-height: 36px;
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #fff;
  flex-shrink: 0;
}

.action-btn:active {
  transform: scale(0.96);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-invite {
  background: var(--grad-primary);
  color: #fff;
}

.btn-accept {
  background: var(--pass);
  color: #fff;
}

.btn-reject {
  background: var(--bg-hover);
  color: var(--text-body);
}

.btn-delete {
  background: var(--main-delete);
  color: #fff;
}

.btn-warn {
  background: var(--coming);
  color: #fff;
}

.btn-view {
  background: var(--primary-light);
  color: var(--primary);
}

.btn-call {
  background: var(--grad-primary);
  color: #fff;
  width: 100%;
  margin-top: 10px;
}

.btn-invited {
  background: var(--bg-hover);
  color: var(--text-gray);
}

.full-width {
  width: 100%;
}

/* ===================== 找学伴 ===================== */
.search-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
}

.search-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--grad-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.search-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-title);
  margin: 0;
}

.search-desc {
  font-size: 12px;
  color: var(--text-gray);
  margin: 4px 0 0;
}

.radar-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 0;
  min-height: 220px;
}

.radar-placeholder {
  text-align: center;
}

.placeholder-icon {
  font-size: 56px;
  margin-bottom: 8px;
  opacity: 0.4;
}

.placeholder-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  margin: 0;
}

.placeholder-desc {
  font-size: 12px;
  color: var(--text-gray);
  margin: 4px 0 0;
}

.search-btn {
  width: 100%;
  min-height: 44px;
  background: var(--grad-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.search-btn:disabled {
  opacity: 0.7;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-section {
  margin-top: 12px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding: 0 2px;
}

.result-count {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}

/* ===================== 我的学伴搜索 ===================== */
.partner-search {
  margin-bottom: 12px;
  padding: 0 !important;
}

.partner-search :deep(.van-search__content) {
  background: var(--bg-card);
}

/* ===================== 空状态 ===================== */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}
.empty-state .action-btn {
  margin-left: auto;
  display: block;
  width: fit-content;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  margin: 0 0 4px;
}

.empty-desc {
  font-size: 13px;
  color: var(--text-gray);
  margin: 0 0 16px;
}

.empty-result {
  text-align: center;
  padding: 30px 20px;
}

.empty-text {
  font-size: 13px;
  color: var(--text-gray);
}

.empty-mini {
  text-align: center;
  color: var(--text-gray);
  padding: 16px;
  font-size: 13px;
}

/* ===================== 小组 ===================== */
.group-actions-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.group-actions-bar .action-btn {
  flex: 1;
  font-size: 12px;
  padding: 6px 8px;
}

.group-invite-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--coming-bg-color);
  color: var(--coming);
  padding: 10px 12px;
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 500;
}

.banner-arrow {
  font-size: 12px;
  font-weight: 600;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.group-card:active {
  background: var(--bg-hover);
}

.group-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.group-info {
  flex: 1;
  min-width: 0;
}

.group-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-name.strong {
  font-size: 16px;
}

.group-meta {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-tag {
  display: inline-block;
  padding: 0 6px;
  font-size: 10px;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: var(--radius-sm);
  margin-left: 4px;
  font-weight: 500;
}

.arrow-icon {
  font-size: 20px;
  color: var(--text-gray);
  flex-shrink: 0;
}

/* 小组详情 */
.group-detail-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-back-bar {
  margin-bottom: 4px;
}

.group-back-btn {
  background: none;
  border: none;
  color: var(--primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 0;
}

.group-detail-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.group-detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.members-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-gray);
  margin-bottom: 6px;
}

.members-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.group-member-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  background: var(--bg-hover);
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-body);
}

.role-mark {
  margin-left: 2px;
}

.group-detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-detail-actions .action-btn {
  flex: 1;
  min-width: 90px;
  font-size: 12px;
}

/* 比赛 */
.comp-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.comp-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
}

.comp-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comp-card {
  background: var(--bg-page);
  border-radius: var(--radius-md);
  padding: 12px;
  border: 1px solid var(--border-color);
}

.comp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  gap: 8px;
}

.comp-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  flex: 1;
  min-width: 0;
}

.comp-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  flex-shrink: 0;
}

.comp-status.pending {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.comp-status.running {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.comp-status.finished {
  background: var(--bg-hover);
  color: var(--text-gray);
}

.comp-meta {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 8px;
}

.comp-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.comp-actions .action-btn {
  font-size: 12px;
  padding: 4px 10px;
  min-height: 32px;
}

/* 群聊 */
.group-chat-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.group-chat-messages {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
  -webkit-overflow-scrolling: touch;
}

.group-msg {
  display: flex;
  gap: 8px;
}

.group-msg.self {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
}

.msg-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.group-msg.self .msg-avatar {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.msg-body {
  max-width: 70%;
}

.group-msg.self .msg-body {
  text-align: right;
}

.msg-sender {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 2px;
}

.msg-bubble {
  display: inline-block;
  padding: 8px 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-title);
  word-break: break-word;
  text-align: left;
}

.group-msg.self .msg-bubble {
  background: var(--primary);
  color: #fff;
}

.msg-image {
  max-width: 160px;
  max-height: 160px;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.msg-time {
  font-size: 10px;
  color: var(--text-gray);
  margin-top: 2px;
}

.group-chat-input-area {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
}

.group-chat-input {
  flex: 1;
  min-height: 36px;
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 13px;
  background: var(--bg-page);
  color: var(--text-title);
  box-sizing: border-box;
}

.group-chat-input:focus {
  outline: none;
  border-color: var(--primary);
}

.chat-send {
  padding: 6px 12px;
}

.chat-img {
  padding: 6px 10px;
  font-size: 16px;
}

/* ===================== 自定义弹窗 ===================== */
.custom-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: overlayFade 0.2s ease;
  padding-bottom: 50px;
}

@keyframes overlayFade {
  from { background: rgba(0, 0, 0, 0); }
  to { background: rgba(0, 0, 0, 0.5); }
}

.custom-dialog {
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  animation: slideUp 0.25s ease;
  -webkit-overflow-scrolling: touch;
}

.custom-dialog.small {
  max-height: 50vh;
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  background: var(--bg-card);
  z-index: 2;
}

.dialog-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.dialog-subtitle {
  font-size: 12px;
  color: var(--text-gray);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dialog-close {
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-gray);
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  flex-shrink: 0;
}

.dialog-body {
  padding: 16px;
}

.dialog-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
  position: sticky;
  bottom: 0;
  background: var(--bg-card);
}

/* 表单 */
.form-item {
  margin-bottom: 14px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 6px;
}

.form-input {
  width: 90%;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-page);
  color: var(--text-title);
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary);
}

.form-textarea {
  width: 100%;
  min-height: 80px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-page);
  color: var(--text-title);
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
}

.form-textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-row .form-item {
  flex: 1;
}

.type-cards {
  display: flex;
  gap: 10px;
}

.type-card {
  flex: 1;
  text-align: center;
  padding: 12px 8px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
}

.type-card.active {
  border-color: var(--primary);
  background: var(--primary-light);
}

.type-icon {
  font-size: 22px;
}

.type-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-top: 4px;
}

.type-desc {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 2px;
}

.dialog-btns {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.dialog-btns .action-btn {
  flex: 1;
}

.confirm-message {
  font-size: 14px;
  color: var(--text-body);
  margin: 0 0 16px;
  line-height: 1.6;
}

.invite-item {
  padding: 12px;
  background: var(--bg-page);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  border: 1px solid var(--border-color);
}

.invite-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}

.invite-item-meta {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 4px;
}

.invite-item-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

/* ===================== 讨论弹窗 ===================== */
.discuss-overlay {
  align-items: stretch;
}

.discuss-dialog {
  height: 100vh;
  max-height: 100vh;
  border-radius: 0;
  display: flex;
  flex-direction: column;
  padding-bottom: 100px;
}

.discuss-body {
  flex: 1;
  overflow: hidden;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  -webkit-overflow-scrolling: touch;
}

.message-item {
  display: flex;
  gap: 8px;
}

.message-item.self {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
}

.message-item.self .message-avatar {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.message-wrapper {
  max-width: 72%;
}

.message-item.self .message-wrapper {
  text-align: right;
}

.message-sender {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 2px;
}

.message-bubble {
  display: inline-block;
  padding: 8px 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-title);
  word-break: break-word;
  text-align: left;
}

.message-item.self .message-bubble {
  background: var(--primary);
  color: #fff;
}

.message-time {
  font-size: 10px;
  color: var(--text-gray);
  margin-top: 2px;
}

.message-input {
  flex: 1;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  font-size: 14px;
  background: var(--bg-page);
  color: var(--text-title);
  box-sizing: border-box;
}

.message-input:focus {
  outline: none;
  border-color: var(--primary);
}

/* ===================== 结对编程弹窗 ===================== */
.pair-overlay {
  align-items: stretch;
}

.pair-dialog {
  height: 100vh;
  max-height: 100vh;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}

.pair-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  -webkit-overflow-scrolling: touch;
}

.pair-problem {
  padding: 14px;
  flex-shrink: 0;
}

.pair-problem-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 8px;
}

.pair-problem-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.difficulty {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}

.diff-easy {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.diff-medium {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.diff-hard {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.pair-mode-tag {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 500;
}

.pair-problem-desc {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.7;
}

.pair-examples {
  margin-top: 12px;
  padding: 10px;
  background: var(--bg-page);
  border-radius: var(--radius-md);
}

.example-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 6px;
}

.example-item {
  font-size: 13px;
  color: var(--text-body);
  margin-bottom: 6px;
  line-height: 1.6;
}

.example-explain {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 2px;
}

.pair-hints {
  margin-top: 12px;
  padding: 10px;
  background: var(--coming-bg-color);
  border-radius: var(--radius-md);
}

.hints-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--coming);
  margin-bottom: 4px;
}

.pair-hints ul {
  margin: 0;
  padding-left: 20px;
}

.pair-hints li {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.6;
}

.pair-editor-section {
  border-top: 1px solid var(--border-color);
  padding: 12px 14px;
  flex-shrink: 0;
  background: var(--bg-card);
}

.pair-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.pair-users {
  font-size: 12px;
  color: var(--text-gray);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pair-link {
  color: var(--primary);
  margin: 0 4px;
}

.language-select {
  padding: 5px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 12px;
  background: var(--bg-page);
  color: var(--text-title);
  flex-shrink: 0;
}

.code-textarea {
  width: 100%;
  height: 200px;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-family: 'Courier New', monospace;
  font-size: 13px;
  background: var(--bg-page);
  color: var(--text-title);
  resize: vertical;
  box-sizing: border-box;
}

.code-textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.pair-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.pair-actions .action-btn {
  flex: 1;
}

.pair-result {
  margin-top: 12px;
  padding: 10px;
  border-radius: var(--radius-md);
  background: var(--bg-page);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  padding: 6px 0;
}

.result-pass {
  color: var(--pass);
}

.result-fail {
  color: var(--main-delete);
}

.result-score {
  font-size: 12px;
  font-weight: 500;
}

.result-analysis {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.6;
  margin-top: 6px;
}

.result-analysis ul {
  margin: 4px 0 0;
  padding-left: 20px;
}

.reference-solution {
  margin-top: 6px;
  padding: 8px;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-body);
}

.encouragement {
  margin-top: 6px;
  font-size: 12px;
  color: var(--coming);
  font-style: italic;
}

/* ===================== 对比成绩弹窗 ===================== */
.compare-dialog {
  max-height: 80vh;
}

.compare-body {
  padding: 16px;
}

.compare-arena {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.compare-user-card {
  background: var(--bg-page);
  border-radius: var(--radius-lg);
  padding: 14px;
  border: 1px solid var(--border-color);
}

.user-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
}

.compare-user-card .user-name {
  flex: 1;
  min-width: 0;
  font-size: 15px;
}

.user-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}

.user-badge.winner {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.user-badge.loser {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.user-badge.tie {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.user-card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-color);
}

.score-item:last-child {
  border-bottom: none;
}

.score-label {
  font-size: 13px;
  color: var(--text-gray);
}

.score-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
}

.score-value.score-high {
  color: var(--pass);
}

.score-value.score-medium {
  color: var(--coming);
}

.score-value.score-low {
  color: var(--main-delete);
}

.score-value.score-zero {
  color: var(--text-gray);
}

.status-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}

.status-value.verdict-pass {
  color: var(--pass);
}

.status-value.verdict-fail {
  color: var(--main-delete);
}

.status-value.verdict-error {
  color: var(--coming);
}

.status-value.verdict-empty {
  color: var(--text-gray);
}

.passed-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-body);
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
}

.vs-text {
  font-size: 18px;
  font-weight: 800;
  font-style: italic;
  color: var(--primary);
  background: var(--primary-light);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-brand);
}

.compare-result-banner {
  margin-top: 16px;
  padding: 14px;
  border-radius: var(--radius-md);
  text-align: center;
}

.compare-result-banner.banner-win {
  background: var(--pass-bg-color);
}

.compare-result-banner.banner-tie {
  background: var(--coming-bg-color);
}

.compare-result-banner .result-text {
  font-size: 15px;
  font-weight: 700;
}

.compare-result-banner.banner-win .result-text {
  color: var(--pass);
}

.compare-result-banner.banner-tie .result-text {
  color: var(--coming);
}

/* ===================== Markdown 渲染 ===================== */
.pair-problem-desc .md-h1,
.share-desc .md-h1,
.md-h1 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin: 10px 0 6px;
  line-height: 1.4;
}

.pair-problem-desc .md-h2,
.share-desc .md-h2,
.md-h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin: 8px 0 4px;
  line-height: 1.4;
}

.pair-problem-desc .md-h3,
.share-desc .md-h3,
.md-h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin: 6px 0 4px;
  line-height: 1.4;
}

.pair-problem-desc .md-p,
.share-desc .md-p,
.md-p {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.7;
  margin: 4px 0;
}

.pair-problem-desc .md-ul,
.share-desc .md-ul,
.md-ul {
  margin: 6px 0;
  padding-left: 20px;
}

.pair-problem-desc .md-li,
.share-desc .md-li,
.md-li {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.7;
  margin: 2px 0;
}

.pair-problem-desc .md-code,
.share-desc .md-code,
.md-code {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  background: var(--bgc-light);
  color: var(--highlight);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  word-break: break-word;
}

.pair-problem-desc .md-link,
.share-desc .md-link,
.md-link {
  color: var(--primary);
  text-decoration: none;
  word-break: break-word;
}

.pair-problem-desc .md-link:active,
.share-desc .md-link:active,
.md-link:active {
  opacity: 0.7;
}

.pair-problem-desc .md-blockquote,
.share-desc .md-blockquote,
.md-blockquote {
  margin: 6px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--primary);
  background: var(--primary-light);
  color: var(--text-body);
  font-size: 13px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
</style>