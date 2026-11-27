<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { postTextApi } from '@/api/mainApi/aiAnswer.js'
import { uploadAvatarApi, submitStuInfoApi } from '@/api/info.js'

const router = useRouter()

// ================== 年级映射 ==================
const GRADE_MAP = {
  1: "大一",
  2: "大二",
  3: "大三",
  4: "大四"
}

// ================== 用户信息 ==================
const loginUser = ref(null)
const submitting = ref(false)

// 学生信息表单
const stuMessage = ref({
  id: null,
  username: '',
  avatar: '',
  email: '',
  sex: null,
  age: null,
  type: 1,
  major: '',
  grade: null
})

// ================== 表单校验规则 ==================
const stuRef = ref(null)
const rules = ref({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  sex: [
    { required: true, message: '请选择性别', trigger: 'change' }
  ],
  age: [
    { required: true, message: '请输入年龄', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value === '' || value === null || value === undefined) {
          callback()
          return
        }
        const ageNum = Number(value)
        if (isNaN(ageNum)) {
          callback(new Error('请输入有效的数字'))
          return
        }
        if (ageNum <= 0 || ageNum > 150) {
          callback(new Error('请输入正确的年龄范围(1-150)'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  grade: [
    { required: true, message: '请选择年级', trigger: 'change' }
  ],
  major: [
    { required: true, message: '请输入专业', trigger: 'blur' },
    { min: 1, max: 20, message: '长度在 1 到 20 个字符', trigger: 'blur' }
  ],
  avatar: [
    { required: true, message: '请上传头像', trigger: 'change' }
  ]
})

// ================== 初始化用户信息 ==================
onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      // 管理员跳转
      if (user.type === 0) {
        ElMessage.info('管理员请前往后台管理系统')
        router.push('/admin')
        return
      }
      loginUser.value = user
      stuMessage.value = {
        id: user.id,
        username: user.username || '',
        avatar: user.avatar || '',
        email: user.email || '',
        sex: user.sex ?? null,
        age: user.age ?? null,
        type: 1,
        major: user.major || '',
        grade: user.grade ?? null
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
})

// ================== 头像上传 ==================
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
      stuMessage.value.avatar = result.data
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
  stuMessage.value.avatar = ''
  ElMessage.info('头像已移除')
}

// ================== 提交信息 ==================
const submit = async () => {
  if (!stuRef.value) return

  stuRef.value.validate(async (valid) => {
    if (!valid) return ElMessage.error('请检查输入内容')

    submitting.value = true

    try {
      // 提交学生信息
      const result = await submitStuInfoApi(stuMessage.value)

      if (result.code) {
        ElMessage.success('信息完善成功！')
        // 更新本地存储
        const oldUser = JSON.parse(localStorage.getItem('loginUser') || '{}')
        const newUser = { ...oldUser, ...stuMessage.value }
        localStorage.setItem('loginUser', JSON.stringify(newUser))
        // 刷新页面
        window.location.reload()

      } else {
        ElMessage.error(result.msg || '提交失败')
      }
    } catch (error) {
      console.error('提交失败:', error)
      ElMessage.error('提交失败，请稍后重试')
    } finally {
      submitting.value = false
    }
  })
}
</script>

<template>
  <div class="user-center">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>您的个人信息</h2>
      <p>确保您的信息准确，系统将根据您的信息提供个性化服务</p>
    </div>

    <!-- 表单内容 -->
    <div class="form-container">
      <el-form
        ref="stuRef"
        :model="stuMessage"
        :rules="rules"
        label-width="100px"
        label-position="right"
        size="large"
      >
        <!-- 头像 -->
        <el-form-item label="头像" prop="avatar">
          <div class="avatar-wrapper">
            <el-upload
              class="avatar-uploader"
              action="#"
              :show-file-list="false"
              :before-upload="beforeAvatarUpload"
              :http-request="uploadAvatar"
            >
              <img v-if="stuMessage.avatar" :src="stuMessage.avatar" class="avatar-img" />
              <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
            </el-upload>
            <el-button
              v-if="stuMessage.avatar"
              type="danger"
              size="small"
              plain
              @click="removeAvatar"
              class="remove-btn"
            >
              移除头像
            </el-button>
          </div>
        </el-form-item>

        <!-- 用户名 -->
        <el-form-item label="用户名" prop="username">
          <el-input v-model="stuMessage.username" placeholder="请输入用户名" />
        </el-form-item>

        <!-- 邮箱（只读） -->
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="stuMessage.email" placeholder="请输入邮箱" disabled />
        </el-form-item>

        <!-- 性别 -->
        <el-form-item label="性别" prop="sex">
          <el-radio-group v-model="stuMessage.sex">
            <el-radio :label="1">男</el-radio>
            <el-radio :label="0">女</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 年龄 -->
        <el-form-item label="年龄" prop="age">
          <el-input-number
            v-model="stuMessage.age"
            :min="1"
            :max="150"
            placeholder="请输入年龄"
            controls-position="right"
          />
        </el-form-item>

        <!-- 年级 -->
        <el-form-item label="年级" prop="grade">
          <el-radio-group v-model="stuMessage.grade">
            <el-radio-button :label="1">大一</el-radio-button>
            <el-radio-button :label="2">大二</el-radio-button>
            <el-radio-button :label="3">大三</el-radio-button>
            <el-radio-button :label="4">大四</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 专业 -->
        <el-form-item label="专业" prop="major">
          <el-input v-model="stuMessage.major" placeholder="请输入专业名称" />
        </el-form-item>

        <!-- 提交按钮 -->
        <el-form-item>
          <el-button
            class="submit-btn"
            type="primary"
            size="large"
            :loading="submitting"
            @click="submit"
          >
            提交信息
          </el-button>
        </el-form-item>
      </el-form>
    </div>


  </div>
</template>

<style scoped>
* {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

.user-center {
  max-width: 720px;
  margin: 0px auto;
  padding: 0 10px 60px;
}

/* ===== 页面标题 ===== */
.page-header {
  text-align: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-title, #1a1a2e);
  margin-bottom: 10px;
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
}

.page-header p {
  font-size: 16px;
  color: var(--text-gray, #888);
}

/* ===== 表单容器 ===== */
.form-container {
  background: var(--bg-card, #fff);
  border-radius: 16px;
  padding: 40px 48px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color, #e8ecf1);
}

/* ===== 头像上传 ===== */
.avatar-wrapper {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.avatar-uploader {
  display: inline-block;
}

.avatar-uploader .avatar-img {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--border-color, #e8ecf1);
  transition: border-color 0.3s;
}

.avatar-uploader .avatar-img:hover {
  border-color: var(--primary, #409eff);
}

.avatar-uploader .el-upload {
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--border-color, #d9d9d9);
  transition: border-color 0.3s;
}

.avatar-uploader .el-upload:hover {
  border-color: var(--primary, #409eff);
}

.avatar-uploader-icon {
  font-size: 40px;
  color: var(--text-gray, #aaa);
}

.remove-btn {
  align-self: flex-end;
  margin-bottom: 8px;
}

/* ===== 表单项 ===== */
:deep(.el-form-item) {
  margin-bottom: 28px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-body, #333);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary, #409eff) inset;
}

:deep(.el-input-number .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary, #409eff) inset;
}

/* ===== 提交按钮 ===== */
.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 18px;
  font-weight: 600;
  border-radius: 8px;
  margin-top: 8px;
}

:deep(.el-button--primary) {
  --el-button-bg-color: var(--primary, #409eff);
  --el-button-border-color: var(--primary, #409eff);
  --el-button-hover-bg-color: var(--primary-hv, #66b1ff);
  --el-button-hover-border-color: var(--primary-hv, #66b1ff);
}



</style>