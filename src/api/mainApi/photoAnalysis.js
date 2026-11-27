import { requestPythonAll } from '@/utils/request'

export const analyzeImageApi = (formData) => {
  return requestPythonAll.post('/api/interrogation/analyze-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

