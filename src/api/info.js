//导入request对象
import request from '@/utils/request.js'

//上传头像
export const uploadAvatarApi = (data) => {
  return request({
    url: '/common/upload',
    method: 'post',
    data: data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

//提交学生信息
export const submitStuInfoApi = (data) => request.post('/submitInfo', data)

//申请成为管理员
export const applyAdminApi = (data) => request.post('/applyAdministrator', data)

