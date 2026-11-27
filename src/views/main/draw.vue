<script setup>
import { ref,onMounted,nextTick, watch } from 'vue'
import { ElMessage,ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { initRadarChart } from './mapJs/radarMap.js' //引入雷达图
import { createResourceWordCloud } from './mapJs/wordCloud.js'//引入词云图
import { createStudyTrendChart } from './mapJs/studyTrendMap.js'//近七天学习时长图
import CalendarChart from '@/components/CalendarChart.vue'//日历组件
import { RsChart } from './mapJs/rsAllMap.js'//资源总量组件
import LearningPlanProgress from '@/components/planProgressMap.vue'//学习计划进度
import { getRadarApi,getWordCloudApi,getSevenDaysStudyTimeApi,getCanlendarApi,getRsAllApi,getPlanProgressApi } from '@/api/mainApi/draw.js'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
const router = useRouter() // 用于跳转
const themeStore = useThemeStore()

//=======================数据=====================
const baseInfo = ref({//用户基本信息
    id: null,
    avatar: '',
    username: '',
    sex: null,
    age: null,
    grade: null,
    major: ''
})
// 基本信息处理
const GRADE_MAP = { //年级映射表
  1: "大一", 
  2: "大二", 
  3: "大三", 
  4: "大四" 
}





//=======================渲染=====================
// 创建雷达图
// 定义雷达图ref获取DOM元素
const radarChartRef = ref(null)
// 创建词云图
// 词云图ref获取DOM元素
const wordCloudRef = ref(null)
// 创建近七天学习时长图
// 近七天学习时长ref获取DOM元素
const studyTrendChartRef = ref(null)
// 创建资源总量
// 资源总量ref获取DOM元素
const rsChartRef = ref(null)

// 图表实例引用
let radarChartInstance = null
let wordCloudChartInstance = null
let studyTrendChartInstance = null
let rsChartInstance = null

//=======================初始化（获取信息）=====================
let loginUser = null
onMounted(async() => {
  // 获取用户基本信息
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)

      if(loginUser){
        // 判断登录用户类型
        if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
          ElMessage.warning('请进行画像构建~')
          router.push('/aiAnswer')
        }
        baseInfo.value = {//用户基本信息
          id: loginUser.id,
          avatar: loginUser.avatar,
          username: loginUser.username,
          sex: loginUser.sex,
          age: loginUser.age,
          grade: loginUser.grade,
          major: loginUser.major
        }
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  // 等待DOM完全渲染
  await nextTick()

  //获取渲染所需所有信息
  await getRadarData()//雷达图数据
  await getWordCloudData()//词云图数据
  await getStudyTrendData()//近七天学习时长数据
  await getCalendarData()//日历数据
  await getRsAllData()//资源总量数据
  await getPlanProgressData()//学习计划进度数据


})


//======================接口数据=====================
// 雷达图数据
const radarData = ref({
  name: '',
  data: []
  // [
  //   {
  //     value: [40, 30, 20, 35, 50, 18, 67, 90],
  //     name: '更新前'
  //   },
  //   {
  //     value: [50, 64, 88, 66, 42, 41, 89, 95],
  //     name: '更新后'
  //   }
  // ] // 测试数据
})

// 词云图数据
const wordCloudData = ref([
  // {
  //     "resourceType": "MIND_MAP",
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
  //     "clickCount": 1,
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
  // }
  
])

// 近七天学习时长数据
const studyTrendData = ref([
  // {
  //     "id": 3,
  //     "userId": 2,
  //     "statDate": "2026-05-23",
  //     "firstLogin": "2026-05-23 10:00",
  //     "lastActive": "2026-05-23 10:00",
  //     "totalSeconds": 2382
  // },
  // {
  //     "id": 4,
  //     "userId": 2,
  //     "statDate": "2026-05-24",
  //     "firstLogin": "2026-05-24 09:15",
  //     "lastActive": "2026-05-24 09:15",
  //     "totalSeconds": 3354
  // },
  // {
  //     "id": 5,
  //     "userId": 2,
  //     "statDate": "2026-05-25",
  //     "firstLogin": "2026-05-25 08:50",
  //     "lastActive": "2026-05-25 08:50",
  //     "totalSeconds": 1342
  // },
  // {
  //     "id": 6,
  //     "userId": 2,
  //     "statDate": "2026-05-26",
  //     "firstLogin": "2026-05-26 14:00",
  //     "lastActive": "2026-05-26 14:00",
  //     "totalSeconds": 2235
  // },
  // {
  //     "id": 7,
  //     "userId": 2,
  //     "statDate": "2026-05-27",
  //     "firstLogin": "2026-05-27 10:20",
  //     "lastActive": "2026-05-27 10:20",
  //     "totalSeconds": 4354
  // },
  // {
  //     "id": 9,
  //     "userId": 2,
  //     "statDate": "2026-05-28",
  //     "firstLogin": "2026-05-28 22:02",
  //     "lastActive": "2026-05-28 22:02",
  //     "totalSeconds": 1424
  // },
  // {
  //     "id": 10,
  //     "userId": 2,
  //     "statDate": "2026-05-29",
  //     "firstLogin": "2026-05-29 15:18",
  //     "lastActive": "2026-05-29 15:18",
  //     "totalSeconds": 5449
  // }
])

// 日历数据
const calendarRef = ref(null)//日历ref获取DOM元素
const currentDisplayYear = ref(new Date().getFullYear())//当前显示的年份
const currentDisplayMonth = ref(new Date().getMonth())//当前显示的月份
const calendarData = ref([])//日历数据
// 月份切换事件
const onMonthChange = async ({ year, month }) => {
  currentDisplayYear.value = year
  currentDisplayMonth.value = month
  console.log(`切换到 ${year}年${month + 1}月`)
  await getCalendarData()
}
// 获取当前显示的月份
const getCurrentMonth = () => {
  const { year, month } = calendarRef.value?.getCurrentDate() || {}
  console.log(`当前显示：${year}年${month + 1}月`)
}

//资源总量数据
const rsData = ref([])

//学习计划进度
// 自定义学习计划数据
const learningPlans = ref([])
// 环形图配置
const ringConfig = {
  showTooltip: true,//是否显示提示
  radiusGap: 16,//环形间距
  startRadiusRatio: 0.30  // 调整起始半径比例
}


//======================接口=====================
// 获取雷达图数据
const getRadarData = async () => {
  const res = await getRadarApi(baseInfo.value.id)
  if (res.code) {
    // 获取雷达图数据
    radarData.value.name = baseInfo.value.username
    radarData.value.data = res.data
    console.log(radarData.value)
    // 渲染雷达图
    radarChartInstance = initRadarChart(radarChartRef.value,radarData.value)
  } else {
    ElMessage.error(res.msg)
  }
}

//获取词云图数据
const getWordCloudData = async () => {
  const res = await getWordCloudApi(baseInfo.value.id)
  if (res.code) {
    // 获取词云图数据
    wordCloudData.value = res.data
    console.log(wordCloudData.value)
    // 渲染词云图
    wordCloudChartInstance = createResourceWordCloud(wordCloudRef.value,wordCloudData.value)
  } else {
    ElMessage.error(res.msg)
  }
}

//获取近七天学习时长数据
const getStudyTrendData = async () => {
  const res = await getSevenDaysStudyTimeApi(baseInfo.value.id)
  if (res.code) {
    // 获取近七天学习时长数据
    studyTrendData.value = res.data
    console.log(studyTrendData.value)
    // 渲染近七天学习时长图
    studyTrendChartInstance = createStudyTrendChart(studyTrendChartRef.value,studyTrendData.value)
  }
}

//获取日历数据
const getCalendarData = async () => {
  console.log(`更新日历数据：${currentDisplayYear.value}年${currentDisplayMonth.value + 1}月`)
  const res = await getCanlendarApi(baseInfo.value.id,currentDisplayYear.value,currentDisplayMonth.value + 1)
  if (res.code) {
    // 合并旧数据和新数据，去重后排序
    const existingDates = new Set(calendarData.value.map(item => item.date));
    const newItems = res.data.filter(item => !existingDates.has(item.date));
    
    // 合并并排序
    calendarData.value = [...calendarData.value, ...newItems]
      .sort((a, b) => a.date.localeCompare(b.date));
    
    console.log('日历数据：',calendarData.value)
  }
}

//获取资源总量数据
const getRsAllData = async () => {
  const res = await getRsAllApi(baseInfo.value.id)
  if (res.code) {
    // 获取资源总量数据
    rsData.value = res.data
    // 渲染资源总量图
    rsChartInstance = RsChart(rsChartRef.value,{
      resourceData: rsData.value,
      onChartReady: (chart) => {
        console.log('图表已就绪')
      }
    })
  }
}

//获取学习计划进度数据
const getPlanProgressData = async () => {
  const res = await getPlanProgressApi(baseInfo.value.id)
  if (res.code) {
    // 获取学习计划进度数据
    learningPlans.value = res.data
    console.log(learningPlans.value)
  }
}

// 重新渲染所有图表
const refreshCharts = () => {
  // 销毁旧实例
  if (radarChartInstance) {
    radarChartInstance.dispose()
    radarChartInstance = null
  }
  if (wordCloudChartInstance) {
    wordCloudChartInstance.dispose()
    wordCloudChartInstance = null
  }
  if (studyTrendChartInstance) {
    studyTrendChartInstance.dispose()
    studyTrendChartInstance = null
  }
  if (rsChartInstance) {
    rsChartInstance.destroy()
    rsChartInstance = null
  }

  // 重新创建图表
  if (radarData.value.data && radarData.value.data.length > 0) {
    radarChartInstance = initRadarChart(radarChartRef.value, radarData.value)
  }
  if (wordCloudData.value && wordCloudData.value.length > 0) {
    wordCloudChartInstance = createResourceWordCloud(wordCloudRef.value, wordCloudData.value)
  }
  if (studyTrendData.value && studyTrendData.value.length > 0) {
    studyTrendChartInstance = createStudyTrendChart(studyTrendChartRef.value, studyTrendData.value)
  }
  if (rsData.value && rsData.value.length > 0) {
    rsChartInstance = RsChart(rsChartRef.value, {
      resourceData: rsData.value
    })
  }
}

// 监听主题变化
watch(() => themeStore.isDark, () => {
  nextTick(() => {
    refreshCharts()
  })
})



</script>

<template>
  <div class="container">
    <div class="draw-header">
      <div class="header-left">
        <h1>学情画像</h1>
        <p class="subtitle">依托多维度学习数据，精准刻画学生学习全貌。</p>
      </div>
    </div>
    <div class="rowFlex topBox">
      <div class="columnFlex topLeftBox">
        <div class="edgeBox topLeftBox-left mapContainer">
          <!-- 雷达图 -->
          <div ref="radarChartRef" class="chart-content"></div>
          <div v-if="!radarData.data || radarData.data.length === 0" class="empty-overlay">
            <el-empty description="暂无雷达图数据" :image-size="80" />
          </div>
        </div>
        <div class="edgeBox topLeftBox-right mapContainer">
          <!-- 资源总量 -->
          <div ref="rsChartRef" class="chart-content rsContanier"></div>
          <div class="wordCloudText rsText">资源数量汇总</div>
          <div v-if="!rsData || rsData.length === 0" class="empty-overlay">
            <el-empty description="暂无资源数据" :image-size="80" />
          </div>
        </div>
      </div>

      <div class="topMidBox">
        <!-- 日历 -->
        <CalendarChart
          ref="calendarRef"
          :data="calendarData"
          @month-change="onMonthChange"
        />
      </div>

      <div class="columnFlex topRightBox">
        <div class="edgeBox topRightBox-left mapContainer">
          <!-- 近七天学习时长 -->
          <div ref="studyTrendChartRef" class="chart-content"></div>
          <div v-if="!studyTrendData || studyTrendData.length === 0" class="empty-overlay">
            <el-empty description="暂无学习时长数据" :image-size="80" />
          </div>
        </div>
        <div class="edgeBox topRightBox-right mapContainer-wordCloud">
          <!-- 词云图（点击量） -->
          <div ref="wordCloudRef" class="chart-content"></div>
          <div class="wordCloudText">总资源点击量词云图</div>
          <div v-if="!wordCloudData || wordCloudData.length === 0" class="empty-overlay">
            <el-empty description="暂无词云数据" :image-size="80" />
          </div>
        </div>
      </div>
    </div>

    <div class="rowFlex bottomBox">
      <div class="bottomMidBox" id="app">
        <!-- 自定义背景，组件会自动透明 -->
        <div class="custom-background">
          <LearningPlanProgress 
            v-if="learningPlans && learningPlans.length > 0"
            title="我的学习计划进度总览"
            :plans="learningPlans"
            :ring-config="ringConfig"
          />
          <div v-else class="empty-chart full-height">
            <el-empty description="暂无学习计划" class="emptyplan-chart" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  min-width: 1314px;
  width: 100%;
  height: 130vh;
  display: flex;
  flex-direction: column;
  padding: 15px 30px;
  background: transparent;
}

/* -------------------- 头部标题区域 -------------------- */
.draw-header {
  text-align: center;
  margin-bottom: 20px;
}
.header-left h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
  color: var(--text-title);
}
.header-left .subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

/* 弹性布局 */
.rowFlex{
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  flex-wrap: nowrap;
}
.columnFlex{
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  flex-wrap: nowrap;
  gap: 15px;
}

/* div[class$="Box"]{
  border: 1px solid red;
} */

.topBox,
.bottomBox { 
  width: 100%;
  /* border: 1px solid black; */
}

.topBox {
  gap: 10px;
  height: 60%;
}
.bottomBox{
  margin-top: 20px;
  height: 40%;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  position: relative;
  /* overflow: hidden; */
}
.bottomBox::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  /* background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary)); */
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}
.bottomBox .bottomMidBox {
  width: 100%;
  height: 100%;
  /* border: 1px solid red; */
}

.topBox .topLeftBox,
.topBox .topRightBox { 
  height: 100%;
  flex: 1;
}
.topBox .topMidBox {
  margin: auto 0;
  height: 80%;
  /* 自动占据剩下的 */
  flex: 2;
}
.topBox .edgeBox { 
  /* border: 1px solid blue; */
  width: 100%;
  height: 50%;
}

.bottomBox>div[class$="Box"] {
  height: 100%;
  flex: 1;
}

/* =====================图宽高==================== */
.mapContainer {
  padding: 10px;
  width: 100%;
  height: 100%;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  border-radius: 12px;
  position: relative;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  /* overflow: hidden; */
}
.mapContainer::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  /* background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary)); */
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.mapContainer:hover {
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.15);
  transform: translateY(-2px);
}

.chart-content {
  width: 100%;
  height: 100%;
}
.rsContanier{
  padding-top: 30px;
}

/* 空图表覆盖层 */
.empty-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  background: rgba(255, 255, 255, 0.9);
  z-index: 2;
}

.dark .empty-overlay {
  background: rgba(30, 41, 59, 0.95);
}

.wordCloudText {
  position: absolute;
  bottom: 10px;
  left: 30%;
  font-size: 15px;
  font-weight: bold;
  color: var(--text-gray);
}
.rsText{
  left: 37%;
}

/* 空图表容器 */
.empty-chart {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-chart.full-height {
  height: 100%;
}

.emptyplan-chart{
  margin-top: 80px;
}

/* 词云图容器 */
.mapContainer-wordCloud {
  width: 100%;
  height: 100%;
  position: relative;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  /* overflow: hidden; */
}
.mapContainer-wordCloud::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  /* background: linear-gradient(90deg, var(--primary), var(--primary-hv), var(--primary)); */
  background-size: 200% 100%;
  animation: shimmer 3s ease-in-out infinite;
}
.mapContainer-wordCloud:hover {
  box-shadow: 0 8px 30px rgba(45, 125, 219, 0.15);
  transform: translateY(-2px);
}

.mapContainer-wordCloud .mapContainer {
  border: none;
  background: transparent;
}

</style>
