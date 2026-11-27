//导入request对象
import request from '@/utils/request.js'
import { requestPython } from '@/utils/request.js'

//根据userId查询视频生成列表
export const getListByUserIdApi = (userId) => request.get(`/video/getList/${userId}`)

//搜索视频接口
export const searchApi = (data) => request.post('/video/getVideoByText', data)

//轮询视频资源接口/根据batchId查询视频列表
export const getProgressApi = (batchId) => request.get(`/video/poll?batchId=${batchId}`)


//根据id删除视频资源接口
export const deleteByIdApi = (batchId) => request.delete(`/video/deleteVideo/${batchId}`)

//获取视频流权限(直接调用python端)
export const getVideoStreamApi = (url) => requestPython.get(`/api/stream?url=${url}`)
// export const getVideoStreamApi = (url) => {
//   return requestPython.get('/api/stream', {
//     params: { url },
//     responseType: 'blob' // 视频返回的是blob类型
//   })
// }


//获取视频信息,流地址
export const getVideoInfoApi = (bvid, page) => request.get(`/video/playInfo/${bvid}/${page}`)

// 上报视频观看行为数据（用于更新学生特征）
export const getUserBehaviourApi = (data) => request.post('/video/userBehaviour', data)

//上报回溯情况
export const postRewindApi = (data) => request.post('/video/reportRewindEvent', data)


//根据python的id查询视频信息
export const getVideoInfoByPythonIdApi = (resourceId) => request.get(`/video/getVideoById/${resourceId}`)

//某集视频播放结束，生成理论题试卷
export const generatePaperApi = (data) => request.post('/video/postVideoQuiz', data)


//==============================视频总结相关===============================
//获取视频总结
export const getVideoSummaryApi = (data) => request.post(`/video/getSummary`, data)

//获取视频思维导图
export const getVideoMindmapApi = (data) => request.post(`/video/getMindmap`, data)