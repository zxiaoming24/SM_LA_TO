//导入request对象
import request from '@/utils/request.js'

//获取雷达图数据
export const getRadarApi = (userId) => request.get(`/draw/radarMap/${userId}`)

//获取词云图数据（点击量）
export const getWordCloudApi = (userId) => request.get(`/click/stats/${userId}`)

//获取近七天学习时长
export const getSevenDaysStudyTimeApi = (userId) => request.get(`/user/online/${userId}`)

//查询某年某月日历图学习信息
export const getCanlendarApi = (userId, year, month) => request.get(`/draw/calendarChartData/${userId}/${year}/${month}`)

//查询资源总量信息
export const getRsAllApi = (userId) => request.get(`/draw/rsAllMsg/${userId}`)

//查询学习计划进度信息
export const getPlanProgressApi = (userId) => request.get(`/draw/planProgressMsg/${userId}`)