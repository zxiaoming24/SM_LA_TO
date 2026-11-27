<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUserListApi,updateUserInfoApi,deleteUserApi,resetPasswordApi } from '@/api/backstage/adUsers.js'
import { uploadAvatarApi } from '@/api/info.js'

let loginUser = null
const information = ref({})

onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser) {
        information.value = loginUser
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  loadUserList()
})

const tableData = ref([])
const loading = ref(false)

const pageInfo = reactive({
  currentPage: 1,
  pageSize: 15,
  total: 0
})

const searchUser = reactive({
  username: '',
  type: '-1',
  createTime: ''
})

const loadUserList = async () => {
  loading.value = true
  try {
    const params = {
      username: searchUser.username,
      type: searchUser.type === '-1' ? '-1' : searchUser.type,
      createTime: searchUser.createTime,
      currentPage: pageInfo.currentPage,
      pageSize: pageInfo.pageSize
    }
    const res = await getUserListApi(params)
    if (res.code === 1) {
      tableData.value = res.data.records || []
      pageInfo.total = res.data.total
      pageInfo.pageSize = res.data.size
      pageInfo.currentPage = res.data.current
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  loadUserList()
}

const handleReset = () => {
  searchUser.username = ''
  searchUser.type = '-1'
  searchUser.createTime = ''
  pageInfo.currentPage = 1
  loadUserList()
}

const handleSizeChange = (val) => {
  pageInfo.pageSize = val
  pageInfo.currentPage = 1
  loadUserList()
}

const handleCurrentChange = (val) => {
  pageInfo.currentPage = val
  loadUserList()
}

const showEditDialog = ref(false)
const editForm = reactive({
  userId: null,
  avatar: '',
  username: '',
  email: '',
  sex: null,
  grade: null,
  major: ''
})

const openEditDialog = (row) => {
  editForm.userId = row.id
  editForm.avatar = row.avatar || ''
  editForm.username = row.username || ''
  editForm.email = row.email || ''
  editForm.sex = row.sex
  editForm.grade = row.grade
  editForm.major = row.major || ''
  showEditDialog.value = true
}

const closeEditDialog = () => {
  showEditDialog.value = false
}

const beforeAvatarUpload = (rawFile) => {
  const isJPGOrPNG = rawFile.type === 'image/jpeg' || rawFile.type === 'image/png'
  const isLt2M = rawFile.size / 1024 / 1024 < 2
  if (!isJPGOrPNG) {
    ElMessage.error('头像只能是 JPG 或 PNG 格式!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB!')
    return false
  }
  return true
}

const uploadAvatar = async (options) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)
  try {
    const loading = ElMessage({
      message: '正在上传头像...',
      type: 'info',
      duration: 0
    })
    const result = await uploadAvatarApi(formData)
    loading.close()
    if (result.code === 1) {
      editForm.avatar = result.data
      ElMessage.success('头像上传成功')
    } else {
      ElMessage.error(result.msg || '上传失败')
    }
  } catch (error) {
    console.error('上传错误:', error)
    ElMessage.error('网络异常，上传失败')
  }
}

const removeAvatar = () => {
  editForm.avatar = ''
  ElMessage.info('头像已移除')
}

const submitEdit = async () => {
  if (!editForm.username) {
    return ElMessage.error('请输入用户名')
  }
  try {
    const params = {
      userId: editForm.userId,
      avatar: editForm.avatar,
      username: editForm.username,
      sex: editForm.sex,
      grade: editForm.grade,
      major: editForm.major
    }
    const res = await updateUserInfoApi(params)
    if (res.code === 1) {
      ElMessage.success('修改成功')
      closeEditDialog()
      loadUserList()
    } else {
      ElMessage.error(res.msg || '修改失败')
    }
  } catch (error) {
    console.error('修改失败:', error)
    ElMessage.error('网络异常，修改失败')
  }
}

const handleResetPassword = async (userId) => {
  try {
    await ElMessageBox.confirm(
      '确定要重置该用户的密码吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const res = await resetPasswordApi(userId)
    if (res.code === 1) {
      ElMessage.success('密码重置成功')
      loadUserList()
    } else {
      ElMessage.error(res.msg || '密码重置失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('重置密码失败:', error)
      ElMessage.error('网络异常，重置密码失败')
    }
  }
}

const handleDeleteUser = async (userId) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除该用户吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const res = await deleteUserApi(userId)
    if (res.code === 1) {
      ElMessage.success('删除成功')
      loadUserList()
    } else {
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('网络异常，删除失败')
    }
  }
}
</script>

<template>
  <div class="user-container">
    <div class="content-panel">
      <div class="search-bar">
        <el-input v-model="searchUser.username" placeholder="请输入用户名" clearable class="search-input" @keyup.enter="handleSearch" />
        <el-select v-model="searchUser.type" placeholder="请选择用户类型" clearable class="search-select" @change="handleSearch">
          <el-option label="全部" value="-1" />
          <el-option label="新注册用户" value="-2" />
          <el-option label="申请管理员中" value="-3" />
          <el-option label="管理员" value="0" />
          <el-option label="学生" value="1" />
        </el-select>
        <el-date-picker
          v-model="searchUser.createTime"
          type="datetimerange"
          range-separator="到"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          size="default"
          clearable
          value-format="YYYY-MM-DD HH:mm:ss"
          class="search-date"
          @change="handleSearch"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <el-table :data="tableData" border style="width: 100%" :loading="loading" stripe fit>
        <el-table-column fixed prop="id" label="ID" align="center" width="60" />
        <el-table-column fixed prop="username" label="用户名" align="center" width="160">
          <template #default="scope">
            <div class="user-info">
              <el-avatar :src="scope.row.avatar || undefined" :size="32" class="user-avatar">
                {{ scope.row.username?.charAt(0) }}
              </el-avatar>
              <span class="user-name">{{ scope.row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="用户类型" align="center" width="110">
          <template #default="scope">
            <span v-if="scope.row.type == 0" class="type-tag type-admin">管理员</span>
            <span v-else-if="scope.row.type == 1" class="type-tag type-student">学生</span>
            <span v-else-if="scope.row.type == -2" class="type-tag type-new">新注册用户</span>
            <span v-else-if="scope.row.type == -3" class="type-tag type-apply">申请管理员中</span>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" align="center" width="180" />
        <el-table-column prop="sex" label="性别" align="center" width="70">
          <template #default="scope">
            <span v-if="scope.row.sex == 1">男</span>
            <span v-else-if="scope.row.sex == 0">女</span>
            <span v-else class="text-gray">无</span>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" align="center" width="180" />
        <el-table-column prop="grade" label="年级" align="center" width="80">
          <template #default="scope">
            <span v-if="scope.row.grade == 1">大一</span>
            <span v-else-if="scope.row.grade == 2">大二</span>
            <span v-else-if="scope.row.grade == 3">大三</span>
            <span v-else-if="scope.row.grade == 4">大四</span>
            <span v-else class="text-gray">无</span>
          </template>
        </el-table-column>
        <el-table-column prop="major" label="专业" align="center" width="180">
          <template #default="scope">
            <span v-if="scope.row?.major">{{ scope.row.major }}</span>
            <span v-else class="text-gray">无</span>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" align="center" min-width="220">
          <template #default="scope">
            <el-button v-if="scope.row.id == 1" type="warning" size="small" :disabled="!(information.id == 1)" @click="handleResetPassword(scope.row.id)">重置密码</el-button>
            <el-button v-else type="warning" size="small" @click="handleResetPassword(scope.row.id)" :disabled="!(information.id == 1)">重置密码</el-button>
            <el-button v-if="scope.row.id == 1" type="primary" size="small" :disabled="!(information.id == 1)" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button v-else type="primary" size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button v-if="scope.row.id == 1" type="danger" size="small" disabled>删除</el-button>
            <el-button v-else type="danger" size="small" @click="handleDeleteUser(scope.row.id)" :disabled="!(information.id == 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pageInfo.currentPage"
          v-model:page-size="pageInfo.pageSize"
          :total="pageInfo.total"
          :page-sizes="[10, 15, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>
  </div>

  <div class="edit-dialog-overlay" v-if="showEditDialog" @click="closeEditDialog">
    <div class="edit-dialog" @click.stop>
      <div class="edit-dialog-header">
        <span class="edit-dialog-title">编辑用户信息</span>
        <button class="edit-dialog-close" @click="closeEditDialog">×</button>
      </div>
      <div class="edit-dialog-body">
        <div class="form-item">
          <label class="form-label">头像</label>
          <div class="avatar-upload-area">
            <el-upload class="avatar-uploader" action="#" :show-file-list="false" :before-upload="beforeAvatarUpload" :http-request="uploadAvatar">
              <img v-if="editForm.avatar" :src="editForm.avatar" class="avatar-preview" />
              <div v-else class="avatar-placeholder">
                <span>{{ editForm.username?.charAt(0) || '?' }}</span>
              </div>
            </el-upload>
            <button v-if="editForm.avatar" class="remove-avatar-btn" @click="removeAvatar">移除头像</button>
          </div>
        </div>
        <div class="form-item">
          <label class="form-label">用户名</label>
          <input type="text" v-model="editForm.username" class="form-input" placeholder="请输入用户名" />
        </div>
        <div class="form-item">
          <label class="form-label">邮箱</label>
          <input type="text" :value="editForm.email" class="form-input" disabled />
        </div>
        <div class="form-item">
          <label class="form-label">性别</label>
          <select v-model="editForm.sex" class="form-select">
            <option :value="null">请选择</option>
            <option :value="1">男</option>
            <option :value="0">女</option>
          </select>
        </div>
        <div class="form-item">
          <label class="form-label">年级</label>
          <select v-model="editForm.grade" class="form-select">
            <option :value="null">请选择</option>
            <option :value="1">大一</option>
            <option :value="2">大二</option>
            <option :value="3">大三</option>
            <option :value="4">大四</option>
          </select>
        </div>
        <div class="form-item">
          <label class="form-label">专业</label>
          <input type="text" v-model="editForm.major" class="form-input" placeholder="请输入专业" />
        </div>
      </div>
      <div class="edit-dialog-footer">
        <button class="btn-cancel" @click="closeEditDialog">取消</button>
        <button class="btn-confirm" @click="submitEdit">确定</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-page);
  padding: 20px 24px;
}

.content-panel {
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  animation: fadeInUp 0.3s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  padding: 16px 18px;
  background: var(--bg-page);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.search-input {
  width: 200px;
}

.search-select {
  width: 150px;
}

.search-date {
  width: 350px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.type-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.type-tag.type-admin {
  background-color: var(--primary-light);
  color: var(--primary);
  border: 1px solid rgba(45, 125, 219, 0.2);
}

.type-tag.type-student {
  background-color: var(--pass-bg-color);
  color: var(--pass);
  border: 1px solid rgba(103, 194, 58, 0.2);
}

.type-tag.type-new {
  background-color: var(--coming-bg-color);
  color: var(--coming);
  border: 1px solid rgba(230, 162, 60, 0.2);
}

.type-tag.type-apply {
  background-color: var(--coming-bg-color);
  color: var(--coming);
  border: 1px solid rgba(230, 162, 60, 0.2);
}

.text-gray {
  color: var(--text-gray);
}

.user-info {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  color: var(--text-body);
}

:deep(.el-table) {
  --el-table-border-color: var(--border-color);
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(45, 125, 219, 0.04);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

:deep(.el-table th.el-table__cell) {
  color: var(--text-title);
  font-weight: 600;
  font-size: 13px;
  background: var(--bg-card) !important;
  padding: 12px 0;
  border-bottom: 2px solid var(--border-color);
}

:deep(.el-table td.el-table__cell) {
  color: var(--text-body);
  font-size: 13px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

:deep(.el-table .el-table__row:hover > td.el-table__cell) {
  background-color: rgba(45, 125, 219, 0.04);
}

:deep(.el-table .el-table__row--striped td.el-table__cell) {
  background-color: var(--bgc-light);
}

:deep(.el-table__empty-text) {
  color: var(--text-gray);
}

:deep(.el-button--primary) {
  background: var(--grad-primary);
  border: none;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.25);
}

:deep(.el-button--primary:hover) {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--primary:active) {
  transform: translateY(0);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, var(--main-delete) 0%, #f78a8a 100%);
  border: none;
  box-shadow: 0 2px 6px rgba(245, 108, 108, 0.25);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, #ff9999 100%);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--default) {
  border-color: var(--border-color);
  color: var(--text-body);
}

:deep(.el-button--default:hover) {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-light);
}

:deep(.el-button--small) {
  padding: 5px 12px;
  font-size: 12px;
  border-radius: 6px;
}

:deep(.el-button.is-disabled),
:deep(.el-button.is-disabled:hover),
:deep(.el-button.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
  opacity: 0.6;
  cursor: not-allowed;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--primary.is-disabled:hover),
:deep(.el-button--primary.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-button--danger.is-disabled),
:deep(.el-button--danger.is-disabled:hover),
:deep(.el-button--danger.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 6px;
  transition: all 0.2s;
}

:deep(.el-input__wrapper:hover),
:deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}

:deep(.el-input__wrapper:focus-within, .el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px rgba(45, 125, 219, 0.1) !important;
}

:deep(.el-pagination) {
  --el-pagination-button-bg-color: transparent;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: var(--grad-primary);
  color: white;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.3);
}

:deep(.el-pagination .el-pager li:hover) {
  color: var(--primary);
}

:deep(.el-table .el-button + .el-button) {
  margin-left: 6px;
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, var(--coming) 0%, #f5c87a 100%);
  border: none;
  color: #fff;
  box-shadow: 0 2px 6px rgba(230, 162, 60, 0.25);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-button--warning:hover) {
  background: linear-gradient(135deg, var(--coming-hover) 0%, #f0b84a 100%);
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.35);
  transform: translateY(-1px);
}

:deep(.el-button--warning:active) {
  transform: translateY(0);
}

:deep(.el-button--warning.is-disabled),
:deep(.el-button--warning.is-disabled:hover),
:deep(.el-button--warning.is-disabled:focus) {
  background-color: var(--bgc-light) !important;
  border-color: var(--border-color) !important;
  color: #fff !important;
  box-shadow: none !important;
}

.edit-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  overflow: hidden;
}

.edit-dialog {
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 480px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.edit-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--primary-light);
}

.edit-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.edit-dialog-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  color: var(--text-gray);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.edit-dialog-close:hover {
  background-color: rgba(0, 0, 0, 0.08);
  color: var(--text-title);
}

.edit-dialog-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.edit-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-page);
}

.form-item {
  margin-bottom: 16px;
}

.form-item:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 8px;
}

.form-input,
.form-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-body);
  background-color: #fff;
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px rgba(45, 125, 219, 0.1);
  border-color: var(--primary);
}

.form-input:disabled {
  background-color: var(--bgc-light);
  color: var(--text-gray);
  cursor: not-allowed;
}

.avatar-upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.avatar-uploader {
  cursor: pointer;
}

.avatar-preview {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--border-color);
}

.avatar-placeholder {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-fade) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--primary);
}

.avatar-placeholder span {
  font-size: 48px;
  color: var(--primary);
  font-weight: 600;
}

.remove-avatar-btn {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid var(--main-delete);
  background-color: transparent;
  color: var(--main-delete);
  cursor: pointer;
  transition: all 0.2s;
}

.remove-avatar-btn:hover {
  background-color: var(--main-fail-status);
}

.btn-cancel,
.btn-confirm {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-cancel {
  background-color: transparent;
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.btn-cancel:hover {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-light);
}

.btn-confirm {
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.25);
}

.btn-confirm:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

.btn-confirm:active {
  transform: translateY(0);
}
</style>