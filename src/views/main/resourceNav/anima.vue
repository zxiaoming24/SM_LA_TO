<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转查看
import { getAnimaListApi, generateAnimaApi, pollAnimaApi, deleteAnimaApi } from '@/api/mainApi/resourceAnima.js'
import emitter from '@/utils/emitter'

//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
const itemRef = ref([])// 循环ref 必须初始化为空数组
const popStore = useActionPopStore()
// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index, rsId, type='animation') => {
  await nextTick()
  const el = itemRef.value[index]
  if (!el) return

  const rect = el.getBoundingClientRect()
  let left = rect.left
  let top = rect.top - 60 // 元素上方60px

  // 顶部越界则改为下方展示
  if (top < 0) {
    top = rect.bottom + 10
  }

  // 每个item对应自身坐标弹出
  console.log('【hover】index：',index,'，rsId：',rsId)
  popStore.showPop(left, top, { id: index, title: `第${index+1}个条目`, rsId: rsId, rsType: type, userId: userId.value })
}


// ===================数据=====================
let loginUser = null
const userId = ref(null)// 用户ID
const skipInfo = ref()//跳转信息
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

  await getList()// 获取列表

  // 检查 应用 中是否有要打开的编程题
  if(isSkip(6) === false){
    console.log('没有编程题需要提前打开')
  }else{
    skipInfo.value = isSkip(6)
    console.log('跳转信息:', skipInfo.value)
    try{
      await getValue(skipInfo.value.resourceId)
    }catch(e){
      ElMessage.error('该动画不存在，可能已经被删除了')
      console.log('打开失败')
    }
    
    removeSkip(6)//删除跳转信息
  }

  await checkList()// 检查列表
  
})

const animaData = ref({
  userId: null,
  text: '',
  enableTts: true  // 是否启用语音，默认开启
})
const animaRef = ref(null)
const btnDisvisible = ref(false)//按钮禁用是否开启
const Rules = {
  text: [
    { required: true, message: '请输入动画主题/知识点', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}
const task = ref({})// 任务项
const taskProgress = ref({})// 任务项进度

const isShow = ref(false)//是否显示预览
const showHtmlData = ref({// 显示的html数据
  id: null,
  text: '',
  status: null,
  createTime: '',
  htmlContent: ''
})
//生成中html
const ingHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#fff; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1); min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center;">
  <div style="width:60px; height:60px; border:4px solid #DBEAFE; border-top-color:#2D7DDB; border-radius:50%; animation:spin 1s linear infinite; margin-bottom:20px;"></div>
  <h2 style="color:#2D7DDB; border-left:4px solid #2D7DDB; padding-left:12px; font-size:20px;">正在生成动画中，请稍候...</h2>
  <p style="color:#64748B; font-size:14px; margin-top:10px;">系统正在处理你的数据，请稍等片刻</p>
  <style>
    @keyframes spin { to { transform:rotate(360deg); } }
  </style>
</div>`
//失败html
const failHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#ffffff; min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.08);">
  <div style="font-size:70px; color:#E53E3E; margin-bottom:24px; animation: shake 0.5s ease-in-out infinite alternate;">✕</div>
  <h2 style="color:#E53E3E; border-left:4px solid #E53E3E; padding-left:12px; font-size:22px; font-weight:bold; margin-bottom:16px;">生成失败</h2>
  <p style="color:#64748B; font-size:15px; text-align:center;">动画生成过程中出现异常，请删除重试</p>
  <style>@keyframes shake{0%{transform:scale(1);opacity:0.8;}100%{transform:scale(1.1);opacity:1;}}</style>
</div>`

// 用于安全显示HTML内容的iframe引用
const iframeRef = ref(null)
// 预览时使用的HTML内容（避免直接v-html）
const previewHtmlContent = ref('')

const allList = ref([])// 所有列表
const showList = ref([])// 显示列表

// ===========函数============
// 查看更多收起
const isOpenList = (operation) => {
  if(operation == 0){//查看更多
    showList.value = [...allList.value]
  }else if(operation == 1){ //收起
    showList.value = allList.value.slice(0,20)
  }else{
    ElMessage.error('失败')
  }
}

//退出预览
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

// 安全显示HTML内容（使用iframe sandbox）
const displayHtmlContent = (htmlString) => {
  if (!htmlString) {
    previewHtmlContent.value = ''
    return
  }
  // 将HTML内容赋值给iframe
  previewHtmlContent.value = htmlString
  // 确保iframe重新加载内容
  setTimeout(() => {
    if (iframeRef.value) {
      const iframeDoc = iframeRef.value.contentDocument || iframeRef.value.contentWindow.document
      iframeDoc.open()
      iframeDoc.write(htmlString)
      iframeDoc.close()
    }
  }, 0)
}

//检查列表
const checkList = async() => { 
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i];
    if(item.status == 1 || item.status == null){
      //轮询获取进度
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(item.id)// 尝试查一次
        if(taskProgress.value == {}){//查不到返回结果
          ElMessage.error('获取生成进度失败')
        }else if(taskProgress.value.status == null){
          await deleteItem(item.id,false)
          ElMessage.error('有生成项请求生成失败，直接删除')
          await getList()
          taskProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      
      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.id} 生成中... 第 ${nowNum} 次轮询`)
        
        // 异步等待 10 秒
        await new Promise(resolve => setTimeout(resolve, 10000))
        
        try {
          console.log('获取进度次数：',nowNum)
          await getProgress(item.id)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      // 轮询结束，判断最终结果
      if (taskProgress.value.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getList()
        taskProgress.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getList()
        taskProgress.value = {}
      } 
    }
  }
}

// 提交表单
const submit = async () => { 
  itemRef.value = []
  animaRef.value.validate(async(valid) => {
    if (valid) {
      animaData.value.userId = userId.value
      console.log('表单校验通过，提交中')
      btnDisvisible.value = true
      
      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        await createTask()//创建任务获取任务项task
        if(taskProgress.value.status == 1 || taskProgress.value.status == null){
          //轮询获取进度
          let nowNum = 0
          let maxNum = 40

          try {
            await getProgress(task.value.id)// 尝试查一次
            if(taskProgress.value == {}){//查不到返回结果
              ElMessage.error('获取生成进度失败')
            }else if(taskProgress.value.status == null){
              await deleteItem(task.value.id,false)
              ElMessage.error('有生成项请求生成失败，直接删除')
              await getList()
              task.value = {}
              taskProgress.value = {}
            }
          } catch (e) {
            console.error('首次查询进度失败', e)
          }

          await getList()
          await getValue(task.value.id)

          // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
          while (taskProgress.value.status == 1 && nowNum < maxNum) {
            nowNum++
            console.log(`任务 ${task.value.id} 生成中... 第 ${nowNum} 次轮询`)

            // 异步等待 10 秒
            await new Promise(resolve => setTimeout(resolve, 10000))

            try {
              console.log('获取进度次数：',nowNum)
              await getProgress(task.value.id)
            } catch (e) {
              console.error('轮询进度失败', e)
            }
          }

          // 轮询结束，判断最终结果
          if (taskProgress.value.status == 2) {
            console.log(` ${task.value.id} 任务完成`)
            await getList()
            await getValue(task.value.id)
            task.value = {}
            taskProgress.value = {}
          } else {
            console.log(` ${task.value.id} 未完成`)
            await getList()
            await getValue(task.value.id)
            task.value = {}
            taskProgress.value = {}
          }
        }else if(taskProgress.value.status == 2 || taskProgress.value.status == 3){//一提交就好了
          await getList()
          await getValue(task.value.id)
          task.value = {}
          taskProgress.value = {}
        }
      } finally {
        clearTimeout(gameInvitationTimer)
      }

      btnDisvisible.value = false
      animaData.value = {userId: null, text: '', enableTts: true}
    }else {
      console.log('校验失败')
      return false
    }
  })
}

// ===========接口============
// 获取列表
const getList = async () => {
  itemRef.value = []
  try {
    const result = await getAnimaListApi(userId.value)
    if(result.code){
      allList.value = result.data
      showList.value = allList.value.slice(0,20)
    }else{
      ElMessage.error('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}
//根据id查询信息(预览html)
const getValue = async (id) => {
  try {
    const result = await pollAnimaApi(id)
    if(result.code && result.data){
      showHtmlData.value = {
        id: result.data.id,
        text: result.data.text || '',
        status: result.data.status,
        createTime: result.data.createTime || '',
        htmlContent: result.data.html || ''
      }
      // 使用安全方式显示HTML内容
      if (result.data.html && result.data.status === 2) {
        displayHtmlContent(result.data.html)
      } else {
        previewHtmlContent.value = ''
      }
      isShow.value = true
    }else if(result.code === 2){
      ElMessage.error('未找到对应资源，可能已被删除')
    }else{
      if(result.data === null && result.code === 0) {
        // 生成失败的场景，构造失败数据
        showHtmlData.value = {
          id: id,
          text: '',
          status: 3,
          createTime: '',
          htmlContent: ''
        }
        isShow.value = true
      } else {
        ElMessage.error(result.msg || '获取信息失败')
      }
    }
  } catch (e) {
    console.error('获取信息失败', e)
    ElMessage.error('获取信息失败')
  }
}
//根据id删除信息
const deleteItem = async (id, isTip = true) => {
  if(isTip == true){//询问是否删除
    //询问是否删除
    await ElMessageBox.confirm('是否删除该信息？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }
  try {
    itemRef.value = []
    const result = await deleteAnimaApi(id)
    if(result.code){
      ElMessage.success('删除成功')
      await getList()
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
    ElMessage.error('删除失败')
  }
}

//创建生成任务
const createTask = async () => {
  try {
    const result = await generateAnimaApi(animaData.value)
    if(result.code){
      task.value = result.data
      // 设置进度状态为生成中
      taskProgress.value = { status: 1, id: result.data.id }
    }else{
      ElMessage.error(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    ElMessage.error('提交失败')
  }
}

//查询任务状态
const getProgress = async (id) => {
  try {
    const result = await pollAnimaApi(id)
    if(result.code && result.data){
      taskProgress.value = result.data
    }else{
      // 如果接口返回失败，认为任务失败
      if(result.code === 0) {
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

</script>

<template>
  <div class="container">
    <div class="title">
      <h1>智能动画 一键生成</h1>
      <p class="subtitle">输入学习主题，AI为你生成生动有趣的动画演示</p>
    </div>

    <div class="main">
      <!-- 输入框 -->
      <div class="top">
        <div class="inputBox">
          <el-form 
            :inline="true"
            :rules="Rules" 
            ref="animaRef" 
            :model="animaData" 
            class="anima-form"
            @keyup.enter.native="submit()"
          >
            <el-form-item class="input-field" label="主题/知识点" prop="text" style="width: 100%; max-width: 600px;">
             <el-input 
                v-model="animaData.text"
                show-word-limit 
                maxlength="30" 
                placeholder="例如：二叉树遍历、冒泡排序、太阳系"
                clearable
                size="large"
              />
            </el-form-item>

            <!-- <el-form-item label="语音讲解" style="margin-left: 0;">
              <el-switch v-model="animaData.enableTts" size="large" />
            </el-form-item> -->
          
            <el-form-item class="btn-item">
              <el-button 
                type="primary" 
                class="submit-btn"
                @click="submit()"
                :disabled="btnDisvisible"
                size="large"
              >
                立即生成动画
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 列表 -->
      <div class="bottom"> 

        <!-- 有数据显示滚动条 -->
        <div class="showMain" v-if="allList?.length">
          <el-scrollbar height="100%" width="100%">
            <div class="scroll-content">

              <div v-for="(item,index) in showList" 
                :key="item.id" class="scrollbar-demo-item"
                ref="itemRef"
              >
                <!-- 成功项 -->
                <div class="normal" 
                  @click="getValue(item.id)" 
                  v-if="item.status == 2"
                  @mouseenter="handleEnter(index,item.id)"
                  @mouseleave="popStore.delayHidePop"
                >
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text || '无标题' }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime || '未知时间' }}
                    </div>
                  </div>
                  <div class="item-right" @click.stop="deleteItem(item.id)">
                    删除
                  </div>
                </div>

                <!-- 生成中项 -->
                <div class="loading"  @click="getValue(item.id)" v-else-if="item.status == 1 || item.status == null">
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text || '生成中...' }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime || '生成中' }}
                    </div>
                  </div>
                  <div class="item-right">
                    <!-- 加载动画 -->
                    <div class="loadingIcon">
                      <el-icon class="is-loading" :size="30" color="#2D7DDB"><Loading /></el-icon>
                    </div>
                    <div class="loadingText">
                      生成中
                    </div>
                  </div>
                </div>

                <!-- 失败项 -->
                <div class="failure" @click="getValue(item.id)" v-else>
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text || '生成失败' }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime || '失败' }}
                    </div>
                  </div>
                  <div class="boxRight">
                    <div class="item-mid">
                      <div class="fail">
                        <el-icon class="shake-icon" :size="30"><CloseBold /></el-icon>
                        <div class="fail-text">生成失败</div>
                      </div>
                    </div>
                    <div class="item-right" @click.stop="deleteItem(item.id)">
                      删除
                    </div>
                  </div>
                  
                </div>
              </div>

              <!-- 底部-查看更多 -->
              <div class="footer" v-if="allList.length > 20">
                <div @click="isOpenList(0)" class="text" v-if="allList?.length && allList.length != showList.length">查看更多</div>
                <div @click="isOpenList(1)" class="text" v-if="allList?.length && allList.length == showList.length">收起</div>
              </div>

            </div>
          </el-scrollbar>
        </div>

        <!-- 无数据时显示空 -->
        <div class="main mainNull" v-else-if="!allList || allList.length === 0">
          <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
          <div class="mainNullText">暂无生成内容</div>
        </div>

      </div>
    </div>
  </div>

  <!-- 预览页 - 使用iframe安全显示动态HTML内容 -->
  <Transition name="fade-slide" mode="out-in">
    <div class="see" v-if="isShow == true">
      <!-- 退出按钮 -->
      <div class="quit" @click="quitShowHtml()">
        <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5824" width="40" height="40"><path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" p-id="5825" fill="#ffffff"></path><path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" p-id="5826" fill="#ffffff"></path></svg>
        <div>退出</div>
      </div>
      <el-scrollbar height="100%" width="100%">
        <div class="scroll-content">
          <!-- 成功项 - 使用iframe安全显示动态HTML -->
          <div class="content" v-if="showHtmlData.status == 2 && showHtmlData.htmlContent"> 
            <div class="title">
              <div class="title-text">{{ showHtmlData.text || '动画预览' }}</div>
              <div class="title-ct">生成时间：{{ showHtmlData.createTime || '' }}</div>
            </div>
            <div class="iframe-wrapper">
              <iframe 
                ref="iframeRef"
                :srcdoc="previewHtmlContent"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals"
                style="width: 100%; min-height: 600px; border: none; border-radius: 8px; background: #fff;"
                title="动画预览"
              ></iframe>
            </div>
          </div>

          <!-- 生成中项 -->
          <div class="content" v-if="showHtmlData.status == 1"> 
            <div class="title">
              <div class="title-text">{{ showHtmlData.text || '动画生成中' }}</div>
              <div class="title-ct">生成时间：{{ showHtmlData.createTime || '' }}</div>
            </div>
            <div class="Html" v-html="ingHtml"></div>
          </div>

          <!-- 失败项 -->
          <div class="content" v-if="showHtmlData.status == 3"> 
            <div class="title">
              <div class="title-text">{{ showHtmlData.text || '生成失败' }}</div>
              <div class="title-ct">生成时间：{{ showHtmlData.createTime || '' }}</div>
            </div>
            <div class="Html" v-html="failHtml"></div>
          </div>

          <!-- 如果status为2但没有html内容，显示默认状态 -->
          <div class="content" v-if="showHtmlData.status == 2 && !showHtmlData.htmlContent">
            <div class="title">
              <div class="title-text">{{ showHtmlData.text || '动画' }}</div>
              <div class="title-ct">生成时间：{{ showHtmlData.createTime || '' }}</div>
            </div>
            <div class="Html" v-html="ingHtml"></div>
          </div>
        </div>
      </el-scrollbar>
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



.container {
  width: 100%;
  height: 100%;
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

.main {
  /* border: 1px solid green; */
  width: 100%;
  height: 75vh;

  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
}

.top {
  width: 100%;
  /* border: 1px solid red; */
  padding: 0; 
  display: flex;
  justify-content: center;
}

.bottom {
  width: 100%;
  /* border: 1px solid blue; */
  padding: 0; 
  flex: 1;
  overflow: hidden;
}



/* 输入区域 */
.top .inputBox {
  padding: 20px 40px 0 40px;
  width: 50%; 
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);
  transition: all 0.5s;
}

.top .inputBox:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}


.anima-form {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: flex-start;
  gap: 20px; 
}

:deep(.el-form-item__label) {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-gray);
}
.submit-btn {
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


/* 列表区域 */
.bottom .showMain { 
  margin: 0 auto;
  /* border: 2px dotted blue; */
  width: 70%;
  height: 100%;
  flex: 1;
  min-height: 0; 
  overflow: hidden; 
}
.scroll-content {
  padding: 0 40px 30px 40px;
  /* 内部发生变化时 自动滚动 */
  
}
.scrollbar-demo-item {
  padding: 10px 30px;
  margin: 10px 0;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--el-fill-color-light);
  box-shadow: var(--shadow-normal);
  overflow: hidden; 
  transition: all 0.3s;
}

/* 夜间模式 - 列表项背景 */
.dark .scrollbar-demo-item {
  background: var(--bg-card);
}

/* 正常项&加载项&删除项 样式 */
.bottom .item-left {
  max-width: 1000px;
}
.bottom .normal .item-left {
  max-width: 1000px;
}
.scrollbar-demo-item>div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bottom .item-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-body);
  /* 溢出隐藏 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bottom .normal .item-ct {
  font-size: 14px;
  color: var(--text-normal);
}

.scrollbar-demo-item .loading{
  animation: pulse 1.5s infinite ease-in-out; 
}

.bottom .loading .loadingIcon {
  width: 50px;
  height: 100%;
}
.bottom .loading .loadingText {
  width: 65px;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  animation: none;
}
.bottom .loading .item-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

/* 生成项动画 */
.loadingIcon {
  width: 100px;
  height: 100px;
  margin: 0 auto;
  display: flex;
  justify-content: center;
  align-items: center;
}
.loadingText {
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out; 
}
.loadingText::after {
  content: '...';
  /* steps(5, end) 计时函数：将动画分成若干个阶梯状的步骤，而不是平滑地渐变 */
  animation: dots 1.5s steps(5, end) infinite;
}
.overBox .el-icon.is-loading {
  color: var(--text-body);
  animation: rotating 2s linear infinite;
}
/* 动效 */
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

/* 失败项动画 */
.fail {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--main-delete); /* 统一使用 Element 危险色 */
}
.fail .shake-icon {
  color: var(--main-delete);
  /* 添加抖动动画 */
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
  transform: translate3d(0, 0, 0);
  backface-visibility: hidden;
  perspective: 1000px;
}
.fail .fail-text {
  font-size: 14px;
  font-weight: 500;
  opacity: 0;
  animation: fade-in-up 0.5s ease-out forwards;
  animation-delay: 0.3s; /* 等图标抖完再显示文字 */
}

/* 列表处失败项文字 */
.bottom .failure .item-text{ 
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
}
.bottom .failure .item-ct{
  animation: fade-in-up 0.5s ease-out;
}
.bottom .failure .boxRight {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 60px;
}
/* 图标抖动动画 (Shake) */
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
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

.bottom .normal .item-right:hover,
.bottom .failure .item-right:hover { 
  cursor: pointer;
  text-decoration: underline;
  color: var(--main-delete);
  transition: all 0.3s;
}
/* 普通项 Hover & 加载项 Hover */
.bottom .scrollbar-demo-item:has(.normal):hover,
.bottom .scrollbar-demo-item:has(.loading):hover {
  cursor: pointer;
  box-shadow: var(--shadow-brand);
  transform: translateY(-3px);
  border-color: var(--primary);
}

/* 失败项 Hover */
.bottom .scrollbar-demo-item:has(.failure):hover {
  /* cursor: no-drop; */
  cursor: pointer;
  transform: translateY(-3px);
  border-color: var(--main-delete);
  background-color: rgba(245, 108, 108, 0.1);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.2);
}

.bottom .mainNull {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.bottom .mainNull img {
  width: 160px;
  margin-bottom: 20px;
}
.bottom .mainNull .mainNullText {
  font-size: 16px;
  color: var(--text-gray);
}

/* 底部的底部区域 */
.bottom .footer {
  /* 居中 */
  left: 5%;
  bottom: 0;
  z-index: 1;
  width: 90%;
  height: 10%;
  flex-shrink: 0; /* 防止被压缩 */
  display: flex;
  justify-content: center;
  align-items: center;
  /* border: 2px solid green; */
  background: transparent;
}
.footer .text{
  font-size: 18px;
  color: var(--text-gray);
}
.footer .text:hover {
  text-decoration: underline;
  color: var(--primary);
  cursor: pointer;
}

/* 预览页 */
.see {
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  /* 修改背景为半透明，并添加磨砂效果 */
  background-color: var(--bgc-transparent); 
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
}
.see .content {
  padding: 80px 0;
  margin: 0 auto;
  width: 78%;
  background-color: var(--bg-page);
}
.see .content .Html {
  padding: 0;
}
.see .scroll-content {
  padding: 50px 60px 50px 60px;
}
.see .quit {
  z-index: 2;
  position: absolute;
  top: 40px;
  right: 40px;
}
.see .quit:hover {
  cursor: pointer;
}
.see .quit svg path {
  fill: var(--text-body) !important;
}
.see .quit:hover svg path {
  fill: var(--main-delete) !important;
}
.see .quit > div {
  color: var(--text-body);
}
.see .quit:hover > div {
  color: var(--main-delete);
}
.see .content .title .title-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}

/* iframe包装器样式 */
.iframe-wrapper {
  width: 100%;
  min-height: 600px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>