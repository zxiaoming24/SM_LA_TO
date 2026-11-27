<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage,ElMessageBox } from 'element-plus'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转查看
import { getPPTListByUserId, getTaskIdApi, getPPTProgressApi, deletePPTByIdApi } from '@/api/mainApi/resourcePPT.js'
import emitter from '@/utils/emitter'

//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
// 不再使用itemRef，改用event.currentTarget获取DOM
const popStore = useActionPopStore()
// 接收事件对象，获取当前 hover 的 DOM
const handleEnter = async (event, index, rsId, type='ppt') => {
  await nextTick()
  const el = event.currentTarget
  if (!el) return

  const rect = el.getBoundingClientRect()
  let left = rect.left - 125
  let top = rect.top - 55 // 元素上方55px

  // 顶部越界则改为下方展示
  if (top < 0) {
    top = rect.bottom + 10
  }

  // 每个item对应自身坐标弹出
  console.log('【hover】index：',index,'，rsId：',rsId)
  popStore.showPop(left, top, { id: index, title: `第${index+1}个条目`, rsId: rsId, rsType: type, userId: userId.value })
}


let loginUser = null
const userId = ref(null)// 用户ID
const skipInfo = ref()// 跳转信息
onMounted(async() => {
  // 获取用户名
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

  // 检查 应用 中是否有要打开的ppt
  if(isSkip(0) === false){
    console.log('没有ppt需要提前打开')
  }else{
    skipInfo.value = isSkip(0)
    console.log('跳转信息:', skipInfo.value)
    
    const res = await getPPTProgressApi(skipInfo.value.resourceId)
    if(res.code){
      if(res.data?.id && res.data.id !== null){
        openPPT(res.data.id,res.data.pptTitle,res.data.ossUrl)
      }else{
        ElMessage.error('该ppt不存在，可能已经被删除了')
      }
    }
    removeSkip(0)//删除跳转信息
  }

  await checkCutPPTTask()//进入截断检查
  
})

//检查截断任务
// 判断pptListAll中是否有status为null的截断ppt任务
//检查截断任务
const checkCutPPTTask = async() => { 
  console.log('检查截断任务')
  
  // 检查是否有截断任务
  const hasCutTask = pptListAll.value.some(item => item.status == null || item.status == 1)
  
  // 如果有截断任务，禁用提交按钮
  if (hasCutTask) {
    submitBtnStatus.value = true
  }
  
  for (let i = 0; i < pptListAll.value.length; i++) {
    const item = pptListAll.value[i]
    
    // 只检查状态为 null (进行中/未知) 的任务
    if (item.status == null || item.status == 1) {
      let nowNum = 0
      let maxNum = 100
      
      try {
        await getPPTProgress(item.id)
        if(PPTPROGRESS.value == '' || PPTPROGRESS.value == undefined || PPTPROGRESS.value == null ){
          ElMessage.error('获取任务进度失败')
        }

      } catch (e) {
        console.error('首次查询进度失败', e)
        continue // 跳过这个任务，查下一个
      }

      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (PPTPROGRESS.value == 1 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.id} 生成中... 第 ${nowNum} 次轮询`)
        
        // 异步等待 3 秒
        await new Promise(resolve => setTimeout(resolve, 3000))
        
        try {
          console.log('获取进度次数：',nowNum)
          await getPPTProgress(item.id)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      // 轮询结束，判断最终结果
      if (PPTPROGRESS.value == 2) {
        // 成功
        ElMessage.success('PPT 生成成功！')
        ossDownloadUrl.value = PPTPROGRESSDATA.value?.ossUrl || ''
        await getPPTList()
      } else {
        // 失败或超时
        ElMessage.warning('PPT 生成失败或超时')
        await getPPTList()
      }
    }
  }
  
  // 截断检查结束，恢复按钮状态
  if (hasCutTask) {
    submitBtnStatus.value = false
  }
}

//================接口==================
//根据用户id查询ppt列表
const getPPTList = async() => {
  console.log('获取PPT列表')
  const result = await getPPTListByUserId(userId.value)
  if(result.code){
    //获取成功
    pptListAll.value = result.data
    //计算ppt总个数
    pptTotalNum.value = pptListAll.value.length
    handleCurrentChange()
  }else{
    ElMessage.error('获取PPT列表失败');
  }
}

// 获取ppt任务id
const PPTTASKID = ref('')//任务id
const getPPTTaskId = async () => {
  PPTTASKID.value = ''//重置任务id
  console.log('获取生成任务id:', pptData.value)
  const result = await getTaskIdApi(userId.value,pptData.value)
  if(result.code){
    ElMessage.success('提交成功,正在生成中...')
    PPTTASKID.value = result.data.id
  }else{
    ElMessage.error('生成失败：',result.msg)
  }
}

// 获取ppt生成进度
const PPTPROGRESS = ref(null)
const PPTPROGRESSDATA = ref(null)// 进度返回的完整数据（成功时含 ossUrl 等）
const getPPTProgress = async (taskId) => {
  console.log('获取进度：',taskId)
  PPTPROGRESS.value = null//重置进度
  PPTPROGRESSDATA.value = null
  const result = await getPPTProgressApi(taskId)
  if(result.code){
    if(result.data.status == 1){
      PPTPROGRESS.value = 1
    }else if(result.data.status == 2){
      PPTPROGRESS.value = 2
      PPTPROGRESSDATA.value = result.data// 保存完整数据（含 ossUrl、imagesUrl 等）
    }else{
      PPTPROGRESS.value = 3
    }
  }else{
    ElMessage.error('获取生成进度失败：',result.msg)
  }
}

const pptRef = ref(null)// 表单校验
const pptData = ref({ // 表单数据
  text: ''
})
// 表单验证规则
const Rules = {
  text: [
    { required: true, message: '请输入主题/大纲', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.replace('T', ' ').substring(0, 19)
}

// 提交表单
const submitBtnStatus = ref(false)// 提交按钮状态
const submit = async() => {
  pptRef.value.validate(async(valid) => {
    if (valid) {
      console.log('表单校验通过，提交中')
      let nowNum = 0
      let maxNum = 100
      submitBtnStatus.value = true//按钮禁止点击

      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        // 获取任务id
        await getPPTTaskId()

        if(PPTTASKID.value == '' || PPTTASKID.value == undefined || PPTTASKID.value == null ){
          ElMessage.error('获取生成任务失败')
          submitBtnStatus.value = false
          return
        }

        //刷新PPT列表
        await getPPTList()

        //获取任务进度
        await getPPTProgress(PPTTASKID.value)

        if(PPTPROGRESS.value == '' || PPTPROGRESS.value == undefined || PPTPROGRESS.value == null ){
          ElMessage.error('获取任务进度失败')
          submitBtnStatus.value = false
          return
        }

        // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
        while (PPTPROGRESS.value == 1 && nowNum < maxNum) {
          nowNum++
          await new Promise(resolve => setTimeout(resolve, 3000))
          await getPPTProgress(PPTTASKID.value)
        }

        // 轮询结束，判断最终结果
        if (PPTPROGRESS.value == 2) {
          // 成功
          ElMessage.success('PPT 生成成功！')
          ossDownloadUrl.value = PPTPROGRESSDATA.value?.ossUrl || ''
          await getPPTList()
        } else {
          // 失败或超时
          ElMessage.warning('PPT 生成失败或超时')
          await getPPTList()
        }
      } finally {
        submitBtnStatus.value = false// 恢复按钮状态
        clearTimeout(gameInvitationTimer)
      }
 
    } else {
      console.log('校验失败')
      return false
    }
  })
}

// PPT列表所有数据（存储）
const pptListAll = ref()
// PPT列表展示数据（渲染）
const pptList = ref()

//============PPT列表=============
const currentPage = ref(1)// 当前页
const pptTotalNum = ref(null)// PPT总个数
const index = ref(null)// 当前页索引
const listLoading = ref(false)// 列表加载页
const openListLoading = (status) => {
  listLoading.value = (status == 1 ? true : false)
}
// 页码切换时执行
const handleCurrentChange = () => {
  //加载页显示
  openListLoading(1)
  //清空pptList数据
  pptList.value = []
  // 不再依赖ref数组，改用event.currentTarget
  // 判断PPT列表数据长度
  if(pptListAll.value.length > 12){
    // 长度大于12，找索引
    index.value = (currentPage.value - 1) * 12
    // 循环12个，不够12个，结束循环
    for(let i = index.value; i < index.value + 12; i++){
      if(pptListAll.value[i] == null){
        break//结束整个循环
      }else{
        pptList.value.push(pptListAll.value[i])
      }
    }
    openListLoading(0)
  }else if(pptListAll.value.length > 0){
    pptList.value = [...pptListAll.value] // 创建新数组引用，确保Vue响应式更新
    openListLoading(0)
  }else{
    //加载页关闭
    openListLoading(0)
  }
}

// 查看PPT
const previewPPTName = ref('')// PPT名称
const pptPreviewUrl = ref('')// PPT地址
const ossDownloadUrl = ref('')// OSS下载地址
const openPPT = (pptId,PPTName,ossUrl) => {
  console.log("查看PPT：",pptId)
  previewPPTName.value = PPTName
  ossDownloadUrl.value = ossUrl
  isShowPPT.value = true
  pptPreviewUrl.value = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(ossUrl)}`
}


// 删除PPT
const deletePPT = async(pptId) => {
  //询问是否删除
  const confirmResult = await ElMessageBox.confirm('是否删除该PPT？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  console.log("删除ppt：",pptId)
  const result = await deletePPTByIdApi(pptId)
  if(result.code){
    ElMessage.success("删除成功")
    await getPPTList()
  }else{
    ElMessage.error("删除失败：",result.msg)
  }
}

//弹出页下载ppt
const downloadPPT = () => {
  if (!ossDownloadUrl.value) {
    ElMessage.warning('下载地址不存在')
    return
  }
  console.log("开始下载:", ossDownloadUrl.value)
  const link = document.createElement('a')// 创建临时 a 标签
  link.href = ossDownloadUrl.value
  
  // 触发点击
  document.body.appendChild(link)
  link.click()
  
  // 清理 DOM
  document.body.removeChild(link)
}

//PPT列表-下载ppt
const downloadPPTInList = (url) => { 
  console.log("开始下载:", url)
  const link = document.createElement('a')
  link.href = url
  
  // 触发点击
  document.body.appendChild(link)
  link.click()
  
  // 清理 DOM
  document.body.removeChild(link)
}

// =============预览弹窗=============
const isShowPPT = ref(false)// 显示 PPT展示页面
const isIframeLoading = ref(true)// 显示 iframe加载中页面

// 返回列表/关闭预览
const close = () => { 
  if(isShowPPT.value == true){
    isShowPPT.value = false
    previewPPTName.value = ''
    pptPreviewUrl.value = ''
  }
  ossDownloadUrl.value = ''
}
</script>

<template>
  <div class="container">
    <div class="title">
      <h1 v-if="isShowPPT == true">PPT 预览</h1>
      <h1 v-else>PPT 智能生成</h1>
      <p class="subtitle" v-if="isShowPPT == true">正在预览 【{{ previewPPTName }}】</p>
      <p class="subtitle" v-else>输入学习主题，一键生成精美讲解PPT</p>
    </div>
    
      
    <Transition name="fade-slide" mode="out-in">
      <!-- ppt列表 -->
      <div class="inputBox" v-if="isShowPPT == false">
      <!-- 左侧预览区（占位） -->
      <div class="left">

        <!-- 加载页 -->
        <div class="list-loading" v-if="listLoading == true"> 
          <el-icon class="is-loading" :size="50" color="var(--primary)"><Loading /></el-icon>
          <span class="loading-text">正在加载</span>
        </div>
        
        <!-- 存在ppt列表时，显示列表 -->
        <div class="pptItems" v-if="pptList != null && pptList.length > 0 && listLoading == false"> 
          <div class="ppt-item" 
            v-for="(item,index) in pptList" :key="item.id"
          >

            <!-- 状态为2时，显示PPT项 -->
            <div class="itemType" 
              v-if="item.status == 2" 
              @click="openPPT(item.id,item.pptTitle,item.ossUrl)"
              @mouseenter="handleEnter($event,index,item.id)"
              @mouseleave="popStore.delayHidePop"
            >
              <!-- 下载按钮 -->
              <div class="downBtn" title="下载" @click.stop="downloadPPTInList(item.ossUrl)">
                <el-icon :size="20" color="var(--bg-card)"><Download /></el-icon>
              </div>
              <!-- 删除按钮 -->
              <div class="delBtn" title="删除" @click.stop="deletePPT(item.id)">
                <el-icon :size="20" color="var(--bg-card)"><Delete /></el-icon>
              </div>
              <div class="image">
                <img :src="item.imageUrl" alt="PPT首图"/>
              </div>
              <div class="info">
                <div class="pptTitle" :title="item.pptTitle">
                  {{ item.pptTitle }}
                </div>
                <div class="pptBottom">
                  <div class="createTime">
                    {{ formatTime(item.createdAt) }}
                  </div>
                  <div class="pageCount">
                    {{ item.pageCount }}页
                  </div>
                </div>
              </div>
            </div>

            <!-- 状态为3时，显示失败项 -->
            <div class="itemType failBox" v-else-if="item.status == 3">
              <!-- 删除按钮 -->
              <!-- .stop阻止父级函数 -->
             <div class="delBtn" title="删除" @click.stop="deletePPT(item.id)"><el-icon :size="20" color="var(--bg-card)"><Delete /></el-icon></div>
             <div class="image fail">
               <el-icon class="shake-icon" :size="50"><CloseBold /></el-icon>
               <div class="fail-text">生成失败</div>
             </div>
             <div class="info">
               <div class="pptTitle">{{ item.pptTitle }}</div>
               <div class="pptBottom">
                 <div class="createTime">
                   {{ formatTime(item.createdAt) }}
                 </div>
               </div>
             </div>
            </div>

            <!-- 状态为1/null时，显示生成项 -->
            <div class="itemType loadingBox" v-else>
             <div class="icon loading-state">
               <!-- 添加 class="is-loading" 以启用旋转动画 -->
               <el-icon class="is-loading" :size="40" color="var(--primary)">
                 <Loading />
               </el-icon>
               <span class="loading-text">智能生成中</span>
             </div>
             <!-- <div class="info">
               <div class="pptTitle">{{ item.ppt_title }}</div>
               <div class="pptBottom">
                 <div class="createTime">
                   {{ item.created_at }}
                 </div>
               </div>
             </div> -->
            </div> 
            
          </div>
        </div> 

        <!-- 无ppt列表时，显示占位符 -->
        <div class="preview-placeholder" v-else-if="pptList != null && pptList.length == 0 && listLoading == false">
          <img src="@/assets/image/emptyStatus.png" alt="">
          <p>暂无PPT</p>
        </div>

        <!-- 分页 -->
        <div class="pageNav" v-if="pptList != null && pptList.length > 0 && listLoading == false">
          <el-pagination
            v-model:current-page="currentPage"
            default-page-size=12
            layout="prev, pager, next, jumper"
            :total="pptTotalNum"
            :page-count="Math.ceil(pptTotalNum/12)"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>

      

      <!-- 右侧表单区 -->
      <div class="right">
        <el-form 
          :rules="Rules" 
          ref="pptRef" 
          :model="pptData" 
          label-position="top"
          class="ppt-form"
          @keyup.enter.native="submit"
        >
          <el-form-item label="主题/大纲/知识点" prop="text">
            <el-input 
              v-model="pptData.text"
              size="large" 
              show-word-limit 
              maxlength="30" 
              placeholder="例如：人工智能的发展历史"
              clearable
            />
          </el-form-item>

          <el-form-item class="btn-item">
            <el-button 
              type="primary" 
              size="large" 
              class="submit-btn"
              @click="submit"
              :disabled="submitBtnStatus"
            >
              立即生成 PPT
            </el-button>
          </el-form-item>
        </el-form>
      </div>
      </div>

      <!-- 预览区域 -->
      <!-- 已完成ppt查看 -->
      <div class="showPPT" v-else-if="isShowPPT == true">
      
      <el-tooltip
        effect="dark"
        content="返回"
        placement="bottom"
      >
        <div class="backA" @click="close">
          <el-icon><Back /></el-icon>
        </div>
      </el-tooltip>
      
      <div class="showArea">
        <!-- 加载遮罩 -->
        <div v-if="isIframeLoading" class="iframe-loading-mask">
          <el-icon class="is-loading" :size="40"><Loading /></el-icon>
          <p>正在加载预览...</p>
        </div>

        <iframe 
          :src="pptPreviewUrl" 
          width="100%" 
          height="100%" 
          frameborder="0"
          @load="isIframeLoading = false"
        ></iframe>
      </div>
      
      <el-tooltip
        effect="dark"
        content="下载ppt"
        placement="bottom"
      >
        <div class="downloadA" @click="downloadPPT">
          <el-icon><Download /></el-icon>
        </div>
      </el-tooltip>
      
      
      </div>


    </Transition>
  

  </div>
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

/* ================= 容器样式 ================= */
.container {
  width: 100%;
  height: 100%;
  padding: 0 30px;
  box-sizing: border-box;
  background: transparent;
}

.title {
  text-align: center;
  margin-bottom: 20px;
}

.title h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
}

.subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

.inputBox {
  width: 100%;
  min-height: 700px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

/* 左侧预览区样式 */
.inputBox .left {
  position: relative;
  flex: 1; /* 自动占据剩余空间 */
  min-height: 500px;
  /* border: 1px solid green; */
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
}

.preview-placeholder {
  text-align: center;
  color: var(--text-gray);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.preview-placeholder img {
  width: 170px;
}

.preview-placeholder p {
  font-size: 15px;
  color: var(--text-gray);
}

/* 右侧表单区样式 */
.inputBox .right {
  width: 400px; 
  height: 200px;
  background-color: var(--bg-card);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);
  padding: 30px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  transition: all 0.5s;
}

.inputBox .right:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}

.ppt-form {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: end;
}

/* 调整表单项间距 */
:deep(.el-form-item) {
  margin-bottom: 22px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-gray);
}

/* 评分组件居中 */
.rate-container {
  display: flex;
  align-items: center;
}

/* 按钮样式优化 */
.btn-item {
  margin-bottom: 0;
  margin-top: 10px;
}

.submit-btn {
  width: 100%;
  font-weight: bold;
  letter-spacing: 1px;
  transition: all 0.3s;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--primary-hv);
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

/* ================ppt item样式================ */
/* 最外层大盒子 */
.pptItems { 
  /* border: 1px solid black; */
  margin-bottom: 25px;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 15px;
  align-content: flex-start;
}
/* ppt项的每个盒子 */
.ppt-item { 
  width: 240px;
  height: 210px;
  /* width: 23.5%;
  height: 31.5%; */
  transition: all 0.3s;
}

.ppt-item:hover { 
  cursor: pointer;
}
/* 鼠标移入时，失败项和生成项鼠标不变样式 */
.ppt-item:has(.failBox):hover,
.ppt-item:has(.loading-state):hover {
  cursor: default;
}
/* 兼容写法 */
.itemType.failBox:hover,
.itemType.loadingBox:hover {
  cursor: default;
}

/* 鼠标移入时，显示删除按钮 */
.ppt-item:hover .itemType .delBtn { 
  opacity: 1;
  visibility: visible;
}

/* 鼠标移入时，显示删除按钮 */
.ppt-item:hover .itemType .downBtn { 
  opacity: 1;
  visibility: visible;
}

/* ppt项内容盒子 */
.itemType {
  width: 100%;
  height: 100%;
  padding: 7px;
  border-radius: 10px;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  transition: all 0.5s;
}
.itemType:hover {
  /* 上升 */
  transform: translateY(-5px);
  box-shadow: var(--shadow-brand);
}
.itemType.failBox:hover {
  box-shadow: 0 4px 10px var(--main-shadow);
}
.itemType .image {
  position: relative;
  width: 100%;
  height: 140px;
  border-radius: 10px;
  overflow: hidden;
}

/* 删除按钮 */
.itemType .delBtn { 
  z-index: 1;
  opacity: 0;
  visibility: hidden;
  position: absolute;
  width: 30px;
  height: 30px;
  top: 12px;
  right: 12px;
  background-color: var(--main-delete);
  border: 1px solid var(--main-delete);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
}
/* 下载按钮 */
.itemType .downBtn { 
  z-index: 1;
  opacity: 0;
  visibility: hidden;
  position: absolute;
  width: 30px;
  height: 30px;
  top: 12px;
  right: 50px;
  background-color: var(--download-btn-bg);
  border: 1px solid var(--download-btn-bg);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
}
.itemType .delBtn:hover,
.itemType .downBtn:hover {
  cursor: pointer;
  transform: translateY(-2px);
  box-shadow: 0 0 12px var(--main-fail-status);
}

.itemType img { 
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: bottom; /* 底部对齐 */
  display: block; /* 消除图片默认的 inline-block 间隙 */
}

/* ppt项下的信息盒子 */
.itemType .info {
  margin-top: 6px;
  padding: 0 4px;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  /* border: 1px solid orange; */
}
/* ppt标题 */
.info .pptTitle {
  font-size: 18px;
  /* 溢出显示省略号 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* ppt底部信息 */
.info .pptBottom {
  /* border: 1px solid blue;  */
  display: flex;
  justify-content: space-between;
}
.pptBottom div {
  font-size: 13px;
  color: var(--text-gray);
}
/* ppt项中，不显示首图时的占位图标 */
.itemType .icon {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

/* ========ppt生成动画======== */
/* 加载状态容器 */
.itemType .icon.loading-state {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background-color: rgba(var(--primary-rgb, 64, 158, 255), 0.05); 
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px; /* 图标和文字的间距 */
  color: var(--text-gray);
}
/* ppt列表-加载图标样式 */
.list-loading {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  color: var(--text-gray);
}
/* 分页栏样式 */
.pageNav {
  width: 100%;
  position: absolute;
  bottom: -20px;
}
.pageNav .el-pagination { 
  display: flex;
  justify-content: center;
  align-items: center;
}
/* 分页组件样式 */
:deep(.el-pagination) {
  --el-pagination-hover-color: var(--primary);
  --el-pagination-button-bg-color: transparent;
}
/* 当前页码高亮 */
:deep(.el-pagination .el-pager li.is-active) {
  color: var(--primary);
  background-color: var(--primary-light);
  font-weight: bold;
}
/* 页码悬停效果 */
:deep(.el-pagination .el-pager li:hover) {
  color: var(--primary);
}
/* 上一页/下一页按钮悬停 */
:deep(.el-pagination button:hover:not(:disabled)) {
  color: var(--primary);
}
/* 跳转输入框聚焦 */
:deep(.el-pagination .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}



/* 加载文字样式 */
.loading-text {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out; /* 文字呼吸效果 */
}
.loading-text::after {
  content: '...';
  /* steps(5, end) 计时函数：将动画分成若干个阶梯状的步骤，而不是平滑地渐变 */
  animation: dots 1.5s steps(5, end) infinite;
}
/* Element Plus 图标旋转动画类 */
.el-icon.is-loading {
  animation: rotating 2s linear infinite;
}
/* 定义旋转关键帧 */
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
/* 定义文字闪烁呼吸关键帧 */
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
/* 定义文字呼吸点关键帧 */
@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}

/* ========生成失败项======== */
/* ppt生成失败时，显示文字样式 */
.itemType .fail {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: var(--main-fail-status);
  animation: bg-pulse 3s infinite ease-in-out;
  color: var(--main-delete); /* 统一使用 Element 危险色 */
}
/* 失败状态下的图标样式 */
.itemType .fail .shake-icon {
  color: var(--main-delete);
  margin-bottom: 8px;
  /* 添加抖动动画 */
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
  transform: translate3d(0, 0, 0);
  backface-visibility: hidden;
  perspective: 1000px;
}

/* 失败文字样式 */
.itemType .fail .fail-text {
  font-size: 14px;
  font-weight: 500;
  opacity: 0;
  animation: fade-in-up 0.5s ease-out forwards;
  animation-delay: 0.3s; /* 等图标抖完再显示文字 */
}
/* 图标抖动动画 (Shake) */
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
/* 背景呼吸动画 (Background Pulse) */
@keyframes bg-pulse {
  0% { background-color: var(--main-fail-status); }
  50% { background-color: var(--main-fail-status-hover); } /* 稍微深一点的红 */
  100% { background-color: var(--main-fail-status); }
}
/* 文字上浮渐显 (Fade In Up) */
@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}


/* ==========================查看ppt====================== */
.showPPT {
  width: 100%;
  height: 680px;
  /* border: 1px solid red; */
  position: relative; /* 为绝对定位的遮罩提供参照 */
  display: flex;
  justify-content: center;
  align-items: center;
}
/* 加载中遮罩 */
.iframe-loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: var(--bg-page);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 2;
  color: var(--text-gray);
}
/* 展示区域 */
.showPPT .showArea { 
  width: 1165px;
  height: 100%;
  border-radius: 20px;
  box-shadow: var(--shadow-normal);
  overflow: hidden;
}

.backA,
.downloadA{
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 2px solid var(--primary-hv);
  display: flex;
  flex-shrink: 0; /* 防止在 Flex 布局中被压缩变形 */
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
}

.backA .el-icon,
.downloadA .el-icon {
  font-size: 40px;
  color: var(--primary-hv);
}

.backA {
  margin-right: 50px;
}

.downloadA {
  margin-left: 50px;
}


.backA:hover,
.downloadA:hover {
  cursor: pointer;
  background-color: var(--primary-hv);
}

.backA:hover .el-icon,
.downloadA:hover .el-icon {
  color: var(--bg-page);
}

.backA:active,
.downloadA:active {
  background-color: var(--primary-light);
}


</style>