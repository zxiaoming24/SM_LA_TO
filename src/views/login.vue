<script setup>
import '@/assets/font.css'
import { ElMessage } from 'element-plus'
import { ref,onMounted,onUnmounted } from 'vue'
import { getCodeApi, loginApi, regAndPwdApi } from '@/api/login'
import { useRouter } from 'vue-router'
const router = useRouter()

const showLoading = ref(false)
const loadingText = ref('')
const appQrcodeFailed = ref(false)
//==================================倒计时器=========================================
// 获取验证码倒计时
let timer = null
const countDown = ref(60)
const disableShow = ref(false)
const buttonText = ref('获取验证码')

onMounted(() => {
  // 强制日间模式
  document.documentElement.classList.remove('dark')
  
  // 页面加载时恢复倒计时
  const stored = localStorage.getItem('countDown')
  if (stored && stored > 0) {
    countDown.value = Number(stored)
    disableShow.value = true
    buttonText.value = `${stored}秒后可重发`
    getCodeTime()
  }
})
// 清理定时器
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
// 倒计时
const getCodeTime = () => {
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    if (countDown.value > 0) {
      disableShow.value = true
      countDown.value--
      buttonText.value = `${countDown.value}秒后可重发`
      localStorage.setItem('countDown', countDown.value)
    } else {
      clearInterval(timer)
      localStorage.removeItem('countDown')
      buttonText.value = '获取验证码'
      countDown.value = 60
      disableShow.value = false
    }
  }, 1000)
}

//==================================表单============================================
// 登录表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
  ]
}
// 注册表单验证规则
const regRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  verificationCode: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '请输入6位数字验证码', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
  ],
  repassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (value !== resData.value.password) {
          callback(new Error('两次输入密码不一致!'))
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ]
}
// 修改密码表单验证规则
const pwdRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  verificationCode: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '请输入6位数字验证码', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '长度在 6 到 20 个字符', trigger: 'blur' }
  ],
  repassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (value !== pwdData.value.password) {
          callback(new Error('两次输入密码不一致!'))
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ]
}

//修改密码表单
const pwdData = ref({email: '', verificationCode: '', password: '', repassword: ''})
const pwdRef = ref()
//登录选择
const loginChose = ref(true)
// 登录表单-邮箱
const loginEmailData = ref({email: '', password: ''})
const loginEmailRef = ref()
// 登录表单-用户名
const loginUsernameData = ref({username: '', password: ''})
const loginUsernameRef = ref()
// 注册表单
const resData = ref({username: '', email: '', verificationCode: '', password: '', repassword: ''})
const resRef = ref()
//表单内容和规则重置
const pwdReset = () => { 
  pwdRef.value.resetFields()
  pwdData.value = {email: '', verificationCode: '', password: '', repassword: ''}
}
const resReset = () => { 
  resRef.value.resetFields()
  resData.value = {username: '', email: '', verificationCode: '', password: '', repassword: ''}
}
const loginReset = () => { 
  if(loginChose.value){
    loginUsernameRef.value.resetFields()
    loginUsernameData.value = {username: '', password: ''}
  }else{
    loginEmailRef.value.resetFields()
    loginEmailData.value = {email: '', password: ''}
  }
}

// ================================动画============================================
//修改密码/注册可见
const Visible = ref(true)//修改密码框可见，注册框不可见，反之
//是否动画
const isAnimation = ref(false)//true:正在执行动画，false:动画结束
// 新增一个响应式变量控制翻转
const isTurned = ref(false)//逆时针旋转
const isBackTurned = ref(false)//顺时针
// 登录->修改密码
const toPwd = () => { 
  if(isAnimation.value) return//禁止有动画时重复点击
  loginReset()//登录表单重置
  Visible.value = true//显示修改密码框
  isTurned.value = true // 触发逆时针翻转
}
// 登录->注册
const toRes = () => { 
  if(isAnimation.value) return
  loginReset()
  Visible.value = false
  isBackTurned.value = true
}
// 修改密码->登录
const pwdToLogin = () => { 
  pwdReset()
  isAnimation.value = true
  isTurned.value = false // 翻转恢复
  // 延时
  setTimeout(() => { 
    Visible.value = false
    isAnimation.value = false
  }, 500)

}
// 注册->登录
const resToLogin = () => { 
  resReset()
  isAnimation.value = true
  isBackTurned.value = false // 恢复
  setTimeout(() => { // 延时，等待旋转完成
    Visible.value = true
    isAnimation.value = false
  }, 500)

}

// =================================接口============================================
// 获取验证码
const getCode = async(isEmail,refMessage) => {
  if(refMessage === 'success'){
    ElMessage.info(`正在尝试发送验证码到${isEmail}`)
    //开始倒计时
    getCodeTime() 
    // 发送验证码
    const result = await getCodeApi(isEmail)
    if(result.code){
      ElMessage.success(`已发送验证码到${isEmail}`)
    }else{
      ElMessage.error(result.msg)
    }
  }else if(refMessage === 'error'){
    ElMessage.error('邮箱格式不正确')
  }else if(refMessage === ''){
    ElMessage.error('请输入先邮箱')
  }
}

// 修改密码提交
const subPwd = async() => { 
  if (!pwdRef.value) return
  pwdRef.value.validate(async valid => {
    if (!valid) return ElMessage.error('请检查输入内容')
    showLoading.value = true
    loadingText.value = '正在修改密码...'
    try {
      const result = await regAndPwdApi(pwdData.value)
      if (result.code) {
        ElMessage.success(result.msg || '无')
        pwdToLogin()
      } else {
        ElMessage.error(result.msg)
      }
    } finally {
      showLoading.value = false
    }
  })
}
// 注册提交
const subReg = async() => { 
  if (!resRef.value) return
  resRef.value.validate(async valid => {
    if (!valid) return ElMessage.error('请检查输入内容')
    showLoading.value = true
    loadingText.value = '正在注册...'
    try {
      const result = await regAndPwdApi(resData.value)
      if (result.code) {
        ElMessage.success(result.msg || '无')
        resToLogin()
      } else {
        ElMessage.error(result.msg)
      }
    } finally {
      showLoading.value = false
    }
  })
}
// 登录提交(用户名登录)
const subLoginUsername = async() => { 
  if (!loginUsernameRef.value) return
  loginUsernameRef.value.validate(async valid => {
    if (!valid) return ElMessage.error('请检查输入内容')
    showLoading.value = true
    loadingText.value = '正在登录...'
    try {
      const result = await loginApi(loginUsernameData.value)
      if (result.code === 1) {
        result.data.loginTime = Date.now()
        localStorage.setItem('loginUser', JSON.stringify(result.data))
        ElMessage.success(result.msg || '无')
        // 跳转
        if(result.data.type == 0){//管理员
          router.push('/admin/index')//跳转管理端
        }else if(result.data.isNew || result.data.type == -2){//新用户(isNew标志或type身份标志)
          router.push('/info')//跳转完善信息
        }else{
          if(result.data.isBuildProfile == 1){//完善信息过了，也构建画像
            router.push('/index')//跳转首页
          }else{
            router.push('/aiAnswer')//完善信息过了，但是没有构建画像，跳转AI问答
          }
        }
        
      } else if(result.code === 2) {
        ElMessage.error(result.msg)
        showLoading.value = false
      }
    } catch {
      showLoading.value = false
    }
  })
}
// 登录提交(邮箱登录)
const subLoginEmail = async() => { 
  if (!loginEmailRef.value) return
  loginEmailRef.value.validate(async valid => {
    if (!valid) return ElMessage.error('请检查输入内容')
    showLoading.value = true
    loadingText.value = '正在登录...'
    try {
      const result = await loginApi(loginEmailData.value)
      if (result.code) {
        localStorage.setItem('loginUser', JSON.stringify(result.data))
        ElMessage.success('登录成功')
        if(result.data.type == 0){
          router.push('/admin/index')
        }else if(result.data.isNew){
          router.push('/info')
        }else{
          if(result.data.isBuildProfile === 1){
            router.push('/index')
          }else{
            router.push('/aiAnswer')
          }
        }
      } else {
        ElMessage.error(result.msg)
        showLoading.value = false
      }
    } catch {
      showLoading.value = false
    }
  })
}
</script>

<template>
  <!-- 背景图 -->
  <div class="bgc">
    
    <!-- 右下角二维码 -->
    <div class="qrcode-fixed">
      <img src="https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/qrcode.png" alt="移动端二维码" />
      <span>移动端H5</span>
    </div>
    <div class="qrcode-fixed  qrcode-fixed2">
      <img 
        src="https://java-web-project-13859154338.oss-cn-beijing.aliyuncs.com/CollectStudySystem/qrcode2.png" 
        alt="移动端app二维码" 
        @error="appQrcodeFailed = true"
        v-show="!appQrcodeFailed"
      />
      <div v-if="appQrcodeFailed" class="qrcode-fail">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <span>二维码加载失败</span>
      </div>
      <span>移动端app</span>
    </div>
    
    <!-- 全屏加载动画 -->
    <div v-if="showLoading" class="loading-overlay">
      <div class="loading-content">
        <div class="loading-ring">
          <div class="ring ring-1"></div>
          <div class="ring ring-2"></div>
          <div class="ring ring-3"></div>
          <div class="ring-center"></div>
        </div>
        <div class="loading-text">{{ loadingText }}</div>
        <div class="loading-dots">
          <span class="dot dot-1">.</span>
          <span class="dot dot-2">.</span>
          <span class="dot dot-3">.</span>
        </div>
      </div>
    </div>
    
    <div class="flip-box" :class="{ 'turn': isTurned,'backturn': isBackTurned }" >
        <!-- 忘记密码容器 -->
        <div class="container pwd-container back" v-if="Visible"> 
         <!-- 头部 -->
         <div class="head pwd-head">
           <!-- login图 -->
           <div class="logo">
             <img src="@/assets/logo/Logo.png" alt=""></img>
             <h1>修改密码</h1>
           </div>
           <div class="slogan">
             <h2>支持通过邮箱验证设置新密码</h2>
           </div>
         </div>
         <!-- 修改密码表单 -->
         <div class="pwd-form"> 
          <el-form label-position="top" ref="pwdRef" :model="pwdData" :rules="pwdRules">
            <el-form-item label="邮箱" prop="email"> 
              <el-input placeholder="请输入邮箱" size="large" v-model="pwdData.email">
                <template #append>
                  <el-button @Click="getCode(pwdData.email,pwdRef.fields[0].validateState)" :disabled="disableShow">{{ buttonText }}</el-button>
                </template>
                <template #prefix>
                  <el-icon><TakeawayBox /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="验证码" prop="verificationCode"> 
              <el-input placeholder="请输入验证码" size="large" v-model="pwdData.verificationCode">
                <template #prefix>
                  <el-icon><Message /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="密码" prop="password"> 
              <el-input 
                placeholder="请输入密码" 
                type="password" 
                size="large" 
                show-password
                v-model="pwdData.password"
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="再次输入密码" prop="repassword"> 
              <el-input 
                placeholder="请输入再次输入密码" 
                type="password" 
                size="large" 
                show-password
                v-model="pwdData.repassword"
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          
            <!-- 确认修改按钮 -->
            <el-form-item class="btn">
              <el-button type="primary" class="pwd-btn" size="large" @click="subPwd()">确认修改</el-button>
            </el-form-item>
          </el-form>
         </div>
         <!-- 返回 -->
         <div class="bot pwdABack"> 
          <el-tooltip content="返回将重置" placement="bottom" hide-after="0">
            <a href="javaScript:void(0)" @click="pwdToLogin()" id="pwdToLogin">返回登录 ▶</a>
          </el-tooltip>
         </div>
        </div>
      
      
      
        <!-- 登录容器 -->
        <div class="container login-container"> 
          <!-- 头部 -->
          <div class="head">
            <!-- login图 -->
            <div class="logo">
              <img src="@/assets/logo/Logo.png" alt=""></img>
              <h1>知行优课</h1>
            </div>
            <div class="slogan">
              <h2>基于大模型的多智能体个性化学习系统</h2>
              <el-switch
                class="chose"
                v-model="loginChose"
                size="large"
                active-text="用户名"
                inactive-text="邮箱"
              />
            </div>
          </div>
          
          
           
        
           <!-- 登录表单-邮箱 -->
           <div class="login-form" v-if="!(loginChose)"> 
            <el-form label-position="top" ref="loginEmailRef" :model="loginEmailData" :rules="loginRules">
              <el-form-item label="邮箱" prop="email"> 
                <el-input placeholder="请输入邮箱" size="large" v-model="loginEmailData.email">
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="密码" prop="password"> 
                <el-input 
                  placeholder="请输入密码" 
                  type="password" 
                  size="large" 
                  show-password
                  v-model="loginEmailData.password"
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            
              <!-- 提交按钮 -->
              <el-form-item class="btn">
                <el-button type="primary" class="login-btn" size="large" @click="subLoginEmail()">邮箱登录</el-button>
              </el-form-item>
            </el-form>
           </div>
          
           <!-- 登录表单-用户名 -->
           <div class="login-form" v-else-if="loginChose"> 
            <el-form label-position="top" ref="loginUsernameRef" :model="loginUsernameData" :rules="loginRules">
              <el-form-item label="用户名" prop="username"> 
                <el-input placeholder="请输入用户名" size="large" v-model="loginUsernameData.username">
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="密码" prop="password"> 
                <el-input 
                  placeholder="请输入密码" 
                  type="password" 
                  size="large" 
                  show-password
                  v-model="loginUsernameData.password"
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            
              <!-- 提交按钮 -->
              <el-form-item class="btn">
                <el-button type="primary" class="login-btn" size="large" @click="subLoginUsername()">用户名登录</el-button>
              </el-form-item>
            </el-form>
           </div>
          
          
          <!-- 忘记密码|注册 -->
          <div class="bot login-bot"> 
            <el-tooltip content="点击修改密码" placement="bottom" hide-after="0">
              <a href="javaScript:void(0)" @click="toPwd()" id="toPwd">忘记密码?</a>
            </el-tooltip>
            <span style="margin: 0 8px; color: #dcdfe6;">|</span>
            <span>没有账号？</span>
            <el-tooltip content="注册新用户" placement="bottom" hide-after="0">
              <a href="javaScript:void(0)" @click="toRes()" id="toRes">注册</a>
            </el-tooltip>
          </div>
        
        </div>
      
      
      
        <!-- 注册容器 -->
        <div class="container res-container back" v-if="!(Visible)"> 
          <!-- 头部 -->
          <div class="head res-head">
            <!-- login图 -->
            <div class="logo">
              <img src="@/assets/logo/Logo.png" alt=""></img>
              <h1>注册</h1>
            </div>
            <div class="slogan">
              <h2>新用户可使用邮箱注册账号</h2>
            </div>
          
          </div>
          <!-- 注册表单 -->
           <div class="res-form"> 
            <el-form label-position="top" ref="resRef" :model="resData" :rules="regRules">
              <el-form-item label="用户名" prop="username"> 
                <el-input placeholder="请输入用户名" size="large" v-model="resData.username">
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="邮箱" prop="email"> 
                <el-input placeholder="请输入邮箱" size="large" v-model="resData.email">
                  <template #append>
                    <el-button @Click="getCode(resData.email,resRef.fields[1].validateState)" :disabled="disableShow">{{ buttonText }}</el-button>
                  </template>
                  <template #prefix>
                    <el-icon><TakeawayBox /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="验证码" prop="verificationCode"> 
                <el-input placeholder="请输入验证码" size="large" v-model="resData.verificationCode">
                  <template #prefix>
                    <el-icon><Message /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="密码" prop="password"> 
                <el-input 
                  placeholder="请输入密码" 
                  type="password" 
                  size="large" 
                  show-password
                  v-model="resData.password"
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="再次输入密码" prop="repassword"> 
                <el-input 
                  placeholder="请输入再次输入密码" 
                  type="password" 
                  size="large" 
                  show-password
                  v-model="resData.repassword"
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
            
              <!-- 注册按钮 -->
              <el-form-item class="btn">
                <el-button type="primary" class="res-btn" size="large" @click="subReg()">注册</el-button>
              </el-form-item>
            </el-form>
           </div>
          
          <!-- 返回 -->
          <div class="bot"> 
            <el-tooltip content="返回将重置" placement="bottom" hide-after="0">
              <a href="javaScript:void(0)" @click="resToLogin()" id="resToLogin">◀ 返回登录</a>
            </el-tooltip>
          </div>
        
        </div>

    </div>

  </div>
</template>

<style scoped>
/* 所有文字不可被光标选中 */
* {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

/* 右下角二维码固定定位 */
.qrcode-fixed {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.qrcode-fixed2 {
  bottom: 200px;
  z-index: 999;
}

.qrcode-fixed span {
  margin-top: 8px;
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.qrcode-fixed img {
  width: 120px;
  height: 120px;
  border-radius: 8px;
}

.qrcode-fail {
  width: 120px;
  height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border-radius: 8px;
  color: #999;
}

.qrcode-fail span {
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}

/* 登录页面样式 */
/* 背景图片，覆盖整个页面 */
.bgc {
  background-image: url("@/assets/image/bgcImage.png");
  height: 100vh;
  width: 100vw;
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
  background-attachment: fixed;

  /* 容器居中 */
  display: flex;
  justify-content: center;
  align-items: center;

}

/* 翻转容器 */
.flip-box {
  position: relative;
  width: 524px;
  height: 614px;
  transform-style: preserve-3d;
  transition: transform 0.7s ease;
  
}
.flip-box.turn {
    transform: rotateY(180deg);
}
.flip-box.backturn {
    transform: rotateY(-180deg);
}

.flip-box > div {
  transition: all 0.7s;
  /* 转到后面要隐藏盒子 */
  backface-visibility: hidden;
  /* 父元素写这个，开启子元素的3d空间效果，默认的flat会将子元素压平 */
  transform-style: preserve-3d;
}

/* 后面容器 */
.back {
  transform: rotateY(180deg);
}

/* 修改密码/登录/注册容器*/
.container {
  width: 520px;
  height: 610px;
  background-color: var(--bg-card);
  border-radius: 20px;
  border: 2px solid var(--border-color);
  box-shadow: var(--shadow-brand);

  padding: 0 60px;
  padding-top: 40px;
  transform-style: preserve-3d;

  position: absolute;
}
.container * {
  /* 文字走到眼前 */
  transform: translateZ(60px);
  backface-visibility: hidden;
}

/* 头部 */
.head {
  width: 100%;
  margin-bottom: 35px;
}
.head .logo {
  width: 100%;
  height: 90px;

  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
}
.head .logo img {
  width: 100px;
  height: 100px;
}
.head .logo h1 {
  font-size: 40px;
}
.head .slogan {
  margin-top: 5px;
  width: 100%;
  text-align: center;
}
.head .slogan h2,
.head .logo h1 {
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}
.head .chose {
  margin-top: 10px;
}

/* 登录表单 */
.login-form {
  width: 100%;
}
.btn .login-btn {
  margin-top: 30px;
  width: 100%;
}
.login-container { 
  z-index: 3;
}

/* 忘记密码&注册 按钮 */
.btn .res-btn,
.btn .pwd-btn {
  margin-top: 10px;
  width: 100%;
}

.btn .pwd-btn {
  margin-top: 25px;
}

/* 底部字样 */
.bot {
  text-align: center;
  font-size: 14px;
}

/* 忘记密码-返回 */
.pwdABack {
  margin-top: 10px;
}

/* 登录-字样 */
.login-bot{
  margin-top: 25px;
}

/* 注册表单 */
.res-head{
  margin-bottom: 5px;
}
.res-container {
  z-index: 2;
  padding-top: 10px;
}

/* 忘记密码表单 */
.pwd-head{
  margin-bottom: 15px;
}
.pwd-container {
  z-index: 1;
}



/* 开关选择器颜色 */
:deep(.el-switch.is-checked .el-switch__core) {
  border-color: var(--el-switch-border-color, var(--primary));
  background-color: var(--primary);
}
:deep(.el-switch__label.is-active) {
  color: var(--primary);
}


/* 获取验证码按钮 */
:deep(.el-input-group__append) {
  background-color: var(--primary);
  color: var(--primary-light);
  box-shadow: none;
}

/* 全屏加载动画 */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 99999;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.loading-ring {
  position: relative;
  width: 100px;
  height: 100px;
}

.ring {
  position: absolute;
  border-radius: 50%;
  border: 3px solid transparent;
  animation: spin 2s linear infinite;
}

.ring-1 {
  width: 100%;
  height: 100%;
  border-top-color: var(--primary);
  border-right-color: var(--primary);
  animation-duration: 1.5s;
}

.ring-2 {
  width: 75%;
  height: 75%;
  top: 12.5%;
  left: 12.5%;
  border-bottom-color: var(--primary);
  border-left-color: var(--primary);
  animation-duration: 2s;
  animation-direction: reverse;
}

.ring-3 {
  width: 50%;
  height: 50%;
  top: 25%;
  left: 25%;
  border-top-color: var(--primary-light);
  border-right-color: var(--primary-light);
  animation-duration: 2.5s;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ring-center {
  position: absolute;
  width: 25%;
  height: 25%;
  top: 37.5%;
  left: 37.5%;
  border-radius: 50%;
  background: var(--primary);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.7; }
}

.loading-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 2px;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.dot {
  font-size: 24px;
  color: var(--primary);
  animation: dotBounce 1.4s ease-in-out infinite both;
}

.dot-1 { animation-delay: -0.32s; }
.dot-2 { animation-delay: -0.16s; }
.dot-3 { animation-delay: 0s; }

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>