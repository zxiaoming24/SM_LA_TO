<script setup>
import { ref, onMounted,nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转查看
import { getListByUserIdApi,submitApi,getProgressApi,deleteByWordIdApi } from '@/api/mainApi/resourceWord.js'
import emitter from '@/utils/emitter'

//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
const itemRef = ref([])// 循环ref 必须初始化为空数组
const popStore = useActionPopStore()

// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index, rsId, type='document') => {
  await nextTick()
  const el = itemRef.value[index]
  if (!el) return

  const rect = el.getBoundingClientRect()
  let left = rect.left - 45
  let top = rect.top - 60 // 元素上方60px

  // 顶部越界则改为下方展示
  if (top < 0) {
    top = rect.bottom + 10
  }

  // 每个item对应自身坐标弹出
  console.log('【hover】index：',index,'，rsId：',rsId)
  popStore.showPop(left, top, { id: index, title: `第${index+1}个条目`, rsId: rsId, rsType: type, userId: userId.value })
}


const userId = ref(null)//用户id
let loginUser = null
const skipInfo = ref()//跳转信息
const skipResultUrl = ref()//跳转word链接'
onMounted(async () => {
  // 获取用户基本信息
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if(loginUser.type == 0){
        ElMessage.info('管理员已被跳转后台管理系统')
        router.push('/admin')
      }else{
        if(loginUser && loginUser.id){
          userId.value = loginUser.id
        }
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  //获取列表
  await getWordList()

  //显示列表信息（前二十条）
  lessList()

  // 检查 应用 中是否有要打开的编程题
  if(isSkip(2) === false){
    console.log('没有编程题需要提前打开')
    //获取列表第一个word展示 + 渲染
    await getValue()
  }else{
    skipInfo.value = isSkip(2)
    console.log('跳转信息:', skipInfo.value)
    skipResultUrl.value = await getProgressApi(skipInfo.value.resourceId)
    if(skipResultUrl.value.code === 1){
      ElMessage.success('正在打开')
      //渲染
      renderWord(skipResultUrl.value.data.ossUrl)
    }else if(skipResultUrl.value.code === 2){
      ElMessage.error('该讲解文档不存在，可能已经被删除了')
      // 显示全屏加载遮罩
      setTimeout(() => {
        const loadingInstance = ElLoading.service({
          fullscreen: true,
          text: '正在加载资源...',
          background: 'rgba(255, 255, 255, 0.9)'
        })

        // 短暂延迟后刷新，确保加载状态可见
        setTimeout(() => {
          window.location.reload()
        }, 1000)
      }, 2000)
    }
    removeSkip(2)//删除跳转信息
  }
  



  // 异步等待 1 秒
  await new Promise(resolve => setTimeout(resolve, 1000))

  //检查是否有截断任务
  await checkList()

  //把展示加载状态设置为false
  showLoading.value = false

  //刷新显示列表
  await getWordList()

  //显示列表信息（前二十条）
  lessList()
  
})


//================================表单================================
const wordData = ref({
  userId: null,
  text: ''
})
const wordRef = ref(null)
const btnDisvisible = ref(false)//按钮禁用是否开启
const Rules = {
  text: [
    { required: true, message: '请输入主题/知识点', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}
//==============================变量=================================
// https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/%E7%AC%AC%E5%85%AB%E7%BB%84%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84%E5%AE%9E%E9%AA%8C%E5%9B%9B%20-%20%E5%89%AF%E6%9C%AC.docx
// https://wha-whaghw.oss-cn-beijing.aliyuncs.com/word/Java%E7%BC%96%E7%A8%8B%E5%9F%BA%E7%A1%80_20260522_173613.docx
const wordUrl = ref('')//word地址
const previewUrl = ref('')//word预览地址

const wordList = ref([
  // {
  //       "id": 1,
  //       "userId": 1,
  //       "text": "标题",
  //       "status": 2,
  //       "createTime": "2025-03-11 18:22:44",
  //       "ossUrl": "https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/%E7%AC%AC%E5%85%AB%E7%BB%84%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84%E5%AE%9E%E9%AA%8C%E5%9B%9B%20-%20%E5%89%AF%E6%9C%AC.docx"
  //   },
  //   {
  //       "id": 2,
  //       "userId": 1,
  //       "text": "Java异常处理机制详解",
  //       "status": 2,
  //       "createTime": "2023-10-05 14:00:00",
  //       "ossUrl": "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/word/Java%E7%BC%96%E7%A8%8B%E5%9F%BA%E7%A1%80_20260522_173613.docx"
  //   },
  //   //截断案例
  //    {
  //       "id": 3,
  //       "userId": 1,
  //       "text": "标题",
  //       "status": 1,
  //       "createTime": "2025-03-11 18:22:44",
  //       "ossUrl": ""
  //   },
  //   //失败案例
  //   {
  //       "id": 4,
  //       "userId": 1,
  //       "text": "标题",
  //       "status": 3,
  //       "createTime": "2025-03-11 18:22:44",
  //       "ossUrl": ""
  //   },
    
])//word列表（全部信息）
const showList = ref([])//显示word列表（刚开始前二十条）

const showWordData = ref({})//当前展示word信息

const progressMsg = ref({})//进度信息

const showLoading = ref(true)

//==============================函数=================================
//渲染word
const renderWord = async (url = '') => { 
  try {
    wordUrl.value = url || showWordData.value.ossUrl 
    previewUrl.value = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(wordUrl.value)}`
  } catch (e) {
    console.error('渲染word信息失败', e)
  }
}
//列表轮询
const checkList = async () =>{
  for (let i = 0; i < wordList.value.length; i++) {
    const item = wordList.value[i];
    if(item.status == 1 || item.status == null){
      //轮询获取进度
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(item.id)// 尝试查一次
        if(progressMsg.value == {}){//查不到返回结果
          ElMessage.error('获取生成进度失败')
        }else if(progressMsg.value.status == null){
          //仅前端改了，数据库未动
          item.status = 3//查到返回结果，但status还为null，判定为失败3
          await delWord(item.id,false)
          await getWordList()
          if(i == 0){
            await getValue()
          }
          progressMsg.value = {}
          continue //跳过这个任务，查下一个
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      
      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (progressMsg.value.status == 1 && nowNum < maxNum) {
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
      if (progressMsg.value.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getWordList()
        await getValue()
        progressMsg.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getWordList()
        await getValue()
        progressMsg.value = {}
      }
    }
  }
}
//查看更多
const moreList = () => {
  showList.value = [...wordList.value]//显示全部
}
//收起
const lessList = () => {
  // 显示前二十条
  showList.value = wordList.value.slice(0,20)
}

//获取一个list的一个word信息来展示
const getValue = async () => { 
  if(wordList.value.length > 0){
    showWordData.value = wordList.value[0]
    //渲染
    renderWord()
  }else{
    console.log('列表为空，无法展示第一个word信息')
  }
}

//下载
const download = async (id) => {
  if (!id) {
    ElMessage.error('未找到该文档信息');
    return;
  } 
  try {
    const index = ref(null)
    for(let i = 0; i < wordList.value.length; i++){
      if(id == wordList.value[i].id){
        index.value = i
        break
      }
    }
    //根据下载链接下载word
    const link = document.createElement('a')// 创建临时 a 标签
    link.href = wordList.value[index.value].ossUrl
    
    // 触发点击
    document.body.appendChild(link)
    link.click()
    
    // 清理 DOM
    document.body.removeChild(link)
  } catch (e) {
    console.error('下载word失败', e)
  }
}

//上下换页
const changePage = async (operation) => {
  //判断是否为第一页或者最后一页
  if(showWordData.value.id == wordList.value[0].id){
    if(operation == 0){
      ElMessage.warning('已经是第一页了')
      console.log('第一页')
      return
    }
  }else if(showWordData.value.id == wordList.value[wordList.value.length-1].id){
    if(operation == 1){
      ElMessage.warning('已经是最后一页了')
      console.log('最后一页')
      return
    }
  }
  try {
    showLoading.value = true
    const index = ref(null)
    for(let i = 0; i < wordList.value.length; i++){
      // 找到当前页索引
      if(showWordData.value.id == wordList.value[i].id){
        index.value = i
        break
      }
    }
    if(operation == 0){
      showWordData.value = wordList.value[index.value - 1]
      renderWord()
    }else if(operation == 1){
      showWordData.value = wordList.value[index.value + 1]
      renderWord()
    }

    // 异步等待 1 秒
    await new Promise(resolve => setTimeout(resolve, 1000))
    showLoading.value = false

  } catch (e) {
    console.error('换页失败', e)
  }
} 


//列表换页
const changePageByList = async (id) => {
  skipResultUrl.value = ''
  //判断是否为正在显示
  if(showWordData.value.id == id){
    ElMessage.warning('该页正在显示')
    console.log('该页正在显示')
    return
  }
  try {
    showLoading.value = true
    const index = ref(null)
    for(let i = 0; i < wordList.value.length; i++){
      // 找到当前页索引
      if(id == wordList.value[i].id){
        index.value = i
        break
      }
    }
    if(index.value == null){
      ElMessage.error('未找到对应资源，可能已被删除')
    }
    showWordData.value = wordList.value[index.value]
    renderWord()

    // 异步等待 1 秒
    await new Promise(resolve => setTimeout(resolve, 1000))
    showLoading.value = false

  } catch (e) {
    console.error('获取信息失败', e)
  }
}

//==============================接口================================
//获取讲解文档列表
const getWordList = async () => { 
  try {
    itemRef.value = []
    const result = await getListByUserIdApi(userId.value)
    if(result.code){
      wordList.value = []
      wordList.value = result.data
      lessList()
    }else{
      ElMessage.error('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}

//获取任务进度
const getProgress = async (id) => { 
  try {
    const result = await getProgressApi(id)
    if(result.code){
      console.log('获取进度成功')
      progressMsg.value = result.data
    }else{
      ElMessage.error('获取进度失败')
    }
  } catch (e) {
    console.error('获取进度失败', e)
  }
}

//删除
const delWord = async (id,isShow = true) => { 
  if(isShow == true){
    //询问是否删除
    const confirmResult = await ElMessageBox.confirm('是否删除该word？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }

  try {
    const result = await deleteByWordIdApi(id)
    if(result.code){
      ElMessage.success('删除成功')
      await getWordList()
      if(showWordData.value.id == id){
        showLoading.value = true
        await getValue()
        showLoading.value = false
      }
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除word失败', e)
  }
}
//提交
const submit = async () => { 
  wordRef.value.validate(async(valid) => { 
    if (valid) { 
      console.log('表单校验通过，提交中')
      btnDisvisible.value = true
      wordData.value.userId = userId.value

      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        const result = await submitApi(wordData.value)
        if(result.code){
          ElMessage.success('提交成功')
          if(result.data.status == 1 || result.data.status == null){
            //轮询获取进度
            let nowNum = 0
            let maxNum = 40

            try {
              await getProgress(result.data.id)// 尝试查一次
              if(progressMsg.value == {}){//查不到返回结果
                ElMessage.error('获取生成进度失败')
              }else if(progressMsg.value.status == null){
                await delWord(result.data.id,false)
                await getWordList()
                if(showWordData.value.id == result.data.id){
                  await getValue()
                }
                progressMsg.value = {}
              }
            } catch (e) {
              console.error('首次查询进度失败', e)
            }


            await getWordList()//新生成的是列表第一个
            await getValue()
        
            // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
            while (progressMsg.value.status == 1 && nowNum < maxNum) {
              nowNum++
              console.log(`任务 ${result.data.id} 生成中... 第 ${nowNum} 次轮询`)

              // 异步等待 10 秒
              await new Promise(resolve => setTimeout(resolve, 10000))

              try {
                console.log('获取进度次数：',nowNum)
                await getProgress(result.data.id)
              } catch (e) {
                console.error('轮询进度失败', e)
              }
            }
        
            // 轮询结束，判断最终结果
            if (progressMsg.value.status == 2) {
              console.log(` ${result.data.id} 任务完成`)
              await getWordList()//新生成的是列表第一个
              await getValue()
              progressMsg.value = {}
            } else {
              console.log(` ${result.data.id} 未完成`)
              await getWordList()
              await getValue()
              progressMsg.value = {}
            }
          }else if(result.data.status == 2 || result.data.status == 3){//一提交就好了
            await getWordList()
            await getValue()
          }
          btnDisvisible.value = false
          wordData.value = {userId: null,text: ''}
          
        }else{
          ElMessage.error('提交失败')
        }
      } finally {
        clearTimeout(gameInvitationTimer)
      }

    } else {
      console.log('校验失败')
      return false
    }
  })
}


</script>

<template>
  <div class="container">
    <!-- 标题 -->
    <div class="title">
      <h1>讲解文档 智能生成</h1>
      <p class="subtitle">输入学习主题，一键生成超详细讲解文档</p>
    </div>

    <!--内容区域 -->
    <div class="showArea">
      <div class="leftBox">

        <!-- 样例（列表没有数据时显示） -->
        <div class="showBox sample" v-if="(!wordList || wordList.length === 0) && !skipResultUrl">
          <img src="@/assets/sample/wordSample.png" alt="word样例">
        </div>

        <!-- 加载遮罩（切换时显示） -->
        <div class="overBox showBox" v-if="showLoading == true">
          <div class="loadingIcon">
            <el-icon class="is-loading" :size="50" color="white"><Loading /></el-icon>
          </div>
          <div class="loadingText">
            加载中
          </div>
        </div>

        <!-- 展示 -->
        <div class="showBox" v-if="wordList?.length || skipResultUrl">
          <!-- word展示 -->
          <div class="show" v-if="showWordData.status == 2 || skipResultUrl"> 
            <!-- word容器 -->
            <iframe
              :src="previewUrl"
              width="100%"
              height="103.5%"
              frameborder="0"
              scrolling="auto"
            >
            </iframe>
          </div>

          <!-- 生成项 -->
          <div class="show creating" v-else-if="showWordData.status == 1 || showWordData.status == null">
            <div class="loadingIcon">
              <el-icon class="is-loading" :size="60"><Loading /></el-icon>
            </div>
            <div class="loadingText">
              生成中
            </div>
          </div>

          <!-- 生成错误项 -->
          <div class="show createFail" v-else>
            <div class="fail">
              <el-icon class="shake-icon" :size="50"><CloseBold /></el-icon>
              <div class="fail-text">生成失败</div>
            </div>
          </div>

          <!-- 底部导航栏 -->
          <div class="message">
            <div class="up" @click="changePage(0)">
              <svg t="1779180913241" class="icon" viewBox="0 0 1024 1024"
               version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12426"
                width="200" height="200"><path d="M512 896c-211.75 0-384-172.25-384-384s172.25-384 384-384 384 
                172.25 384 384-172.25 384-384 384z m0-708.92c-179.16 0-324.92 145.76-324.92 324.92S332.84 836.92 
                512 836.92 836.92 691.16 836.92 512 691.16 187.08 512 187.08z" fill="#333333" p-id="12427"></path>
                <path d="M541.54 659.69c-7.56 0-15.12-2.88-20.88-8.65L402.5 532.88c-11.54-11.54-11.54-30.23 0-41.77l118.15-118.15c11.54-11.54
                 30.23-11.54 41.77 0 11.54 11.54 11.54 30.23 0 41.77L465.15 512l97.27 97.27c11.54 11.54 11.54 30.23 0 41.77-5.77 5.77-13.32 8.65-20.88 
                 8.65z" fill="#333333" p-id="12428"></path>
              </svg>
            </div>
            <div class="textMsg">
              <div class="wordTitle">
                {{ showWordData?.text || skipResultUrl?.data?.text }}
              </div>
              <div class="wordSubtitle">
                {{ showWordData.createTime || skipResultUrl?.data?.createTime }}
              </div>
            </div>
            <div class="down"@click="changePage(1)">
              <svg t="1779180971620" class="icon" viewBox="0 0 1024 1024" 
                version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="12587" 
                width="200" height="200"><path d="M512 127.99999999c211.75000001 
                0 384.00000001 172.25 384.00000001 384.00000001s-172.25 
                384.00000001-384.00000001 384.00000001-384.00000001-172.25-384.00000001-384.00000001 
                172.25-384.00000001 384.00000001-384.00000001z m0 708.92000001c179.16 0 324.92-145.76 
                324.92-324.92S691.16 187.08 512 187.08 187.08 332.84 187.08 512 332.84 836.92 512 836.92z" 
                fill="#333333" p-id="12588"></path><path d="M482.46 364.31c7.56000001 0 15.12 2.88 20.88 
                8.65L621.5 491.12c11.54 11.54 11.54 30.23 0 41.77l-118.15 118.15c-11.54 11.54-30.23 11.54-41.77
                0-11.54-11.54-11.54-30.23 0-41.77L558.85 512l-97.27-97.27c-11.54-11.54-11.54-30.23 0-41.77 
                5.77-5.77 13.32-8.65 20.88-8.65z" fill="#333333" p-id="12589"></path>
             </svg>
            </div>
          </div>
        </div>
      </div>


      <!-- 右侧区域 -->
      <div class="rightBox">
        <!-- 输入框 -->
        <div class="inputBox">
          <el-form 
            :rules="Rules" 
            ref="wordRef" 
            :model="wordData" 
            label-position="top"
            class="word-form"
            @keyup.enter.native="submit()"
          >
            <el-form-item label="主题/知识点" prop="text">
              <el-input 
                v-model="wordData.text"
                size="large" 
                show-word-limit 
                maxlength="30" 
                placeholder="例如：python基础"
                clearable
              />
            </el-form-item>

            <el-form-item class="btn-item">
              <el-button 
                type="primary" 
                size="large" 
                class="submit-btn"
                @click="submit()"
                :disabled="btnDisvisible"
              >
                立即生成
              </el-button>
            </el-form-item>
          </el-form>
          <p class="subtitle tips">*word生成</p>
        </div>

        <!-- 显示列表 -->
        <div class="showList">
          <div class="header">
            <svg t="1779185007722" class="icon" viewBox="0 0 1024 1024" 
              version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6163" 
              width="200" height="200"><path d="M785.546573 781.547354c-35.593048 
              35.093146-76.984964 62.787737-123.275923 82.183948-47.890646 20.196055-98.780707 
              30.694005-151.470416 31.193908h-4.099199c-53.289592 
              0-104.579574-10.297989-152.770162-30.594025-46.49092-19.596173-87.882835-47.690685-123.075962-83.383714-70.286272-71.386057-108.278852-166.667448-106.679164-267.947666 
              0.799844-52.089826 11.497754-102.280023 31.893771-149.570787 19.696153-45.791056 47.590705-86.78305 82.883811-121.976177 
              72.585823-72.285882 169.466901-112.17809 272.446788-112.17809 52.389768 0 103.179848 10.198008 
              150.970514 30.194103 46.190978 19.296231 87.482913 46.990822 123.075961 82.183948 35.593048 35.193126 63.4876 76.08514 82.883812 
              121.676235 20.096075 47.090803 30.394064 97.181019 30.394064 148.770943 0 101.780121-40.19215 197.461433-113.177895 269.447374M511.400117 
              69.286467c-246.951767 0-443.413396 198.261277-447.112673 442.813513C60.488186 759.351689 259.649287 954.813513 506.701035 954.813513h4.699082c246.951767-2.499512 
              447.212654-198.161297 447.212654-442.813513 0.09998-244.452255-200.260887-442.713533-447.212654-442.713533" p-id="6164"></path>
              <path d="M736.656122 517.998828H511.200156V290.543253c0-16.596758-13.397383-29.994142-29.994142-29.994141s-29.994142 13.397383-29.994141 29.994141V547.89299c0 
              16.596758 13.397383 29.994142 29.994141 29.994141h255.350127c16.596758 0 29.994142-13.397383 29.994142-29.994141 0-16.496778-13.397383-29.894161-29.894161-29.894162" p-id="6165"></path>
            </svg>
            <div class="text">最近生成</div>
          </div>


          <!-- 有数据显示滚动条 -->
          <div class="main" v-if="wordList?.length">
            <el-scrollbar height="100%" width="100%">
              <div class="scroll-content">

                <div v-for="(item,index) in showList" :key="item.id" 
                  class="scrollbar-demo-item" 
                  :class="{ 'failFixedShow': showWordData.id == item.id && showWordData.status == 3 },{ 'norFixedShow': showWordData.id == item.id && (showWordData.status == 2 || showWordData.status == 1) }"
                  ref="itemRef"
                >
                  <!-- 普通项 -->
                  <div class="normal" 
                    v-if="item.status == 2" 
                    @click="changePageByList(item.id)"
                    @mouseenter="handleEnter(index,item.id)"
                    @mouseleave="popStore.delayHidePop"
                  >
                    <div class="item-left">
                      <div class="item-text">
                        {{ item.text }}
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>

                    <div class="normal-right">
                      <div class="item-mid" @click.stop="download(item.id)">下载</div>
                      <div class="item-right" @click.stop="delWord(item.id)">删除</div>
                    </div>
                    

                  </div>

                  <!-- 生成项 -->
                  <div class="loading" v-else-if="item.status == 1 || item.status == null" @click="changePageByList(item.id)">
                    <div class="item-left">
                      <div class="item-text">
                        {{ item.text }}
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>
                    <div class="item-right">
                      <div class="loadingIcon">
                        <el-icon class="is-loading" :size="30" color="#2D7DDB"><Loading /></el-icon>
                      </div>
                      <div class="loadingText">
                        生成中
                      </div>
                    </div>
                  </div>

                  <!-- 失败项 -->
                  <div class="failure" v-else-if="item.status == 3"  @click="changePageByList(item.id)">
                    <div class="item-left">
                      <div class="item-text">
                        {{ item.text }}
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>
                    <div class="item-mid">
                      <div class="fail">
                        <el-icon class="shake-icon" :size="30"><CloseBold /></el-icon>
                        <div class="fail-text">生成失败</div>
                      </div>
                    </div>
                    <div class="item-right" @click.stop="delWord(item.id)">
                      删除
                    </div>
                  </div>

                </div>
              </div>
            </el-scrollbar>
          </div>
          <!-- 无数据时显示空 -->
          <div class="main mainNull"  v-else-if="!wordList || wordList.length === 0">
            <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
            <div class="mainNullText">暂无生成内容</div>
          </div>

          <div class="footer">
            <div @click="moreList()" class="text" v-if="wordList?.length && wordList.length > 20 && showList.length != wordList.length">查看更多</div>
            <div @click="lessList()" class="text" v-if="wordList?.length && wordList.length > 20 && showList.length == wordList.length">收起</div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
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

/* 主区域 */
.showArea {
  /* background-color: skyblue; */
  width: 100%;
  min-height: 699px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}


/* 左侧区域 */
.showArea .leftBox {
  position: relative;
  flex: 1;
  height: 699px;
  /* border: 2px dotted blue; */
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border-color);

  display: flex;
  justify-content: center;
  align-items: center;
  
  box-shadow: var(--shadow-normal);
}
.leftBox .showBox {
  /* 宽度尝试占满，但高度不能超过父元素 */
  width: 100%;
  max-height: 100%;
  /* background-color: red; */
  background-color: var(--bg-card);
  height: auto;
  width: max(100%, 699px);
  aspect-ratio: 1.46 / 1;
}
/* 显示区域 */
.showBox .show {
  /* border:1px solid orange; */
  width: 100%;
  height: 93%;
  overflow: hidden;
  /* 其子元素往x-，y-方向移动0.1px */
  transform: translate(-0.8px, -0.8px);

}
/* 信息区域 */
.showBox .message {
  padding: 0 10px;
  /* background-color: green; */
  background-color: var(--bg-card);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 0 25px var(--shadow-color);
  width: 100%;
  height: 7%;

  display: flex;
  justify-content: space-between;
  align-items: center;
}
.message .up,
.message .down {
  /* background-color: yellow; */
  background-color: var(--bg-card);
  width: 5%;
  height: 100%;
  padding: 3px;
}
.up svg,
.down svg {
  width: 95%;
  height: 95%;
  stroke: var(--text-body);
  stroke-width: 1; 
  transition: all 0.3s ease-in-out;
}
.up:hover svg path,
.down:hover svg path {
  fill: var(--primary) !important;
  stroke: var(--primary);
}
/* 强制覆盖 path 的填充，防止 SVG 内部属性干扰 */
.up svg path,
.down svg path {
  fill: var(--text-body) !important;
  transition: stroke-dashoffset 1s ease-in-out;
}

.message .up:hover,
.message .down:hover {
  cursor: pointer;
}

.message .textMsg {
  /* background-color: pink; */
  background-color: var(--bg-card);
  width: 90%;
  height: 100%;

  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.textMsg .wordTitle {
  /* 最小 12px, 首选 容器宽度的 1.1%, 最大 24px */
  font-size: clamp(12px, 1.1cqw, 24px);
  font-weight: 700;
  color: var(--text-body);
  /* 优化长文本显示 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%; /* 确保不超出父容器 */
}

.textMsg .wordSubtitle {
  font-size: clamp(6px, 0.7cqw, 14px);
  color: var(--text-gray);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* 左侧-遮罩加载层 */
.leftBox .overBox {
  z-index: 1;
  position: absolute;
  background-color: var(--bg-card);
  
  display: flex;
  flex-direction: column;
  justify-content: center;
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


/* 右侧区域 */
.showArea .rightBox {
  width: 400px; 
  height: 699px;
  /* border: 2px dotted black; */
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 20px;

  min-width: 396px;
}
/* 输入区域 */
.rightBox .inputBox {
  padding: 30px;
  width: 100%;
  height: 30%;
  /* border: 2px dotted red; */
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);
  transition: all 0.5s;
}
.rightBox .inputBox:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}
.inputBox .tips {
  font-size: 14px;
}
.word-form {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}
/* 调整表单项间距 */
:deep(.el-form-item) {
  margin-bottom: 22px;
}
:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-gray);
}
/* 按钮样式优化 */
.btn-item {
  margin-bottom: 0;
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

/* 显示列表区域 */
.rightBox .showList {
  width: 100%;
  flex: 1;
  /* border: 2px dotted purple; */
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);

  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;

  /* 关键：防止内容溢出导致撑开 */
  overflow: hidden; 
  min-height: 0; /* Flex 子项收缩关键属性 */
}
.showList .header {
  margin-top: 8px;
  z-index: 1;
  width: 100%;
  height: 14%;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  padding: 0 25px;
  gap: 10px;
  /* background-color: pink; */
}
/* 顶部区域 */
.header .text{
  font-size: 20px;
  font-weight: 700;
}
.header svg {
  width: 10%;
}
.header svg path {
  fill: var(--primary) !important;
  stroke: var(--primary);
}
/* 底部区域 */
.showList .footer {
  z-index: 1;
  width: 100%;
  height: 10%;
  flex-shrink: 0; /* 防止被压缩 */
  display: flex;
  justify-content: center;
  align-items: center;
}
.footer .text{
  font-size: 14px;
  color: var(--text-gray);
}
.footer .text:hover {
  text-decoration: underline;
  color: var(--primary);
  cursor: pointer;
}
/* 主区域 */
.showList .main { 
  width: 100%;
  flex: 1;
  /* 关键：允许 flex 子项缩小到内容以下，触发滚动 */
  min-height: 0; 
  overflow: hidden; 
}
.scroll-content {
  padding: 0 25px 10px 25px;
}
.scrollbar-demo-item {
  padding: 10px 15px;
  margin: 10px 0;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--el-fill-color-light);
  /* 确保内部 flex 子项不会溢出 */
  overflow: hidden; 
  transition: all 0.3s;
}

/* 夜间模式 - 列表项背景 */
.dark .scrollbar-demo-item {
  background: var(--bg-card);
}

/* 正常项&加载项&删除项 样式 */
.showList .item-left {
  max-width: 220px;
}
.showList .normal .item-left {
  max-width: 240px;
}
.scrollbar-demo-item>div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.showList .item-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-body);
  /* 溢出隐藏 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.showList .normal .item-ct {
  font-size: 14px;
  color: var(--text-normal);
}

.scrollbar-demo-item .loading{
  animation: pulse 1.5s infinite ease-in-out; 
}

.showList .loading .loadingIcon {
  width: 50px;
  height: 100%;
}
.showList .loading .loadingText {
  width: 65px;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  animation: none;
}
.showList .loading .item-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
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
.showList .failure .item-text{ 
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
}
.showList .failure .item-ct{
  animation: fade-in-up 0.5s ease-out;
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

.showList .normal .normal-right {
  width: 100px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}

.showList .normal .item-mid:hover { 
  cursor: pointer;
  text-decoration: underline;
  color: var(--primary);
  transition: all 0.3s;
}

.showList .normal .item-right:hover,
.showList .failure .item-right:hover { 
  cursor: pointer;
  text-decoration: underline;
  color: var(--main-delete);
  transition: all 0.3s;
}

/* 普通项 Hover & 加载项 Hover */
/* hover子级，父级变化 (has) */
.norFixedShow,
.showList .scrollbar-demo-item:has(.normal):hover,
.showList .scrollbar-demo-item:has(.loading):hover {
  cursor: pointer;
  box-shadow: var(--shadow-brand);
  transform: translateY(-3px);
  border-color: var(--primary);
}

/* 加载项 Hover */
/* .showList .scrollbar-demo-item:has(.loading):hover {
  cursor: wait;
  background-color: var(--el-fill-color); 
} */

/* 失败项 Hover */
.failFixedShow,
.showList .scrollbar-demo-item:has(.failure):hover {
  cursor: pointer;
  border-color: var(--main-delete);
  background-color: rgba(245, 108, 108, 0.1);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.2);
}

.showList .mainNull {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.showList .mainNull img {
  width: 160px;
  margin-bottom: 20px;
}
.showList .mainNull .mainNullText {
  font-size: 16px;
  color: var(--text-gray);
}


/* 样例 */
.sample { 
  z-index: 2;
  position: absolute;
  width: 100%;
  height: 100%;
  background-color: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
}
.sample img {
  width: 100%;
}

/* 展示处生成项 */
.leftBox .creating,
.leftBox .createFail {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: var(--primary-fade);
}
.creating .loadingIcon {
  width: 100%;
  height: 100px;
}
.creating .is-loading,
.creating .loadingText {
  font-size: 16px;
  color: var(--primary);
}

/* 展示处失败项 */
.leftBox .createFail {
  background-color: var(--main-fail-status);
}
</style>
