<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转查看
import { initMindMapChart } from './../mapJs/mindMap.js' //引入思维导图
import { getListByUserIdApi,getValueByMindMapIdApi,
  changeMindMapApi,submitGetMindMapIdApi,getProgressApi,deleteByMindMapIdApi } 
  from '@/api/mainApi/resourceMindMap.js'
import emitter from '@/utils/emitter'

//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
const itemRef = ref([])// 循环ref 必须初始化为空数组
const popStore = useActionPopStore()
// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index, rsId, type='mindmap') => {
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

// 创建思维导图
// 定义思维导图ref获取DOM元素
const mindMapChartRef = ref(null)//思维导图DOM
const userId = ref(null)//用户id

let loginUser = null
const skipInfo = ref()//跳转信息
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

  
  // 获取思维导图信息表
  await getList()

  lessList()//列表显示前20条

  // 检查 应用 中是否有要打开的思维导图
  if(isSkip(1) === false){
    console.log('没有思维导图需要提前打开')
    // 获取列表第一个思维导图
    await getValue()
  }else{
    skipInfo.value = isSkip(1)
    console.log('跳转信息:', skipInfo.value)
    try{
      await changePageByList(skipInfo.value.resourceId)
    }catch(e){
      ElMessage.error('该思维导图不存在，可能已经被删除了')
      console.log('打开失败')
    }
    
    removeSkip(1)//删除跳转信息
  }

  // 异步等待 1 秒
  await new Promise(resolve => setTimeout(resolve, 1000))

  // 思维导图在DOM挂载完成后初始化
  if (mindMapChartRef.value) {
    initMindMapChart(mindMapChartRef.value,showData.value)
  } else {
    console.error('思维导图 DOM 未找到')
  }

  showLoading.value = false


  // 列表轮询检查所有思维导图状态
  await checkList()

  lessList()//列表显示前20条


})

// ===========================数据===========================
const mindMapList = ref([])//思维导图基础信息表
const mindMapValue = ref({})//列表第一个思维导图所有数据|需要渲染的思维导图所有信息
const showData = ref({})//echarts显示数据
const proObject = ref(null)//获取进度后返回信息
const showLoading = ref(true)//换页时的遮罩是否显示

const listData = ref([])//列表显示信息（刚开始前二十条，点了更多后显示所有）

//表单
const mindMapData = ref({
  userId: null,
  text: ''
})
const mindMapRef = ref(null)
const btnDisvisible = ref(false)//按钮禁用是否开启
const Rules = {
  text: [
    { required: true, message: '请输入主题/知识点', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}

// =====================事件============================
//列表轮询
const checkList = async () =>{
  for (let i = 0; i < mindMapList.value.length; i++) {
    const item = mindMapList.value[i];
    if(item.status == 1 || item.status == null){
      //轮询获取进度
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(item.id)// 尝试查一次
        if(proObject.value == {}){//查不到返回结果
          ElMessage.error('获取生成进度失败')
        }else if(proObject.value.status == null){
          //仅前端改了，数据库未动
          item.status = 3//查到返回结果，但status还为null，判定为失败3
          await delMindMap(item.id,false)
          await getList()
          if(i == 0){
            await getValue()
          }
          proObject.value = {}
          continue //跳过这个任务，查下一个
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      
      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (proObject.value.status == 1 && nowNum < maxNum) {
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
      if (proObject.value.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getList()
        await getValue()
        proObject.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getList()
        await getValue()
        proObject.value = {}
      }
    }
  }
}

//查看更多
const moreList = () => {
  listData.value = [...mindMapList.value]
}
//收起
const lessList = () => {
  // 显示前二十条
  listData.value = mindMapList.value.slice(0,20)
}

// ==========================接口===============================
//获取信息表
const getList = async () => {
  try {
    itemRef.value = []
    const result = await getListByUserIdApi(userId.value)
    if(result.code){
      mindMapList.value = []
      mindMapList.value = result.data
      lessList()
    }else{
      ElMessage.error('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}

//获取列表第一个思维导图所有信息
const getValue = async () => {
  if (!mindMapList.value || mindMapList.value.length === 0) return
  try {
    const result = await getValueByMindMapIdApi(mindMapList.value[0].id)
    if(result.code){
      mindMapValue.value = result.data//要渲染的思维导图所有信息
      if (result.data.value) {
        try {
          showData.value = typeof result.data.value === 'string' 
            ? JSON.parse(result.data.value) 
            : result.data.value
        } catch (e) {
          console.error('思维导图数据解析失败', e)
          showData.value = {}
        }

        if (mindMapChartRef.value) {
          initMindMapChart(mindMapChartRef.value, showData.value)
        }
      } else {
        showData.value = {}
      }//渲染数据值
    }else{
      ElMessage.error('获取信息失败')
    }
  } catch (e) {
    console.error('获取单个思维导图信息失败', e)
  }
}

//获取思维导图进度
const getProgress = async (taskId) => { 
  try {
    const result = await getProgressApi(taskId)
    if(result.code){
      proObject.value = result.data
    }else{
      ElMessage.error('获取生成进度失败')
    }
  } catch (e) {
    console.error('获取思维导图进度失败', e)
  }
}

//删除思维导图
const delMindMap = async (mindMapId,isTip = true) => {
  if(isTip == true){
    //询问是否删除
    const confirmResult = await ElMessageBox.confirm('是否删除该思维导图？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }
  try {
    const result = await deleteByMindMapIdApi(mindMapId)
    if(result.code){
      ElMessage.success('删除成功')
      await getList()
      if(mindMapValue.value.id == mindMapId){
        showLoading.value = true
        await getValue()
        showLoading.value = false
      }
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除思维导图失败', e)
  }
}

//上下换页
const changePage = async (operation) => {
  //判断是否为第一页或者最后一页
  if(mindMapValue.value.id == mindMapList.value[0].id){
    if(operation == 0){
      ElMessage.warning('已经是第一页了')
      console.log('第一页')
      return
    }
  }else if(mindMapValue.value.id == mindMapList.value[mindMapList.value.length-1].id){
    if(operation == 1){
      ElMessage.warning('已经是最后一页了')
      console.log('最后一页')
      return
    }
  }
  try {
    const result = await changeMindMapApi(mindMapValue.value.id,userId.value,operation)
    if(result.code){
      showLoading.value = true
      mindMapValue.value = result.data
      if(mindMapValue.value.status == 2){
        if (result.data.value) {
          try {
            showData.value = typeof result.data.value === 'string' 
              ? JSON.parse(result.data.value) 
              : result.data.value
          } catch (e) {
            showData.value = {}
          }
        }


        await new Promise(resolve => setTimeout(resolve, 1000))
        if (mindMapChartRef.value) {
          initMindMapChart(mindMapChartRef.value,showData.value)
        } else {
          console.error('思维导图 DOM 未找到')
        }
      }
      showLoading.value = false
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除思维导图失败', e)
  }
} 


//列表换页
const changePageByList = async (mindMapId) => {
  //判断是否为正在显示
  if(mindMapValue.value.id == mindMapId){
    ElMessage.warning('该页正在显示')
    console.log('该页正在显示')
    return
  }
  try {
    const result = await getValueByMindMapIdApi(mindMapId)
    if(result.code){
      showLoading.value = true
      mindMapValue.value = result.data
      if(mindMapValue.value.status == 2){
        if (result.data.value) {
          try {
            showData.value = typeof result.data.value === 'string' 
              ? JSON.parse(result.data.value) 
              : result.data.value
          } catch (e) {
            showData.value = {}
          }
        }


        await new Promise(resolve => setTimeout(resolve, 1000))
        if (mindMapChartRef.value) {
          initMindMapChart(mindMapChartRef.value,showData.value)
        } else {
          console.error('思维导图 DOM 未找到')
        }
      }
      showLoading.value = false
    }else if(result.code === 2){
      ElMessage.error('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取单个思维导图信息失败', e)
  }
}

//提交生成
const submit = async() => {
  itemRef.value = []
  mindMapRef.value.validate(async(valid) => {
    if (valid) {
      itemRef.value = []
      console.log('表单校验通过，提交中')
      btnDisvisible.value = true
      mindMapData.value.userId = userId.value

      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        const result = await submitGetMindMapIdApi(mindMapData.value)
        if(result.code){
          ElMessage.success('提交成功')
          if(result.data.status == 1 || result.data.status == null){

            //轮询获取进度
            let nowNum = 0
            let maxNum = 40

            try {
              await getProgress(result.data.taskId)// 尝试查一次
              if(proObject.value == {}){//查不到返回结果
                ElMessage.error('获取生成进度失败')
              }else if(proObject.value.status == null){
                //仅前端改了，数据库未动
                //item.status = 3//查到返回结果，但status还为null，判定为失败3
                await delMindMap(result.data.taskId,false)
                proObject.value = {}
              }
            } catch (e) {
              console.error('首次查询进度失败', e)
            }
        
            await getList()
            // await getValue()

            // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
            while (proObject.value.status == 1 && nowNum < maxNum) {
              nowNum++
              console.log(`任务 ${result.data.taskId} 生成中... 第 ${nowNum} 次轮询`)

              
              // 异步等待 10 秒
              await new Promise(resolve => setTimeout(resolve, 10000))

              try {
                console.log('获取进度次数：',nowNum)
                await getProgress(result.data.taskId)
              } catch (e) {
                console.error('轮询进度失败', e)
              }
            }
        
            // 轮询结束，判断最终结果
            if (proObject.value.status == 2) {
              console.log(` ${result.data.taskId} 任务完成`)
              await getList()//新生成的是列表第一个
              await getValue()
              proObject.value = {}
            } else {
              console.log(` ${result.data.taskId} 未完成`)
              await getList()
              await getValue()
              proObject.value = {}
            }
          }else if(result.data.status == 2 || result.data.status == 3){//一提交就好了
            await getList()
            await getValue()
          }
          btnDisvisible.value = false
          mindMapData.value = {userId: null,text: ''}
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
      <h1>思维导图 智能生成</h1>
      <p class="subtitle">输入学习主题，一键生成精细化思维导图</p>
    </div>

    <!--内容区域 -->
    <div class="showArea">
      <div class="leftBox">

        <!-- 样例（列表没有数据且没有跳转图表时显示） -->
        <div class="showBox sample" v-if="(!mindMapList || mindMapList.length === 0) && mindMapValue.status !== 2">
          <img src="@/assets/sample/mindMapSample.png" alt="思维导图样例">
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

        <!-- 展示区域（列表有数据或跳转打开图表时显示） -->
        <div class="showBox" v-if="mindMapList?.length || mindMapValue.status === 2">
          <!-- 思维导图echarts容器（始终渲染，确保跳转时可找到） -->
          <div ref="mindMapChartRef" class="mindMapChart-container" :style="{ display: mindMapValue.status === 2 ? 'block' : 'none' }"></div>

          <!-- 生成项 -->
          <div class="show creating" v-if="mindMapValue.status == 1 || mindMapValue.status == null">
            <div class="loadingIcon">
              <el-icon class="is-loading" :size="60"><Loading /></el-icon>
            </div>
            <div class="loadingText">
              生成中
            </div>
          </div>

          <!-- 生成错误项 -->
          <div class="show createFail" v-else-if="mindMapValue.status != 2">
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
              <div class="mindMapTitle">
                {{ mindMapValue.text }}
              </div>
              <div class="mindMapSubtitle">
                {{ mindMapValue.createTime }}
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
            ref="mindMapRef" 
            :model="mindMapData" 
            label-position="top"
            class="mindMap-form"
            @keyup.enter.native="submit()"
          >
            <el-form-item label="主题/知识点" prop="text">
              <el-input 
                v-model="mindMapData.text"
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
          <p class="subtitle tips">*点击结点可展开或收起，光标悬浮可查看该结点内容</p>
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
          <div class="main" v-if="mindMapList?.length">
            <el-scrollbar height="100%" width="100%">
              <div class="scroll-content">

                <div 
                  v-for="(item,index) in listData" :key="item.id" 
                  class="scrollbar-demo-item" 
                  :class="{ 'failFixedShow': mindMapValue.id == item.id && mindMapValue.status == 3 },{ 'norFixedShow': mindMapValue.id == item.id && (mindMapValue.status == 2 || mindMapValue.status == 1) }"
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
                    <div class="item-right" @click.stop="delMindMap(item.id)">
                      删除
                    </div>
                  </div>

                  <!-- 生成项 -->
                  <div class="loading" v-else-if="item.status == 1 || item.status == null"  @click="changePageByList(item.id)">
                    <div class="item-left">
                      <div class="item-text">
                        {{ item.text }}
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
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
                    <div class="item-right" @click.stop="delMindMap(item.id)">
                      删除
                    </div>
                  </div>
                </div>

              </div>
            </el-scrollbar>
          </div>
          <!-- 无数据时显示空 -->
          <div class="main mainNull" v-else-if="!mindMapList || mindMapList.length === 0">
            <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
            <div class="mainNullText">暂无生成内容</div>
          </div>

          <div class="footer">
            <div @click="moreList()" class="text" v-if="mindMapList?.length && mindMapList.length > 20 && listData.length != mindMapList.length">查看更多</div>
            <div @click="lessList()" class="text" v-if="mindMapList?.length && mindMapList.length > 20 && listData.length == mindMapList.length">收起</div>
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
  /* margin-top: 10px; */
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
  /* 新增：声明这是一个容器，名称为 mindmap-container */
  container-type: inline-size;
  container-name: mindmap-container;

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
  position: relative;
}
/* 显示区域 */
.showBox .show {
  /* border:1px solid orange; */
  width: 100%;
  height: 100%;
}
/* 信息区域（压在图表底部） */
.showBox .message {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0 10px;
  background-color: var(--bg-card);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 -2px 10px var(--shadow-color);
  width: 100%;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 10;
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
.textMsg .mindMapTitle {
  /* 最小 12px, 首选 容器宽度的 2%, 最大 24px */
  font-size: clamp(12px, 2cqw, 24px);
  font-weight: 700;
  color: var(--text-body);
  
  /* 优化长文本显示 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%; /* 确保不超出父容器 */
}

.textMsg .mindMapSubtitle {
  /* 最小 6px, 首选 容器宽度的 1.2%, 最大 14px */
  font-size: clamp(6px, 1.2cqw, 14px);
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
.mindMap-form {
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
  max-width: 270px;
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

/* =========================echarts========================== */
/* 图表容器高度预留底部栏空间 */
.mindMapChart-container {
  width: 100%;
  height: calc(100% - 60px);
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
