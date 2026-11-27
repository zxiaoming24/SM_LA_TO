<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showDialog } from 'vant'
import { uploadAvatarApi, submitStuInfoApi } from '@/api/info'
import { exitApi } from '@/api/login'

const router = useRouter()

// 年级映射
const GRADE_MAP = { 1: '大一', 2: '大二', 3: '大三', 4: '大四' }
const gradeOptions = [
  { text: '大一', value: 1 },
  { text: '大二', value: 2 },
  { text: '大三', value: 3 },
  { text: '大四', value: 4 }
]

// 用户信息
const loginUser = ref(null)
const submitting = ref(false)
const showGradePicker = ref(false)

// 存储初始表单数据
const initialStuMessage = ref(null)

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

// 检测表单是否发生变化
const isFormChanged = computed(() => {
  if (!initialStuMessage.value) return false
  const current = stuMessage.value
  const initial = initialStuMessage.value
  // 比较关键字段
  return current.username !== initial.username ||
    current.sex !== initial.sex ||
    current.age !== initial.age ||
    current.major !== initial.major ||
    current.grade !== initial.grade ||
    current.avatar !== initial.avatar
})

// 初始化
onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
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
      // 保存初始数据
      initialStuMessage.value = { ...stuMessage.value }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
})

// 头像上传
const onAvatarChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  const isJPGOrPNG = file.type === 'image/jpeg' || file.type === 'image/png'
  if (!isJPGOrPNG) {
    showFailToast('头像只能是 JPG 或 PNG')
    return
  }
  if (file.size / 1024 / 1024 > 2) {
    showFailToast('头像不能超过 2MB')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  try {
    const result = await uploadAvatarApi(formData)
    if (result.code === 1) {
      stuMessage.value.avatar = result.data
      showSuccessToast('头像上传成功')
    } else {
      showFailToast(result.msg || '上传失败')
    }
  } catch {
    showFailToast('网络异常，上传失败')
  }
}

// 年级选择确认
const onGradeConfirm = ({ selectedValues }) => {
  stuMessage.value.grade = selectedValues[0]
  showGradePicker.value = false
}

// 提交信息
const submit = async () => {
  if (!stuMessage.value.username) return showFailToast('请输入用户名')
  if (!stuMessage.value.email) return showFailToast('请输入邮箱')
  if (stuMessage.value.sex === null) return showFailToast('请选择性别')
  if (!stuMessage.value.age) return showFailToast('请输入年龄')
  if (!stuMessage.value.grade) return showFailToast('请选择年级')
  if (!stuMessage.value.major) return showFailToast('请输入专业')

  submitting.value = true
  try {
    const result = await submitStuInfoApi(stuMessage.value)
    if (result.code) {
      showSuccessToast('信息完善成功')
      const oldUser = JSON.parse(localStorage.getItem('loginUser') || '{}')
      const newUser = { ...oldUser, ...stuMessage.value }
      localStorage.setItem('loginUser', JSON.stringify(newUser))
      window.location.reload()
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch {
    showFailToast('提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

// 退出登录
const logout = async () => {
  try {
    await showDialog({
      title: '退出登录',
      message: '确定要退出登录吗？',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      showCancelButton: true
    })
    
    // 调用退出 API
    if (loginUser.value?.id) {
      await exitApi(loginUser.value.id)
    }
    
    // 清除本地存储
    localStorage.removeItem('loginUser')
    showSuccessToast('已退出登录')
    
    // 跳转到登录页
    router.push('/phone/login')
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <div class="phone-user-center">
    <!-- 头像区域 -->
    <div class="avatar-section">
      <label class="avatar-label">
        <img v-if="stuMessage.avatar" :src="stuMessage.avatar" class="avatar-img" />
        <div v-else class="avatar-placeholder">
          <van-icon name="photograph" size="24" />
        </div>
        <input type="file" accept="image/jpeg,image/png" style="display:none" @change="onAvatarChange" />
        <span class="avatar-tip">点击更换头像</span>
      </label>
    </div>

    <!-- 表单 -->
    <div>
      <van-cell-group inset title="基本信息">
        <van-field
          v-model="stuMessage.username"
          label="用户名"
          placeholder="请输入用户名"
        />
        <van-field
          v-model="stuMessage.email"
          label="邮箱"
          placeholder="邮箱"
          disabled
        />
        <van-field name="sex" label="性别">
          <template #input>
            <van-radio-group v-model="stuMessage.sex" direction="horizontal">
              <van-radio :name="1">男</van-radio>
              <van-radio :name="0">女</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-model="stuMessage.age"
          label="年龄"
          type="digit"
          placeholder="请输入年龄"
        />
        <van-field
          label="年级"
          :model-value="GRADE_MAP[stuMessage.grade] || ''"
          is-link
          readonly
          @click="showGradePicker = true"
        />
        <van-field
          v-model="stuMessage.major"
          label="专业"
          placeholder="请输入专业名称"
        />
      </van-cell-group>

      <div class="submit-wrap">
        <van-button
          type="primary"
          block
          round
          size="large"
          :loading="submitting"
          :disabled="!isFormChanged"
          loading-text="提交中..."
          @click="submit"
        >
          修改提交
        </van-button>
      </div>

      <div class="logout-wrap">
        <van-button
          type="danger"
          block
          round
          size="large"
          plain
          @click="logout"
        >
          退出登录
        </van-button>
      </div>
    </div>

    <!-- 年级选择器 -->
    <van-popup v-model:show="showGradePicker" position="bottom" round>
      <van-picker
        :columns="gradeOptions"
        @confirm="onGradeConfirm"
        @cancel="showGradePicker = false"
      />
    </van-popup>
  </div>
</template>

<style scoped>
.phone-user-center {
  padding: 16px 0;
  padding-bottom: 60px;
}

.avatar-section {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.avatar-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.avatar-img {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--border-color);
}

.avatar-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--bg-hover);
  border: 2px dashed var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-gray);
}

.avatar-tip {
  font-size: 12px;
  color: var(--text-gray);
}

:deep(.van-cell-group__title) {
  color: var(--text-body);
}

:deep(.van-cell-group--inset) {
  background: var(--bg-card);
  margin: 0 16px 16px;
}

:deep(.van-field__label) {
  color: var(--text-body);
}

:deep(.van-field__control) {
  color: var(--text-title);
}

:deep(.van-field__control:disabled) {
  color: var(--text-gray);
  -webkit-text-fill-color: var(--text-gray);
}

.submit-wrap {
  padding: 24px 16px 0;
}

.logout-wrap {
  padding: 16px 16px 0;
}

:deep(.van-button--primary) {
  background: var(--primary);
  border-color: var(--primary);
}

:deep(.van-button--primary:active) {
  background: var(--primary-act);
  border-color: var(--primary-act);
}
</style>
