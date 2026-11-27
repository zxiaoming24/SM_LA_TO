<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { loginApi } from '@/api/login'

const router = useRouter()

// 登录表单
const loginData = ref({ username: '', password: '' })
const loading = ref(false)

// 登录提交
const subLogin = async () => {
  if (!loginData.value.username) {
    showFailToast('请输入用户名')
    return
  }
  if (!loginData.value.password) {
    showFailToast('请输入密码')
    return
  }

  loading.value = true
  try {
    const result = await loginApi(loginData.value)
    if (result.code === 1) {
      const user = result.data
      // 移动端限制：不允许新用户和管理员登录
      if (user.type === 0) {
        showFailToast('管理员请使用PC端登录')
        return
      }
      if (user.isNew) {
        showFailToast('新用户请先在PC端完善信息')
        return
      }
      // 登录成功
      user.loginTime = Date.now()
      localStorage.setItem('loginUser', JSON.stringify(user))
      showSuccessToast('登录成功')
      router.push('/phone/index')
    } else if (result.code === 2) {
      showFailToast(result.msg || '登录失败')
    }
  } catch (e) {
    showFailToast('网络异常，登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="phone-login">
    <!-- Logo区域 -->
    <div class="login-header">
      <img src="@/assets/logo/Logo.png" class="login-logo" />
      <h1 class="login-title">知行优课</h1>
      <p class="login-slogan">基于大模型的多智能体个性化学习系统</p>
    </div>

    <!-- 登录表单 -->
    <div class="login-form">
      <van-cell-group inset>
        <van-field
          v-model="loginData.username"
          label="用户名"
          placeholder="请输入用户名"
          left-icon="manager-o"
          clearable
        />
        <van-field
          v-model="loginData.password"
          label="密码"
          placeholder="请输入密码"
          type="password"
          left-icon="lock"
          clearable
        />
      </van-cell-group>
      <div class="login-btn-wrap">
        <van-button
          type="primary"
          block
          round
          size="large"
          :loading="loading"
          loading-text="登录中..."
          @click="subLogin"
        >
          登录
        </van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-login {
  min-height: 100vh;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px 40px;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.login-logo {
  width: 120px;
  height: 120px;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-title);
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
  margin-bottom: 8px;
}

.login-slogan {
  font-size: 13px;
  color: var(--text-gray);
}

.login-form {
  width: 100%;
  max-width: 400px;
}

.login-form :deep(.van-cell-group--inset) {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.login-form :deep(.van-field__label) {
  color: var(--text-body);
}

.login-form :deep(.van-field__control) {
  color: var(--text-title);
  font-size: 16px;
}

.login-btn-wrap {
  margin: 24px 16px 0;
}

.login-form :deep(.van-button--primary) {
  background: var(--primary);
  border-color: var(--primary);
}

.login-form :deep(.van-button--primary:active) {
  background: var(--primary-act);
  border-color: var(--primary-act);
}
</style>