<script setup>
import { ref, computed, onMounted, nextTick, onUnmounted, watch, inject } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { saveSkip } from '@/utils/skip.js'
import RadarScanner from '@/components/RadarScanner.vue'
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
import {
  Document,
  EditPen,
  Connection,
  Reading,
  VideoCamera,
  Picture,
  Promotion,
  DataLine,
  Search,
  User,
  UserFilled,
  InfoFilled,
  Plus,
  Clock
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
let loginUser = null
const userId = ref('')

// 注入语音通话方法
const startVoiceCall = inject('startVoiceCall')
const isInCall = inject('isInCall')

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
const groupDialogData = ref({}) // 弹窗携带的数据
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

// 用户信息缓存（userId -> { username, avatar }）
const userInfoMap = ref({})

// 批量获取用户信息
const fetchUserInfos = async (userIds) => {
  if (!userIds || userIds.length === 0) return
  // 过滤掉已缓存的 ID
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

// 根据 userId 获取显示名称
const getUserName = (uid) => {
  if (!uid) return ''
  if (uid === userId.value) return '我'
  const info = userInfoMap.value[uid]
  return info ? info.username : uid
}

// 获取用户头像首字母
const getUserInitial = (uid) => {
  if (!uid) return '?'
  const info = userInfoMap.value[uid]
  if (info && info.username) {
    return info.username.charAt(0).toUpperCase()
  }
  return uid.slice(-2).toUpperCase()
}

// 获取用户头像 URL
const getUserAvatar = (uid) => {
  if (!uid) return ''
  const info = userInfoMap.value[uid]
  return info && info.avatar ? info.avatar : ''
}

// 计算是否可以邀请成员
const canInviteMember = computed(() => {
  if (!currentGroupDetail.value) return false
  const group = currentGroupDetail.value
  const isOwner = userId.value === group.creator_id
  return group.is_public || isOwner || group.role === 'admin'
})

// 导航
const navItems = [
  { label: '找学伴', value: 'find-partner' },
  { label: '我的学伴', value: 'my-partner' },
  { label: '邀请', value: 'invited' },
  { label: '共享', value: 'shared' },
  { label: '共同学习', value: 'tg-study' },
  { label: '小组', value: 'group' }
]
const currentNav = ref('find-partner')

// =============================== 弹窗滚动控制（放在变量声明之后） ===============================
watch(discussDialogVisible, (val) => {
  document.body.style.overflow = val ? 'hidden' : ''
})

watch(pairDialogVisible, (val) => {
  document.body.style.overflow = val ? 'hidden' : ''
})

watch(compareDialogVisible, (val) => {
  document.body.style.overflow = val ? 'hidden' : ''
})

// =============================== 计算属性 ===============================
const currentPageTitle = computed(() => {
  const found = navItems.find(item => item.value === currentNav.value)
  return found ? found.label : '未知页面'
})

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
/**
 * 根据用户ID列表获取用户信息（用户名、头像）
 * @param {Array|Object} arr - 用户数据数组或单个对象
 * @param {Array|string} idFields - 需要查询的ID字段名，如 ['user_id', 'invited_by']
 */
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
                if (!item.username) {
                  item.username = '用户'
                }
                if (!item.avatar) {
                  item.avatar = ''
                }
              } else if (field === 'sharer_id') {
                if (!item.sharer_name) {
                  item.sharer_name = String(id)
                }
                if (!item.sharer_avatar) {
                  item.sharer_avatar = ''
                }
              } else {
                const nameKey = field + '_name'
                if (!item[nameKey]) {
                  item[nameKey] = String(id)
                }
              }
            }
          }
        })
      })
    } else {
      console.warn('获取用户信息失败:', res.msg || '未知错误')
      list.forEach(item => {
        fields.forEach(field => {
          const id = item[field]
          if (id !== undefined && id !== null && id !== '') {
            if (field === 'user_id' || field === 'invited_by') {
              if (!item.username) {
                item.username = '用户'
              }
            } else if (field === 'sharer_id') {
              if (!item.sharer_name) {
                item.sharer_name = String(id)
              }
            } else {
              const nameKey = field + '_name'
              if (!item[nameKey]) {
                item[nameKey] = String(id)
              }
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
            if (!item.username) {
              item.username = '用户'
            }
          } else if (field === 'sharer_id') {
            if (!item.sharer_name) {
              item.sharer_name = String(id)
            }
          } else {
            const nameKey = field + '_name'
            const avatarKey = field + '_avatar'
            if (!item[nameKey]) {
              item[nameKey] = String(id)
            }
            if (!item[avatarKey]) {
              item[avatarKey] = ''
            }
          }
        }
      })
    })
  }
}

// 为共同学习列表获取用户信息
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
      ElMessage.error(res.data.error)
    } else {
      ElMessage.error('获取数据失败，请稍后重试')
    }
  } catch (e) {
    console.error('搜索学伴失败：', e)
    isScanning.value = false
    ElMessage.error('搜索失败，请重试')
  }
}

const invite = async (otherId) => {
  try {
    const res = await inviteApi({
      fromUser: userId.value,
      toUser: otherId
    })
    if (res.code) {
      ElMessage.success('邀请发送成功')
      await searchPartner()
    } else {
      ElMessage.error(res.msg || '邀请失败')
    }
  } catch (e) {
    console.error('邀请失败：', e)
    ElMessage.error('邀请失败，请重试')
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
  console.log('📞 发起语音通话：', item)
  if (startVoiceCall && item.user_id) {
    startVoiceCall(String(item.user_id))
  } else {
    ElMessage.warning('无法发起语音通话')
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
      ElMessage.success(res.data.message)
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
    'ppt': '/ppt',
    'mindmap': '/mindMap',
    'doc': '/word',
    'extension': '/reading',
    'practice': '/code',
    'video': '/video',
    'animation': '/anima',
    'question': '/paper'
  }
  const path = routeMap[rsType]
  if (path) {
    router.push(path)
  } else {
    console.log('不存在该资源，无法跳转')
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
      ElMessage.success(res.data?.message || (accept ? '已接受' : '已拒绝'))
      await fetchStudyList()
      await getInvitedList()
      await getMyPartnerList()
    }
  } catch (e) {
    console.error('操作失败：', e)
    ElMessage.error('操作失败，请重试')
  }
}

const handleDelete = async (inviteId) => {
  try {
    await ElMessageBox.confirm('确定要删除此记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await delSTApi({ invitationId: inviteId, userId: userId.value })
    if (res.code) {
      ElMessage.success(res.data?.message || '删除成功')
      await fetchStudyList()
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败：', e)
      ElMessage.error('删除失败，请重试')
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
    ElMessage.error('发送失败，请重试')
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
    ElNotification({
      title: '错误',
      message: '获取会话数据失败',
      type: 'error',
      position: 'bottom-left',
      zIndex: 9999,
      duration: 3000
    })
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
    ElMessage.warning('请先编写代码')
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
        ElNotification({
          title: '提示',
          message: '您已提交过代码，不能重复提交',
          type: 'warning',
          position: 'bottom-left',
          zIndex: 9999,
          duration: 4000
        })
        submittingPair.value = false
        return
      }
      
      const result = data?.result
      if (result) {
        pairSubmitResult.value = result
        ElMessage.success('代码提交成功')
      } else {
        ElMessage.success(data?.message || '代码提交成功')
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
      ElMessage.error(res.msg || '提交失败，请重试')
    }
  } catch (e) {
    console.error('提交代码失败：', e)
    const errorMsg = e?.response?.data?.data?.error || e?.message || ''
    if (errorMsg.includes('已提交过')) {
      ElNotification({
        title: '提示',
        message: '您已提交过代码，不能重复提交',
        type: 'warning',
        position: 'bottom-left',
        zIndex: 9999,
        duration: 4000
      })
    } else {
      ElMessage.error('提交失败，请重试')
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
      
      // 获取用户信息
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
            
            // 填充用户名和头像
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
    ElMessage.error('获取对比数据失败')
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
  // 根据获胜者id查找对应的用户名
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
const getResourceIcon = (type) => {
  const map = {
    'doc': Document,
    'practice': EditPen,
    'mindmap': Connection,
    'extension': Reading,
    'video': VideoCamera,
    'animation': Picture,
    'ppt': Promotion,
    'question': DataLine
  }
  return map[type] || Document
}

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

const getStatusLabel = (status) => {
  const map = {
    'pending': '待处理',
    'accepted': '已接受',
    'rejected': '已拒绝'
  }
  return map[status] || status || '未知'
}

// =============================== 导航切换 ===============================
// =============================== 小组相关方法 ===============================
const createGroupNameRef = ref(null)
const inviteUserIdRef = ref(null)
let _confirmCallback = null

// 弹窗通用方法
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
  if (!name) { ElMessage.warning('请输入小组名称'); return }
  groupDialogLoading.value = true
  try {
    const res = await createGroupApi({
      name,
      creator_id: userId.value,
      description: groupDialogData.value.description?.trim() || '',
      is_public: groupDialogData.value.is_public
    })
    if (res.success) {
      ElMessage.success('🎉 小组创建成功！')
      closeGroupDialog()
      loadMyGroups()
    } else {
      ElMessage.error(res.error || '创建失败')
    }
  } catch (e) {
    ElMessage.error('创建失败: ' + e.message)
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
      ElMessage.error(res.detail || '获取小组列表失败')
    }
    // 获取邀请人信息
    const inviterIds = (pendingGroupInvites.value || []).map(inv => inv.inviter_id)
    if (inviterIds.length > 0) {
      await fetchUserInfos(inviterIds)
    }
  } catch (e) {
    ElMessage.error('获取小组列表失败: ' + e.message)
  }
}

const showDiscoverGroups = async () => {
  currentGroupView.value = 'discover'
  try {
    const res = await getAllGroupsApi()
    if (res.success) {
      discoverGroups.value = res.groups || []
      // 获取创建者信息
      const creatorIds = (res.groups || []).map(g => g.creator_id)
      if (creatorIds.length > 0) {
        await fetchUserInfos(creatorIds)
      }
    } else {
      ElMessage.error(res.detail || '获取小组列表失败')
    }
  } catch (e) {
    ElMessage.error('获取小组列表失败: ' + e.message)
  }
}

const quickJoinGroup = async (groupId, groupName) => {
  try {
    const res = await joinGroupApi({ group_id: groupId, user_id: userId.value })
    if (res.success) {
      ElMessage.success('已加入 ' + groupName)
      loadMyGroups()
    } else {
      ElMessage.error(res.error || '加入失败')
    }
  } catch (e) {
    ElMessage.error('加入失败: ' + e.message)
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
    // 批量获取用户信息
    const userIds = []
    if (detailRes.group?.members) {
      detailRes.group.members.forEach(m => userIds.push(m.user_id))
    }
    if (msgRes.messages) {
      msgRes.messages.forEach(m => userIds.push(m.sender_id))
    }
    await fetchUserInfos(userIds)
    try {
      const compRes = await getGroupCompetitionsApi(groupId)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } catch(e) {}
    startGroupChatPolling(groupId)
  } catch (e) {
    ElMessage.error('获取小组详情失败: ' + e.message)
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
      // 获取新消息中未缓存的用户信息
      if (res.messages) {
        const userIds = res.messages.map(m => m.sender_id)
        await fetchUserInfos(userIds)
      }
    }
  } catch(e) {}
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
  } catch(e) {
    ElMessage.error('发送失败')
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
      ElMessage.error(res.error || '上传失败')
    }
  } catch(e) {
    ElMessage.error('上传失败: ' + e.message)
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
      ElMessage.success('已退出')
      closeGroupDialog()
      backToGroupList()
      loadMyGroups()
    } else {
      ElMessage.error(res.error || '退出失败')
    }
  } catch(e) {
    ElMessage.error('退出失败: ' + e.message)
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
      ElMessage.success('小组已解散')
      closeGroupDialog()
      backToGroupList()
      loadMyGroups()
    } else {
      ElMessage.error(res.error || '解散失败')
    }
  } catch(e) {
    ElMessage.error('解散失败: ' + e.message)
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
  if (!inviteeId) { ElMessage.warning('请输入用户ID'); return }
  groupDialogLoading.value = true
  try {
    const res = await inviteToGroupApi({
      group_id: currentGroupId.value,
      inviter_id: userId.value,
      invitee_id: inviteeId
    })
    if (res.success) {
      ElMessage.success('邀请已发送')
      closeGroupDialog()
    } else {
      ElMessage.error(res.error || '邀请失败')
    }
  } catch(e) {
    ElMessage.error('邀请失败: ' + e.message)
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
      ElMessage.success(accept ? '已加入小组' : '已拒绝')
      const pendingRes = await getPendingGroupInvitesApi(userId.value)
      if (pendingRes.success) {
        pendingGroupInvites.value = pendingRes.invites || []
      }
      closeGroupDialog()
      loadMyGroups()
    } else {
      ElMessage.error(res.error || '操作失败')
    }
  } catch(e) {
    ElMessage.error('操作失败: ' + e.message)
  }
}

const showCreateCompetitionDialog = () => {
  const defaultStart = new Date(Date.now() + 5*60000).toISOString().slice(0,16)
  const defaultEnd = new Date(Date.now() + 2*3600000).toISOString().slice(0,16)
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
  if (!title) { ElMessage.warning('请输入比赛名称'); return }
  const problemCount = parseInt(groupDialogData.value.problem_count)
  if (!problemCount || problemCount < 1) { ElMessage.warning('题目数量必须是一个大于 0 的整数'); return }
  groupDialogLoading.value = true
  try {
    // 1. 创建比赛
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
      ElMessage.error(res.error || '创建失败')
      return
    }
    const compId = res.competition_id

    // 2. 生成赛题
    ElMessage.info('比赛创建成功，正在生成赛题...')
    const topic = groupDialogData.value.topic?.trim() || '编程算法'
    const genRes = await generateProblemsApi({
      competition_id: compId,
      user_id: userId.value,
      input_text: topic,
      problem_count: problemCount
    })
    if (genRes.success) {
      ElMessage.success(`已生成 ${genRes.count || problemCount} 道赛题！`)
      closeGroupDialog()
      // 刷新比赛列表
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      ElMessage.warning('比赛创建成功，但赛题生成失败: ' + (genRes.error || ''))
    }
  } catch(e) {
    ElMessage.error('创建失败: ' + e.message)
  } finally {
    groupDialogLoading.value = false
  }
}

const openCompetition = async (compId) => {
  try {
    const res = await getCompetitionDetailApi(compId)
    if (!res.success || !res.competition) {
      ElMessage.error('比赛不存在')
      return
    }
    // 打开全屏竞技场
    openCompetitionArena(res.competition)
  } catch (e) {
    ElMessage.error('加载比赛失败: ' + e.message)
  }
}

// 全屏竞技场相关
let arenaOverlay = null
let arenaData = null
let arenaCurrentIdx = 0
let arenaProblemStatus = {}
let arenaRankTimer = null
let arenaTimerInterval = null

const openCompetitionArena = async (comp) => {
  arenaData = comp
  arenaCurrentIdx = 0
  arenaProblemStatus = {}
  
  // 创建覆盖层
  arenaOverlay = document.createElement('div')
  arenaOverlay.id = 'arenaOverlay'
  arenaOverlay.style.cssText = 'position:fixed;inset:0;z-index:10000;background:#0f172a;display:flex;flex-direction:column;'
  
  arenaOverlay.innerHTML = `
    <!-- 顶栏 -->
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 20px;background:#1e293b;border-bottom:1px solid #334155;flex-shrink:0">
      <div style="display:flex;align-items:center;gap:12px">
        <button id="arenaCloseBtn" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:14px">x 退出</button>
        <span style="color:#e2e8f0;font-weight:600"><svg style="width:16px;height:16px;vertical-align:middle;margin-right:4px" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg> ${comp.title}</span>
      </div>
      <div style="display:flex;align-items:center;gap:16px">
        <span id="arenaTimer" style="color:#22c55e;font-size:14px;font-weight:600;font-family:monospace"></span>
        <span id="arenaSolvedCount" style="color:#94a3b8;font-size:13px">已通过: 0/${comp.problems?.length || 0}</span>
      </div>
    </div>
    <!-- 主体 -->
    <div style="display:flex;flex:1;overflow:hidden">
      <!-- 左侧: 题目导航 -->
      <div id="arenaNav" style="width:200px;background:#1e293b;border-right:1px solid #334155;overflow-y:auto;flex-shrink:0;padding:12px"></div>
      <!-- 中间: 题目 + 编辑器 -->
      <div style="flex:1;display:flex;flex-direction:column;overflow:hidden">
        <div id="arenaProblemArea" style="flex:1;overflow-y:auto;padding:20px"></div>
        <div style="border-top:1px solid #334155;background:#1e293b;padding:12px 20px;flex-shrink:0">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <select id="arenaLang" style="padding:6px 10px;border:1px solid #334155;border-radius:6px;background:#0f172a;color:#e2e8f0;font-size:13px;cursor:pointer">
              <option value="python">Python</option>
              <option value="cpp">C++</option>
              <option value="java">Java</option>
              <option value="javascript">JavaScript</option>
              <option value="c">C</option>
            </select>
            <div style="flex:1"></div>
            <button id="arenaPrevBtn" style="padding:6px 16px;background:#334155;color:#e2e8f0;border:none;border-radius:6px;cursor:pointer;font-size:13px">&lt; 上一题</button>
            <button id="arenaSubmitBtn" style="padding:6px 20px;background:#22c55e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600">提交</button>
            <button id="arenaNextBtn" style="padding:6px 16px;background:#334155;color:#e2e8f0;border:none;border-radius:6px;cursor:pointer;font-size:13px">下一题 &gt;</button>
          </div>
          <textarea id="arenaCodeEditor" placeholder="# 在此编写代码..." style="width:100%;height:200px;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:12px;font-family:monospace;font-size:13px;resize:none"></textarea>
        </div>
        <!-- 判分结果 -->
        <div id="arenaJudgeResult" style="display:none;padding:12px 20px;border-top:1px solid #334155;flex-shrink:0;background:#1e293b"></div>
      </div>
      <!-- 右侧: 排行 -->
      <div id="arenaRanking" style="width:300px;background:#1e293b;border-left:1px solid #334155;overflow-y:auto;flex-shrink:0;padding:12px"></div>
    </div>
  `
  
  document.body.appendChild(arenaOverlay)
  
  // 绑定事件
  document.getElementById('arenaCloseBtn').onclick = closeCompetitionArena
  document.getElementById('arenaPrevBtn').onclick = arenaPrevProblem
  document.getElementById('arenaNextBtn').onclick = arenaNextProblem
  document.getElementById('arenaSubmitBtn').onclick = arenaSubmit
  
  // 渲染左侧导航
  renderArenaNav()
  // 显示第一题
  arenaShowProblem(0)
  // 加载排行
  if (comp.status === 'running' || comp.status === 'finished') {
    arenaLoadRanking()
    if (comp.status === 'running') {
      arenaRankTimer = setInterval(arenaLoadRanking, 5000)
      arenaStartTimer()
    }
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
  arenaData = null
}

const renderArenaNav = () => {
  const nav = document.getElementById('arenaNav')
  if (!nav || !arenaData) return
  const problems = arenaData.problems || []
  let html = '<div style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:10px">题目列表</div>'
  problems.forEach((p, idx) => {
    const status = arenaProblemStatus[p.id]
    let icon = '○', color = '#64748b'
    if (status === 'accepted') { icon = '●'; color = '#22c55e' }
    else if (status === 'wrong') { icon = '●'; color = '#ef4444' }
    else if (status === 'partial') { icon = '●'; color = '#f59e0b' }
    const isActive = idx === arenaCurrentIdx
    html += `<div onclick="window.__arenaShowProblem(${idx})" style="padding:8px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;background:${isActive ? '#334155' : 'transparent'};border-left:3px solid ${isActive ? '#6366f1' : 'transparent'}">
      <div style="display:flex;align-items:center;gap:8px">
        <span style="color:${color};font-size:16px">${icon}</span>
        <span style="color:#e2e8f0;font-size:13px">${getLetter(idx)}. ${p.title}</span>
      </div>
      ${status ? `<div style="font-size:11px;color:${color};margin-top:2px;margin-left:24px">${status === 'accepted' ? '已通过' : status === 'wrong' ? '未通过' : '部分通过'}</div>` : ''}
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
  const diffClass = p.difficulty === '简单' ? 'easy' : p.difficulty === '困难' ? 'hard' : 'medium'
  
  // 更新题目描述区
  const area = document.getElementById('arenaProblemArea')
  area.innerHTML = `
    <div style="background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div style="font-size:18px;font-weight:700;color:#e2e8f0">${getLetter(idx)}. ${p.title}</div>
        <span class="p-diff ${diffClass}" style="font-size:12px">${p.difficulty} · ${p.score}分</span>
      </div>
      <div style="font-size:14px;color:#cbd5e1;line-height:1.8;white-space:pre-wrap">${p.description}</div>
    </div>
  `
  
  // 恢复编辑器内容
  const editor = document.getElementById('arenaCodeEditor')
  const savedCode = localStorage.getItem('arena_code_' + arenaData.id + '_' + p.id) || ''
  if (editor) {
    editor.value = savedCode
  }
  
  // 更新导航高亮
  renderArenaNav()
  updateSolvedCount()
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
    ElMessage.warning('请先编写代码')
    return
  }
  
  // 保存代码到 localStorage
  localStorage.setItem('arena_code_' + arenaData.id + '_' + p.id, code)
  
  const resultDiv = document.getElementById('arenaJudgeResult')
  resultDiv.style.display = 'block'
  resultDiv.innerHTML = '<div style="color:#94a3b8;font-size:13px">⏳ 评判中...</div>'
  
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
      resultDiv.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center">
        <div><span style="font-size:16px;font-weight:700;color:${res.status === 'accepted' ? '#22c55e' : res.status === 'partial' ? '#f59e0b' : '#ef4444'}">${statusText}</span>
        <span style="color:#94a3b8;font-size:13px;margin-left:12px">得分: ${res.score} · ${passText}</span></div>
        <button onclick="document.getElementById('arenaJudgeResult').style.display='none'" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:12px">关闭</button>
      </div>`
      renderArenaNav()
      updateSolvedCount()
      arenaLoadRanking()
    } else {
      resultDiv.innerHTML = `<div style="color:#ef4444;font-size:13px">${res.error || '提交失败'}</div>`
    }
  } catch (e) {
    resultDiv.innerHTML = `<div style="color:#ef4444;font-size:13px">提交失败: ${e.message}</div>`
  }
}

const updateSolvedCount = () => {
  const solved = Object.values(arenaProblemStatus).filter(s => s === 'accepted').length
  const total = (arenaData && arenaData.problems) ? arenaData.problems.length : 0
  const el = document.getElementById('arenaSolvedCount')
  if (el) el.textContent = `已通过: ${solved}/${total}`
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
      // 获取排行榜用户信息
      const userIds = ranking.map(r => r.user_id)
      await fetchUserInfos(userIds)
      let html = '<div style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:10px">实时排行</div>'
      if (ranking.length === 0) {
        html += '<div style="text-align:center;color:#64748b;padding:20px">暂无排行</div>'
      } else {
        ranking.forEach((rank, idx) => {
          const isMe = rank.user_id === userId.value
          const displayName = rank.user_id === userId.value ? '我' : (userInfoMap.value[rank.user_id]?.username || rank.user_id)
          html += `<div style="display:flex;align-items:center;padding:10px 12px;border-radius:8px;margin-bottom:6px;background:${isMe ? 'rgba(96,165,250,0.1)' : '#0f172a'};border:${isMe ? '1px solid rgba(96,165,250,0.3)' : '1px solid transparent'}">
            <div style="width:32px;height:32px;border-radius:50%;background:${idx === 0 ? 'linear-gradient(135deg,#fbbf24,#f59e0b)' : idx === 1 ? 'linear-gradient(135deg,#94a3b8,#64748b)' : idx === 2 ? 'linear-gradient(135deg,#fb923c,#ea580c)' : 'linear-gradient(135deg,#667eea,#764ba2)'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0">${idx + 1}</div>
            <div style="flex:1;margin-left:12px;font-size:13px;font-weight:600;color:#e2e8f0">${displayName}</div>
            <div style="font-size:13px;font-weight:700;color:#22c55e;margin-right:12px">${rank.total_score || 0}分</div>
            <div style="font-size:12px;color:#64748b">通过: ${rank.solved || 0}/${arenaData.problems?.length || 0}</div>
          </div>`
        })
      }
      container.innerHTML = html
    }
  } catch (e) {
    console.error('加载排行榜失败:', e)
  }
}

const startCompetition = async (compId) => {
  try {
    const res = await startCompetitionApi({ group_id: compId, user_id: userId.value })
    if (res.success) {
      ElMessage.success('比赛已开始！')
      // 刷新比赛列表
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      ElMessage.error(res.error || '开始失败')
    }
  } catch (e) {
    ElMessage.error('开始失败: ' + e.message)
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
      ElMessage.success('比赛已结束')
      closeGroupDialog()
      // 刷新比赛列表
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      ElMessage.error(res.error || '结束失败')
    }
  } catch (e) {
    ElMessage.error('结束失败: ' + e.message)
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
      ElMessage.success('比赛已删除')
      closeGroupDialog()
      // 刷新比赛列表
      const compRes = await getGroupCompetitionsApi(currentGroupId.value)
      if (compRes.success && compRes.competitions) {
        currentGroupCompetitions.value = compRes.competitions
      }
    } else {
      ElMessage.error(res.error || '删除失败')
    }
  } catch(e) {
    ElMessage.error('删除失败: ' + e.message)
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
  return String.fromCharCode(65 + idx) // A, B, C, D...
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

// =============================== 生命周期 ===============================
onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        // 判断登录用户类型
        if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
          ElMessage.warning('请进行画像构建~')
          router.push('/aiAnswer')
        }
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  await getInvitedList()//获取邀请列表
  await getMyPartnerList()//获取我的学伴列表
  await fetchStudyList()//获取共同学习列表
  await getSharedList()//获取共同学习列表
  
  // 检查路由参数，如果有 tab 参数则切换到对应导航
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
})
</script>

<template>
  <div class="nav-page-container">
    <!-- 顶部导航栏 -->
    <div class="top-nav">
      <div
        v-for="item in navItems"
        :key="item.value"
        class="nav-item"
        :class="{ active: currentNav === item.value }"
        @click="changeNav(item.value)"
      >
        {{ item.label }}
        <el-badge v-if="item.label === '邀请' && invitedNum !== 0" :value="invitedNum" class="huizhang"></el-badge>
        <el-badge v-if="item.label === '共同学习' && pendingCount !== 0" :value="pendingCount" class="huizhang"></el-badge>
        <el-badge v-if="item.label === '小组' && pendingGroupInvites.length !== 0" :value="pendingGroupInvites.length" class="huizhang"></el-badge>
      </div>
    </div>

    <!-- 页面内容区域 + 切换动画 -->
    <Transition name="slide" mode="out-in">
      <div class="page-content" :key="currentNav">
        <h2 class="page-title">{{ currentPageTitle }}</h2>

        <!-- 1. 找学伴 -->
        <div v-if="currentNav === 'find-partner'" class="find navItem">
          <div class="navItemContent">
            <!-- 搜索区域 -->
            <div class="search-section">
              <div class="search-header">
                <div class="search-icon-wrapper">
                  <el-icon :size="32"><Search /></el-icon>
                </div>
                <div class="search-info">
                  <h3 class="search-title">发现学习伙伴</h3>
                  <p class="search-desc">根据你的学习特征，智能匹配志同道合的学伴</p>
                </div>
              </div>
              
              <!-- 雷达扫描器 -->
              <div class="radar-wrapper" :class="{ 'has-result': allPartnerList?.length }">
                <RadarScanner
                  v-if="isSeeRadar"
                  ref="radarRef"
                  :scanning="isScanning"
                />
                <div class="radar-placeholder" v-else>
                  <div class="placeholder-icon">
                    <el-icon :size="56"><User /></el-icon>
                  </div>
                  <div class="placeholder-text">
                    <p class="placeholder-title">准备扫描</p>
                    <p class="placeholder-desc">点击下方按钮开始寻找你的学习伙伴</p>
                  </div>
                </div>
              </div>

              <!-- 搜索按钮 -->
              <button 
                @click="searchPartner()" 
                class="search-btn btn btn-primary" 
                :disabled="isScanning"
              >
                <el-icon v-if="!isScanning" :size="18"><Search /></el-icon>
                <span v-if="isScanning" class="btn-spinner"></span>
                {{ isScanning ? '扫描中...' : '搜索相似学伴' }}
              </button>
            </div>

            <!-- 匹配结果 -->
            <TransitionGroup name="expand-down">
              <div class="result-section" v-if="allPartnerList?.length">
                <div class="result-header">
                  <span class="result-count">找到 {{ allPartnerList.length }} 位学伴</span>
                  <span class="result-hint">点击"未邀请"按钮可发送邀请</span>
                </div>
                <div class="partner-list">
                  <div 
                    class="partner-card" 
                    v-for="(item, index) in allPartnerList" 
                    :key="item.user_id"
                    :style="{ animationDelay: (index * 0.04) + 's' }"
                  >
                    <div class="card-left">
                      <div class="avatar-wrapper">
                        <el-avatar :size="52" :src="item.avatar" class="partner-avatar">
                          {{ item.username?.[0] || '用' }}
                        </el-avatar>
                        <div class="online-dot"></div>
                      </div>

                      <div class="user-info">
                        <div class="user-name">{{ item.username || '用户' }}</div>
                        <div class="user-id">ID：{{ item.user_id }}</div>
                      </div>

                      <div class="similarity-tag">
                        <div class="similarity-score">{{ item.similarity }}</div>
                        <div class="similarity-label">匹配度</div>
                      </div>

                      <div class="reason-tag">
                        <el-icon :size="14"><InfoFilled /></el-icon>
                        <span>{{ item.reason || '根据学习特征匹配' }}</span>
                      </div>
                    </div>

                    <div class="card-right">
                      <button 
                        @click="invite(item.user_id)" 
                        class="btn invite-btn" 
                        :class="item.relationship_status === 'pending' ? 'btn-invited' : 'btn-invite'"
                        :disabled="item.relationship_status === 'pending'"
                      >
                        <el-icon v-if="item.relationship_status !== 'pending'" :size="16"><Plus /></el-icon>
                        {{ item.relationship_status === 'pending' ? '已邀请' : '邀请' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </TransitionGroup>

            <div class="empty-result" v-if="isSeeRadar && !isScanning && !allPartnerList?.length">
              <img src="@/assets/image/emptyStatus.png" alt="暂无匹配">
              <p class="empty-text">暂无匹配的学伴，稍后再试试吧</p>
            </div>
          </div>
        </div>

        <!-- 2. 我的学伴 -->
        <div v-else-if="currentNav === 'my-partner'" class="navItem">
          <div class="my-partner-section">
            <div class="section-header">
              <div class="header-left">
                <el-icon :size="24"><UserFilled /></el-icon>
                <span class="header-title">我的学伴</span>
                <span class="header-count" v-if="myPartnerList?.length">共 {{ myPartnerList.length }} 位</span>
              </div>
              <div class="header-right">
                <el-input
                  v-model="partnerSearchKeyword"
                  placeholder="搜索学伴..."
                  size="small"
                  prefix-icon="Search"
                  class="search-input"
                  clearable
                />
              </div>
            </div>

            <TransitionGroup name="expand-down">
              <div class="partner-list" v-if="filteredPartnerList?.length">
                <div 
                  class="partner-card partner-card-my" 
                  v-for="(item, index) in filteredPartnerList" 
                  :key="item.companion_id"
                  :style="{ animationDelay: (index * 0.03) + 's' }"
                >
                  <div class="card-left">
                    <div class="avatar-wrapper">
                      <el-avatar :size="52" :src="item.avatar" class="partner-avatar">
                        {{ item.username?.[0] || '用' }}
                      </el-avatar>
                      <!-- <div class="online-dot online"></div> -->
                    </div>

                    <div class="user-info">
                      <div class="user-name">{{ item.username || '用户' }}</div>
                      <div class="user-id">ID：{{ item.user_id }}</div>
                    </div>

                    <div class="phase-tag">
                      <span class="phase-label">当前阶段</span>
                      <span class="phase-value">{{ item.current_phase || '学习中' }}</span>
                    </div>

                    <div class="time-tag">
                      <el-icon :size="14"><Clock /></el-icon>
                      <span>{{ formatTime(item.established_at) }}</span>
                    </div>
                  </div>

                  <div class="card-right">
                    <div class="action-buttons">
                      <button class="btn btn-primary btn-sm" @click="handleViewProfile(item)" :disabled="isInCall">📞 通话</button>
                    </div>
                  </div>
                </div>
              </div>
              <div class="empty-state" v-else>
                <img src="@/assets/image/emptyStatus.png" alt="暂无学伴">
                <p class="empty-title">还没有学伴</p>
                <p class="empty-desc">去「找学伴」页面发现志同道合的学习伙伴吧</p>
                <button class="btn btn-primary" @click="changeNav('find-partner')">去发现学伴 →</button>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <!-- 3. 邀请 -->
        <div v-else-if="currentNav === 'invited'" class="navItem">
          <div class="tip">
            <div class="myTitle">待处理的学伴邀请</div>
          </div>
          <TransitionGroup name="expand-down">
            <div class="partner-list invitedList" v-if="inviteList?.length">
              <div class="partner-item" v-for="item in inviteList" :key="item.id">
                <div class="leftBox partnerBox">
                  <div class="partnerAvatar">
                    <el-avatar :size="45" :src="item.avatar" style="border: 1px solid #eee">
                      {{ item.username?.[0] || '用' }}
                    </el-avatar>
                  </div>
                  <div class="mesPartners">
                    <div class="partnerDetails">
                      <div class="partnerUsername">{{ item.username || '用户' }}</div>
                      <div class="partnerId">ID：{{ item.invited_by }}</div>
                    </div>
                    <div class="reason">
                      <div class="partnerSimilarityText">{{ item.status === 'pending' ? '待处理': '已处理' }}</div>
                      <div class="partnerReasonText">邀请时间：{{ formatTime(item.created_at) }}</div>
                    </div>
                  </div>
                </div>
                <div class="rightBox">
                  <div class="invitedBtn" v-if="item.status === 'pending'">
                    <button @click="isAccept(item.id,false)" class="btn btn-secondary btn-sm" :disabled="item.status === 'pending' ? false:true">拒绝</button>
                    <button @click="isAccept(item.id,true)" class="btn btn-success btn-sm" :disabled="item.status === 'pending' ? false:true">通过</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="null" v-else>
              <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
              <div class="mainNullText">暂无学伴邀请</div>
            </div>
          </TransitionGroup>
        </div>

        <!-- 4. 共享 -->
        <div v-else-if="currentNav === 'shared'" class="navItem">
          <div class="tip">
            <div class="myTitle">学伴共享的资料库</div>
          </div>
          <TransitionGroup name="expand-down">
            <div class="partner-list sharedList" v-if="sharedList?.length">
              <div class="partner-item" v-for="item in sharedList" :key="item.resource_id">
                <div class="leftBox partnerBox">
                  <div class="resource-icon" :class="getResourceIconClass(item.resource_type)">
                    <el-icon :size="28"><component :is="getResourceIcon(item.resource_type)" /></el-icon>
                  </div>
                  <div class="partnerDetails sharedDetails">
                    <div class="partnerUsername">
                      <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                      {{ item.title || '未命名资源' }}
                    </div>
                    <div class="partnerId">
                      <el-avatar :size="20" :src="item.sharer_avatar" style="margin-right: 4px; vertical-align: middle;">
                        {{ item.sharer_name?.[0] || '用' }}
                      </el-avatar>
                      分享人：{{ item.sharer_name || item.sharer_id || '用户' }}
                    </div>
                  </div>
                  <div class="reason sharedReason">
                    <div class="partnerReasonText">分享时间：{{ formatTime(item.created_at) }}</div>
                  </div>
                </div>
                <div class="rightBox">
                  <button @click="viewRs(item.resource_type,item.resource_id)" class="btn btn-secondary btn-sm">查看</button>
                </div>
              </div>
            </div>
            <div class="null" v-else>
              <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
              <div class="mainNullText">暂无学伴分享的资料</div>
            </div>
          </TransitionGroup>
        </div>

        <!-- 5. 共同学习 -->
        <div v-else-if="currentNav === 'tg-study'" class="navItem">
          <div class="study-list-wrap">
            <div class="tip">
              <div class="myTitle">共学记录</div>
              <div class="tip-content" style="font-size:13px;color:#909399;">
                显示所有共学相关的记录
                <span v-if="pendingCount > 0" style="color:#E6A23C;font-weight:600;">（有 {{ pendingCount }} 条待处理）</span>
              </div>
            </div>
            <TransitionGroup name="expand-down">
              <div class="partner-list STList" v-if="studyList?.length">
                <div class="partner-item" v-for="item in studyList" :key="item.id + '_' + (item._type || 'record')">
                  <div class="leftBox partnerBox">
                    <div class="resource-icon" :class="getResourceIconClass(item.resource_type)">
                      <el-icon :size="28"><component :is="getResourceIcon(item.resource_type)" /></el-icon>
                    </div>
                    <div class="partnerDetails sharedDetails">
                      <div class="partnerUsername">
                        <template v-if="item._type === 'pending'">
                          <span class="inviter-name">{{ item.inviter_name || item.inviter_id }}</span>
                          邀请你共学
                          <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                          <span class="status-tag status-pending-tag">待处理</span>
                        </template>
                        <template v-else-if="item._type === 'sent'">
                          你邀请 <span class="inviter-name">{{ item.invitee_name || item.invitee_id }}</span>
                          共学 <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                          <span :class="['status-tag', item.status === 'pending' ? 'status-pending-tag' : 'status-accepted-tag']">
                            {{ item.status === 'pending' ? '等待响应' : '已接受' }}
                          </span>
                        </template>
                        <template v-else>
                          <span class="inviter-name">{{ item.inviter_name || item.inviter_id }}</span>
                          与 <span class="inviter-name">{{ item.invitee_name || item.invitee_id }}</span>
                          共学 <span class="resource-tag">{{ getResourceTypeLabel(item.resource_type) }}</span>
                          <span :class="['status-tag', item.status === 'accepted' ? 'status-accepted-tag' : 'status-rejected-tag']">
                            {{ getStatusLabel(item.status) }}
                          </span>
                          <span v-if="item.mode === 'pair'" class="mode-tag pair">结对编程</span>
                          <span v-else class="mode-tag separate">独立作答</span>
                        </template>
                      </div>
                      <div class="partnerId resource-title">{{ item.title || '未命名资源' }}</div>
                      <div class="partnerId">
                        <template v-if="item._type === 'pending' || item._type === 'sent'">
                          模式：{{ item.mode === 'pair' ? '结对编程' : '独立作答' }}
                          <span class="partner-time">· {{ formatTime(item.created_at) }}</span>
                        </template>
                        <template v-else>
                          创建：{{ formatTime(item.created_at) }}
                          <span v-if="item.responded_at">· 响应：{{ formatTime(item.responded_at) }}</span>
                        </template>
                      </div>
                    </div>
                  </div>
                  <div class="rightBox">
                    <template v-if="item._type === 'pending'">
                      <button @click="handleAccept(item.id, false)" class="btn btn-secondary btn-sm">拒绝</button>
                      <button @click="handleAccept(item.id, true)" class="btn btn-success btn-sm">接受</button>
                    </template>
                    <template v-else-if="item._type === 'sent' && item.status === 'pending'">
                      <button @click="handleDelete(item.id)" class="btn btn-danger btn-sm">删除</button>
                    </template>
                    <template v-else>
                      <button @click="handleDiscuss(item)" class="btn btn-primary btn-sm">讨论</button>
                      <template v-if="item.resource_type === 'practice'">
                        <button v-if="item.mode === 'pair'" @click="handlePairProgramming(item)" class="btn btn-success btn-sm">结对编程</button>
                        <button v-else @click="handleCompareScore(item)" class="btn btn-warning btn-sm">对比成绩</button>
                        <button v-if="item.mode !== 'pair'" @click="handleGoAnswer(item)" class="btn btn-secondary btn-sm">去作答</button>
                      </template>
                      <template v-else>
                        <button @click="handleView(item)" class="btn btn-secondary btn-sm">查看</button>
                      </template>
                      <button @click="handleDelete(item.id)" class="btn btn-danger btn-sm">删除</button>
                    </template>
                  </div>
                </div>
              </div>
              <div class="null" v-else>
                <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
                <div class="mainNullText">暂无共学记录</div>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <!-- 6. 小组 -->
        <div v-else-if="currentNav === 'group'" class="navItem">
          <div class="study-list-wrap group-wrap">
            <div class="tip">
              <div class="myTitle">学习小组</div>
              <div class="tip-content" style="font-size:13px;color:#909399;">
                创建或加入学习小组，与成员一起学习和比赛
              </div>
            </div>
            <div class="group-actions-bar">
              <button @click="showCreateGroupDialog" class="btn btn-primary btn-sm"><el-icon><Plus /></el-icon> 创建小组</button>
              <button @click="showDiscoverGroups" class="btn btn-success btn-sm"><el-icon><Search /></el-icon> 发现小组</button>
              <button @click="loadMyGroups" class="btn btn-warning btn-sm"><el-icon><List /></el-icon> 我的小组</button>
            </div>
            
            <!-- 待处理邀请通知 -->
            <div v-if="pendingGroupInvites.length > 0" class="group-invite-banner" @click="showPendingInvitesDialog">
              <span><el-icon><Message /></el-icon> 你有 {{ pendingGroupInvites.length }} 条小组邀请待处理</span>
              <button class="btn btn-danger btn-sm">查看 →</button>
            </div>
            
            <!-- 小组列表视图 -->
            <div v-if="currentGroupView === 'list'" class="group-content">
              <div v-if="myGroups.length === 0 && pendingGroupInvites.length === 0" class="empty-state">
                <div class="empty-icon"><el-icon :size="48"><User /></el-icon></div>
                <p>还没有加入任何小组</p>
                <button @click="showDiscoverGroups" class="btn btn-success btn-sm" style="margin-top:12px"><el-icon><Search /></el-icon> 发现小组</button>
              </div>
              <div v-else class="group-grid">
                <div v-for="group in myGroups" :key="group.id" class="group-card" @click="openGroupDetail(group.id)">
                  <div class="group-avatar">{{ group.name.charAt(0).toUpperCase() }}</div>
                  <div class="group-info">
                    <div class="group-name">
                      {{ group.name }}&nbsp;&nbsp;&nbsp;
                      <span style="font-size:11px;color:#888">
                        <el-icon v-if="group.role === 'owner'" :size="12"><Setting /></el-icon>
                        <el-icon v-else-if="group.role === 'admin'" :size="12"><Service /></el-icon>
                        <el-icon v-else :size="12"><User /></el-icon>
                        {{ group.role === 'owner' ? '创建者' : group.role === 'admin' ? '管理员' : '成员' }}
                      </span>
                    </div>
                    <div class="group-meta">{{ group.description || '暂无描述' }} · {{ group.member_count || 0 }} 人</div>
                  </div>
                  <span style="font-size:18px;color:#ccc">→</span>
                </div>
              </div>
            </div>
            
            <!-- 小组详情视图 -->
            <div v-else-if="currentGroupView === 'detail' && currentGroupDetail" class="group-detail-view">
              <div class="group-back-bar">
                <button @click="backToGroupList" class="group-back-btn">
                  <el-icon><ArrowLeft /></el-icon>
                  <span>返回小组列表</span>
                </button>
              </div>
              <div style="display:flex;gap:16px;flex-wrap:nowrap">
                <!-- 左侧：小组信息 -->
                <div style="width:220px;flex-shrink:0">
                  <div class="group-detail-card">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
                      <div class="group-avatar" style="width:40px;height:40px;font-size:18px">{{ currentGroupDetail.name.charAt(0).toUpperCase() }}</div>
                      <div>
                        <strong style="font-size:15px">{{ currentGroupDetail.name }}</strong>
                        <div style="font-size:12px;color:#888">{{ currentGroupDetail.members?.length || 0 }} 人</div>
                      </div>
                    </div>
                    <div style="font-size:12px;font-weight:600;color:#888;margin-bottom:6px">成员</div>
                    <div style="margin-bottom:10px">
                      <span v-for="member in currentGroupDetail.members" :key="member.user_id" class="group-member-tag">
                        {{ getUserName(member.user_id) }}
                        <el-icon v-if="member.role === 'owner'" :size="12" style="margin-left:2px"><Crown /></el-icon>
                        <el-icon v-else-if="member.role === 'admin'" :size="12" style="margin-left:2px"><Shield /></el-icon>
                      </span>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px">
                      <button v-if="canInviteMember" @click="showInviteMemberDialog" class="btn btn-primary btn-sm" style="width:100%"><el-icon><UserFilled /></el-icon> 邀请成员</button>
                      <button v-if="currentGroupDetail.creator_id === userId" @click="showCreateCompetitionDialog" class="btn btn-warning btn-sm" style="width:100%"><el-icon><Trophy /></el-icon> 发布比赛</button>
                      <button v-if="currentGroupDetail.creator_id === userId" @click="dissolveGroup(currentGroupId)" class="btn btn-danger btn-sm" style="width:100%"><el-icon><Delete /></el-icon> 解散小组</button>
                      <button v-else @click="leaveGroupWithConfirm(currentGroupId)" class="btn btn-secondary btn-sm" style="width:100%">退出小组</button>
                    </div>
                  </div>
                </div>
                
                <!-- 中间：比赛列表 -->
                <div style="flex:1;min-width:0">
                  <div style="font-size:14px;font-weight:600;margin-bottom:10px"><el-icon><Trophy /></el-icon> 比赛</div>
                  <div v-if="currentGroupCompetitions.length === 0" class="empty-state" style="padding:20px">
                    <p>暂无比赛</p>
                  </div>
                  <div v-else>
                    <div v-for="comp in currentGroupCompetitions" :key="comp.id" class="comp-card">
                      <div class="comp-header">
                        <div class="comp-title"><el-icon><Trophy /></el-icon> {{ comp.title }}</div>
                        <span class="comp-status" :class="comp.status">
                          {{ comp.status === 'pending' ? '待开始' : comp.status === 'running' ? '进行中' : '已结束' }}
                        </span>
                      </div>
                      <div class="comp-meta">
                        {{ comp.problem_count || 0 }} 道题 · {{ formatCompTime(comp.start_at) }}~{{ formatCompTime(comp.end_at) }}
                      </div>
                      <div class="comp-actions">
                        <button v-if="comp.status === 'pending' || comp.status === 'running'" @click="openCompetition(comp.id)" class="btn btn-primary btn-sm">
                          <el-icon v-if="comp.status === 'pending'"><Edit /></el-icon>
                          <el-icon v-else><VideoPlay /></el-icon>
                          {{ comp.status === 'pending' ? '管理赛题' : '进入比赛' }}
                        </button>
                        <button v-if="comp.status === 'finished'" @click="openCompetition(comp.id)" class="btn btn-secondary btn-sm"><el-icon><DataLine /></el-icon> 查看排行</button>
                        <button v-if="comp.created_by === userId && comp.status === 'pending'" @click="startCompetition(comp.id)" class="btn btn-success btn-sm"><el-icon><VideoPlay /></el-icon> 开始</button>
                        <button v-if="comp.created_by === userId && comp.status === 'running'" @click="endCompetition(comp.id)" class="btn btn-danger btn-sm"><el-icon><VideoPause /></el-icon> 结束</button>
                        <button v-if="comp.created_by === userId" @click="deleteCompetition(comp.id)" class="btn btn-danger btn-sm"><el-icon><Delete /></el-icon></button>
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- 右侧：聊天 -->
                <div style="width:520px;flex-shrink:0">
                  <div class="group-chat-card">
                    <div style="font-size:14px;font-weight:600;margin-bottom:10px"><el-icon><ChatDotRound /></el-icon> 群聊</div>
                    <div class="group-chat-messages">
                      <div v-for="msg in currentGroupMessages" :key="msg.id" class="group-msg" :style="{ flexDirection: msg.sender_id === userId ? 'row-reverse' : 'row' }">
                        <div class="msg-avatar" :style="{ background: msg.sender_id === userId ? 'linear-gradient(135deg,#22c55e,#16a34a)' : '' }">
                          <img v-if="getUserAvatar(msg.sender_id)" :src="getUserAvatar(msg.sender_id)" style="width:100%;height:100%;border-radius:8px;object-fit:cover">
                          <span v-else>{{ getUserInitial(msg.sender_id) }}</span>
                        </div>
                        <div class="msg-body" :style="{ textAlign: msg.sender_id === userId ? 'right' : 'left' }">
                          <div class="msg-sender">{{ getUserName(msg.sender_id) }}</div>
                          <div class="msg-bubble" :style="{ background: msg.sender_id === userId ? '#667eea' : '', color: msg.sender_id === userId ? '#fff' : '' }">
                            <img v-if="msg.msg_type === 'image'" :src="msg.content" @click="window.open(msg.content, '_blank')" alt="图片" style="max-width:200px;max-height:200px;border-radius:8px;cursor:pointer">
                            <span v-else>{{ msg.content }}</span>
                          </div>
                          <div class="msg-time">{{ (msg.created_at || '').slice(11,19) }}</div>
                        </div>
                      </div>
                      <div v-if="currentGroupMessages.length === 0" style="text-align:center;color:#aaa;padding:20px">暂无消息</div>
                    </div>
                    <div style="display:flex;gap:8px;margin-top:12px">
                      <input v-model="groupChatInput" type="text" placeholder="输入消息..." class="group-chat-input" @keydown.enter="sendGroupMessage">
                      <button @click="sendGroupMessage" class="btn btn-primary btn-sm">发送</button>
                      <input type="file" ref="groupImageInputRef" accept="image/*" style="display:none" @change="uploadGroupImage">
                      <!-- <button @click="$refs.groupImageInputRef.click()" class="btn btn-secondary btn-sm"><el-icon><Picture /></el-icon></button> -->
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 发现小组视图 -->
            <div v-else-if="currentGroupView === 'discover'" class="group-content">
              <div class="group-back-bar">
                <button @click="currentGroupView = 'list'" class="group-back-btn">
                  <el-icon><ArrowLeft /></el-icon>
                  <span>返回我的小组</span>
                </button>
              </div>
              <div style="margin-bottom:12px;font-size:14px;font-weight:600;color:#333"><el-icon><Search /></el-icon> 发现公开小组</div>
              <div v-if="discoverGroups.length === 0" class="empty-state">
                <div class="empty-icon"><el-icon :size="48"><Search /></el-icon></div>
                <p>暂无公开小组，创建一个吧</p>
              </div>
              <div v-else class="group-grid">
                <div v-for="group in discoverGroups" :key="group.id" class="group-card">
                  <div class="group-avatar">{{ group.name.charAt(0).toUpperCase() }}</div>
                  <div class="group-info">
                    <div class="group-name">{{ group.name }}&nbsp;&nbsp;&nbsp;<span style="font-size:11px;color:#888"><el-icon :size="12"><Sunny /></el-icon> 公开</span></div>
                    <div class="group-meta">创建者: {{ getUserName(group.creator_id) }} · {{ group.member_count || 0 }} 人</div>
                  </div>
                  <button @click.stop="quickJoinGroup(group.id, group.name)" class="btn btn-success btn-sm">加入</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 小组自定义弹窗 -->
    <!-- 创建小组弹窗 -->
    <div v-if="groupDialogType === 'create'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog" style="max-width:450px">
        <div class="dialog-header">
          <span class="dialog-title"><el-icon><Edit /></el-icon> 创建学习小组</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">小组名称 *</label>
            <input v-model="groupDialogData.name" type="text" placeholder="取一个响亮的名字" class="group-dialog-input" ref="createGroupNameRef">
          </div>
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">小组描述</label>
            <textarea v-model="groupDialogData.description" placeholder="介绍一下你们小组..." class="group-dialog-textarea"></textarea>
          </div>
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333;margin-bottom:6px;display:block">小组类型</label>
            <div style="display:flex;gap:12px">
              <label class="group-type-card" :class="{ active: groupDialogData.is_public }" @click="groupDialogData.is_public = true">
                <div style="font-size:18px"><el-icon><Sunny /></el-icon></div>
                <div style="font-size:13px;font-weight:600;margin-top:2px">公开小组</div>
                <div style="font-size:11px;color:#888">任何人可加入</div>
              </label>
              <label class="group-type-card" :class="{ active: !groupDialogData.is_public }" @click="groupDialogData.is_public = false">
                <div style="font-size:18px"><el-icon><Lock /></el-icon></div>
                <div style="font-size:13px;font-weight:600;margin-top:2px">私密小组</div>
                <div style="font-size:11px;color:#888">需邀请才能加入</div>
              </label>
            </div>
          </div>
          <button @click="doCreateGroup" class="group-dialog-btn primary" :disabled="groupDialogLoading">
            {{ groupDialogLoading ? '创建中...' : '创建' }}
          </button>
          <button @click="closeGroupDialog" class="group-dialog-btn cancel">取消</button>
        </div>
      </div>
    </div>

    <!-- 邀请成员弹窗 -->
    <div v-if="groupDialogType === 'invite'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog" style="max-width:400px">
        <div class="dialog-header">
          <span class="dialog-title"><el-icon><UserFilled /></el-icon> 邀请成员</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">输入用户ID</label>
            <input v-model="groupDialogData.invitee_id" type="text" placeholder="例如: user_002" class="group-dialog-input" ref="inviteUserIdRef">
          </div>
          <button @click="doInviteToGroup" class="group-dialog-btn primary" :disabled="groupDialogLoading"><el-icon><Message /></el-icon> 发送邀请</button>
          <button @click="closeGroupDialog" class="group-dialog-btn cancel">取消</button>
        </div>
      </div>
    </div>

    <!-- 待处理邀请弹窗 -->
    <div v-if="groupDialogType === 'pending'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog" style="max-width:500px;max-height:70vh;overflow-y:auto">
        <div class="dialog-header">
          <span class="dialog-title"><el-icon><Message /></el-icon> 小组邀请 ({{ pendingGroupInvites.length }})</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div v-if="pendingGroupInvites.length === 0" style="text-align:center;color:#aaa;padding:30px">暂无待处理的邀请</div>
          <div v-for="inv in pendingGroupInvites" :key="inv.id" class="group-invite-item">
            <div style="font-size:14px;font-weight:600"><el-icon><Lock /></el-icon> {{ inv.group_name }}</div>
            <div style="font-size:12px;color:#888">邀请人: {{ getUserName(inv.inviter_id) }} · {{ inv.member_count || 0 }} 人</div>
            <div style="margin-top:10px;display:flex;gap:8px">
              <button @click="respondGroupInvite(inv.id, true)" class="btn btn-success btn-sm"><el-icon><Check /></el-icon> 接受</button>
              <button @click="respondGroupInvite(inv.id, false)" class="btn btn-secondary btn-sm"><el-icon><Close /></el-icon> 拒绝</button>
            </div>
          </div>
          <button @click="closeGroupDialog" class="group-dialog-btn cancel">关闭</button>
        </div>
      </div>
    </div>

    <!-- 发布比赛弹窗 -->
    <div v-if="groupDialogType === 'competition'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog" style="max-width:500px">
        <div class="dialog-header">
          <span class="dialog-title"><el-icon><Trophy /></el-icon> 发布比赛</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">比赛名称 *</label>
            <input v-model="groupDialogData.title" type="text" placeholder="例如：算法挑战赛" class="group-dialog-input">
          </div>
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">比赛描述</label>
            <textarea v-model="groupDialogData.description" placeholder="描述一下比赛内容..." class="group-dialog-textarea" style="min-height:60px"></textarea>
          </div>
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">比赛主题（用于生成赛题）</label>
            <textarea v-model="groupDialogData.topic" placeholder="输入比赛主题/知识点，例如：动态规划、字符串处理..." class="group-dialog-textarea" style="min-height:60px"></textarea>
          </div>
          <div style="margin-bottom:14px">
            <label style="font-size:13px;font-weight:600;color:#333">题目数量</label>
            <input v-model="groupDialogData.problem_count" type="number" min="1" max="20" class="group-dialog-input">
          </div>
          <div style="display:flex;gap:12px;margin-bottom:14px">
            <div style="flex:1">
              <label style="font-size:13px;font-weight:600;color:#333">开始时间</label>
              <input v-model="groupDialogData.start_at" type="datetime-local" class="group-dialog-input">
            </div>
            <div style="flex:1">
              <label style="font-size:13px;font-weight:600;color:#333">结束时间</label>
              <input v-model="groupDialogData.end_at" type="datetime-local" class="group-dialog-input">
            </div>
          </div>
          <button @click="doCreateCompetition" class="group-dialog-btn primary" :disabled="groupDialogLoading">
            {{ groupDialogLoading ? '创建中...' : '创建并生成赛题' }}
          </button>
          <button @click="closeGroupDialog" class="group-dialog-btn cancel">取消</button>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="groupDialogType === 'confirm'" class="custom-overlay" @click.self="closeGroupDialog">
      <div class="custom-dialog" style="max-width:400px">
        <div class="dialog-header">
          <span class="dialog-title">{{ groupDialogData.title || '确认' }}</span>
          <button class="dialog-close" @click="closeGroupDialog">×</button>
        </div>
        <div class="dialog-body">
          <p style="margin-bottom:20px;color:#666">{{ groupDialogData.message }}</p>
          <button @click="doConfirmAction" class="group-dialog-btn danger" :disabled="groupDialogLoading">
            {{ groupDialogLoading ? '处理中...' : (groupDialogData.confirmText || '确定') }}
          </button>
          <button @click="closeGroupDialog" class="group-dialog-btn cancel">取消</button>
        </div>
      </div>
    </div>

    <!-- 自定义讨论弹窗 -->
    <div v-if="discussDialogVisible" class="custom-overlay" @click.self="closeDiscussDialog">
      <div class="custom-dialog discuss-dialog">
        <div class="dialog-header">
          <div class="dialog-header-left">
            <span class="dialog-title">讨论</span>
            <span class="dialog-subtitle">{{ currentDiscussItem?.title || '' }}</span>
          </div>
          <div class="dialog-header-right">
            <span class="online-status">
              <span class="status-dot"></span>
              实时交流
            </span>
            <button class="dialog-close" @click="closeDiscussDialog">×</button>
          </div>
        </div>
        <div class="dialog-body">
          <div class="message-list" ref="messageListRef">
            <div
              v-for="msg in discussMessages"
              :key="msg.id"
              class="message-item"
              :class="{ self: msg.sender_id === userId }"
            >
              <div class="message-avatar">
                <el-avatar :size="34" :src="msg.sender_avatar">
                  {{ msg.sender_name?.[0] || 'U' }}
                </el-avatar>
              </div>
              <div class="message-wrapper">
                <div class="message-sender">{{ msg.sender_name }}</div>
                <div class="message-bubble">
                  <div class="message-content">{{ msg.content }}</div>
                </div>
                <div class="message-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>
            <div v-if="!discussMessages.length" class="empty-message">
              <div class="empty-text">暂无消息，开始交流吧</div>
            </div>
          </div>
        </div>
        <div class="dialog-footer">
          <div class="message-input-area">
            <input
              v-model="discussInput"
              class="message-input"
              placeholder="输入消息..."
              @keyup.enter="sendDiscussMessage"
              :disabled="isSending"
            />
            <button class="btn btn-primary btn-sm" @click="sendDiscussMessage" :disabled="isSending">
              {{ isSending ? '发送中...' : '发送' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 自定义结对编程弹窗 -->
    <div v-if="pairDialogVisible" class="custom-overlay" @click.self="closePairDialog">
      <div class="custom-dialog pair-dialog">
        <div class="dialog-header">
          <span class="dialog-title">结对编程</span>
          <button class="dialog-close" @click="closePairDialog">×</button>
        </div>
        <div class="dialog-body pair-container">
          <div class="pair-left">
            <div class="pair-problem">
              <h3>{{ pairProblem?.title || '题目' }}</h3>
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
          </div>
          <div class="pair-right">
            <div class="pair-editor-header">
              <span class="pair-users">
                {{ pairItem?.inviter_name || pairItem?.inviter_id }}
                <span style="color:#909399;margin:0 8px;">⟷</span>
                {{ pairItem?.invitee_name || pairItem?.invitee_id }}
              </span>
              <div class="pair-language-selector">
                <label class="language-label">语言：</label>
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
            </div>
            <div class="pair-editor">
              <textarea
                :value="pairCodeContent"
                class="code-textarea"
                placeholder="在这里编写代码..."
                @input="onCodeChange"
              ></textarea>
            </div>
            <div class="pair-actions">
              <button class="btn btn-secondary btn-sm" @click="closePairDialog">关闭</button>
              <button 
                class="btn btn-warning btn-sm" 
                @click="submitPairCode" 
                :disabled="submittingPair"
                :class="{ 'btn-loading': submittingPair }"
              >
                <span v-if="submittingPair" class="loading-spinner"></span>
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

    <!-- 自定义对比成绩弹窗 -->
    <div v-if="compareDialogVisible" class="custom-overlay" @click.self="closeCompareDialog">
      <div class="custom-dialog compare-dialog">
        <div class="dialog-header">
          <span class="dialog-title">成绩对比</span>
          <button class="dialog-close" @click="closeCompareDialog">×</button>
        </div>
        <div class="dialog-body compare-body">
          
          <div class="compare-arena">
            <div class="compare-user-card user-a">
              <div class="user-card-header">
                <div class="user-avatar">
                  <el-avatar :size="40" :src="compareData?.user_a_avatar">
                    {{ compareData?.user_a_name?.[0] || 'A' }}
                  </el-avatar>
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

            <div class="compare-user-card user-b">
              <div class="user-card-header">
                <div class="user-avatar">
                  <el-avatar :size="40" :src="compareData?.user_b_avatar">
                    {{ compareData?.user_b_name?.[0] || 'B' }}
                  </el-avatar>
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
        <div class="dialog-footer compare-footer">
          <button class="btn btn-secondary" @click="closeCompareDialog">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>


<style scoped>
/* ================= 列表入场动画 ================= */
.partner-card,
.partner-item {
  width: 100%;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 12px;
  background-color: var(--bg-card, #ffffff);
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  box-sizing: border-box;
  transition: all 0.3s ease;
  animation: fadeSlideUp 0.4s ease forwards;
  opacity: 0;
  transform: translateY(20px);
}

.partner-card:hover,
.partner-item:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-color: var(--primary, #2D7DDB);
}

.partner-card:nth-child(1),
.partner-item:nth-child(1) { animation-delay: 0.02s; }
.partner-card:nth-child(2),
.partner-item:nth-child(2) { animation-delay: 0.05s; }
.partner-card:nth-child(3),
.partner-item:nth-child(3) { animation-delay: 0.08s; }
.partner-card:nth-child(4),
.partner-item:nth-child(4) { animation-delay: 0.11s; }
.partner-card:nth-child(5),
.partner-item:nth-child(5) { animation-delay: 0.14s; }
.partner-card:nth-child(6),
.partner-item:nth-child(6) { animation-delay: 0.17s; }
.partner-card:nth-child(7),
.partner-item:nth-child(7) { animation-delay: 0.20s; }
.partner-card:nth-child(8),
.partner-item:nth-child(8) { animation-delay: 0.23s; }
.partner-card:nth-child(9),
.partner-item:nth-child(9) { animation-delay: 0.26s; }
.partner-card:nth-child(10),
.partner-item:nth-child(10) { animation-delay: 0.29s; }

@keyframes fadeSlideUp {
  0% { opacity: 0; transform: translateY(24px) scale(0.97); }
  60% { opacity: 0.7; transform: translateY(-2px) scale(1.01); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

.expand-down-enter-active,
.expand-down-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.expand-down-enter-from {
  max-height: 0;
  opacity: 0;
  transform: scale(0.95);
}
.expand-down-enter-to {
  max-height: 2000px;
  opacity: 1;
  transform: scale(1);
}
.expand-down-leave-from {
  max-height: 2000px;
  opacity: 1;
  transform: scale(1);
}
.expand-down-leave-to {
  max-height: 0;
  opacity: 0;
  transform: scale(0.95);
}

/* ================= 全局 ================= */
.huizhang {
  z-index: 3;
  position: absolute;
  top: 5px;
  right: 8px;
}
.nav-page-container {
  min-width: 1300px;
  width: 100%;
  min-height: 85vh;
  background: transparent;
}
.top-nav {
  display: flex;
  justify-content: center;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  background: transparent;
  padding: 0 20px;
}
.nav-item {
  padding: 12px 28px;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-gray, #909399);
  cursor: pointer;
  background: transparent;
  border: none;
  border-bottom: 1px solid transparent;
  margin-bottom: -1px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  letter-spacing: 1px;
}
.nav-item:hover { color: var(--primary); }
.nav-item.active { color: var(--primary); }
.nav-item::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 50%;
  width: 0;
  height: 2px;
  background: currentColor;
  transition: width 0.3s ease, left 0.3s ease;
}
.nav-item:hover::after {
  width: 100%;
  left: 0;
}
.nav-item.active::after {
  width: 100%;
  left: 0;
  background: currentColor;
}

.page-content {
  padding: 20px;
  min-height: 750px;
  background-color: var(--bg-card, #ffffff);
  border-radius: 12px;
  box-shadow: var(--shadow-normal, 0 2px 12px 0 rgba(0, 0, 0, 0.05));
  margin: 0 20px;
}
.page-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 20px;
  color: var(--text-title, #303133);
  border-left: 4px solid var(--primary);
  padding-left: 16px;
}
.navItem {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  width: 100%;
}
.navItemContent {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 1000px;
}

/* ================= 按钮 ================= */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s ease;
  background: transparent;
  outline: none;
  box-sizing: border-box;
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  pointer-events: none;
}
.btn-sm { padding: 6px 14px; font-size: 12px; border-radius: 6px; }
.btn-primary {
  background-color: var(--primary, #2D7DDB);
  border-color: var(--primary, #2D7DDB);
  color: #ffffff;
}
.btn-primary:hover:not(:disabled) {
  background-color: var(--primary-hv, #4A90E2);
  border-color: var(--primary-hv, #4A90E2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}
.btn-secondary {
  background-color: var(--bgc-light, rgba(51, 65, 85, 0.06));
  border-color: var(--border-color, #E2E8F0);
  color: var(--text-body, #334155);
}
.btn-secondary:hover:not(:disabled) {
  background-color: var(--bgc-mid, rgba(51, 65, 85, 0.12));
}
.btn-success {
  background-color: #67C23A;
  border-color: #67C23A;
  color: #ffffff;
}
.btn-success:hover:not(:disabled) {
  background-color: #5dae2f;
  border-color: #5dae2f;
  transform: translateY(-2px);
}
.btn-danger {
  background-color: #F56C6C;
  border-color: #F56C6C;
  color: #ffffff;
}
.btn-danger:hover:not(:disabled) {
  background-color: #DD4B39;
  border-color: #DD4B39;
  transform: translateY(-2px);
}
.btn-warning {
  background-color: #E6A23C;
  border-color: #E6A23C;
  color: #ffffff;
}
.btn-warning:hover:not(:disabled) {
  background-color: #c77c0c;
  border-color: #c77c0c;
  transform: translateY(-2px);
}
.btn-outline {
  background-color: transparent;
  border-color: var(--primary);
  color: var(--primary);
}
.btn-outline:hover:not(:disabled) {
  background-color: var(--primary-light, #EFF6FF);
}

.btn-loading {
  position: relative;
  padding-left: 32px;
}
.loading-spinner {
  position: absolute;
  left: 10px;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ================= 找学伴 ================= */
.search-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
}
.search-header {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
  border-radius: 12px;
  border: 1px solid #d6e8f5;
}
.search-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--primary, #2D7DDB);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.search-info { flex: 1; }
.search-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title, #303133);
  margin: 0 0 4px 0;
}
.search-desc {
  font-size: 14px;
  color: var(--text-gray, #64748B);
  margin: 0;
}

.radar-wrapper {
  width: 100%;
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bgc-light, #f8f9fa);
  border-radius: 12px;
  border: 2px dashed var(--border-color, #e4e7ed);
  transition: all 0.3s ease;
  padding: 20px;
}
.radar-wrapper.has-result {
  border-style: solid;
  border-color: var(--primary, #2D7DDB);
  background: #fff;
}

.radar-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-gray, #909399);
}
.placeholder-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--bgc-light, #f0f2f5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-gray-light, #b0b8c4);
}
.placeholder-title {
  width: 75px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-body, #334155);
  margin: 0 auto;
}
.placeholder-desc {
  font-size: 14px;
  color: var(--text-gray, #909399);
  margin: 0;
}

.search-btn {
  padding: 12px 36px;
  font-size: 16px;
  border-radius: 10px;
  min-width: 200px;
}
.search-btn .btn-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.result-section {
  width: 100%;
  margin-top: 8px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px 12px 4px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  width: 100%;
}
.result-count {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #303133);
}
.result-hint {
  font-size: 13px;
  color: var(--text-gray, #909399);
}

/* ================= 卡片通用 ================= */
.partner-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.partner-list.sharedList,
.partner-list.invitedList,
.partner-list.STList { 
  padding: 0 230px;
}

.partner-card,
.partner-item {
  width: 100%;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 12px;
  background-color: var(--bg-card, #ffffff);
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  box-sizing: border-box;
  transition: all 0.3s ease;
  animation: fadeSlideUp 0.4s ease forwards;
  opacity: 0;
  transform: translateY(20px);
}
.partner-card:hover,
.partner-item:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-color: var(--primary, #2D7DDB);
}

.card-left {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}
.partner-avatar {
  border: 2px solid var(--border-color, #e4e7ed);
}
.online-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #d0d5dd;
  border: 2px solid #fff;
}
.online-dot.online {
  background: #67C23A;
}

.user-info {
  min-width: 80px;
}
.user-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #303133);
}
.user-id {
  font-size: 12px;
  color: var(--text-gray, #909399);
}

.similarity-tag {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 12px;
  background: #E8F5E9;
  border-radius: 8px;
  min-width: 50px;
}
.similarity-score {
  font-size: 18px;
  font-weight: 700;
  color: #388E3C;
}
.similarity-label {
  font-size: 10px;
  color: #66BB6A;
}

.reason-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: var(--bgc-light, #f0f2f5);
  border-radius: 16px;
  font-size: 13px;
  color: var(--text-gray, #64748B);
}

.card-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.invite-btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-weight: 600;
  min-width: 80px;
}
.btn-invite {
  background-color: var(--primary, #2D7DDB);
  border-color: var(--primary, #2D7DDB);
  color: #ffffff;
}
.btn-invite:hover:not(:disabled) {
  background-color: var(--primary-hv, #4A90E2);
  border-color: var(--primary-hv, #4A90E2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}
.btn-invited {
  background-color: var(--bgc-light, rgba(51, 65, 85, 0.06));
  border-color: var(--border-color, #E2E8F0);
  color: var(--text-gray, #909399);
  cursor: default;
}

/* ================= 我的学伴 ================= */
.my-partner-section {
  width: 100%;
  max-width: 1000px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px 16px 4px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  width: 100%;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left .el-icon {
  color: var(--primary, #2D7DDB);
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title, #303133);
}
.header-count {
  font-size: 14px;
  color: var(--text-gray, #909399);
  background: var(--bgc-light, #f0f2f5);
  padding: 2px 12px;
  border-radius: 12px;
}
.header-right .search-input {
  width: 200px;
}
.header-right .search-input :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.partner-card-my {
  border-left: 4px solid var(--primary, #2D7DDB);
}

.phase-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #FFF3E0;
  border-radius: 16px;
}
.phase-label {
  font-size: 11px;
  color: var(--text-gray, #909399);
}
.phase-value {
  font-size: 13px;
  font-weight: 500;
  color: #E65100;
}

.time-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-gray-light, #b0b8c4);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

/* ================= 邀请、共享、共同学习通用 ================= */
.mesPartners{
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 30px;
}
.partner-item {
  border-left: 4px solid var(--primary, #2D7DDB);
}
.partner-item .partnerBox {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 15px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}
.partner-item .partnerDetails {
  color: var(--text-body, #334155);
  font-size: 15px;
  flex: 1;
  min-width: 0;
}
.partner-item .partnerDetails .partnerUsername {
  font-weight: 600;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.partner-item .partnerDetails .partnerId {
  color: var(--text-gray, #64748B);
  font-size: 12px;
  display: flex;
  align-items: center;
}
.partner-item .rightBox {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.partner-item .invitedBtn { 
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
}
.partner-item .reason {
  color: var(--text-gray, #64748B);
  font-size: 13px;
  flex-shrink: 0;
}
.partner-item .reason .partnerSimilarityText {
  font-size: 16px;
  font-weight: 700;
  color: var(--pass, #67C23A);
}
.partner-item .sharedDetails {
  max-width: 600px;
}

/* ================= 资源图标 ================= */
.resource-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
}
.resource-icon.icon-doc { background: linear-gradient(135deg, #4A90D9, #357ABD); }
.resource-icon.icon-practice { background: linear-gradient(135deg, #F5A623, #F7B731); }
.resource-icon.icon-mindmap { background: linear-gradient(135deg, #7B61FF, #6C4CE0); }
.resource-icon.icon-extension { background: linear-gradient(135deg, #4ECDC4, #36B5A8); }
.resource-icon.icon-video { background: linear-gradient(135deg, #FF6B6B, #E05555); }
.resource-icon.icon-animation { background: linear-gradient(135deg, #FF9F43, #E8832A); }
.resource-icon.icon-ppt { background: linear-gradient(135deg, #E17055, #D63031); }
.resource-icon.icon-question { background: linear-gradient(135deg, #00B894, #00A381); }
.resource-icon.icon-default { background: linear-gradient(135deg, #8395A7, #576574); }

.resource-tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
  background: var(--bgc-light, #f0f2f5);
  color: var(--text-gray, #64748B);
}
.resource-title {
  font-size: 14px !important;
  color: var(--text-body, #334155) !important;
  font-weight: 500;
}
.inviter-name { font-weight: 600; color: var(--primary, #2D7DDB); }

.status-tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.status-pending-tag { background: #FDF6EC; color: #E6A23C; }
.status-accepted-tag { background: #E8F5E9; color: #388E3C; }
.status-rejected-tag { background: #FFEBEE; color: #D32F2F; }

.mode-tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-left: 4px;
}
.mode-tag.pair { background: #E8F5E9; color: #388E3C; }
.mode-tag.separate { background: #E3F2FD; color: #1976D2; }

.sharedDetails .partnerUsername {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

/* ================= 空状态 ================= */
.null,
.empty-state {
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-gray, #64748B);
}
.null img,
.empty-state img {
  width: 160px;
}
.mainNullText,
.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-gray, #334155);
  margin: 0;
}
.empty-desc {
  font-size: 14px;
  color: var(--text-gray, #909399);
  margin: 0;
}

.tip {
  color: var(--text-gray, #64748B);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
}
.tip .tip-title { font-size: 25px; font-weight: 700; color: var(--pass, #67C23A); }
.tip .tip-content { font-size: 15px; }
.tip .myTitle { font-size: 20px; font-weight: 700; }

/* ================= 共同学习 ================= */
.study-list-wrap { width: 100%; }

/* ================= 小组相关样式 ================= */
.group-wrap { 
  width: 100%;
  padding: 0 30px;
}

/* ================= 自定义弹窗 ================= */
.custom-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  backdrop-filter: blur(4px);
  animation: overlayFadeIn 0.25s ease;
}
@keyframes overlayFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.custom-dialog {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  animation: dialogSlideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes dialogSlideUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  flex-shrink: 0;
}
.dialog-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dialog-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dialog-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title, #303133);
}
.dialog-subtitle {
  font-size: 14px;
  color: var(--text-gray, #64748B);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dialog-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 22px;
  cursor: pointer;
  color: var(--text-gray, #909399);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.dialog-close:hover {
  background: var(--bgc-light, #f0f2f5);
  color: var(--text-title, #303133);
}
.online-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #67C23A;
  background: #E8F5E9;
  padding: 4px 12px;
  border-radius: 12px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #67C23A;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.dialog-body {
  padding: 16px 20px;
  overflow: auto;
  flex: 1;
}
.dialog-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border-color, #e4e7ed);
  flex-shrink: 0;
}

/* ================= 讨论弹窗 ================= */
.discuss-dialog { width: 620px; max-width: 92vw; }
.discuss-dialog .message-list {
  min-height: 400px;
  max-height: 400px;
  overflow-y: auto;
  padding: 8px 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.discuss-dialog .message-list::-webkit-scrollbar {
  width: 4px;
}
.discuss-dialog .message-list::-webkit-scrollbar-thumb {
  background: var(--border-color, #d0d5dd);
  border-radius: 4px;
}

.discuss-dialog .message-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  animation: messageIn 0.25s ease;
}
@keyframes messageIn {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.discuss-dialog .message-item.self { flex-direction: row-reverse; }

.discuss-dialog .message-avatar {
  flex-shrink: 0;
}
.discuss-dialog .message-avatar :deep(.el-avatar) {
  border: 2px solid var(--border-color, #e4e7ed);
}
.discuss-dialog .message-item.self .message-avatar :deep(.el-avatar) {
  border-color: var(--primary, #2D7DDB);
}

.discuss-dialog .message-wrapper {
  max-width: 72%;
  display: flex;
  flex-direction: column;
}
.discuss-dialog .message-item.self .message-wrapper {
  align-items: flex-end;
}

.discuss-dialog .message-sender {
  font-size: 12px;
  color: var(--text-gray, #909399);
  margin-bottom: 2px;
  font-weight: 500;
}

.discuss-dialog .message-bubble {
  padding: 10px 16px;
  border-radius: 16px;
  background: var(--bgc-light, #f0f2f5);
  word-break: break-word;
  position: relative;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  width: fit-content;
  max-width: 100%;
}
.discuss-dialog .message-item.self .message-bubble {
  background: var(--primary, #2D7DDB);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.discuss-dialog .message-item:not(.self) .message-bubble {
  border-bottom-left-radius: 4px;
}

.discuss-dialog .message-content { font-size: 14px; line-height: 1.6; }
.discuss-dialog .message-time {
  font-size: 10px;
  color: var(--text-gray-light, #b0b8c4);
  margin-top: 3px;
}
.discuss-dialog .message-item.self .message-time { color: rgba(255,255,255,0.6); }

.discuss-dialog .empty-message {
  text-align: center;
  padding: 60px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.discuss-dialog .empty-text {
  color: var(--text-gray, #909399);
  font-size: 14px;
}

.discuss-dialog .message-input-area {
  display: flex;
  gap: 10px;
  align-items: center;
}
.discuss-dialog .message-input {
  flex: 1;
  padding: 10px 16px;
  border: 2px solid var(--border-color, #e4e7ed);
  border-radius: 10px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
  background: var(--bgc-light, #f8f9fa);
}
.discuss-dialog .message-input:focus {
  border-color: var(--primary, #2D7DDB);
  background: #fff;
}
.discuss-dialog .message-input:disabled {
  background: var(--bgc-light, #f0f2f5);
}

/* ================= 结对编程弹窗 ================= */
.pair-dialog { width: 950px; max-width: 95vw; }
.pair-container {
  display: flex;
  gap: 20px;
  min-height: 400px;
}
.pair-left {
  flex: 0 0 45%;
  overflow-y: auto;
  padding-right: 12px;
  border-right: 1px solid var(--border-color, #e4e7ed);
  max-height: 560px;
}
.pair-left::-webkit-scrollbar { width: 4px; }
.pair-left::-webkit-scrollbar-thumb {
  background: var(--border-color, #d0d5dd);
  border-radius: 4px;
}
.pair-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.pair-problem h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: var(--text-title, #303133);
}
.pair-problem-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.difficulty {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.diff-easy { background: #E8F5E9; color: #388E3C; }
.diff-medium { background: #FFF3E0; color: #E65100; }
.diff-hard { background: #FFEBEE; color: #C62828; }
.pair-mode-tag {
  font-size: 13px;
  color: var(--primary, #2D7DDB);
}
.pair-problem-desc {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-body, #334155);
  margin-bottom: 12px;
  background: var(--bgc-light, #f5f7fa);
  padding: 10px 14px;
  border-radius: 8px;
}
.pair-problem-desc :deep(.md-h1),
.pair-problem-desc :deep(.md-h2),
.pair-problem-desc :deep(.md-h3) {
  font-weight: 600;
  margin-top: 10px;
  margin-bottom: 5px;
  line-height: 1.4;
}
.pair-problem-desc :deep(.md-h1) { font-size: 18px; color: #1e293b; }
.pair-problem-desc :deep(.md-h2) { font-size: 16px; color: #334155; }
.pair-problem-desc :deep(.md-h3) { font-size: 14px; color: #475569; }
.pair-problem-desc :deep(.md-p) {
  margin: 4px 0;
  line-height: 1.7;
}
.pair-problem-desc :deep(strong) {
  font-weight: 600;
  color: #1e293b;
}
.pair-problem-desc :deep(em) {
  font-style: italic;
  color: #64748b;
}
.pair-problem-desc :deep(.md-code) {
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  color: #e11d48;
  border: 1px solid #cbd5e1;
}
.pair-problem-desc :deep(.md-ul) {
  padding-left: 20px;
  margin: 6px 0;
}
.pair-problem-desc :deep(.md-li) {
  margin: 3px 0;
  line-height: 1.6;
}
.pair-problem-desc :deep(.md-blockquote) {
  border-left: 3px solid #3b82f6;
  padding-left: 10px;
  margin: 8px 0;
  color: #64748b;
  font-style: italic;
}
.pair-problem-desc :deep(.md-link) {
  color: #3b82f6;
  text-decoration: none;
}
.pair-problem-desc :deep(.md-link:hover) {
  text-decoration: underline;
}
.pair-examples { margin-bottom: 12px; }
.example-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--text-title, #303133);
}
.example-item {
  background: var(--bgc-light, #f5f7fa);
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;
}
.example-item div { margin: 2px 0; }
.example-explain {
  color: var(--text-gray, #64748B);
  font-size: 12px;
  margin-top: 4px;
}
.pair-hints { margin-top: 8px; }
.hints-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-title, #303133);
  margin-bottom: 4px;
}
.pair-hints ul {
  margin: 4px 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-body, #334155);
}
.pair-hints ul li { margin: 3px 0; }

.pair-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bgc-light, #f5f7fa);
  border-radius: 8px 8px 0 0;
  border: 1px solid var(--border-color, #e4e7ed);
  border-bottom: none;
  font-size: 13px;
  flex-wrap: wrap;
  gap: 8px;
}
.pair-users {
  font-weight: 500;
  color: var(--text-body, #334155);
}
.pair-language-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}
.language-label {
  font-size: 12px;
  color: var(--text-gray, #64748B);
}
.language-select {
  padding: 4px 10px;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: var(--text-body, #334155);
  outline: none;
  cursor: pointer;
  font-family: inherit;
}
.language-select:focus {
  border-color: var(--primary, #2D7DDB);
}
.pair-editor {
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 0 0 8px 8px;
  flex: 1;
  min-height: 200px;
}
.pair-editor .code-textarea {
  width: 100%;
  height: 100%;
  min-height: 200px;
  border: none;
  border-radius: 0 0 8px 8px;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.7;
  resize: vertical;
  padding: 12px 14px;
  background: #1e1e2e;
  color: #cdd6f4;
  outline: none;
  box-sizing: border-box;
}
.pair-editor .code-textarea:focus { box-shadow: none; }
.pair-editor .code-textarea::placeholder { color: #6c7086; }
.pair-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
.pair-result {
  margin-top: 12px;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 8px;
  padding: 12px 16px;
  max-height: 200px;
  overflow-y: auto;
  font-size: 13px;
}
.result-header {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color, #e4e7ed);
}
.result-pass { color: #67C23A; }
.result-fail { color: #F56C6C; }
.result-score {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-gray, #64748B);
}
.result-analysis {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-body, #334155);
}
.result-analysis ul {
  margin: 4px 0;
  padding-left: 18px;
}
.result-analysis ul li { margin: 2px 0; }
.reference-solution {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--bgc-light, #f5f7fa);
  border-radius: 6px;
  font-size: 13px;
}
.encouragement {
  margin-top: 8px;
  padding: 8px 12px;
  background: #FFF8E1;
  border-radius: 6px;
  color: #E6A23C;
  font-size: 13px;
}

/* ================= 对比成绩弹窗 ================= */
.compare-dialog {
  width: 720px;
  max-width: 92vw;
}
.compare-body {
  padding: 20px 24px;
}


.compare-arena {
  display: flex;
  align-items: stretch;
  gap: 20px;
  margin-bottom: 24px;
}

.compare-user-card {
  flex: 1;
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  padding: 16px 20px 20px;
  border: 2px solid var(--border-color, #e4e7ed);
  transition: all 0.3s ease;
  min-width: 0;
}
.compare-user-card.user-a {
  border-color: #4A90D9;
  background: linear-gradient(145deg, #f0f7ff, #ffffff);
}
.compare-user-card.user-b {
  border-color: #FF6B6B;
  background: linear-gradient(145deg, #fff5f5, #ffffff);
}

.user-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.user-avatar .el-avatar {
  border: 2px solid #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.compare-user-card.user-a .user-avatar .el-avatar {
  border-color: #4A90D9;
}
.compare-user-card.user-b .user-avatar .el-avatar {
  border-color: #FF6B6B;
}

.user-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #303133);
  flex: 1;
}
.user-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 12px;
  border-radius: 12px;
  white-space: nowrap;
}
.user-badge.winner {
  background: #E8F5E9;
  color: #388E3C;
}
.user-badge.loser {
  background: #FFEBEE;
  color: #C62828;
}
.user-badge.tie {
  background: #FFF8E1;
  color: #F57F17;
}

.user-card-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
}
.score-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.score-label {
  font-size: 11px;
  color: var(--text-gray-light, #b0b8c4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.score-value {
  font-size: 26px;
  font-weight: 700;
}
.score-value.score-high { color: #388E3C; }
.score-value.score-medium { color: #F57F17; }
.score-value.score-low { color: #E65100; }
.score-value.score-zero { color: var(--text-gray-light, #b0b8c4); }

.status-value {
  font-size: 14px;
  font-weight: 600;
}
.status-value.verdict-pass { color: #388E3C; }
.status-value.verdict-fail { color: #C62828; }
.status-value.verdict-error { color: #E65100; }
.status-value.verdict-empty { color: var(--text-gray-light, #b0b8c4); }

.passed-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-body, #334155);
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 44px;
}
.vs-text {
  font-size: 20px;
  font-weight: 800;
  color: var(--primary, #2D7DDB);
  background: var(--bgc-light, #f0f2f5);
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--border-color, #e4e7ed);
}

.compare-result-banner {
  padding: 14px 20px;
  border-radius: 10px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.compare-result-banner.banner-win {
  background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
  border: 2px solid #81C784;
}
.compare-result-banner.banner-tie {
  background: linear-gradient(135deg, #FFF8E1, #FFECB3);
  border: 2px solid #FFD54F;
}
.result-text {
  font-size: 20px;
  font-weight: 700;
}
.banner-win .result-text { color: #2E7D32; }
.banner-tie .result-text { color: #F57F17; }

.compare-footer {
  display: flex;
  justify-content: center;
  padding: 12px 20px;
}

/* ============ 夜间模式适配 ============ */

/* 搜索区域 */
.dark .search-header {
  background: var(--bg-card);
  border-color: var(--border-color);
}

/* 雷达图容器 */
.dark .radar-wrapper.has-result {
  background: var(--bg-card);
}

/* 在线状态点 */
.dark .online-dot {
  border-color: var(--bg-card);
}

/* 相似度标签 */
.dark .similarity-tag {
  background: rgba(74, 222, 128, 0.1);
}

/* 阶段标签 */
.dark .phase-tag {
  background: rgba(251, 146, 60, 0.1);
}

/* 状态标签 */
.dark .status-pending-tag { background: rgba(251, 146, 60, 0.15); }
.dark .status-accepted-tag { background: rgba(74, 222, 128, 0.15); }
.dark .status-rejected-tag { background: rgba(248, 113, 113, 0.15); }

/* 模式标签 */
.dark .mode-tag.pair { background: rgba(74, 222, 128, 0.15); }
.dark .mode-tag.separate { background: rgba(59, 130, 246, 0.15); }

/* 自定义弹窗 */
.dark .custom-dialog {
  background: var(--bg-card);
}

/* 在线状态 */
.dark .online-status {
  background: rgba(74, 222, 128, 0.15);
}

/* 讨论输入框 */
.dark .discuss-dialog .message-input:focus {
  background: var(--bg-card);
}

/* 难度标签 */
.dark .diff-easy { background: rgba(74, 222, 128, 0.15); }
.dark .diff-medium { background: rgba(251, 146, 60, 0.15); }
.dark .diff-hard { background: rgba(248, 113, 113, 0.15); }

/* 问题描述markdown样式 */
.dark .pair-problem-desc :deep(.md-h1) { color: var(--text-title); }
.dark .pair-problem-desc :deep(.md-h2) { color: var(--text-body); }
.dark .pair-problem-desc :deep(.md-h3) { color: var(--text-gray); }
.dark .pair-problem-desc :deep(strong) { color: var(--text-title); }
.dark .pair-problem-desc :deep(em) { color: var(--text-gray); }
.dark .pair-problem-desc :deep(.md-code) {
  background: rgba(59, 130, 246, 0.15);
  border-color: var(--border-color);
}
.dark .pair-problem-desc :deep(.md-blockquote) { color: var(--text-gray); }
.dark .pair-problem-desc :deep(.md-link) { color: var(--primary); }

/* 语言选择器 */
.dark .language-select {
  background: var(--bg-card);
}

/* 鼓励信息 */
.dark .encouragement {
  background: rgba(251, 146, 60, 0.15);
}

/* 对比成绩弹窗 */
.dark .compare-user-card.user-a {
  background: linear-gradient(145deg, rgba(59, 130, 246, 0.1), var(--bg-card));
}

.dark .compare-user-card.user-b {
  background: linear-gradient(145deg, rgba(248, 113, 113, 0.1), var(--bg-card));
}

.dark .user-badge.winner { background: rgba(74, 222, 128, 0.15); }
.dark .user-badge.loser { background: rgba(248, 113, 113, 0.15); }
.dark .user-badge.tie { background: rgba(251, 146, 60, 0.15); }

.dark .compare-result-banner.banner-win {
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.15), rgba(74, 222, 128, 0.05));
  border-color: rgba(74, 222, 128, 0.3);
}

.dark .compare-result-banner.banner-tie {
  background: linear-gradient(135deg, rgba(251, 146, 60, 0.15), rgba(251, 146, 60, 0.05));
  border-color: rgba(251, 146, 60, 0.3);
}

/* ================= 小组相关样式 ================= */
/* 返回按钮 */
.group-back-bar {
  margin-bottom: 16px;
}
.group-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: var(--shadow-normal);
}
.group-back-btn:hover {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
  transform: translateX(-2px);
}
.group-back-btn .el-icon {
  font-size: 14px;
}

.group-actions-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.group-content {
  min-height: 200px;
}

/* 小组网格布局 */
.group-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

/* 小组卡片 */
.group-card {
  display: flex;
  align-items: center;
  padding: 16px;
  border-radius: var(--radius-lg);
  margin-bottom: 10px;
  background: var(--primary-light);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all .2s;
}
.group-card:hover {
  background: var(--bg-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-normal);
}

/* 小组头像 */
.group-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
}

/* 小组信息 */
.group-info {
  flex: 1;
  margin: 0 14px;
}
.group-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}
.group-meta {
  font-size: 12px;
  color: var(--text-gray);
}

/* 邀请通知横幅 */
.group-invite-banner {
  background: var(--pass-bg-color);
  border: 1px solid var(--pass-shadow);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all .2s;
}
.group-invite-banner:hover {
  background: var(--pass-shadow-hover);
}
.group-invite-banner span {
  font-size: 14px;
  color: var(--pass);
  font-weight: 600;
}

/* 小组详情卡片 */
.group-detail-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
  margin-bottom: 12px;
}

.group-member-tag {
  display: inline-block;
  padding: 2px 10px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  font-size: 12px;
  margin: 2px;
  color: var(--text-body);
}

/* 群聊卡片 */
.group-chat-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
}

.group-chat-messages {
  max-height: 320px;
  overflow-y: auto;
  margin-bottom: 12px;
  padding: 4px;
}

.group-chat-input {
  flex: 1;
  padding: 10px 14px;
  border: 2px solid var(--border-color);
  border-radius: 10px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.3s;
  background: var(--bg-input);
  color: var(--text-body);
}
.group-chat-input:focus {
  border-color: var(--primary);
}

/* 群聊消息 */
.group-msg {
  display: flex;
  margin-bottom: 12px;
  gap: 8px;
}
.group-msg .msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.group-msg .msg-body {
  max-width: 75%;
}
.group-msg .msg-body .msg-sender {
  font-size: 11px;
  color: var(--text-gray);
  font-weight: 600;
  margin-bottom: 2px;
}
.group-msg .msg-body .msg-bubble {
  padding: 8px 14px;
  border-radius: var(--radius-lg);
  font-size: 13px;
  background: var(--bg-hover);
  color: var(--text-body);
  display: inline-block;
}
.group-msg .msg-body .msg-bubble img {
  max-width: 200px;
  border-radius: var(--radius-md);
  margin-top: 4px;
  cursor: pointer;
  border: 1px solid var(--border-color);
}
.group-msg .msg-body .msg-time {
  font-size: 10px;
  color: var(--text-gray);
  margin-top: 2px;
}

/* 比赛卡片 */
.comp-card {
  padding: 16px;
  border-radius: var(--radius-lg);
  margin-bottom: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
}
.comp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.comp-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}
.comp-status {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 600;
}
.comp-status.pending {
  background: var(--coming-bg-color);
  color: var(--coming);
}
.comp-status.running {
  background: var(--pass-bg-color);
  color: var(--pass);
  animation: statusPulse 1.5s ease-in-out infinite;
}
@keyframes statusPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
.comp-status.finished {
  background: var(--bg-hover);
  color: var(--text-gray);
}
.comp-meta {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 6px;
}
.comp-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 邀请条目 */
.group-invite-item {
  background: var(--coming-bg-color);
  border: 1px solid var(--coming-shadow);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 10px;
}

/* 题目卡片 */
.problem-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
}
.p-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.prob-title-display {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}
.p-diff {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.p-diff.easy {
  background: var(--pass-bg-color);
  color: var(--pass);
}
.p-diff.medium {
  background: var(--coming-bg-color);
  color: var(--coming);
}
.p-diff.hard {
  background: var(--main-fail-status);
  color: var(--main-delete);
}
.p-desc {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 排行榜 */
.leaderboard-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
}
.leaderboard-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-title);
}
.live-dot {
  width: 8px;
  height: 8px;
  background: var(--pass);
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.rank-row {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  margin-bottom: 6px;
  background: var(--bg-hover);
  transition: all 0.2s;
}
.rank-row:hover {
  background: var(--bg-page);
}
.rank-row.is-me {
  background: var(--primary-light);
  border: 1px solid var(--primary-fade);
}
.rank-pos {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.rank-row:nth-child(1) .rank-pos {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
}
.rank-row:nth-child(2) .rank-pos {
  background: linear-gradient(135deg, #94a3b8, #64748b);
}
.rank-row:nth-child(3) .rank-pos {
  background: linear-gradient(135deg, #fb923c, #ea580c);
}
.rank-name {
  flex: 1;
  margin-left: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}
.rank-score {
  font-size: 13px;
  font-weight: 700;
  color: var(--pass);
  margin-right: 12px;
}
.rank-solved {
  font-size: 12px;
  color: var(--text-gray);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-gray);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-state p {
  font-size: 15px;
  margin-bottom: 16px;
}

/* 小组弹窗样式 */
.group-dialog-input {
  width: 100%;
  padding: 10px 14px;
  border: 2px solid var(--border-color);
  border-radius: 10px;
  font-size: 14px;
  margin-top: 4px;
  outline: none;
  transition: border-color 0.2s;
  background: var(--bg-input);
  color: var(--text-body);
}
.group-dialog-input:focus {
  border-color: var(--primary);
}

.group-dialog-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 2px solid var(--border-color);
  border-radius: 10px;
  font-size: 14px;
  margin-top: 4px;
  outline: none;
  min-height: 80px;
  resize: vertical;
  transition: border-color 0.2s;
  background: var(--bg-input);
  color: var(--text-body);
}
.group-dialog-textarea:focus {
  border-color: var(--primary);
}

.group-type-card {
  flex: 1;
  padding: 10px 16px;
  border: 2px solid var(--border-color);
  border-radius: 10px;
  cursor: pointer;
  text-align: center;
  transition: all .2s;
  background: var(--bg-card);
  color: var(--text-body);
}
.group-type-card.active {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}

.group-dialog-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 8px;
}
.group-dialog-btn.primary {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
}
.group-dialog-btn.primary:hover {
  opacity: 0.9;
}
.group-dialog-btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.group-dialog-btn.cancel {
  background: #f3f4f6;
  color: #666;
}
.group-dialog-btn.cancel:hover {
  background: #e5e7eb;
}
.group-dialog-btn.danger {
  background: #ef4444;
  color: #fff;
}
.group-dialog-btn.danger:hover {
  background: #dc2626;
}
.group-dialog-btn.danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 暗色模式 - 弹窗 */
.dark .group-dialog-input,
.dark .group-dialog-textarea {
  background: #1e293b;
  border-color: #334155;
  color: #e2e8f0;
}
.dark .group-type-card {
  border-color: #334155;
  background: #1e293b;
}
.dark .group-type-card.active {
  border-color: #0ea5e9;
  background: rgba(14, 165, 233, 0.1);
}
.dark .group-dialog-btn.cancel {
  background: #334155;
  color: #e2e8f0;
}

</style>