import { requestPythonAll } from '@/utils/request'

// 获取数据结构列表
export const getStructuresApi = (userId) => {
  return requestPythonAll.get('/algorithm-lab/structures', { params: { user_id: userId } })
}

// 获取初始状态
export const getInitialStateApi = (structureKey, count, userId) => {
  return requestPythonAll.get('/algorithm-lab/initial-state', {
    params: { structure_key: structureKey, count, user_id: userId }
  })
}

// 获取操作列表
export const getOperationsApi = (structureKey, userId) => {
  return requestPythonAll.get('/algorithm-lab/operations', {
    params: { structure_key: structureKey, user_id: userId }
  })
}

// 执行操作
export const executeOperationApi = (data) => {
  return requestPythonAll.post('/algorithm-lab/execute', data)
}

// 执行自定义操作（AI生成）
export const executeCustomOperationApi = (data) => {
  return requestPythonAll.post('/algorithm-lab/execute-custom', data)
}

// 添加自定义数据结构
export const addCustomStructureApi = (data) => {
  return requestPythonAll.post('/algorithm-lab/custom-structures', data)
}

// 删除自定义数据结构
export const deleteCustomStructureApi = (userId, key) => {
  return requestPythonAll.delete('/algorithm-lab/custom-structures', {
    params: { user_id: userId, key }
  })
}
