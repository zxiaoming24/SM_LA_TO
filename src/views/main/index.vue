<script setup>
import { ref, onMounted, computed,onUnmounted } from 'vue'
import { ElMessage,ElMessageBox } from 'element-plus'
import { getWordCloudApi } from '@/api/mainApi/draw.js'//获取点击量
import { isSkip, removeSkip, saveSkip } from '@/utils/skip.js'//跳转
import { getPostsListApi,getPostApi,replyPostApi,deleteReplyApi,deletePostApi,getUserInfoApi,submitPostApi,uploadCommonFileApi,getGlobalRankingApi } from '@/api/mainApi/index.js'
import { useRouter } from 'vue-router'
import PdfViewer from '@/components/PdfViewer.vue'
import { closeTourApi } from '@/api/mainApi/layout.js'
import emitter from '@/utils/emitter'// 导入事件总线封装类（子->父传递数据）

const router = useRouter()
const skipInfo = ref()//跳转信息
// 排行榜数据
const rankList = ref([])
const rankLoading = ref(false)
const rankStats = ref({ total_users: 0, user_rank: 0, user_score: 0, top_score: 0 })
const rankWeights = ref({})
const hoveredRankItem = ref(null)

const info = ref({
  rankId: -1, // 初始化为 -1，表示未找到排名
  id: null,
  username: '',
  avatar: '',
  score: null
})

// 计算属性：获取当前用户在排行榜中的完整数据，避免模板中多次访问可能存在的 undefined
const myRankData = computed(() => {//获取当前用户在排行榜中的完整数据 对象
  if (info.value.rankId !== -1 && rankList.value[info.value.rankId]) {
    return rankList.value[info.value.rankId]
  }
  return null
})


let loginUser = null
const userId = ref('')// 用户ID
const showTopBtn = ref(false)//回到顶部按钮


// 滚动监听
const scrollHandler = () => {
  // 滚动大于80px显示按钮，可自定义高度
  showTopBtn.value = window.scrollY > 80
}

// 回到顶部
const backTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

//滑到底部
const scrollToBottom = () => {
  window.scrollTo({ bottom: 0, behavior: 'smooth' })
}

onMounted(async () => {

  // 页面初始置顶
  window.scrollTo(0, 0)
  window.addEventListener('scroll', scrollHandler)

  const userStr = localStorage.getItem('loginUser')
  if (userStr) {

    //获取用户id
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        // 判断是否需要跳转
        if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
          ElMessage.warning('请进行画像构建~')
          router.push('/aiAnswer')
        }
        // 已是字符串直接赋值，否则转字符串
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
        // 简写
        // userId.value = loginUser.id + ''
      }
      if(loginUser.tour === 1){
        emitter.emit('startTour')
        const res = await closeTourApi(userId.value)
        if(res.code === 1){
          loginUser.tour = 0
          // 更新本地存储中的用户信息状态
          localStorage.setItem('loginUser', JSON.stringify(loginUser))
        }
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
    
    //排名
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser) {

        // 合并信息
        info.value = { ...info.value, ...loginUser }
        // 查找排名
        const index = rankList.value.findIndex(item => item.id === info.value.id)
        if (index !== -1) {
          info.value.rankId = index
        } else {
          console.warn('当前用户不在排行榜中')
          info.value.rankId = -1
        }
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }

    //左侧资源
    await getLeftRsList()

    // 获取排行榜
    await fetchRanking()

    // 检查 应用 中是否有要打开的帖子
    if(isSkip(9) === false){
      console.log('没有帖子需要提前打开')
    }else{
      skipInfo.value = isSkip(9)
      console.log('跳转信息:', skipInfo.value)
      try{
        await getPost(skipInfo.value.resourceId)

      }catch(e){
        ElMessage.error('该帖子不存在，可能已经被删除了')
        console.log('打开失败')
      }

      removeSkip(9)//删除跳转信息
    }

    // 获取帖子列表
    await getPostsList(1,10,0)

  }
})

// ==================评论区=====================

//===================数据====================


const page = ref(1)//页码
const pageSize = ref(10)//每页帖子数量
const totalPages = ref(1)//总页数
const postsLoading = ref(false)//帖子加载状态

const postsList = ref([//展示帖子信息
  // {
  //     "id": 25,
  //     "post_id": "post_b55764f734e8",
  //     "user_id": "2",
  //     "title": "天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气天气",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "tags": ["资源","c语言","提问问题","c语言","提问问题","c语言","提问问题","c语言","提问问题","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:35:21.923784",
  //     "updated_at": "2026-06-04T10:35:21.923784",
  //     "zone": "life",
  //     "zone_name": "生活区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 23,
  //     "post_id": "post_5f80b7495941",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": [],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:20:40.703621",
  //     "updated_at": "2026-06-04T10:20:40.703621",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 22,
  //     "post_id": "post_53a1f77c4779",
  //     "user_id": "2",
  //     "title": "递归函数怎么理解？",
  //     "content": "学了半天递归还是不太明白，有没有好的理解方式？",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": [],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:14:12.239470",
  //     "updated_at": "2026-06-04T10:14:12.239470",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // },
  // {
  //     "id": 24,
  //     "post_id": "post_08d0bb6e4f83",
  //     "user_id": "user_001",
  //     "title": "天气",
  //     "content": "今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好今天的天气很好",
  //     "username": '张三',
  //     "avatar": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  //     "tags": ["资源","c语言","提问问题"],
  //     "reply_count": 0,
  //     "created_at": "2026-06-04T10:28:46.324109",
  //     "updated_at": "2026-06-04T10:28:46.324109",
  //     "zone": "learning",
  //     "zone_name": "学习区"
  // }
])//帖子列表

//打开的帖子信息
const openPostMsg = ref({
    // "id": 1,
    // "post_id": "post_274622015268",
    // "user_id": "2",
    // "title": "排序",
    // "username": "张三",
    // "avatar": "",
    // "content": "所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的所有的排序哪一种是最块的",
    // "tags": ["换行"],
    // "reply_count": 2,
    // "created_at": "2026-05-25T19:55:35.936007",
    // "updated_at": "2026-05-25T20:05:48.463908",
    // "zone": "learning",
    // "zone_name": "学习区"
})

//打开的帖子回复信息
const openPostReply = ref([
    // {
    //     "id": 1,
    //     "reply_id": "reply_b1717c37732b",
    //     "post_id": "post_274622015268",
    //     "user_id": "test_3",
    //     "username": "李四",
    //     "avatar": "",
    //     "content": "111",
    //     "parent_reply_id": null,
    //     "created_at": "2026-05-25T19:58:09.900822"
    // },
    // {
    //     "id": 2,
    //     "reply_id": "reply_1ed14534e9ad",
    //     "post_id": "post_274622015268",
    //     "user_id": "2",
    //     "username": "王五",
    //     "avatar": "",
    //     "content": "11111",
    //     "parent_reply_id": null,
    //     "created_at": "2026-05-25T20:05:48.463908"
    // }
])

//回复表单
const replyForm = ref({
  userId: '',
  postId: '',
  content: '',
  parentReplyId: ''
})

// 回复文件上传相关
const replyFileInputRef = ref(null)
const replyFile = ref(null)
const replyFileUrl = ref('')
const isReplyUploading = ref(false)

const handleReplyFileSelect = async (event) => {
  const file = event.target.files[0]
  if (file) {
    if (file.size > 200 * 1024 * 1024) {
      ElMessage.warning('文件大小不能超过200MB')
      return
    }
    replyFile.value = file
    try {
      isReplyUploading.value = true
      const formData = new FormData()
      formData.append('file', file)
      const res = await uploadCommonFileApi(formData)
      if (res.code === 1) {
        replyFileUrl.value = res.data
        ElMessage.success('文件上传成功')
      } else {
        ElMessage.error('文件上传失败')
        replyFile.value = null
        replyFileUrl.value = ''
      }
    } catch (error) {
      console.error('文件上传错误：', error)
      ElMessage.error('文件上传失败')
      replyFile.value = null
      replyFileUrl.value = ''
    } finally {
      isReplyUploading.value = false
    }
  }
}

const clearReplyFile = () => {
  replyFile.value = null
  replyFileUrl.value = ''
  if (replyFileInputRef.value) {
    replyFileInputRef.value.value = ''
  }
}

//===================函数====================
const choosedArea = ref(0)//选中的分类
//分类切换
const changeArea = async (area) => {
  if(choosedArea.value === area) {
    console.log('已选分类不切换')
    return
  }
  switch (area) {
    case 0:
      console.log('切换到 全部')
      page.value = 1
      choosedArea.value = 0
      await getPostsList(1,10,0)
      break
    case 1:
      console.log('切换到 学习区')
      page.value = 1
      choosedArea.value = 1
      await getPostsList(1,10,1)
      break
    case 2:
      console.log('切换到 生活区')
      page.value = 1
      choosedArea.value = 2
      await getPostsList(1,10,2)
      break
    case 3:
      console.log('切换到 资源共享区')
      page.value = 1
      choosedArea.value = 3
      await getPostsList(1,10,3)
      break
    case 4:
      console.log('切换到 反馈建议区')
      page.value = 1
      choosedArea.value = 4
      await getPostsList(1,10,4)
      break
    default:
      console.log('错误：无效的分类')
  } 
}

//清除帖子展示所有信息
const clearPostReply = () => {
  openPostMsg.value = {}
  openPostReply.value = []
  replyForm.value = {userId: '',postId: '',content: '',parentReplyId: ''}
}

//帖子发布表单
const postForm = ref({
  userId: '',
  title: '',
  content: '',
  tags: [],
  zone: 1
})

const newTag = ref('')

const addTag = () => {
  const tag = newTag.value.trim()
  if (tag && !postForm.value.tags.includes(tag)) {
    postForm.value.tags.push(tag)
  }
  newTag.value = ''
}

const addTagOnBlur = () => {
  addTag()
}

const removeTag = (index) => {
  postForm.value.tags.splice(index, 1)
}

// 文件上传相关
const fileInputRef = ref(null)
const uploadedFile = ref(null)
const uploadProgress = ref(0)
const isUploading = ref(false)
const fileUrl = ref('')

/**
 * 格式化后端 T分隔时间 2026-06-04T10:35:21.923784 → yyyy-MM-dd HH:mm:ss
 * @param {string} timeStr
 * @returns {string}
 */
function formatTime(timeStr) {
  const d = new Date(timeStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}:${s}`
}

/**
 * 格式化文件大小
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

//发布帖子
const postBtnDisabled = ref(false)//发帖提交按钮禁用
const submitPost = async () => { 
  try{
    //检测表单
    if (!postForm.value.title || !postForm.value.content) {
      ElMessage.warning('标题或内容是必填项')
      return
    }
    if (!postForm.value.tags || postForm.value.tags.length === 0) {
      ElMessage.warning('请写入标签')
      return
    }
    if (!postForm.value.zone) {
      ElMessage.warning('请选择帖子分区')
      return
    }

    postBtnDisabled.value = true

    //发布帖子
    console.log('发布帖子')
    postForm.value.userId = userId.value
    postForm.value.url = fileUrl.value
    const res = await submitPostApi(postForm.value)
    if (res.code && res.data.success === true) {
      ElMessage.success('发布成功')
      await getPostsList(1,10,0)//获取帖子列表
      await getPost(res.data.post.post_id)//打开帖子
      backTop()
      // 清空表单
      postForm.value = {
        userId: '',
        title: '',
        content: '',
        tags: [],
        zone: 1
      }
      uploadedFile.value = null
      fileUrl.value = ''
      postBtnDisabled.value = false
    }else {
      ElMessage.error('发布失败：' + (res.data || '服务器错误'))
    }
    postBtnDisabled.value = false
  }catch(error){
    console.error('发布帖子失败：', error)
    postBtnDisabled.value = false
  }
}

// 上传文件
const uploadFile = async (file) => {
  if (!file) return ''
  
  try {
    isUploading.value = true
    uploadProgress.value = 0
    
    const formData = new FormData()
    formData.append('file', file)
    
    // 这里应该使用实际的上传API
    // 由于没有具体的API，我们模拟上传过程
    const res = await uploadCommonFileApi(formData)
    
    if (res.code === 1) {
      ElMessage.success('文件上传成功')
      return res.data
    } else {
      ElMessage.error('文件上传失败：' + (res.msg || '未知错误'))
      return ''
    }
  } catch (error) {
    console.error('文件上传错误：', error)
    ElMessage.error('文件上传失败：' + error.message)
    return ''
  } finally {
    isUploading.value = false
  }
}

// 处理文件选择
const handleFileSelect = async (event) => {
  const file = event.target.files[0]
  if (file) {
    // 检查文件大小（限制为200MB）
    if (file.size > 200 * 1024 * 1024) {
      ElMessage.warning('文件大小不能超过200MB')
      return
    }
    
    uploadedFile.value = file
    
    // 立即上传文件
    try {
      isUploading.value = true
      const formData = new FormData()
      formData.append('file', file)
      
      const res = await uploadCommonFileApi(formData)
      
      if (res.code === 1) {
        fileUrl.value = res.data
        ElMessage.success('文件上传成功')
      } else {
        ElMessage.error('文件上传失败：' + (res.msg || '未知错误'))
        uploadedFile.value = null
        fileUrl.value = ''
      }
    } catch (error) {
      console.error('文件上传错误：', error)
      ElMessage.error('文件上传失败：' + error.message)
      uploadedFile.value = null
      fileUrl.value = ''
    } finally {
      isUploading.value = false
    }
  }
}

// 清除已选择的文件
const clearSelectedFile = () => {
  uploadedFile.value = null
  fileUrl.value = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

// 上一页
const prevPage = async () => { 
  console.log('上一页')
  if (postsLoading.value) return
  if (page.value === 1) {
    ElMessage.warning('已经是第一页了')
    return
  }
  try {
    postsLoading.value = true
    page.value--
    await getPostsList(page.value,10,choosedArea.value)
  } catch (e) {
    console.error('获取帖子列表失败：', e)
  } finally {
    postsLoading.value = false
  }
}

// 下一页
const nextPage = async () => { 
  console.log('下一页')
  if (postsLoading.value) return
  if (page.value === totalPages.value) {
    ElMessage.warning('已经是最后一页了')
    return
  }
  try {
    postsLoading.value = true
    page.value++
    await getPostsList(page.value,10,choosedArea.value)
  } catch (e) {
    console.error('获取帖子列表失败：', e)
  } finally {
    postsLoading.value = false
  }
}

// ==================接口=====================

// 为所传数组/对象加username,avatar字段
const userIdInfo = ref({userIdList:[]})
const addUserInfo = async (arr) => {
  // 兼容单个对象{} 或 数组[]
  let list = Array.isArray(arr) ? arr : [arr];
  //把arr中所有user_id取出，保存在数组中，不重复
  const userIdList = [...new Set(list.map(item => item.user_id))]
  userIdInfo.value.userIdList = userIdList
  //把userIdList传给getUserInfoApi接口
  try {
    const res = await getUserInfoApi(userIdInfo.value)
    if (res.code) {
      const userMap = {}
      res.data.forEach(u => {
        userMap[u.userId] = u
      })
      // 直接修改原对象/原数组里的对象，无返回
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
const getPostsList = async (p,ps,category) => {
  try {
    const res = await getPostsListApi(p,ps,category)
    if (res.code) {
      postsList.value = res.data.posts
      await addUserInfo(postsList.value)//添加用户信息
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    } else {
      ElMessage.error('获取帖子列表失败：' + (res.data || '服务器错误'))
    }
  } catch (error) {
    console.error('获取帖子列表失败：', error)
  }
}

//根据帖子id获取帖子详情
const isLookPost = ref(false)//是否查看帖子详情
const getPost = async (postId) => { 
  try {
    const res = await getPostApi(postId)
    if (res.code) {
      if(isLookPost.value !== true){
        backTop()
      }
      isLookPost.value = true
      openPostMsg.value = res.data.post
      await addUserInfo(openPostMsg.value)
      openPostReply.value = res.data.replies
      await addUserInfo(openPostReply.value)
      parsePostContent(openPostMsg.value.content, openPostMsg.value.tags)
    } else {
      ElMessage.error('获取帖子详情失败：' + (res.data || '服务器错误'))
    }
  } catch (error) {
    console.error('获取帖子详情失败：', error)
  }
}

// 刷新回复列表
const refreshReplyList = async () => {
  if (!openPostMsg.value.post_id) {
    ElMessage.warning('未打开帖子')
    return
  }
  try {
    const res = await getPostApi(openPostMsg.value.post_id)
    if (res.code) {
      openPostReply.value = res.data.replies
      await addUserInfo(openPostReply.value)
      ElMessage.success('刷新成功')
    } else {
      ElMessage.error('刷新失败：' + (res.data || '服务器错误'))
    }
  } catch (error) {
    console.error('刷新回复列表失败：', error)
    ElMessage.error('刷新失败')
  }
}

//根据帖子id回复帖子
const replyPost = async (postId) => { 
  if (!replyForm.value.content && !replyFileUrl.value) {
    ElMessage.warning('请输入回复内容或上传文件')
    return
  }

  try {
    replyForm.value.postId = postId
    replyForm.value.userId = userId.value
    // 先拷贝参数再发请求，马上清空表单
    const params = { ...replyForm.value, url: replyFileUrl.value }
    replyForm.value = {userId: '',postId: '',content: '',parentReplyId: ''}
    clearReplyFile()
    ElMessage.success('回复中...，画像分析需要时间，请稍等')
    const res = await replyPostApi(params)
    if (res.code && res.data.success == true) {
      ElMessage.success('回复成功')
      await getPost(postId)//获取帖子详情
      scrollToBottom()
    } else {
      ElMessage.error('回复失败：' + (res.data || '服务器错误'))
    }
  } catch (error) {
    console.error('回复失败：', error)
  }
}

//根据回复id删除回复
const deleteReply = async (replyUserId,replyId) => { 
  // 询问是否删除
  const confirmResult = await ElMessageBox.confirm('是否删除该回复？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  try {
    const res = await deleteReplyApi(replyUserId,replyId)
    if (res.code && res.data.success == true) {
      ElMessage.success('删除成功')
      await getPost(openPostMsg.value.post_id)//获取帖子详情
    } else {
      ElMessage.error('删除失败：' + (res.data || '服务器错误'))
    }
  } catch (error) {
    console.error('删除失败：', error)
  }
}

//根据帖子id删除帖子
const deletePost = async (postId) => { 
  // 询问是否删除
  const confirmResult = await ElMessageBox.confirm('是否删除该帖子？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  try {
    isLookPost.value = false
    const res = await deletePostApi(userId.value,postId)
    if (res.code && res.data.success == true) {
      ElMessage.success('删除成功')
      await getPostsList(page.value,10,choosedArea.value)//获取帖子列表
    } else {
      ElMessage.error('删除失败：' + (res.data || '服务器错误'))
    }
    clearPostReply()
  } catch (error) {
    console.error('删除失败：', error)
  }
}


// ======================左上角======================

//推荐资源列表
const rcRsList = ref([
  // {
  //     "resourceType": "POST",
  //     "clickCount": 6,
  //     "percentage": 54.55
  // },
  // {
  //     "resourceType": "ANIMATION",
  //     "clickCount": 2,
  //     "percentage": 18.18
  // },
  // {
  //     "resourceType": "PAPER",
  //     "clickCount": 24,
  //     "percentage": 9.09
  // },
  // {
  //     "resourceType": "READING",
  //     "clickCount": 1,
  //     "percentage": 9.09
  // },
  // {
  //     "resourceType": "VIDEO",
  //     "clickCount": 1,
  //     "percentage": 9.09
  // },
  // {
  //     "resourceType": "PPT",
  //     "clickCount": 1,
  //     "percentage": 9.09
  // },
  // {
  //     "resourceType": "AI_ANSWER",
  //     "clickCount": 20,
  //     "percentage": 9.09
  // }

  {content: 0}
])

//数组排序
const sortAndValidateData = () => {
  // 判断rcRsList是否有值且为数组
  if (rcRsList.value && Array.isArray(rcRsList.value) && rcRsList.value.length > 0) {
    // 过滤掉空对象，确保有有效数据
    const validData = rcRsList.value.filter(item => item && typeof item === 'object' && Object.keys(item).length > 0);
    
    if (validData.length > 0) {
      // 有有效数据，按clickCount从大到小排序，并最多保留前五个
      rcRsList.value = validData
        .sort((a, b) => b.clickCount - a.clickCount)
        .slice(0, 5); // 只保留前5个
    } else {
      // 只有空对象，设置默认值
      rcRsList.value = [{ content: 0 }];
    }
  } else {
    // 没有值或不是数组，设置默认值
    rcRsList.value = [{ content: 0 }];
  }
}

// 处理帖子内容，提取链接并分类
// 解析帖子内容
const processedContent = ref({
  textParts: [],
  links: []
})

// 分享资源帖信息
const shareResourceInfo = ref(null) // { resourceId, rsType, routePath }

// 资源类型映射：tag字符串 → rsType → 路由路径
const resourceTypeMap = {
  'ppt': { rsType: 0, routePath: '/ppt', name: 'PPT' },
  'mindmap': { rsType: 1, routePath: '/mindMap', name: '思维导图' },
  'mindMap': { rsType: 1, routePath: '/mindMap', name: '思维导图' },
  'doc': { rsType: 2, routePath: '/word', name: '文档' },
  'docment': { rsType: 2, routePath: '/word', name: '文档' },
  'document': { rsType: 2, routePath: '/word', name: '文档' },
  'extension': { rsType: 3, routePath: '/reading', name: '拓展阅读' },
  'practice': { rsType: 4, routePath: '/code', name: '编程练习' },
  'video': { rsType: 5, routePath: '/video', name: '视频' },
  'animation': { rsType: 6, routePath: '/anima', name: '动画' },
  'question': { rsType: 7, routePath: '/paper', name: '试卷' },
  // 中文标签也支持
  '动画': { rsType: 6, routePath: '/anima', name: '动画' },
  '视频': { rsType: 5, routePath: '/video', name: '视频' },
  '文档': { rsType: 2, routePath: '/word', name: '文档' },
  'PPT': { rsType: 0, routePath: '/ppt', name: 'PPT' },
  '思维导图': { rsType: 1, routePath: '/mindMap', name: '思维导图' },
  '拓展阅读': { rsType: 3, routePath: '/reading', name: '拓展阅读' },
  '编程练习': { rsType: 4, routePath: '/code', name: '编程练习' },
  '试卷': { rsType: 7, routePath: '/paper', name: '试卷' }
}

// 图片预览
const showImagePreview = ref(false)
const previewImageUrl = ref('')

const openImagePreview = (url) => {
  previewImageUrl.value = url
  showImagePreview.value = true
  document.body.style.overflow = 'hidden'
}

const closeImagePreview = () => {
  showImagePreview.value = false
  previewImageUrl.value = ''
  document.body.style.overflow = ''
}

const parsePostContent = (content, tags = []) => {
  if (!content) {
    processedContent.value = { paragraphs: [] }
    shareResourceInfo.value = null
    return
  }
  
  // 重置分享资源信息
  shareResourceInfo.value = null
  
  // 检测是否为分享资源帖（以"分享者"开头）
  const isSharePost = content.startsWith('分享者')
  
  if (isSharePost && tags && tags.length > 0) {
    // 检索"资源ID"获取其后的字符串（兼容中英文冒号，冒号后可能有空格）
    const resourceIdMatch = content.match(/资源ID[：:]\s*([^\s\n]+)/)
    if (resourceIdMatch) {
      const resourceId = resourceIdMatch[1].trim()
      // 遍历tags查找匹配的资源类型
      let typeInfo = null
      for (const tag of tags) {
        if (resourceTypeMap[tag]) {
          typeInfo = resourceTypeMap[tag]
          break
        }
      }
      if (typeInfo && resourceId) {
        shareResourceInfo.value = {
          resourceId,
          rsType: typeInfo.rsType,
          routePath: typeInfo.routePath,
          resourceName: typeInfo.name
        }
        console.log('shareResourceInfo set:', shareResourceInfo.value)
      }
    }
  }
  
  console.log('final shareResourceInfo:', shareResourceInfo.value)
  
  const urlRegex = /(https?:\/\/[^\s`\n]+)/g
  const lines = content.split(/\n/)
  const paragraphs = []
  
  lines.forEach((line, lineIndex) => {
    if (!line.trim()) {
      paragraphs.push({ type: 'empty' })
      return
    }
    
    const parts = line.split(urlRegex)
    const paragraphParts = []
    
    parts.forEach((part, index) => {
      const urlMatch = part.match(urlRegex)
      if (urlMatch) {
        const url = part.trim()
        const linkInfo = classifyLink(url)
        paragraphParts.push({
          type: 'link',
          url: url,
          ...linkInfo,
          uniqueId: `${lineIndex}-${index}`
        })
      } else {
        paragraphParts.push({
          type: 'text',
          content: part
        })
      }
    })
    
    paragraphs.push({
      type: 'paragraph',
      parts: paragraphParts
    })
  })
  
  processedContent.value = {
    paragraphs
  }
}

// 从URL中提取文件名
const extractFileName = (url) => {
  try {
    // 移除查询参数和哈希
    const cleanUrl = url.split('?')[0].split('#')[0]
    // 获取最后一个斜杠后的部分
    const fileName = cleanUrl.split('/').pop()
    // 如果有文件名且包含扩展名，返回文件名
    if (fileName && fileName.includes('.')) {
      return decodeURIComponent(fileName)
    }
    return null
  } catch (e) {
    return null
  }
}

const classifyLink = (url) => {
  const lowerUrl = url.toLowerCase()
  const fileName = extractFileName(url)
  
  if (lowerUrl.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/)) {
    return { type: 'image', label: fileName || '图片' }
  }
  
  if (lowerUrl.match(/\.(pdf)$/)) {
    return { type: 'pdf', label: fileName || 'PDF文档' }
  }
  
  if (lowerUrl.match(/\.(doc|docx)$/)) {
    return { type: 'word', label: fileName || 'Word文档' }
  }
  
  if (lowerUrl.match(/\.(ppt|pptx)$/)) {
    return { type: 'ppt', label: fileName || 'PPT文档' }
  }
  
  if (lowerUrl.match(/\.(xls|xlsx)$/)) {
    return { type: 'excel', label: fileName || 'Excel文档' }
  }
  
  if (lowerUrl.includes('bilibili.com') || lowerUrl.includes('youtube.com') || 
      lowerUrl.includes('youku.com') || lowerUrl.includes('tencent.com') ||
      lowerUrl.includes('.mp4') || lowerUrl.includes('.mov') || lowerUrl.includes('.avi')) {
    return { type: 'video', label: fileName || '视频链接' }
  }
  
  return { type: 'other', label: fileName || '下载链接' }
}

const getOfficePreviewUrl = (url) => {
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`
}

const handleDownload = (url) => {
  window.open(url, '_blank')
}

// 跳转到分享资源页面
const jumpToResource = () => {
  if (!shareResourceInfo.value) return
  const { resourceId, rsType, routePath } = shareResourceInfo.value
  
  // 使用 saveSkip 保存跳转信息
  saveSkip(rsType, resourceId)
  
  // 路由跳转
  router.push(routePath)
  
  ElMessage.success('正在跳转到资源页面...')
}

// 解析回复内容中的链接
const parseReplyContent = (content) => {
  if (!content) return []
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const parts = []
  let lastIndex = 0
  let match
  
  while ((match = urlRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    }
    const url = match[0]
    const linkInfo = classifyLink(url)
    parts.push({ type: 'link', url, ...linkInfo })
    lastIndex = match.index + match[0].length
  }
  
  if (lastIndex < content.length) {
    parts.push({ type: 'text', content: content.slice(lastIndex) })
  }
  
  return parts
}

// 资源类型名称
const resourceTypeName = (type) => {
  const map = {
    MIND_MAP: '思维导图',
    ANIMATION: '动画',
    PAPER: '试卷',
    READING: '阅读资料',
    VIDEO: '教学视频',
    PPT: 'PPT',
    WORD: 'Word',
    CODE: '编程题',
    PATHPLAN: '智学路径',
    EVALUATE: '智评优化',
    AI_ANSWER: 'AI智能助手答疑',
    POST: '帖子',
    PARTNERS: '学伴',
    WRONG_QUESTION: '错题本',
  }
  return map[type] || type
}

//跳转
const skipRs = (type) => {
  if(type === 'POST'){
     // 滚动100px，不跳转
    window.scrollTo({
      top: 900,
      behavior: 'smooth'
    })
  }else{
    // 特殊处理 ANIMATION 类型
    if (type === 'ANIMATION') {
      type = 'anima'
    }

    const path = '/' + type.replace(/_/g, '').toLowerCase()
    router.push(path)
  }

}

//获取资源显示表
const getLeftRsList = async() => {
  try{
    const res = await getWordCloudApi(userId.value)
    if(res.code){
      rcRsList.value = res.data
      sortAndValidateData()
    }
  }catch(e){
    console.log('获取点击量失败：',e)
  }
}

// 获取排行榜数据
const fetchRanking = async () => {
  if (rankLoading.value) return
  rankLoading.value = true
  try {
    const limit = 10
    const res = await getGlobalRankingApi(limit, userId.value)
    if (res.success || res.code === 1) {
      const data = res.data || res
      const rankings = data.rankings || []
      
      // 更新统计信息
      if (data.total_users !== undefined) rankStats.value.total_users = data.total_users
      if (data.user_rank !== undefined) rankStats.value.user_rank = data.user_rank
      const myRanking = rankings.find(r => String(r.user_id) === String(userId.value))
      if (myRanking && myRanking.composite_score !== undefined) {
        rankStats.value.user_score = myRanking.composite_score
      } else if (data.user_score !== undefined) {
        rankStats.value.user_score = data.user_score
      }
      if (rankings.length > 0) rankStats.value.top_score = rankings[0].composite_score
      
      // 更新权重信息
      if (data.weights) rankWeights.value = data.weights
      
      // 获取用户信息（头像、用户名）
      const userIdList = [...new Set(rankings.map(r => r.user_id))]
      if (userIdList.length > 0) {
        try {
          const userRes = await getUserInfoApi({ userIdList })
          if (userRes.code) {
            const userMap = {}
            userRes.data.forEach(u => { userMap[u.userId] = u })
            rankings.forEach(r => {
              const user = userMap[r.user_id]
              if (user) {
                r.username = user.username
                r.avatar = user.avatar
              } else {
                r.username = r.user_id
                r.avatar = ''
              }
            })
          }
        } catch (e) {
          console.error('获取排行榜用户信息失败:', e)
          rankings.forEach(r => { r.username = r.user_id; r.avatar = '' })
        }
      }
      
      // 映射数据到 rankList
      const mappedList = rankings.slice(0, 10).map((r, idx) => ({
        id: r.user_id,
        username: r.username || r.user_id,
        avatar: r.avatar || '',
        score: r.composite_score,
        rank: r.rank || idx + 1,
        dimension_scores: r.dimension_scores || {},
        submission_stats: r.submission_stats || {}
      }))
      
      rankList.value = mappedList
      

    }
  } catch (e) {
    console.error('获取排行榜失败:', e)
  } finally {
    rankLoading.value = false
  }
}



// 获取维度分数百分比（自动判断是0-1还是0-100范围）
const getDimensionPercent = (value) => {
  if (!value) return '0%'
  // 如果值大于1，认为是0-100范围；否则是0-1范围
  const percent = value > 1 ? value : value * 100
  return Math.min(percent, 100) + '%'
}

// 获取维度分数显示值
const getDimensionValue = (value) => {
  if (!value) return '0'
  // 如果值大于1，认为是0-100范围直接显示；否则转换为百分比显示
  const displayValue = value > 1 ? value : value * 100
  return Math.min(displayValue, 100).toFixed(0)
}

// 排行榜区域滚动处理 - 阻止父页面滚动
const handleRankWheel = (e) => {
  e.preventDefault()
  const scrollbar = e.currentTarget.querySelector('.el-scrollbar__wrap')
  if (scrollbar) {
    scrollbar.scrollTop += e.deltaY
  }
}

onUnmounted(() => {
  window.removeEventListener('scroll', scrollHandler)
})
</script>

<template>
  <!-- 回顶按钮 -->
  <div v-if="showTopBtn" class="back-top" @click="backTop">↑</div>
  <div class="container">

    <!-- 顶部 -->
    <div class="top">
      <!-- 左侧 -->
      <div class="left">
        <!-- 左上侧 -->
        <div class="left-top">
          <!-- 功能区 -->
          <div class="left-card">
            <!-- 标题 -->
            <div class="topHead">
              <div class="mainTitle">
                智推资源
              </div>
              <div class="subTitle">
                根据你的系统资源使用情况，为你推荐
              </div>
            </div>
            <!-- 底部内容 -->
            <div class="bottomContent">
              <div class="rcNull" v-if="rcRsList[0]?.content === 0">
                <div class="null-content">
                  <div class="null-icon">
                    <img src="@/assets/image/emptyStatus.png" alt="">
                  </div>
                  <div class="null-title">暂无推荐资源</div>
                  <div class="null-subtitle">请先使用系统一段时间</div>
                  <div class="null-subtitle">系统会根据你的使用情况推荐</div>
                </div>
              </div>
              <div class="resource-list" v-else>
                <div @click="skipRs(item.resourceType)" class="rsItem" v-for="(item,index) in rcRsList" :key="index">
                  <div class="itemLeft">
                    <div>
                      {{ resourceTypeName(item.resourceType) }}
                    </div>
                    <div>
                      使用次数：{{ item.clickCount }} 次
                    </div>
                  </div>
                  <div class="itemRight">
                    <el-icon><ArrowRight /></el-icon>
                  </div>
                </div>
              </div> 
            </div>
          </div>
          <!-- 轮播图 -->
          <div class="panner">
            <el-carousel height="500px" motion-blur style="z-index: 1">
              <!-- <el-carousel-item v-for="item in 4" :key="item">
                <h3 class="small justify-center" text="2xl">{{ item }}</h3>
              </el-carousel-item> -->
              <!-- 默认轮播图 -->
              <el-carousel-item>
                  <img src="@/assets/panner-default/panner1.png" alt="">
              </el-carousel-item>
              <el-carousel-item>
                  <img src="@/assets/panner-default/panner2.png" alt="">
              </el-carousel-item>
              <el-carousel-item>
                  <img src="@/assets/panner-default/panner3.png" alt="">
              </el-carousel-item>
              <el-carousel-item>
                  <img src="@/assets/panner-default/panner4.png" alt="">
              </el-carousel-item>
            </el-carousel>
          </div>
        </div>

        <!-- 左下侧-写心得评论 -->
        <div class="left-bottom">
          <div class="write-card">
            <div class="write-header">
              <div class="header-left">
                <span class="title">
                <svg t="1779529434395" class="icon write-icon" viewBox="0 0 1152 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7062" width="30" height="30"><path d="M1018.84131 962.095718h-345.632242c-265.672544 0-482.337531-216.664987-482.337531-484.916877S412.695214 0 673.209068 0s479.758186 216.664987 479.758186 484.916877c0 118.649874-43.848866 232.141058-123.808564 319.838791-15.476071 15.476071-33.531486 15.476071-54.166247 5.15869-15.476071-15.476071-15.476071-33.531486-5.15869-54.166247 64.483627-74.801008 103.173804-172.816121 103.173804-270.831234 0-224.403023-180.554156-407.536524-402.377834-407.536524S265.672544 260.513854 265.672544 482.337531s188.292191 404.957179 410.115869 404.957179h345.632242c20.634761 0 38.690176 15.476071 38.690176 38.690177 0 20.634761-15.476071 36.110831-41.269521 36.110831z" fill="#515151" p-id="7063"></path><path d="M668.050378 696.423174c-49.007557 0-90.277078-23.214106-116.070529-61.904282-7.738035-12.896725-7.738035-36.110831 7.738035-43.848867 12.896725-7.738035 36.110831-7.738035 43.848867 7.738035 12.896725 23.214106 41.269521 30.952141 61.904282 30.952142 25.793451 0 49.007557-12.896725 61.904282-36.110832 7.738035-12.896725 30.952141-18.055416 43.848866-7.738035 12.896725 7.738035 18.055416 30.952141 7.738036 43.848867-15.476071 38.690176-61.904282 61.904282-110.911839 67.062972z m-214.085642 260.513854c-15.476071 2.579345-28.372796 2.579345-43.848867 2.579345h-296.624685c-18.055416 0-33.531486 12.896725-33.531486 33.531486 0 18.055416 12.896725 30.952141 33.531486 30.952141h296.624685c61.904282 0 121.229219-12.896725 172.816121-38.690176-43.848866-2.579345-87.697733-12.896725-128.967254-28.372796z m-301.783376-64.483627c12.896725-12.896725 12.896725-30.952141 5.15869-46.428212-56.745592-64.483627-90.277078-149.602015-90.277078-234.720403 0-87.697733 33.531486-167.657431 87.697733-229.561713 12.896725-49.007557 33.531486-95.435768 61.904282-136.70529C87.697733 314.680101 0 453.964736 0 611.304786c0 103.173804 38.690176 198.609572 105.753149 275.989924 12.896725 12.896725 30.952141 12.896725 46.428211 5.158691z" fill="#515151" p-id="7064"></path></svg>
                写下您的心得
              </span>

              <span class="tip">分享您的智慧与感悟</span>
              </div>
              <div class="header-right">
                <div class="postTitle">
                  <div class="post-title">标题：</div>
                  <el-input v-model="postForm.title" placeholder="请输入帖子标题" class="title-input" />
                </div>
                <div class="header-zone">
                  <select v-model="postForm.zone">
                    <option value="1">学习区</option>
                    <option value="2">生活区</option>
                    <option value="3">资源共享区</option>
                    <option value="4">反馈建议区</option>
                  </select>
                </div>
              </div>
            </div>
            
            <div class="write-content">
              <el-input
                v-model="postForm.content"
                type="textarea"
                :rows="7"
                placeholder="请输入您想分享的内容..."
                resize="none"
                class="custom-textarea"
              />
            </div>

            <div class="write-footer">
              <!-- 标签器 -->
              <div class="tags">
                <div class="tag-title">标签：</div>
                <div class="tags-container">
                  <div 
                    v-for="(tag, index) in postForm.tags" 
                    :key="index" 
                    class="tag-item"
                  >
                    {{ tag }}
                    <span class="tag-remove" @click="removeTag(index)">×</span>
                  </div>
                  <input 
                    type="text" 
                    v-model="newTag"
                    placeholder="输入标签回车添加"
                    class="tag-input"
                    @keyup.enter="addTag"
                    @blur="addTagOnBlur"
                  />
                </div>
              </div>
              <!-- 操作项 -->
              <div class="actions" @click="router.push('/code')">
                <el-tooltip content="前往资源页分享资源" placement="bottom">
                  <el-icon class="action-icon"><DocumentAdd /></el-icon>
                </el-tooltip>
              </div>
              <!-- 文件上传图标 -->
              <div class="upload-icon" @click="fileInputRef?.click()">
                <input 
                  ref="fileInputRef"
                  type="file" 
                  @change="handleFileSelect" 
                  style="display: none"
                >
                <el-tooltip content="上传资源" placement="bottom">
                  <el-icon class="action-icon"><Upload /></el-icon>
                </el-tooltip>
              </div>
              <!-- 已上传文件信息 -->
              <div v-if="uploadedFile" class="uploaded-file-info">
                <span class="uploaded-file-name">{{ uploadedFile.name }}</span>
                <el-button size="small" @click="clearSelectedFile" type="danger" text>清空</el-button>
              </div>
              <!-- 发布按钮 -->
              <div class="postBtn" @click="submitPost()" :class="postBtnDisabled ? 'postBtnStop' : ''">
                发布心得
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 右侧-排行榜 -->
      <div class="right">
        <div class="rank-card" @wheel="handleRankWheel">
          <div class="rank-card-title">
            <svg t="1779534825496" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="17006" width="32" height="32"><path d="M898.133 481.711l-184.035 12.714c-4.434 0.306-8.869 0.613-13.15 3.136l5.315-310.041c-2.297-33.26-30.743-58.028-61.785-55.884l-298.486 65.179c-31.042 2.145-55.811 30.59-53.514 63.85l17.447 123.555c-4.434 0.306-9.022-1.604-13.457-1.298l-176.537 56.754c-33.26 2.299-58.028 30.744-55.731 64.002l80.78 330.828c2.298 33.259 30.59 55.811 61.633 53.666l654.099-45.189c31.042-2.144 55.811-30.59 53.666-61.632l45.541-243.756c-2.298-33.259-30.743-58.028-61.786-55.884zM373.666 823.162l-170.73 11.795c-2.218 0.153-2.37-2.065-2.37-2.065l-80.781-330.827c-0.153-2.217 2.064-2.37 2.064-2.37l187.623-57.52c2.217-0.153 2.37 2.064 2.37 2.064l61.824 378.923z m274.944-18.994l-219.512 15.164-83.407-562.343c-0.153-2.218 2.064-2.37 2.064-2.37l300.703-65.332c2.218-0.153 2.37 2.063 2.37 2.063l-2.218 612.818z m208.425-14.399l-152.993 10.569 0.888-245.127c-0.152-2.217 2.064-2.37 2.064-2.37l192.904-13.327c2.217-0.153 2.37 2.064 2.37 2.064L856.881 787.55c2.218-0.151 2.37 2.065 0.154 2.219z" p-id="17007" fill="#2D7DDB"></path><path d="M566.113 377.896l-40.273 146.69-46.34 3.201 40.251-150.664-40.464 2.796 14.74-33.596 49.91-3.45c6.642-0.458 12.086 1.09 16.349 4.64 4.543 3.788 7.045 9.13 7.522 16.025 0.305 4.343-0.263 9.131-1.695 14.358zM301.071 609.96c3.534 15.665-1.16 32.015-14.073 49.062-10.886 14.388-24.395 25.821-40.531 34.294l59.73-13.482-3.259 27.445-91.174 20.576 1.889-26.582c11.846-8.241 23.271-19.843 34.268-34.805 13.202-17.967 18.559-32.458 16.074-43.456-2.573-11.415-8.259-16.131-17.047-14.144l-1.133 0.257c0.662 1.565 1.084 2.783 1.284 3.654 1.342 5.943 0.054 11.491-3.858 16.661-3.663 4.92-8.579 8.081-14.748 9.472-6.055 1.37-11.793 0.614-17.216-2.262-5.694-3.001-9.21-7.469-10.553-13.407-2.191-9.722 0.867-17.296 9.188-22.72 5.588-3.711 15.568-7.188 29.952-10.437 15.021-3.391 26.427-4.645 34.21-3.775 14.804 1.623 23.801 9.505 26.997 23.649zM843.891 614.556l-31.156 39.643c5.508 3.387 10.086 8.059 13.719 14.029 3.938 6.369 5.716 12.597 5.325 18.691-0.837 12.945-6.37 23.031-16.59 30.25-8.539 6.009-19.709 9.637-33.507 10.895-8.767 0.804-18.724 0.604-29.885-0.609-5.796-0.653-10.717-2.956-14.763-6.909-4.249-4.178-6.187-9.103-5.822-14.757 0.373-5.699 2.929-10.33 7.672-13.878 4.517-3.347 9.628-4.831 15.337-4.472 5.814 0.383 10.748 2.521 14.789 6.419 4.254 4.125 6.201 9.051 5.828 14.758-0.169 2.632-0.818 5.018-1.951 7.139 6.165 0.072 11.389-2.24 15.656-6.921 4.147-4.525 6.441-10.131 6.872-16.83 0.503-7.788-2.524-14.655-9.086-20.59-5.525-4.925-11.611-7.907-18.265-8.948l25.755-27.6-44.941-2.899 10.566-22.879 84.447 5.468z" p-id="17008" fill="#2D7DDB"></path></svg>
            <span>积分排行榜 - TOP10</span>
          </div>
          
          <!-- 统计信息行 -->
          <div class="rank-stats-row" v-if="rankStats.total_users > 0">
            <div class="rank-stat-card">
              <div class="stat-value">{{ rankStats.total_users }}</div>
              <div class="stat-label">总用户数</div>
            </div>
            <div class="rank-stat-card">
              <div class="stat-value">{{ rankStats.user_rank || '-' }}</div>
              <div class="stat-label">我的排名</div>
            </div>
            <div class="rank-stat-card">
              <div class="stat-value">{{ rankStats.user_score || '-' }}</div>
              <div class="stat-label">我的分数</div>
            </div>
            <div class="rank-stat-card">
              <div class="stat-value">{{ rankStats.top_score || '-' }}</div>
              <div class="stat-label">排行最高分</div>
            </div>
          </div>
          
          <!-- 权重信息 -->
          <div class="rank-weights-row" v-if="rankWeights.coding_score">
            <span class="weights-title">评分权重:</span>
            <span class="weight-tag">编程能力 {{ (rankWeights.coding_score * 100).toFixed(0) }}%</span>
            <span class="weight-tag">准确率 {{ (rankWeights.accuracy_score * 100).toFixed(0) }}%</span>
            <span class="weight-tag">学习时长 {{ (rankWeights.learning_time_score * 100).toFixed(0) }}%</span>
            <span class="weight-tag">做题数量 {{ (rankWeights.problem_count_score * 100).toFixed(0) }}%</span>
          </div>
          
          <!-- 排行榜列表 -->
          <el-scrollbar height="600px" v-if="rankList.length">
            <div class="rank-card-content"> 
              <div 
                v-for="(item, index) in rankList" 
                :key="item.id" 
                class="rank-item rank-like"
                :class="{ 'top-three': index < 3 }"
              >
                <!-- 排名序号 -->
                <div class="rank-medal" v-if="index < 3">
                  <div class="one" v-if="index == 0">
                    <svg t="1779531288175" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6142" width="28" height="28"><path d="M604.813241 0l-153.688275 282.094345 283.489103 94.384552L938.160552 0H604.813241z" fill="#FFFFFF" p-id="6143"></path><path d="M600.046345 0l-148.921379 284.813241 86.528 31.426207L694.642759 0h-94.596414z" fill="#2157CC" p-id="6144"></path><path d="M648.986483 345.335172l88.187586 31.143725L938.160552 0h-96.397242l-192.794482 345.335172z" fill="#DF202A" p-id="6145"></path><path d="M419.186759 0l153.688275 282.094345-283.489103 94.384552L85.839448 0h333.347311z" fill="#FFFFFF" p-id="6146"></path><path d="M408.717241 0l148.939035 284.813241-86.528 31.426207L314.138483 0h94.596414z" fill="#2378F1" p-id="6147"></path><path d="M375.013517 345.335172l-88.187586 31.143725L85.839448 0h96.397242l192.794482 345.335172z" fill="#F5222D" p-id="6148"></path><path d="M209.125517 283.61269l184.002207 9.163034 119.913931-127.117241 119.896276 127.117241 192.264828-9.163034-9.304276 181.036138L953.37931 589.735724l-137.480827 117.971862 8.280276 189.175173-182.960552-8.139035L512 1024l-129.218207-135.256276-182.960552 8.121379 8.280276-189.157517L70.62069 589.735724l138.504827-125.086896-8.26262-181.036138h8.26262z" fill="#FFDA35" p-id="6149"></path><path d="M283.700966 572.239448c0 124.38069 104.96 225.880276 235.908413 225.880276s235.908414-100.510897 235.908414-225.880276c0-124.38069-104.96-225.880276-235.908414-225.880276s-235.908414 101.499586-235.908413 225.880276z" fill="#FABA00" p-id="6150"></path><path d="M570.120828 676.193103l-51.500138-30.27862-51.482483 30.260965a7.256276 7.256276 0 0 1-8.756966 0c-2.913103-1.942069-4.855172-5.843862-2.913103-8.77462l12.641103-61.510621-43.731862-41.012966c-2.913103-2.930759-4.855172-5.861517-2.913103-8.792275 1.942069-2.930759 4.855172-5.861517 7.768276-5.861518l59.268414-5.843862 24.293517-56.637793c1.942069-2.930759 4.855172-5.861517 7.768276-5.861517 2.930759 0 5.826207 2.930759 7.768275 5.861517l24.311173 56.637793 59.268414 5.843862c2.913103 0 5.826207 2.930759 5.826207 5.861518 1.942069 2.930759 0 7.821241-1.942069 8.792275l-43.731862 41.012966 12.641103 61.510621c0 2.930759 0 7.803586-2.913103 8.77462-3.884138 1.959724-8.756966 1.959724-11.652414 0z" fill="#FFD81F" p-id="6151"></path></svg>
                  </div>
                  <div class="two" v-else-if="index == 1">
                    <svg t="1779531242145" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6262" width="28" height="28"><path d="M601.158621 0L450.206897 291.310345 728.275862 388.413793 926.896552 0z" fill="#FFFFFF" p-id="6263"></path><path d="M601.688276 0L450.206897 286.013793l87.710896 31.77931L697.37931 0z" fill="#2157CC" p-id="6264"></path><path d="M644.413793 356.051862L730.729931 388.413793 926.896552 0h-94.155035z" fill="#DF202A" p-id="6265"></path><path d="M405.186207 0L556.137931 291.310345 278.068966 388.413793 79.448276 0z" fill="#FFFFFF" p-id="6266"></path><path d="M404.656552 0L556.137931 286.013793 468.427034 317.793103 308.965517 0z" fill="#2378F1" p-id="6267"></path><path d="M361.931034 356.051862L275.614897 388.413793 79.448276 0h94.155034z" fill="#F5222D" p-id="6268"></path><path d="M214.121931 277.451034l180.630069 9.604414L512 158.896552l117.248 128.176551 188.557241-9.622069-7.944827 182.625104L944.551724 586.646069l-134.673655 118.554483 7.927172 190.640551-179.058758-8.015448L512 1024l-126.764138-136.174345-179.023448 8.015448 7.909517-190.640551L79.448276 586.646069l134.673655-126.569931-7.927172-182.625104z" fill="#DFE8ED" p-id="6269"></path><path d="M273.655172 582.62069c0 126.764138 102.753103 229.517241 229.517242 229.517241s229.517241-102.753103 229.517241-229.517241-102.753103-229.517241-229.517241-229.517242-229.517241 102.753103-229.517242 229.517242z" fill="#C2CBD4" p-id="6270"></path><path d="M559.457103 687.315862l-55.490206-32.909241-55.490207 32.909241a10.328276 10.328276 0 0 1-9.798621 0c-3.248552-1.641931-4.890483-6.585379-3.248552-9.886896l13.064828-65.800828-47.351173-44.438069c-3.266207-3.283862-4.890483-6.585379-3.266206-9.869241 1.641931-3.283862 4.908138-6.585379 8.156689-6.58538l63.664552-6.585379 26.112-60.875035c1.624276-3.301517 4.890483-6.585379 8.15669-6.585379s6.532414 3.283862 8.156689 6.585379l26.129655 60.875035 63.646897 6.585379c3.266207 0 6.532414 3.301517 6.532414 6.58538 1.624276 3.283862 0 8.22731-1.641931 9.886896l-47.315862 44.420414 13.047172 65.818483c0 3.283862 0 8.22731-3.266207 9.886896-1.624276 1.624276-6.532414 1.624276-9.798621 0z" fill="#DFE8ED" p-id="6271"></path></svg>
                  </div>
                  <div class="three" v-else>
                    <svg t="1779531009068" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="22567" width="28" height="28"><path d="M601.158621 0L450.206897 291.310345 728.275862 388.413793 926.896552 0z" fill="#FFFFFF" p-id="22568"></path><path d="M601.688276 0L450.206897 286.013793l87.710896 31.77931L697.37931 0z" fill="#2157CC" p-id="22569"></path><path d="M644.413793 356.051862L730.729931 388.413793 926.896552 0h-94.155035z" fill="#DF202A" p-id="22570"></path><path d="M405.186207 0L556.137931 291.310345 278.068966 388.413793 79.448276 0z" fill="#FFFFFF" p-id="22571"></path><path d="M404.656552 0L556.137931 286.013793 468.427034 317.793103 308.965517 0z" fill="#2378F1" p-id="22572"></path><path d="M361.931034 356.051862L275.614897 388.413793 79.448276 0h94.155034z" fill="#F5222D" p-id="22573"></path><path d="M214.121931 277.451034l180.630069 9.604414L512 158.896552l117.248 128.176551 188.557241-9.622069-7.944827 182.625104L944.551724 586.646069l-134.673655 118.554483 7.927172 190.640551-179.058758-8.015448L512 1024l-126.764138-136.174345-179.023448 8.015448 7.909517-190.640551L79.448276 586.646069l134.673655-126.569931-7.927172-182.625104z" fill="#F8D197" p-id="22574"></path><path d="M273.655172 582.62069c0 126.764138 102.753103 229.517241 229.517242 229.517241s229.517241-102.753103 229.517241-229.517241-102.753103-229.517241-229.517241-229.517242-229.517241 102.753103-229.517242 229.517242z" fill="#E8A152" p-id="22575"></path><path d="M559.457103 687.315862l-55.490206-32.909241-55.490207 32.909241a10.328276 10.328276 0 0 1-9.798621 0c-3.248552-1.641931-4.890483-6.585379-3.248552-9.886896l13.064828-65.800828-47.351173-44.438069c-3.266207-3.283862-4.890483-6.585379-3.266206-9.869241 1.641931-3.283862 4.908138-6.585379 8.156689-6.58538l63.664552-6.585379 26.112-60.875035c1.624276-3.301517 4.890483-6.585379 8.15669-6.585379s6.532414 3.283862 8.156689 6.585379l26.129655 60.875035 63.646897 6.585379c3.266207 0 6.532414 3.301517 6.532414 6.58538 1.624276 3.283862 0 8.22731-1.641931 9.886896l-47.315862 44.420414 13.047172 65.818483c0 3.283862 0 8.22731-3.266207 9.886896-1.624276 1.624276-6.532414 1.624276-9.798621 0z" fill="#F8D197" p-id="22576"></path></svg>
                  </div>
                </div>
                <div class="rank-index" v-else>
                  {{ index + 1 }}
                </div>

                <!-- 用户信息 -->
                <div class="rank-info">
                  <div class="user-avatar">
                    <el-avatar :size="30" :src="item.avatar" style="border: 1px solid #eee">
                      {{ item.username.charAt(0) }}
                    </el-avatar>
                  </div>
                  <div class="user-details">
                    <span class="user-name">{{ item.username }}</span>
                  </div>
                </div>

                <div class="score">
                  <span class="user-score">{{ item.score }} 分</span>
                </div>

                <!-- hover 显示维度分数和提交统计 -->
                <div class="rank-item-detail">
                  <div class="dimension-bars">
                    <div class="dimension-bar-item">
                      <span class="dim-label">编程</span>
                      <div class="dimension-bar">
                        <div class="dimension-fill coding" :style="{ width: getDimensionPercent(item.dimension_scores?.coding_score) }">
                          <span class="dimension-text">{{ getDimensionValue(item.dimension_scores?.coding_score) }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="dimension-bar-item">
                      <span class="dim-label">准确</span>
                      <div class="dimension-bar">
                        <div class="dimension-fill accuracy" :style="{ width: getDimensionPercent(item.dimension_scores?.accuracy_score) }">
                          <span class="dimension-text">{{ getDimensionValue(item.dimension_scores?.accuracy_score) }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="dimension-bar-item">
                      <span class="dim-label">时长</span>
                      <div class="dimension-bar">
                        <div class="dimension-fill time" :style="{ width: getDimensionPercent(item.dimension_scores?.learning_time_score) }">
                          <span class="dimension-text">{{ getDimensionValue(item.dimension_scores?.learning_time_score) }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="dimension-bar-item">
                      <span class="dim-label">做题</span>
                      <div class="dimension-bar">
                        <div class="dimension-fill count" :style="{ width: getDimensionPercent(item.dimension_scores?.problem_count_score) }">
                          <span class="dimension-text">{{ getDimensionValue(item.dimension_scores?.problem_count_score) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="submission-stats" v-if="item.submission_stats">
                    <div class="submission-item">
                      <span class="stat-label">提交</span>
                      <span class="stat-value">{{ item.submission_stats.total_submissions || 0 }}</span>
                    </div>
                    <div class="submission-item">
                      <span class="stat-label">通过</span>
                      <span class="stat-value">{{ item.submission_stats.accepted_count || 0 }}</span>
                    </div>
                    <div class="submission-item">
                      <span class="stat-label">均分</span>
                      <span class="stat-value">{{ (item.submission_stats.avg_score || 0).toFixed(1) }}</span>
                    </div>
                    <div class="submission-item">
                      <span class="stat-label">准确率</span>
                      <span class="stat-value">{{ (item.submission_stats.accuracy || 0).toFixed(1) }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-scrollbar>

          <div class="rankNull" v-else>
            <img src="@/assets/image/emptyStatus.png" alt="暂无排名">
            <div class="text">暂无排名</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 评论区 -->
    <div class="comment-area">
      <div class="content">
        <div class="title">
          帖子社区
        </div>

        <div class="nav">
          <ul>
            <li :class="choosedArea === 0 ? 'choosed' : ''">
              <a href="javascript:void(0)" @click="changeArea(0)">全部</a>
            </li>
            <li :class="choosedArea === 1 ? 'choosed' : ''">
              <a href="javascript:void(0)" @click="changeArea(1)">学习区</a>
            </li>
            <li :class="choosedArea === 2 ? 'choosed' : ''">
              <a href="javascript:void(0)" @click="changeArea(2)">生活区</a>
            </li>
            <li :class="choosedArea === 3 ? 'choosed' : ''">
              <a href="javascript:void(0)" @click="changeArea(3)">资源共享区</a>
            </li>
            <li :class="choosedArea === 4 ? 'choosed' : ''">
              <a href="javascript:void(0)" @click="changeArea(4)">反馈建议区</a>
            </li>
          </ul>
        </div>


        <!-- 帖子列表 -->
        <div class="comment-list" v-if="postsList.length !== 0"> 

          <!-- 帖子组 -->
          <div class="post">
            <div class="postItem" 
              :class="userId === item.user_id ? 'myPost' : ''"
              v-for="item in postsList" 
              @click="getPost(item.post_id)"
            >


              <!-- 楼主信息 -->
              <div class="post-header">
                <!-- 头像 -->
                <div class="post-avatar">
                  <el-avatar :size="45" :src="item.avatar" style="border: 1px solid #eee">
                    {{ item.username?.[0] || '用' }}
                  </el-avatar>
                </div>

                <!-- 用户信息 -->
                <div class="post-details">
                  <div class="post-username">{{ item.username || '用户' }}</div>
                  <div class="post-id">ID：{{ item.user_id }}</div>
                </div>

                <!-- 评论数 -->
                <div class="postReplyCount">
                  评论数：{{ item.reply_count }}
                </div>

                <!-- 帖子区 -->
                <div class="post-zone">
                  {{ item.zone_name }}
                </div>
                <!-- 帖子时间 -->
                <div class="post-time">发布时间：{{ formatTime(item.created_at) }}</div>
              </div>

              
              <!-- 帖子标题 -->
              <div class="postBigTitle" :title="item.title"> 
                {{ item.title }}
              </div>

              <!-- 帖子标签 -->
              <div class="postTags" v-if="item.tags.length !== 0">
                <div class="postTag" v-for="tag in item.tags">
                  {{ tag }}
                </div>
              </div>

              <div class="postTags" v-if="item.tags.length === 0">
                <div class="tagNull">
                  暂无标签
                </div>
              </div>


            </div>
          </div>

          <!-- 翻页 -->
          <div class="pageCt">
            <div class="upPage pageBtn" @click="prevPage()" :class="page === 1 ? 'disabled' : ''">
              <span v-if="postsLoading">
                <svg class="loading-spinner" viewBox="0 0 24 24"><circle class="path" cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="60" stroke-dashoffset="0"></circle></svg>
              </span>
              <span v-else>上一页</span>
            </div>
            <div class="pageCount">
              {{ page }}/{{ totalPages }}
            </div>
            <div class="downPage pageBtn" @click="nextPage()" :class="page === totalPages ? 'disabled' : ''">
              <span v-if="postsLoading">
                <svg class="loading-spinner" viewBox="0 0 24 24"><circle class="path" cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="60" stroke-dashoffset="0"></circle></svg>
              </span>
              <span v-else>下一页</span>
            </div>
          </div>

        </div>

        <!-- 帖子列表为空 -->
        <div class="comment-nullList" v-else> 
          <div class="nullPost">
            <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
          </div>
          <div>暂无信息</div>
        </div>

      </div>

    </div>

    <!-- 查看帖子 -->
    <Transition name="fade-slide" mode="out-in">
      <div class="lookPost" v-if="isLookPost">
        <!-- 退出按钮 -->
        <div class="quit" @click="isLookPost = false,clearPostReply()">
          <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5824" width="40" height="40"><path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" p-id="5825" fill="#ffffff"></path><path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" p-id="5826" fill="#ffffff"></path></svg>
          <div>退出</div>
        </div>

        <!-- 删除按钮 -->
        <div class="delPost" 
          v-if="userId === openPostMsg.user_id"
          @click="deletePost(openPostMsg.post_id)"
        >
          <svg t="1780732732052" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1864" width="40" height="40"><path d="M861.184 192.512q30.72 0 50.688 10.24t31.744 25.6 16.384 33.28 4.608 33.28q0 7.168-0.512 11.264t-0.512 7.168l0 6.144-67.584 0 0 537.6q0 20.48-8.192 39.424t-23.552 33.28-37.376 23.04-50.688 8.704l-456.704 0q-26.624 0-50.176-8.192t-40.448-23.04-26.624-35.84-9.728-47.616l0-527.36-63.488 0q-1.024-1.024-1.024-5.12-1.024-5.12-1.024-31.744 0-13.312 6.144-29.696t18.432-30.208 31.744-23.04 46.08-9.216l91.136 0 0-62.464q0-26.624 18.432-45.568t45.056-18.944l320.512 0q35.84 0 49.664 18.944t13.824 45.568l0 63.488q21.504 1.024 46.08 1.024l47.104 0zM384 192.512l320.512 0 0-64.512-320.512 0 0 64.512zM352.256 840.704q32.768 0 32.768-41.984l0-475.136-63.488 0 0 475.136q0 21.504 6.656 31.744t24.064 10.24zM545.792 839.68q17.408 0 23.552-9.728t6.144-31.232l0-475.136-63.488 0 0 475.136q0 40.96 33.792 40.96zM738.304 837.632q18.432 0 24.576-9.728t6.144-31.232l0-473.088-64.512 0 0 473.088q0 40.96 33.792 40.96z" p-id="1865" fill="#8a8a8a"></path></svg>
          <div>删除帖子</div>
        </div>

        <div class="post-header">
          <!-- 头像 -->
          <div class="post-avatar">
            <el-avatar :size="45" :src="openPostMsg.avatar" style="border: 1px solid #eee">
              {{ openPostMsg.username?.[0] || '用' }}
            </el-avatar>
          </div>

          <!-- 用户信息 -->
          <div class="post-details">
            <div class="post-username">{{ openPostMsg.username || '用户' }}</div>
            <div class="post-id">ID：{{ openPostMsg.user_id }}</div>
          </div>

          <!-- 帖子区 -->
          <div class="post-zone">
            {{ openPostMsg.zone_name }}
          </div>
          <!-- 帖子时间 -->
          <div class="post-time">发布时间：{{ formatTime(openPostMsg.created_at) }}</div>
        </div>

        <!-- 帖子标题 -->
        <div class="postBigTitle" :title="openPostMsg.title"> 
          {{ openPostMsg.title }}
        </div>

        <!-- 分享资源跳转按钮 -->
        <div v-if="shareResourceInfo" class="share-resource-bar">
          <span class="resource-info">📦 {{ shareResourceInfo.resourceName }} · ID: {{ shareResourceInfo.resourceId }}</span>
          <button class="resource-jump-btn" @click="jumpToResource">
            <el-icon><Link /></el-icon>
            前往查看
          </button>
        </div>

        <!-- 帖子内容 -->
        <div class="postContent">
          <template v-for="(paragraph, pIndex) in processedContent.paragraphs" :key="pIndex">
            <br v-if="paragraph.type === 'empty'" />
            <div v-else class="post-paragraph">
              <template v-for="(part, partIndex) in paragraph.parts" :key="part.uniqueId || partIndex">
                <span v-if="part.content" class="post-text">{{ part.content }}</span>
                <img v-else-if="part.type === 'image'" :src="part.url" class="post-image" @click="openImagePreview(part.url)" />
                <div v-else-if="part.type === 'pdf'" class="file-wrapper">
                  <PdfViewer :url="part.url" class="pdf-viewer-container" />
                  <button class="file-download-btn" @click="handleDownload(part.url)" title="下载">
                    <el-icon><Download /></el-icon>
                  </button>
                </div>
                <div v-else-if="['word', 'ppt', 'excel'].includes(part.type)" class="file-wrapper">
                  <div class="office-container">
                    <iframe :src="getOfficePreviewUrl(part.url)" class="office-preview" frameborder="0"></iframe>
                  </div>
                  <button class="file-download-btn" @click="handleDownload(part.url)" title="下载">
                    <el-icon><Download /></el-icon>
                  </button>
                </div>
                <a v-else-if="part.type === 'video'" :href="part.url" target="_blank" class="video-link">
                  <el-icon><VideoPlay /></el-icon>
                  <span>{{ part.label }}</span>
                </a>
                <button v-else-if="part.url" class="download-btn" @click="handleDownload(part.url)">
                  <el-icon><Download /></el-icon>
                  <span>{{ part.label }}</span>
                </button>
              </template>
            </div>
          </template>
        </div>

        <!-- 帖子标签 -->
        <div class="postTags" v-if="openPostMsg.tags.length !== 0">
          <div class="postTag" v-for="tag in openPostMsg.tags">
            {{ tag }}
          </div>
        </div>

        <div class="postTags" v-if="openPostMsg.tags.length === 0">
          <div class="lookTagNull">
            暂无标签
          </div>
        </div>

        <!-- 回复区 -->
        <div class="replyArea">
          <!-- 刷新按钮 -->
          <div class="reply-header">
            <span class="reply-title">回复列表</span>
            <el-button type="primary" size="small" @click="refreshReplyList" :icon="Refresh">
              刷新
            </el-button>
          </div>
          <div class="replyItem" 
            v-for="(item,index) in openPostReply" :key="index"
            :class="{my: item.user_id === userId }"
          >
            <!-- 头像 -->
            <el-avatar class="avatar" :src="item.avatar" size="42">
              {{ item.username?.[0] || '用'}}
            </el-avatar>
            <!-- 消息内容框 -->
            <div class="msg-box">
              <div class="name">
                <span class="delReply" @click="deleteReply(item.user_id,item.reply_id)" v-if="item.user_id === userId">删除</span>
                <span style="font-size: 12px;" v-if="item.user_id === userId">&nbsp;&nbsp;ID：{{ item.user_id }}&nbsp;</span>
                {{ item.username || '用户' }}
                <span style="font-size: 12px;" v-if="item.user_id !== userId">&nbsp;ID：{{ item.user_id }}&nbsp;&nbsp;</span>
                <span class="delReply" @click="deleteReply(item.user_id,item.reply_id)" v-if="item.user_id !== userId && openPostMsg.user_id === userId">删除</span>
              </div>
              <div class="msg-content">
                <template v-for="(part, idx) in parseReplyContent(item.content)" :key="idx">
                  <span v-if="part.type === 'text'">{{ part.content }}</span>
                  <img v-else-if="part.type === 'image'" :src="part.url" class="reply-image" @click="openImagePreview(part.url)" />
                  <a v-else-if="part.type === 'video'" :href="part.url" target="_blank" class="reply-video-link">
                    <el-icon><VideoPlay /></el-icon>
                    <span>{{ part.label }}</span>
                  </a>
                  <a v-else-if="part.url" :href="part.url" target="_blank" class="reply-file-link" :title="part.label">
                    <el-icon><Document /></el-icon>
                    <span>{{ part.label }}</span>
                  </a>
                </template>
              </div>
              <div class="ct">{{ formatTime(item.created_at) }}</div>
            </div>
          </div>

          <!-- 输入框 -->
          <div class="input-box">
            <!-- 已上传文件信息 -->
            <div v-if="replyFile" class="reply-file-info">
              <el-icon><Document /></el-icon>
              <span class="reply-file-name">{{ replyFile.name }}</span>
              <el-button size="small" @click="clearReplyFile" type="danger" text>清空</el-button>
            </div>
            <el-input class="input" v-model="replyForm.content" placeholder="输入您想回复的话..." @keyup.enter="replyPost(openPostMsg.post_id)"/>
            <div class="btn">
              <!-- 上传文件按钮 -->
                <el-tooltip effect="dark" content="上传文件" placement="top">
                  <div class="reply-upload-icon" @click="replyFileInputRef?.click()">
                    <input 
                      ref="replyFileInputRef"
                      type="file" 
                      @change="handleReplyFileSelect" 
                      style="display: none"
                    >
                      <el-icon class="btn-icon"><Upload /></el-icon>
                  </div>
                </el-tooltip>
              <el-tooltip effect="dark" content="发送" placement="top">
                <a href="javaScript:void(0)" @click="replyPost(openPostMsg.post_id)">
                  <el-icon class="btn-icon"><Promotion /></el-icon>
                </a>
              </el-tooltip>
            </div>
          </div>

        </div>
            
      </div>
    </Transition>
    
  </div>
  
  <!-- 图片预览弹窗 -->
  <Transition name="fade">
    <div v-if="showImagePreview" class="image-preview-mask" @click="closeImagePreview">
      <div class="image-preview-container" @click.stop>
        <img :src="previewImageUrl" class="preview-image" />
        <button class="close-preview-btn" @click="closeImagePreview">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ================= 页面过渡动画样式 ================= */

/* 1. 定义进入和离开的起始/结束状态 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.5s ease-in-out;
}

/* 2. 进入前状态 (透明 + 稍微向下偏移 + 轻微缩小) */
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
}

/* 3. 离开后状态 (透明 + 稍微向上偏移 + 轻微缩小) */
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.98);
}

/* 回顶按钮 */
.back-top {
  position: fixed;
  right: 30px;
  bottom: 50px;
  width: 50px;
  height: 50px;
  background: var(--primary);
  color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border-radius: 50%;
  text-align: center;
  line-height: 45px;
  font-size: 30px;
  cursor: pointer;
  transition: all 0.3s ease;
  transform: scale(1);
}
.back-top:hover {
  box-shadow: var(--shadow-brand);
  transform: scale(1.15);
}

.container {
  position: relative;
  min-width: 1400px;
  width: 100%;
  min-height: 1700px;
  max-height: 2513px;
  padding-top: 30px;
  background: transparent;
}
.top {
  width: 100%;
  display: flex;
  justify-content: space-between;
}
.left {
  width: 80%;
}
.right {
  padding: 0 10px;
  width: 20%;
  /* border: 1px solid red; */
}
.left-top {
  /* border: 1px solid red; */
  padding-left: 10px;
  width: 100%;
  height: 500px;
  display: flex;
  justify-content: space-between;
}
/* 功能区 */
.left-card {
  border-radius: 12px;
  width: 25%;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  overflow: hidden;
  position: relative;
  transition: all 0.3s ease;
}
.left-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary));
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.left-card:hover {
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.15);
  transform: translateY(-2px);
}
/* 写心得评论 */
.left-bottom {
  padding-top: 10px;
  padding-left: 10px;
  width: 100%;
  height: 300px;
  /* border: 1px solid red; */
}
/* 轮播图 */
.panner {
  width: 75%;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}
.panner:hover {
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.15);
}
.el-carousel__item h3 {
  color: #475669;
  opacity: 0.75;
  line-height: 500px;
  margin: 0;
  text-align: center;
}
.el-carousel__item img {
  width: 100%;
  height: 500px;
  object-fit: cover;
  object-position: center;
}
.el-carousel__item:nth-child(2n) {
  background-color: #99a9bf;
}
.el-carousel__item:nth-child(2n + 1) {
  background-color: #d3dce6;
}



/* 排行榜卡片 */
.rank-card {
  position: relative;
  width: 100%;
  height: 100%;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  border-top: 5px solid var(--primary);
}


/* 写心得评论区域优化 */
.left-bottom {
  padding-top: 10px;
  padding-left: 10px;
  width: 100%;
  height: 300px; /* 保持原有高度 */
  /* border: 1px solid red; */
}

/* 写心得评论卡片内部布局 */
.write-card {
  width: 100%;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background-color: var(--bg-card);
  display: flex;
  flex-direction: column;
  padding: 16px;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}
.write-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary));
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}

.write-header {
  padding-bottom: 8px;
  font-size: 22px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.write-header .title {
  margin-left: 5px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
  font-size: 20px;
  color: var(--text-title);
}

.write-header .tip {
  font-size: 13px;
  color: var(--text-gray);
  font-weight: normal;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right .postTitle {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px; 
}

.header-right .title-input {
  width: 520px;
  height: 32px;
}

.header-right .title-input :deep(.el-input__wrapper) {
  background-color: var(--bg-card);
  border-color: var(--border-color);
}

.header-right .title-input :deep(.el-input__inner) {
  color: var(--text-body);
}

.write-icon path {
  fill: var(--text-body) !important;
}

.header-right .header-zone select {
  padding: 4px 8px;
  border: 1px solid var(--text-gray);
  border-radius: 6px;
  outline: none;
  font-size: 13px;
  min-width: 90px;
  transition: border 0.2s;
}

.header-right .header-zone select:focus {
  border-color: var(--primary);
}

.postTitle .post-title {
  font-size: 20px;
  font-weight: 600; 
  white-space: nowrap;
  color: var(--text-body);
}
/* ================= 表单样式 ================= */
:deep(.el-button--primary){
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
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}


.write-content {
  flex: 1;
  margin: 6px 0;
  overflow: hidden;
  min-height: 0;
}

.custom-textarea {
  height: 100%;
}

.custom-textarea :deep(.el-textarea__inner) {
  height: 100% !important;
  min-height: unset !important;
  border: none;
  box-shadow: none;
  padding: 0;
  font-size: 14px;
  overflow-y: auto;
  background-color: var(--bg-card);
  color: var(--text-body);
}

.write-footer {
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  gap: 12px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.write-footer .tags {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  white-space: nowrap;
}

.write-footer .tags .tag-title {
  font-size: 14px;
  font-weight: 600; 
  white-space: nowrap;
  color: var(--text-body);
  flex-shrink: 0;
}

.write-footer .tags .tags-container {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 900px;
  overflow: hidden;
}

.write-footer .tags .tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background-color: var(--primary-light);
  color: var(--primary);
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.write-footer .tags .tag-remove {
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  line-height: 1;
  color: var(--text-body);
}

.write-footer .tags .tag-remove:hover {
  color: var(--danger);
}

.write-footer .tags .tag-input {
  flex: 1;
  min-width: 80px;
  max-width: 200px;
  height: 30px;
  padding: 0 6px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  outline: none;
  background-color: var(--bg-card);
  color: var(--text-body);
}

.write-footer .tags .tag-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary) inset;
}

.write-footer .tags .tag-input::placeholder {
  color: var(--text-gray);
}

.write-footer .actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.write-footer .upload-icon {
  display: flex;
  align-items: center;
  cursor: pointer;
  flex-shrink: 0;
}

.write-footer .action-icon { 
  font-size: 18px;
  color: var(--text-gray);
  transition: color 0.2s;
}

.write-footer .action-icon:hover {
  cursor: pointer; 
  color: var(--primary);
}

.uploaded-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background-color: var(--bg-input);
  border-radius: 4px;
  flex-shrink: 0;
}

.uploaded-file-name {
  font-size: 12px;
  color: var(--text-body);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.write-footer .postBtn {
  color: var(--primary);
  border: 1px solid var(--primary);
  padding: 6px 16px;
  border-radius: 10px;
  transition: all 0.2s ease-in-out;
  font-size: 14px;
  font-weight: 500;
}

.write-footer .postBtn:hover {
  cursor: pointer;
  background-color: var(--primary);
  color: var(--bg-card);
  transition: all 0.2s ease-in-out;
}

.write-footer .postBtn.postBtnStop {
  color: var(--primary-hv);
  border: 1px solid var(--primary-hv);
}

.write-footer .postBtn.postBtnStop:hover {
  cursor: not-allowed;
  color: var(--primary-light);
  border: 1px solid var(--primary-light);
}


/* 右侧排行榜卡片优化 */
.right {
  padding: 0 10px;
  width: 20%;
  /* border: 1px solid red; */
}

.rank-card {
  width: 100%;
  height: 100%;
  min-width: 217px;
  min-height: 500px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background-color: var(--bg-card);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}
.rank-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary));
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}
.rank-card:hover {
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.15);
  transform: translateY(-2px);
}

.rank-card-title {
  padding: 10px 15px;
  font-size: 22px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank-card-content {
  flex: 1;
  padding: 10px 0;
  overflow-y: auto; /* 如果列表很长，允许滚动 */
}

.rank-item {
  min-width: 24px;
  min-height: 24px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 15px;
  transition: background-color 0.3s;
}

.rank-item:hover {
  background-color: var(--bg-hover, #f5f7fa);
}

/* 排行榜空 */
.rankNull {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
}
.rankNull img {
  width: 150px;
}
.rankNull .text {
  font-size: 14px;
  color: var(--text-gray);
}

/* 排名序号样式 */
.rank-index {
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  font-weight: bold;
  font-size: 14px;
  color: var(--primary-act);
  background-color: var(--primary-fade);
  margin-right: 10px;
  border-radius: 4px;
  /* 防止压缩 */
  flex-shrink: 0; 
}


/* 用户信息区域 */
.rank-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-details {
  min-width: 100px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
}

.user-name {
  font-size: 14px;
  color: var(--text-body);
  font-weight: 500;
}

.user-score {
  font-size: 13px;
  color: var(--text-gray);
}

.rank-footer {
  position: absolute;
  bottom: 0;
  width: 100%;
  text-align: center;
  border-top: 1px solid var(--border-color, #ebeef5);
}
.rank-footer span {
  font-size: 12px;
  color: var(--text-gray);
}

/* 排行榜 hover 详情区域 */
.rank-item {
  flex-wrap: wrap;
}

.rank-item-detail {
  width: 100%;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-height 0.6s ease, opacity 0.6s ease, padding 0.6s ease;
  padding: 0 4px;
  box-sizing: border-box;
}

.rank-item:hover .rank-item-detail {
  max-height: 200px;
  opacity: 1;
  padding: 8px 4px 4px;
}

.dimension-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.dimension-bar-item {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

.dim-label {
  font-size: 10px;
  color: var(--text-gray);
  width: 24px;
  flex-shrink: 0;
  text-align: right;
}

.dimension-bar {
  flex: 1;
  min-width: 0;
  height: 12px;
  background: var(--bg-hover, #e8e8e8);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.dimension-fill {
  height: 100%;
  min-width: 0;
  border-radius: 6px;
  transition: width 0.5s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.dimension-fill.coding {
  background: linear-gradient(90deg, var(--primary), #764ba2);
}

.dimension-fill.accuracy {
  background: linear-gradient(90deg, #10b981, #059669);
}

.dimension-fill.time {
  background: linear-gradient(90deg, #f59e0b, #d97706);
}

.dimension-fill.count {
  background: linear-gradient(90deg, #ec4899, #db2777);
}

.dimension-text {
  font-size: 8px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  padding-right: 3px;
  white-space: nowrap;
  line-height: 1;
}

.submission-stats {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border-color, #ebeef5);
}

.submission-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.stat-label {
  font-size: 10px;
  color: var(--text-gray);
}

.stat-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}

/* 查看更多按钮 */
.load-more-wrapper {
  padding: 10px 0;
  text-align: center;
}

.load-more-btn {
  padding: 6px 24px;
  border: 1px solid var(--primary);
  border-radius: 16px;
  background: transparent;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.load-more-btn:hover:not(:disabled) {
  background: var(--primary);
  color: white;
}

.load-more-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 统计信息行 */
.rank-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color, #ebeef5);
}

.rank-stat-card {
  text-align: center;
  padding: 4px;
  background: var(--bg-hover, #f5f7fa);
  border-radius: 6px;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}

.stat-label {
  font-size: 10px;
  color: var(--text-gray);
  margin-top: 2px;
}

/* 权重信息行 */
.rank-weights-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 12px;
  align-items: center;
  border-bottom: 1px solid var(--border-color, #ebeef5);
  font-size: 11px;
}

.weights-title {
  font-weight: 600;
  color: var(--text-body);
}

.weight-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: var(--bg-hover, #f5f7fa);
  border-radius: 10px;
  font-size: 11px;
  color: var(--text-body);
}

/* 点赞区域 */
/* .likeArea {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.likeArea .like-count {
  font-size: 12px;
  color: var(--text-body);
}

.okLike:hover {
  cursor: pointer;
}
.okLike:hover .likeArea .like-count {
  color: var(--primary);
}

.okLike .like-icon svg path{
  transition: all 0.3s;
}

.okLike:hover .likeArea:hover .like-icon svg path {
  transform: scale(1.1);
  fill: var(--primary);
}

.noLike:hover {
  cursor: not-allowed;
} */


/* 评论区 */
.comment-area {
  width: 100%;
  /* height: 1000px; */
  padding: 10px;
  /* border: 1px solid red; */
}

.comment-area .content {
  width: 100%;
  height: 100%;
  /* border: 1px solid green; */
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}

.comment-area .content .title {
  margin-top: 10px;
  color: var(--text-title);
  font-size: 35px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}
.comment-area .content .title::before {
  content: "—— ";
  color: var(--text-gray);
}
.comment-area .content .title::after {
  content: " ——";
  color: var(--text-gray);
}

/* 导航栏部分 */
a,a:hover {
  text-decoration: none;
  color: var(--text-body);
  transition: all 0.3s;
}

.nav {
  width: 100%;
  height: 56px;
  /* border-bottom: 1px solid var(--border-color); */
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
  background: transparent;
  /* backdrop-filter: blur(10px); */
}
.nav ul {
  min-width: 1000px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-wrap: nowrap;
  justify-content: center;
  align-items: center;
  gap: 16px;
}

.nav ul li {
  border: 1px solid var(--border-color);
  border-radius: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  height: 36px;
  background-color: var(--bg-card);
}

.nav ul li a {
  color: var(--text-body);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0 20px;
  width: 100%;
  height: 100%;
  border-radius: 24px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 14px;
  font-weight: 500;
}

.nav ul li:hover {
  transform: translateY(-2px);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.15);
}

.nav ul li a:hover {
  background-color: var(--primary);
  color: #fff;
}

.nav ul > li.choosed {
  transform: translateY(-2px);
  background-color: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.2);
}

.nav ul > li.choosed a {
  color: #fff;
}



.comment-area .content .comment-list {
  width: 100%;
  height: 100%;
  /* border: 1px solid red; */
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}

.comment-area .content .comment-nullList { 
  margin: 0 auto;
  margin-top: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}
.comment-nullList > div {
  font-size: 16px;
  color: var(--text-gray);
}

.comment-nullList img {
  width: 200px;
}

.comment-list .post {
  width: 100%;
  /* border: 1px solid blue; */
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px; /* 卡片间距 */
  padding: 10px;
  box-sizing: border-box;
}

.post .postItem {
  height: auto;
  min-height: 120px;
  width: calc(50% - 12px);
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 16px;
  box-sizing: border-box;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}
.post .postItem::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--primary), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}
.post .postItem.myPost {
  background-color: var(--primary-light);
}
.post .postItem:hover {
  cursor: pointer;
  transform: translateY(-4px) scale(1.01);
  box-shadow: 0 12px 40px rgba(45, 125, 219, 0.18);
  border-color: var(--primary);
  background-color: var(--primary-light);
}
.post .postItem:hover::before {
  opacity: 1;
}




.post-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 15px;
  margin: 0 10px;

  border-bottom: 1px solid var(--border-color);
  padding-bottom: 5px;
}

.post-details {
  color: var(--text-body);
  font-size: 18px;
}
.post-details .post-username {
  font-weight: 700;
}
.post-details .post-id {
  color: var(--text-gray);
  font-size: 12px;
}

.post-header .post-time {
  position: absolute;
  right: 0;
  bottom: 6px;
  color: var(--text-gray);
  font-size: 14px;
}
.post-header .post-zone {
  position: absolute;
  right: 0;
  top: 0;
  color: var(--primary);
  font-size: 16px;
  border-radius: 12px;
  border: 1px solid var(--primary);
  padding: 0 10px;
}
.post-header .postReplyCount {
  position: absolute;
  right: 220px;
  bottom: 6px;
  color: var(--text-gray);
  font-size: 14px;
}

.postItem .postBigTitle {
  font-size: 20px;
  color: var(--text-title);
  font-weight: 700;
  margin: 5px 0;
  padding: 0 5px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;

  display: -webkit-box;
  line-clamp: 1;
  -webkit-line-clamp: 1;       /* 两行省略 */
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.postItem .postContent {
  height: 120px;
  font-size: 15px;
  color: var(--text-body);
  padding: 0 5px;
  line-height: 2;
  display: -webkit-box;
  line-clamp: 4;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.postItem .postTags {
  height: 35px;
  border-top: 1px solid var(--border-color);
  padding-top: 10px;
  margin: 0 10px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  flex-wrap: nowrap;
  overflow: hidden; /* 超出隐藏 */
  gap: 10px;
}
.postTags .postTag {
  flex-shrink: 0; /* 标签不压缩宽度 */
  padding: 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--pass);
  border: 1.5px solid var(--pass);
  border-radius: 10px;
}
.postTags .tagNull{
  color: var(--text-gray);
  margin: 0 auto;
  width: 60px;
}

.comment-list .pageCt {
  font-size: 14px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  padding: 20px 0;
}

.pageCt .pageBtn {
  color: var(--primary);
  border: 1px solid var(--border-color);
  padding: 8px 20px;
  border-radius: 24px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  background: var(--bg-card);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.pageCt .pageBtn:not(.disabled):hover {
  color: #fff;
  background-color: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
  transform: translateY(-1px);
}
.pageCt .pageBtn.disabled {
  color: var(--text-gray);
  border-color: var(--border-color);
  cursor: not-allowed;
}
.pageCt .pageBtn.disabled:hover {
  color: var(--text-gray);
  border-color: var(--border-color);
  background: var(--bg-card);
  transform: none;
}

.pageCt .pageCount {
  padding: 8px 20px;
  background: var(--bg-hover);
  border-radius: 24px;
  color: var(--text-body);
  font-weight: 500;
  min-width: 80px;
  text-align: center;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}
.loading-spinner .path {
  animation: dash 1.5s ease-in-out infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes dash {
  0% { stroke-dashoffset: 60; }
  50% { stroke-dashoffset: 15; }
  100% { stroke-dashoffset: 60; }
}


/* =====================看帖子================= */
.lookPost {
  padding: 20px 200px;
  padding-bottom: 90px;
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  min-height: 100%;
  width: 100%;
  background-color: var(--bg-page);
}
.lookPost .postBigTitle {
  font-size: 20px;
  color: var(--text-title);
  font-weight: 700;
  margin: 5px 0;
  padding: 0 5px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

/* 分享资源跳转栏 */
.lookPost .share-resource-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12px 5px;
  padding: 10px 16px;
  background: linear-gradient(135deg, var(--primary-light) 0%, #f0f7ff 100%);
  border: 1px solid var(--primary-fade);
  border-radius: 10px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}

.lookPost .share-resource-bar .resource-info {
  font-size: 13px;
  color: var(--text-body);
  font-weight: 500;
}

.lookPost .share-resource-bar .resource-jump-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  background: var(--grad-primary);
  color: #fff;
  border: none;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.lookPost .share-resource-bar .resource-jump-btn:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-brand);
}

.lookPost .share-resource-bar .resource-jump-btn:active {
  transform: scale(0.97);
}

.lookPost .postContent {
  font-size: 15px;
  color: var(--text-body);
  padding: 0 5px;
  line-height: 2;
  word-break: break-word;
}

.lookPost .postContent .post-paragraph {
  margin-bottom: 12px;
  line-height: 1.8;
}

.lookPost .postContent .post-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.lookPost .postContent .post-image {
  max-width: 100%;
  max-height: 300px;
  display: block;
  margin: 8px 0;
  border-radius: 4px;
}

.lookPost .postContent .office-preview {
  width: 100%;
  height: 600px;
  display: block;
  margin: 8px 0;
  border-radius: 4px;
}

.lookPost .postContent .pdf-viewer-container {
  width: 100%;
  margin: 8px 0;
}

.lookPost .postContent .video-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background-color: var(--primary-light);
  color: var(--primary);
  border-radius: 4px;
  text-decoration: none;
  font-size: 14px;
  margin: 4px 0;
}

.lookPost .postContent .video-link:hover {
  background-color: var(--primary);
  color: white;
}

.lookPost .postContent .download-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  background-color: var(--bg-input);
  color: var(--text-body);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  margin: 4px 0;
}

.lookPost .postContent .download-btn:hover {
  background-color: var(--primary);
  color: white;
  border-color: var(--primary);
}

.lookPost .postContent .file-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
}

.lookPost .postContent .file-download-btn {
  position: absolute;
  top: 12px;
  right: 10px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s, background-color 0.3s;
  z-index: 10;
}

.lookPost .postContent .file-wrapper:hover .file-download-btn {
  opacity: 1;
}

.lookPost .postContent .file-download-btn:hover {
  background-color: var(--primary);
}

.lookPost .postTags {
  height: 35px;
  padding-top: 5px;
  margin: 0 10px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;

  border-bottom: 1px solid var(--border-color);
  padding-bottom: 10px;
}
.lookPost .postTags .postTag {
  flex-shrink: 0;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--pass);
  border: 1.5px solid var(--pass);
  border-radius: 10px;
}
.lookPost .postTags .lookTagNull{
  color: var(--text-gray);
  width: 60px;
}

.lookPost .quit {
  z-index: 2;
  position: absolute;
  top: 40px;
  right: 40px;
}
.lookPost .delPost {
  position: absolute;
  top: 40px;
  left: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 5px;
}
.lookPost .quit:hover,
.lookPost .delPost:hover {
  cursor: pointer;
}
.lookPost .quit svg path,
.lookPost .delPost svg path {
  fill: var(--text-body) !important;
}
.lookPost .quit:hover svg path,
.lookPost .delPost:hover svg path {
  fill: var(--main-delete) !important;
}
.lookPost .quit > div,
.lookPost .delPost > div {
  color: var(--text-body);
}
.lookPost .quit:hover > div,
.lookPost .delPost:hover > div {
  color: var(--main-delete);
}

/* 回复列表头部 */
.reply-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 10px;
}

.reply-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-title);
}

/* 回复框 */
.replyItem{
  padding: 0 20px;
  display:flex;
  gap:10px;
  margin:14px 0;
}
/* 自己消息靠右 */
.replyItem.my{
  flex-direction: row-reverse;
}
.replyItem .msg-box{
  max-width:70%;
}
.replyItem.my .msg-box {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.replyItem .name{
  font-size:14px;
  font-weight: 700;
  color:var(--text-gray);
  margin-bottom:4px;
}
.replyItem.my .name {
  text-align: right;
}
.name .delReply {
  color: var(--main-shadow);
  font-weight: 700;
  font-size: 14px;
}
.name .delReply:hover {
  cursor: pointer;
  text-decoration: underline;
  color: var(--main-delete);
}
.replyItem .ct{
  font-size:10px;
  color:var(--text-gray);
  margin-top:4px;
}
.replyItem .msg-content{
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
  padding:8px 12px;
  border-radius:8px;
  width: fit-content;
}
/* 我的气泡变色 */
.replyItem.my .msg-content{
  text-align: left;
  background: var(--primary);
  border: 1px solid var(--primary);
  box-shadow: var(--shadow-brand);
  color:var(--bg-card);
}

/* 输入框 */
.input-box {
  z-index: 2;
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 30px;
  min-height: 60px;
  width: 765px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;

  /* 进一步降低默认透明度 */
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 25px;
  box-shadow:
    0 8px 32px rgba(0,0,0,0.02),
    0 0 25px rgba(255,255,255,0.02);
  transition: all 0.3s ease;
  opacity: 0.55;
}
/* hover整体提亮上浮 */
.input-box:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.24);
  transform: translateX(-50%) translateY(-4px);
  box-shadow:
    0 12px 38px rgba(0,0,0,0.1),
    0 0 30px rgba(255,255,255,0.08);
}
/* 点击输入聚焦立刻变回完全实色 */
.input-box:focus-within {
  opacity: 1;
  background: rgba(255, 255, 255, 0.22);
}

.input-box .btn,
.input-box .btn a {
  display: inline-block;
  width: 40px;
  height: 40px;
  box-shadow: 0 4px 30px rgba(0,0,0,0.1);
  background: linear-gradient(to right, var(--primary), var(--primary-hv));
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.input-box .btn {
  width: auto;
  gap: 10px;
  background: none;
  box-shadow: none;
}

.input-box .btn a:hover {
  transform: scale(1.08);
  background: var(--primary-hv);
  box-shadow: var(--shadow-brand);
}

.input-box .btn a:active {
  transform: scale(0.95);
  background: var(--primary-act);
}

.input-box .input {
  width: 700px;
  height: 50px;
  border-radius: 100%;
  --el-input-focus-border-color: var(--primary);
  --el-input-hover-border-color: var(--primary-hv);
}
.input-box .btn-icon {
  color: var(--bg-card);
  font-size: 20px;
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.input-box .input:deep(.el-input__wrapper) {
  border-radius: 25px !important; 
}
.input-box .input:deep(.el-input__wrapper.is-focus) {
  border-radius: 25px !important;
  box-shadow: 0 0 0 2px var(--primary-hv) !important;
  border: 0.5px solid var(--el-input-focus-border-color) !important;
}

.input-box .talk {
  animation: pulse 1.5s infinite ease-in-out;
}

/* 回复上传文件按钮 */
.reply-upload-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  width: 40px;
  height: 40px;
  box-shadow: 0 4px 30px rgba(0,0,0,0.1);
  background: linear-gradient(to right, var(--primary), var(--primary-hv));
  border-radius: 50%;
  transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.reply-upload-icon:hover {
  transform: scale(1.08);
}

.reply-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  margin-bottom: 6px;
  background-color: var(--bg-input);
  border-radius: 6px;
  font-size: 13px;
}

.reply-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 回复内容中的链接样式 */
.reply-image {
  max-width: 320px;
  max-height: 240px;
  border-radius: 6px;
  cursor: zoom-in;
  margin: 4px 0;
  display: block;
}

.reply-video-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background-color: var(--primary-light);
  color: var(--primary);
  border-radius: 4px;
  text-decoration: none;
  font-size: 13px;
  margin: 2px 0;
}

.reply-video-link:hover {
  background-color: var(--primary);
  color: white;
}

.reply-file-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background-color: var(--pass);
  color: #ffffff;
  border-radius: 4px;
  text-decoration: none;
  font-size: 13px;
  margin: 2px 0;
  transition: all 0.3s ease;
}

.reply-file-link:hover {
  background-color: var(--pass-hover);
  color: #ffffff;
  box-shadow: 0 2px 8px var(--pass-shadow);
}

/* 左上角 */

.left-card .bottomContent{
  padding: 0;
}
.left-card .topHead {
  padding: 10px 20px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f0fe 100%);
  border-radius: 12px 12px 0 0;
  border-bottom: 2px solid rgba(64, 158, 255, 0.15);
}

.topHead .mainTitle {
  font-size: 25px;
  font-weight: 700;
  color: #1a3a5c;
  letter-spacing: 0.5px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.topHead .subTitle {
  font-size: 13px;
  color: #5b7a9a;
  font-weight: 400;
  letter-spacing: 0.3px;
  margin-top: 2px;
}

/* 可选：增加小点缀，让头部更精致 */
.topHead .mainTitle::before {
  content: "✦ ";
  color: #409eff;
  font-size: 20px;
  opacity: 0.7;
}
.bottomContent{
  width: 100%;
  /* border: 1px solid black; */
}
.bottomContent .resource-list{
  width: 100%;
  /* border: 1px solid red; */
}
.resource-list {
  z-index: 2;
  width: 100%;
  max-width: 480px;
  /* border-radius: 20px; */
  border-radius: 10px 0 0 10px;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
}

.resource-list .rsItem {
  width: 100%;
  height: 80px;
  border: 1px solid var(--border-color);
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* border-radius: 12px; */
  background-color: var(--bg-card);
  cursor: default;
  /* 核心：transition 负责 hover 移出时的平滑复位 */
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
  transform: translateX(0);
  will-change: transform;
}

/* hover 时启动摇摆动画 */
.resource-list .rsItem:hover {
  cursor: pointer;
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.18);
  animation: swingRightLeft 1.5s ease-in-out infinite;
}

.rsItem .itemLeft {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.rsItem .itemLeft > div:first-child {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-body);
  line-height: 1.3;
}
.rsItem .itemLeft > div:first-child::before {
  content: "✦ ";
  color: #409eff;
  font-size: 20px;
  opacity: 0.3;
}

.rsItem .itemLeft > div:last-child {
  padding-left: 22px;
  font-size: 14px;
  color: var(--text-gray, #7f8c8d);
  letter-spacing: 0.3px;
}
/* .rsItem .itemLeft > div::before {
  content: "> ";
  color: #409eff;
  font-size: 14px;
  opacity: 0.3;
} */

.rsItem .itemRight {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a0aec0;
  font-size: 22px;
  transition: transform 0.25s, color 0.25s;
}

.rsItem:hover .itemRight {
  color: #409eff;
  transform: translateX(5px);
}

/* 核心动画：向右 → 向左 → 向右 循环 */
@keyframes swingRightLeft {
  0% {
    transform: translateX(0px);
  }
  25% {
    transform: translateX(25px); /* 向右 */
  }
  50% {
    transform: translateX(-2px); /* 向左回摆 */
  }
  75% {
    transform: translateX(25px); /* 再向右 */
  }
  100% {
    transform: translateX(0px); /* 回到原位 */
  }
}

/* 空状态 */
.rcNull {
  width: 100%;
  padding-top: 100px;
}
.rcNull .null-content{
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
}
.rcNull img {
  width: 150px;
}
.rcNull .null-title {
  font-size: 18px;
}
.rcNull .null-subtitle {
  font-size: 12px;
}

/* 图片预览弹窗 */
.image-preview-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  cursor: zoom-out;
}

.image-preview-container {
  position: relative;
  max-width: 90%;
  max-height: 90%;
  cursor: default;
}

.preview-image {
  max-width: 100%;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.close-preview-btn {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: background-color 0.3s;
}

.close-preview-btn:hover {
  background-color: rgba(255, 255, 255, 0.4);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 帖子图片添加点击指针 */
.lookPost .postContent .post-image {
  cursor: zoom-in;
}


</style>
