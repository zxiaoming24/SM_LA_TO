import { requestPythonAll } from '@/utils/request.js'


// 获取媒体文件列表
export const getMediaFilesApi = () => {
  return requestPythonAll.get('/admin/video/files')
}

// 上传媒体文件
export const uploadMediaFileApi = (formData) => {
  return requestPythonAll.post('/admin/video/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// 删除媒体文件
export const deleteMediaFileApi = (filename) => {
  return requestPythonAll.delete(`/admin/video/files/${encodeURIComponent(filename)}`)
}
