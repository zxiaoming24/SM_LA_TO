// @/api/mainApi/partners.js

//导入request对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

// 搜索对应的学伴
export const searchApi = (userId) => request.get(`/StudyBuddy/Search/${userId}`)

//邀请和自己特征相似的学伴
export const inviteApi = (data) => request.post('/StudyBuddy/Invite', data)

//获取对应用户的学伴列表
export const partnersListApi = (userId) => request.get(`/StudyBuddy/getStudyBuddyList/${userId}`)

//获取待处理的学伴邀请列表
export const getInvitedApi = (userId) => request.get(`/StudyBuddy/PendingInvitations/${userId}`)

//同意或者拒绝邀请
export const isAcceptApi = (data) => request.post('/StudyBuddy/Accept', data)


//分享资源给学伴/社区
export const shareRsApi = (data) => request.post('/StudyBuddy/shareResources', data)

//获取别人分享给我的资源
export const otherSharedRsApi = (userId) => request.get(`/StudyBuddy/getOtherShareResources/${userId}`)



//*************读取别人分享给我的资源内容
// export const otherRsContentApi = (userId, resourceType, resourceId) => request.get(`/StudyBuddy/readContent/${userId}/${resourceType}/${resourceId}`)

//=======================共学邀请============================
//获取共学记录列表
export const getSTListApi = (userId) => request.get(`/ColearningRecords/getRecordsList/${userId}`)

//获取待处理的共学邀请（被邀请方显示）
export const getPostSTApi = (userId) => request.get(`/ColearningRecords/getInvitation/${userId}`)

//接收和拒绝共学邀请
export const isSTApi = (data) => request.post('/ColearningRecords/AcceptInvitation', data)

//获取某个资源的讨论消息列表
export const getSTDialogApi = (invitationId) => request.get(`/ColearningRecords/GetMessage/${invitationId}`)

//共学会话中发送消息
export const postDialogMsgApi = (data) => request.post('/ColearningRecords/SendMessage', data)

//删除共学记录（三个列表都能删）
export const delSTApi = (data) => request.post('/ColearningRecords/DeleteMessage', data)

//对比两个人之间的成绩
export const compareScoreApi = (problemId, userId_a, userId_b) => request.get(`/ColearningRecords/CompareScores/${problemId}/${userId_a}/${userId_b}`)

//获取自己发送出去的邀请（含状态）（邀请方显示）
export const getMyInvitationApi = (userId) => request.get(`/ColearningRecords/getMySentInvitations/${userId}`)


//获取结对编程会话内容（开始结对编程时，再开始轮询）
export const getPairDialogApi = (invitationId) => request.get(`/ColearningRecords/getPairProgrammingSessions/${invitationId}`)

//更新结对编程的代码（监听表单，变化即调用）
export const updatePairCodeApi = (data) => request.post('/ColearningRecords/updateCode', data)

// 提交结对编程的代码（编写完成提交）
export const submitPairCodeApi = (data) => request.post('/ColearningRecords/submitPairProgrammingCode', data)

//共学通知(共学方面的未处理的信息)
export const colearningNoticeApi = (userId) => request.get(`/ColearningRecords/getCoStudyNotifications/${userId}`)


//==============================小组相关===============================
//写法样例：
// export const colearningNoticeApi = (userId) => requestPythonAll.get(`/ColearningRecords/getCoStudyNotifications/${userId}`)

// 创建学习小组
export const createGroupApi = (data) => requestPythonAll.post('/group/create', data)

// 获取用户的小组列表
export const getMyGroupsApi = (userId) => requestPythonAll.get(`/group/list/${userId}`)

// 获取所有公开小组
export const getAllGroupsApi = () => requestPythonAll.get('/group/all')

// 加入小组
export const joinGroupApi = (data) => requestPythonAll.post('/group/join', data)

// 获取小组详情
export const getGroupDetailApi = (groupId) => requestPythonAll.get(`/group/detail/${groupId}`)

// 获取小组消息列表
export const getGroupMessagesApi = (groupId, limit = 50) => requestPythonAll.get(`/group/messages/${groupId}?limit=${limit}`)

// 发送小组消息
export const sendGroupMessageApi = (data) => requestPythonAll.post('/group/message', data)

// 上传小组图片
export const uploadGroupImageApi = (data) => requestPythonAll.post('/group/upload-image', data)

// 退出小组
export const leaveGroupApi = (data) => requestPythonAll.post('/group/leave', data)

// 解散小组
export const dissolveGroupApi = (data) => requestPythonAll.post('/group/dissolve', data)

// 获取待处理的小组邀请
export const getPendingGroupInvitesApi = (userId) => requestPythonAll.get(`/group/invites/pending/${userId}`)

// 邀请成员加入小组
export const inviteToGroupApi = (data) => requestPythonAll.post('/group/invite', data)

// 响应小组邀请（接受/拒绝）
export const respondGroupInviteApi = (data) => requestPythonAll.post('/group/invite/respond', data)

// 获取小组比赛列表
export const getGroupCompetitionsApi = (groupId) => requestPythonAll.get(`/group/competitions/${groupId}`)

// 获取比赛详情
export const getCompetitionDetailApi = (competitionId) => requestPythonAll.get(`/group/competition/detail/${competitionId}`)

// 创建比赛
export const createCompetitionApi = (data) => requestPythonAll.post('/group/competition/create', data)

// 生成赛题
export const generateProblemsApi = (data) => requestPythonAll.post('/group/competition/generate-problems', data)

// 开始比赛
export const startCompetitionApi = (data) => requestPythonAll.post('/group/competition/start', data)

// 结束比赛
export const endCompetitionApi = (data) => requestPythonAll.post('/group/competition/end', data)

// 删除比赛
export const deleteCompetitionApi = (data) => requestPythonAll.post('/group/competition/delete', data)

// 提交答案
export const submitAnswerApi = (data) => requestPythonAll.post('/group/competition/submit', data)

// 获取排行榜
export const getRankingApi = (competitionId) => requestPythonAll.get(`/group/competition/ranking/${competitionId}`)