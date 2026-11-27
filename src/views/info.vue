<script setup>
import { useRouter } from 'vue-router'
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { postTextApi } from '@/api/mainApi/aiAnswer.js'
import { uploadAvatarApi, submitStuInfoApi, applyAdminApi } from '@/api/info.js'
import { Loading } from '@element-plus/icons-vue'
import { exitApi } from '@/api/login.js'//登出

// 基本信息处理
const GRADE_MAP = { //年级映射表
  1: "大一",
  2: "大二",
  3: "大三",
  4: "大四"
}
// ==================顶部导航栏===================
const router = useRouter()

const loginName = ref('') //用户信息
const loginAvatar = ref('') //头像
const information = ref({ //用户信息
  id: null,
  username: '',
  email: '',
  avatar: ''
})
let loginUser = null //登录用户
onMounted(() => {
  // 强制日间模式
  document.documentElement.classList.remove('dark')
  
  // 获取用户名
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        loginName.value = loginUser.username
        loginAvatar.value = loginUser.avatar
        information.value = {
          id: loginUser.id,
          username: loginUser.username,
          email: loginUser.email,
          avatar: loginUser.avatar,
          isNew: loginUser.isNew,
          isBuildProfile: loginUser.isBuildProfile,
          type: loginUser.type
        }
      }
      
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  //校验用户是否生成管理员中
  if(information.value.isNew && information.value.type == -3){
    localStorage.removeItem('loginUser')
    ElMessage.info('已申请为管理员，请等待管理员审核')
    router.push('/login')
  }else if(information.value.isNew == false && information.value.isBuildProfile == 0){
    ElMessage.warning('已完善信息，请进行画像构建~')
    router.push('/aiAnswer')
  }else if(information.value.isNew == false && information.value.type == 1){
    ElMessage.success('用户您好，您已完善信息，为您跳转用户端首页~')
    router.push('/index')
  }else if(information.value.isNew == false && information.value.type == 0){ 
    ElMessage.success('管理员您好，您已完善信息，为您跳转管理端首页~')
    router.push('/admin/index')
  }else if(information.value.isNew && information.value.type == -2){
    ElMessage.info('请完善信息')
  }else{
    ElMessage.error('非法闯入！')
    router.push('/login')
  }
})

// 退出登录
const exitLogin = async () => {
  try{
    const res = await exitApi(typeof information.value.id === 'string' ? information.value.id : String(information.value.id))
    if(res.code){
      localStorage.removeItem('loginUser')
      ElMessage.success('退出登录成功')
      router.push('/login')
    }else{
      ElMessage.error(res.msg)
    }
  }catch(error){
    ElMessage.error('退出登录失败')
  }
}

// =================用户选择===================
const okType = ref('') //选择的用户类型

const back = () => {
  clear(okType.value)
  okType.value = ''
}
// 清空对应表单信息
const clear = (inputType) => {
  if (inputType == 'student') {
    stuMessage.value = {
      isNew: false,
      id: null,
      username: '',
      avatar: '',
      email: '',
      sex: null,
      age: null,
      type: 1,
      major: ''
    }
    stuRef.value?.resetFields()
  } else if (inputType == 'admin') {
    adminMessage.value = {
      isNew: true,
      id: null,
      username: '',
      avatar: '',
      email: '',
      remark: '',
      type: -3,
    }
    adminRef.value?.resetFields()
  }
}
// 选择学生
const chooseStudentType = () => {
  okType.value = 'student'
  stuMessage.value.id = information.value.id
  stuMessage.value.username = information.value.username
  stuMessage.value.email = information.value.email
  stuMessage.value.avatar = information.value.avatar
}
// 选择管理员
const chooseAdminType = () => {
  okType.value = 'admin'
  adminMessage.value.id = information.value.id
  adminMessage.value.usernam = information.value.usernam
  adminMessage.value.email = information.value.email
  adminMessage.value.avatar = information.value.avatar
}
// 选择其它
const chooseOtherType = () => {
  ElNotification({
    title: '温馨提示',
    message: '其它类型暂未开发，敬请谅解',
    type: 'primary',
    position: 'bottom-right',
  })
}

// =================头像上传===================
// 1. 上传前校验
const beforeAvatarUpload = (rawFile) => {
  const isJPGOrPNG = rawFile.type === 'image/jpeg' || rawFile.type === 'image/png';
  const isLt2M = rawFile.size / 1024 / 1024 < 2;

  if (!isJPGOrPNG) {
    ElMessage.error('头像只能是 JPG 或 PNG 格式!');
    return false;
  }
  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB!');
    return false;
  }
  return true;
}
// 2. 自定义上传方法 (对接后端接口)
const uploadAvatar = async (options) => {
  const { file } = options;
  // 创建 FormData 对象
  const formData = new FormData();
  formData.append('file', file);
  try {
    // 显示加载状态
    const loading = ElMessage({
      message: '正在上传头像...',
      type: 'info',
      duration: 0
    });

    // 发送请求到 /common/upload
    const result = await uploadAvatarApi(formData);

    loading.close();

    // 根据接口文档判断成功与否
    if (result.code === 1) {
      // 获取返回的图片路径
      const imageUrl = result.data;

      // 更新 avatar
      if (okType.value == 'student') {
        stuMessage.value.avatar = imageUrl;
      } else if (okType.value == 'admin') {
        adminMessage.value.avatar = imageUrl;
      }

      ElMessage.success('头像上传成功');
      console.log('头像URL:', imageUrl);
    } else {
      ElMessage.error(res.data.message || '上传失败');
    }

  } catch (error) {
    console.error('上传错误:', error);
    ElMessage.error('网络异常，上传失败');
  }
};
// 3. 移除头像
const removeAvatar = () => {
  if (okType.value === 'student') {
    stuMessage.value.avatar = '';
  } else if (okType.value === 'admin') {
    adminMessage.value.avatar = '';
  }
  ElMessage.info('头像已移除');
};

// =================管理员信息===================
const adminMessage = ref({
  // 唯一标识
  isNew: true,
  id: null,

  // ========== 1. 登录信息 ==========
  username: '', // 姓名
  avatar: '', // 头像
  email: '', // 邮箱
  remark: '', // 备注

  // ========== 2. 管理员信息 ==========
  type: -3, // 用户类型：0-管理员
})

// =================学生信息===================
const stuMessage = ref({
  // 固定标识
  isNew: false,
  id: null,
  // ========== 1. 基础身份信息（必填） ==========
  username: '', // 姓名
  avatar: '', // 头像
  email: '', // 邮箱
  sex: null, // 性别 0-女 1-男
  age: null,
  // ========== 2. 学业核心信息（个性化学习核心依据） ==========
  type: 1, // 用户类型：1-学生
  major: null, // 专业
  grade: null, // 年级
})

// =================表单规则及校验===================
const stuRef = ref('') // 学生表单校验信息
const adminRef = ref('') // 管理员表单校验信息
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
  major: [
    { required: true, message: '请输入专业', trigger: 'blur' },
    { min: 1, max: 20, message: '长度在 1 到 20 个字符', trigger: 'blur' }
  ],
  avatar: [
    { required: true, message: '请上传头像', trigger: 'change' }
  ],
  grade: [
    { required: true, message: '请选择年级', trigger: 'change' }
  ],
  remark: [
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' }
  ],
  age: [
    { required: true, message: '请输入年龄', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        // 1. 如果值为空，由 required 规则处理，这里直接通过，避免重复报错
        if (value === '' || value === null || value === undefined) {
          callback();
          return;
        }

        // 2. 确保转换为数字进行比较（防止字符串比较错误）
        const ageNum = Number(value);

        // 3. 校验是否合法数字
        if (isNaN(ageNum)) {
          callback(new Error('请输入有效的数字'));
          return;
        }

        // 4. 校验范围 (例如：1 到 150 岁)
        if (ageNum <= 0 || ageNum > 150) {
          callback(new Error('请输入正确的年龄范围(1-150)'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    },
  ],
})

// ==================提交===================
const submitting = ref(false) // 提交加载状态

const submit = async () => {
  if (okType.value === 'student') {
    if (!stuRef.value) return
    stuRef.value.validate(async valid => {
      if (!valid) return ElMessage.error('请检查输入内容')

      // 开启全屏加载
      submitting.value = true

      try {
        const content = `我叫${stuMessage.value.username}，性别${(stuMessage.value.sex == 0 ? '女' : '男')}，年龄${stuMessage.value.age}，专业是${stuMessage.value.major}，目前年级${GRADE_MAP[stuMessage.value.grade]}。`

        // ai对话
        const res = await postTextApi({
          userId: information.value.id,
          text: content,
          rsType: null
        })

        if (res.data.status !== 'need_more_info') {
          ElMessage.error('ai对话初始化失败，请稍后再试')
          submitting.value = false
          return
        }

        const result = await submitStuInfoApi(stuMessage.value)
        if (result.code) {
          ElMessage.success('提交成功')
          // 更新本地存储 (合并数据，防止字段丢失)
          const oldUser = JSON.parse(localStorage.getItem('loginUser') || '{}')
          const newUser = { ...oldUser, ...stuMessage.value }
          localStorage.setItem('loginUser', JSON.stringify(newUser))

          router.push('/aiAnswer')
        } else {
          ElMessage.error(result.msg)
        }
      } catch (error) {
        console.error('提交失败:', error)
        ElMessage.error('提交失败，请稍后重试')
      } finally {
        // 无论成功还是失败，都关闭加载
        submitting.value = false
      }
    })
  } else if (okType.value === 'admin') {
    if (!adminRef.value) return
    adminRef.value.validate(async valid => {
      if (!valid) return ElMessage.error('请检查输入内容')

      // 开启全屏加载
      submitting.value = true

      try {
        const result = await applyAdminApi(adminMessage.value)
        if (result.code) {
        ElMessage.success('申请已提交，注意查收邮箱信息')
        ElMessage.info('请耐心等待审核结果，请勿重复提交申请')
        localStorage.removeItem('loginUser')
        router.push('/login')
        } else {
          ElMessage.error(result.msg)
        }
      } catch (error) {
        console.error('提交失败:', error)
        ElMessage.error('提交失败，请稍后重试')
      } finally {
        submitting.value = false
      }
    })
  }
}



</script>

<template>
  <!-- 顶部导航栏 -->
  <div class="topNav">
    <div class="logo" title="知行优课">
      <img src="@/assets/logo/Logo.png" alt="知行优课logo" />
      <h1>知行优课</h1>
    </div>

    <div class="title">
      <h2>新用户基本信息完善</h2>
    </div>

    <div class="user">
      <!-- 头像 -->
      <div class="avatar">
        <el-avatar :src="loginAvatar">x</el-avatar>
      </div>
      <!-- 用户信息 -->
      <div class="username">
        <a href="javascript:void(0)">{{ loginName }}</a>
        <el-icon><arrow-down /></el-icon>
        <ul class="dropdown">
          <li><a href="javascript:void(0)" @click="exitLogin()">退出登录</a></li>
        </ul>
      </div>
    </div>
  </div>

  <div class="bottom">
    <!-- 用户类型选择 -->
    <Transition name="fade-slide" mode="out-in">
      <div class="type" v-if="!(okType)">
        <div class="title">
          <h2>请选择用户类型</h2>
          <p>系统将结合用户类型及其基本信息，选择合适的智能体为您服务</p>
        </div>
        <!-- 类型选择框 -->
        <div class="bigBox">
          <div class="left-type" @click="chooseStudentType()">
            <div class="intro">
              <h2>学生</h2>
            </div>
            <div class="svgicon">
              <svg t="1777968248587" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="28260" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="200"><path d="M78.605809 620.348548c25.493776 0 42.489627-16.995851 42.489627-42.489627V301.676349L257.062241 352.6639v135.966805c0 25.493776 16.995851 42.489627 46.738589 59.485478 12.746888 114.721992 106.224066 199.701245 216.697095 199.701244 110.473029 0 203.950207-89.228216 216.697096-199.701244 25.493776-12.746888 46.738589-33.991701 46.738589-59.485478V352.6639l186.954357-72.232365c16.995851-4.248963 25.493776-21.244813 25.493776-38.240664s-8.497925-33.991701-25.493776-38.240664L533.244813 4.248963c-12.746888-4.248963-25.493776-4.248963-33.991701 0L65.858921 203.950207c-21.244813 4.248963-29.742739 21.244813-29.742738 38.240664v335.66805c0 25.493776 16.995851 42.489627 42.489626 42.489627z m437.643154 42.489626c-55.236515 0-101.975104-38.240664-123.219917-89.228215 63.73444 12.746888 123.219917 12.746888 123.219917 12.746887s63.73444 0 123.219917-12.746887c-21.244813 50.987552-67.983402 89.228216-123.219917 89.228215z m178.456431-191.203319c-25.493776 12.746888-89.228216 29.742739-178.456431 29.742738s-152.962656-16.995851-178.456432-29.742738v-84.979253l161.460581 63.734439c4.248963 0 8.497925 4.248963 16.995851 4.248963s8.497925 0 16.99585-4.248963l161.460581-63.734439v84.979253z m-178.456431-378.157677l322.921161 144.464731-322.921161 123.219917-322.921162-123.219917 322.921162-144.464731zM996.381743 956.016598c-89.228216-127.46888-276.182573-208.19917-480.13278-208.199171S125.344398 828.547718 36.116183 956.016598c-12.746888 21.244813-8.497925 46.738589 8.497925 59.485477 21.244813 12.746888 46.738589 8.497925 59.485477-8.497926 72.232365-106.224066 233.692946-169.958506 412.149378-169.958506s339.917012 67.983402 412.149377 169.958506c8.497925 12.746888 21.244813 16.995851 33.991701 16.995851 8.497925 0 16.995851-4.248963 25.493776-8.497925 16.995851-12.746888 21.244813-42.489627 8.497926-59.485477z" fill="#374151" p-id="28261"></path></svg>
            </div>
          </div>

          <!-- 申请管理员 -->
          <div class="middle-type" @click="chooseAdminType()">
            <div class="intro">
              <h2>管理员</h2>
            </div>
            <div class="svgicon">
              <svg t="1777967719671" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="21769" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="200"><path d="M315.392 507.904c-81.92-40.96-137.216-122.88-137.216-221.184 0-135.168 110.592-245.76 245.76-245.76s245.76 110.592 245.76 245.76c0 133.12-104.448 241.664-237.568 245.76h-2.048c-202.752 0-368.64 165.888-368.64 368.64 0 12.288-8.192 20.48-20.48 20.48s-20.48-8.192-20.48-20.48c0-186.368 124.928-344.064 294.912-393.216z m108.544-16.384c112.64 0 204.8-92.16 204.8-204.8s-92.16-204.8-204.8-204.8-204.8 92.16-204.8 204.8 92.16 204.8 204.8 204.8z m561.152 135.168l4.096 10.24-49.152 59.392c-8.192 10.24-8.192 26.624 0 36.864l49.152 57.344-4.096 10.24c-10.24 28.672-24.576 57.344-45.056 79.872l-8.192 8.192-75.776-12.288c-12.288-2.048-26.624 6.144-30.72 18.432l-26.624 73.728-10.24 2.048c-38.912 8.192-77.824 8.192-116.736 0l-12.288-2.048-24.576-71.68c-4.096-12.288-18.432-20.48-30.72-18.432l-77.824 12.288-8.192-8.192c-10.24-10.24-18.432-22.528-24.576-34.816-8.192-14.336-16.384-30.72-20.48-47.104l-4.096-10.24 51.2-57.344c8.192-10.24 8.192-26.624 0-34.816l-49.152-59.392 4.096-10.24c10.24-30.72 26.624-57.344 47.104-81.92l8.192-8.192 73.728 12.288c12.288 2.048 26.624-6.144 32.768-18.432l26.624-71.68 10.24-2.048c36.864-8.192 75.776-8.192 114.688 0l12.288 2.048 24.576 69.632c4.096 12.288 18.432 22.528 32.768 20.48l75.776-10.24 8.192 8.192c10.24 12.288 18.432 22.528 24.576 36.864 6.144 10.24 12.288 26.624 18.432 40.96z m-57.344-24.576c-4.096-8.192-8.192-14.336-14.336-22.528l-53.248 6.144c-32.768 4.096-65.536-16.384-75.776-47.104l-16.384-47.104c-24.576-4.096-49.152-4.096-73.728 0l-18.432 49.152c-10.24 30.72-45.056 51.2-77.824 45.056l-51.2-8.192c-12.288 14.336-20.48 32.768-28.672 49.152l34.816 40.96c20.48 24.576 20.48 63.488 0 88.064l-34.816 40.96c4.096 10.24 8.192 18.432 14.336 28.672 4.096 8.192 8.192 14.336 14.336 20.48l55.296-8.192c32.768-4.096 65.536 16.384 75.776 47.104l16.384 49.152c24.576 4.096 51.2 4.096 75.776 0l18.432-51.2c10.24-30.72 45.056-51.2 75.776-45.056l51.2 8.192c10.24-14.336 20.48-30.72 26.624-49.152l-32.768-38.912c-20.48-24.576-22.528-63.488-2.048-88.064l34.816-40.96c-4.096-8.192-8.192-16.384-14.336-26.624z m-196.608 204.8c-51.2 0-92.16-40.96-92.16-92.16s40.96-92.16 92.16-92.16 92.16 40.96 92.16 92.16-43.008 92.16-92.16 92.16z m0-40.96c28.672 0 51.2-22.528 51.2-51.2s-22.528-51.2-51.2-51.2-51.2 22.528-51.2 51.2 22.528 51.2 51.2 51.2z" fill="#4A4A4A" p-id="21770" data-spm-anchor-id="a313x.search_index.0.i20.7d803a81WhKnsX" class="selected"></path></svg>
            </div>
          </div>

          <div class="right-type" @click="chooseOtherType()">
            <div class="intro">
              <h2>其它</h2>
            </div>
            <div class="svgicon">
              <svg t="1777966077607" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="15651" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="200"><path d="M516.05504 555.33568c-23.4496 0-46.91968-5.2224-68.77184-15.6672L118.96832 382.7712c-24.04352-11.48928-38.97344-35.18464-38.97344-61.82912s14.92992-50.33984 38.99392-61.82912L447.2832 102.1952c43.70432-20.8896 93.83936-20.8896 137.54368 0l328.31488 156.89728c24.04352 11.48928 38.97344 35.18464 38.97344 61.82912s-14.92992 50.33984-38.99392 61.82912L584.8064 539.648c-21.83168 10.46528-45.30176 15.68768-68.75136 15.68768zM179.56864 320.9216l303.04256 144.83456c21.25824 10.15808 45.62944 10.15808 66.88768 0l303.04256-144.83456-303.04256-144.81408c-21.25824-10.15808-45.62944-10.15808-66.88768 0L179.56864 320.9216z" fill="#231815" p-id="15652"></path><path d="M516.05504 751.26784c-20.04992 0-40.07936-4.46464-58.73664-13.37344L103.85408 568.95488c-20.41856-9.74848-29.04064-34.2016-19.29216-54.62016 9.74848-20.41856 34.2016-29.04064 54.62016-19.29216l353.44384 168.91904c14.88896 7.10656 31.9488 7.10656 46.83776 0L892.928 495.04256c20.41856-9.74848 44.87168-1.10592 54.62016 19.29216 9.74848 20.41856 1.10592 44.87168-19.29216 54.62016l-353.44384 168.91904c-18.67776 8.92928-38.72768 13.39392-58.75712 13.39392z" fill="#231815" p-id="15653"></path><path d="M516.05504 944.68096c-20.04992 0-40.07936-4.46464-58.73664-13.37344L103.85408 762.38848c-20.41856-9.74848-29.04064-34.2016-19.29216-54.62016 9.74848-20.41856 34.2016-29.04064 54.62016-19.29216l353.44384 168.91904c14.88896 7.10656 31.9488 7.10656 46.83776 0L892.928 688.47616c20.41856-9.74848 44.87168-1.10592 54.62016 19.29216 9.74848 20.41856 1.10592 44.87168-19.29216 54.62016l-353.44384 168.91904c-18.67776 8.9088-38.72768 13.37344-58.75712 13.37344z" fill="#231815" p-id="15654"></path></svg>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 内容 -->
    <!-- 学生 -->
    <Transition name="fade-slide" mode="out-in">
      <div class="content" v-if="okType == 'student'">
        <div class="head" @click="back()">
          ◀ 返回
        </div>
        <div class="subTitle">
          <h2>学生基本信息完善</h2>
          <h3>请将基本信息完善信息（将会同步更新），以便于系统初始化</h3>
        </div>
        <div class="container">
          <el-form :model="stuMessage" label-position="left" :rules="rules" ref="stuRef" label-width="80px">

            <!-- 头像 -->
            <el-form-item label="头像" prop="avatar">
              <div class="avatarPart">
                <el-upload class="avatar-uploader" action="#" :show-file-list="false" :before-upload="beforeAvatarUpload" :http-request="uploadAvatar">
                  <img v-if="stuMessage.avatar" :src="stuMessage.avatar" class="imgAvatar" />
                  <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
                </el-upload>
                <div class="avatar-controls" v-if="stuMessage.avatar">
                  <el-button type="danger" size="small" @click="removeAvatar">移除头像</el-button>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="用户名" prop="username">
              <el-input v-model="stuMessage.username" placeholder="请输入用户名" size="large" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="stuMessage.email" placeholder="请输入邮箱" disabled size="large" />
            </el-form-item>
            <el-form-item label="性别" prop="sex">
              <el-select placement="right" popper-style='text-align: center' placeholder="请选择您的性别" v-model="stuMessage.sex" size="large">
                <el-option label="男" value="1" />
                <el-option label="女" value="0" />
              </el-select>
            </el-form-item>
            <el-form-item label="年龄" prop="age">
              <el-input v-model="stuMessage.age" placeholder="请输入年龄" size="large" />
            </el-form-item>
            <el-form-item label="年级" prop="grade">
              <el-select placement="right" popper-style='text-align: center' placeholder="请选择您的年级" v-model="stuMessage.grade" size="large">
                <el-option label="大一" value="1" />
                <el-option label="大二" value="2" />
                <el-option label="大三" value="3" />
                <el-option label="大四" value="4" />
              </el-select>
            </el-form-item>
            <el-form-item label="专业" prop="major">
              <el-input v-model="stuMessage.major" placeholder="请输入专业名称" size="large" />
            </el-form-item>
          </el-form>

          <div class="btnPart">
            <el-button class="subBtn" type="primary" size="large" @click="submit" :loading="submitting">提交</el-button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 管理员 -->
    <Transition name="fade-slide" mode="out-in">
      <div class="content" v-if="okType == 'admin'">
        <div class="head" @click="back()">
          ◀ 返回
        </div>
        <div class="subTitle">
          <h2>申请成为管理员</h2>
          <h3>请填写申请信息（头像和用户名将会同步更新），管理员审核通过后，即可成为管理员</h3>
        </div>
        <div class="container">
          <el-form :model="adminMessage" label-position="left" :rules="rules" ref="adminRef" label-width="80px">
            <!-- 头像 -->
            <el-form-item label="头像">
              <div class="avatarPart">
                <el-upload class="avatar-uploader" action="#" :show-file-list="false" :before-upload="beforeAvatarUpload" :http-request="uploadAvatar">
                  <img v-if="adminMessage.avatar" :src="adminMessage.avatar" class="imgAvatar" />
                  <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
                </el-upload>
                <div class="avatar-controls" v-if="adminMessage.avatar">
                  <el-button type="danger" size="small" @click="removeAvatar">移除头像</el-button>
                </div>
              </div>
            </el-form-item>

            <el-form-item label="用户名" prop="username">
              <el-input v-model="adminMessage.username" placeholder="请输入您的用户名" size="large" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="adminMessage.email" placeholder="请输入邮箱" size="large" disabled />
            </el-form-item>
            <el-form-item label="申请理由" prop="remark">
              <el-mention size="large" v-model="adminMessage.remark" type="textarea" style="width: 100%" placeholder="请输入申请理由" />
            </el-form-item>

            <div class="btnPart">
              <el-button class="subBtn" type="primary" size="large" @click="submit" :loading="submitting">提交申请</el-button>
            </div>
          </el-form>
        </div>
      </div>
    </Transition>
  </div>

  <!-- 全屏加载遮罩 -->
  <transition name="fade">
    <div v-if="submitting" class="fullscreen-loading">
      <div class="loading-content">
        <el-icon class="loading-icon" :size="50">
          <Loading />
        </el-icon>
        <p class="loading-text">正在提交数据，请稍候...</p>
        <div class="loading-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
/* 所有文字不可被光标选中 */
* {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
/* ================= 页面过渡动画样式 ================= */

/* 1. 定义进入和离开的起始/结束状态 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.5s ease-in-out;
}

/* 2. 进入前状态 (透明 + 稍微向下偏移 + 轻微缩小) */
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
}

/* 3. 离开后状态 (透明 + 稍微向上偏移 + 轻微缩小) */
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.98);
}

/* 4. 确保绝对定位的元素在过渡期间保持布局稳定 */
/* 如果 .type 是 absolute，可能需要给父容器 .bottom 设置 min-height 防止塌陷 */
.bottom {
  position: relative;
  min-height: 80vh;
  /* 确保底部容器有高度 */
}
/* 可选：为了让内容切换更平滑，确保 content 也有类似的过渡 */
.content {
  /* 保持原有的 padding 等样式 */
  padding: 0 100px;
  /* 确保内容区域也是相对定位或具有明确高度 */
  position: relative;
  z-index: 10;
  /* 确保内容在 type 消失后能正常显示 */
}

/* ======================顶部导航栏==================== */
ul,
li {
  margin: 0;
  padding: 0;
  list-style: none;
}
/* 顶部导航栏 */
.topNav {
  z-index: 100;
  min-width: 1200px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 100px;
  height: 60px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  transition: all 0.3s ease-in-out;
}
.topNav .title h2 {
  font-size: 25px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
}
/* logo部分 */
.logo {
  width: 200px;
  gap: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo:hover {
  cursor: pointer;
}
.logo img {
  width: 70px;
  height: 70px;
  margin-left: 3px;
}

.logo h1 {
  color: var(--text-title);
  font-size: 25px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

/* 用户信息 */
.user {
  width: 200px;
  display: flex;
  align-items: center;
  gap: 5px;
}
/* 用户区域 */
/* 头像 */
.user .avatar {
  margin-right: 10px;
  padding-top: 7px;
}
/* 用户信息 */
.username {
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}
.username a {
  color: var(--text-body);
}
.username:hover>a,
.username:hover .el-icon,
.mes:hover .el-icon {
  color: var(--primary);
  text-decoration: none;
}
/* 下拉菜单 */
.dropdown {
  min-width: 100px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border: 1.5px solid var(--border-color);
  border-radius: 8px;
  position: absolute;
  top: 100%;
  /* 确保位于触发元素正下方 */
  right: -10px;
  margin-top: 8px;
  opacity: 0;
  visibility: hidden;
  /* 动画效果：淡入 + 轻微上浮 */
  transform: translateY(-10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  /* 确保层级足够高 */
  overflow: hidden;
  /* 防止圆角溢出 */
}
.dropdown li a {
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  width: 100%;
  height: 40px;
  color: var(--text-body);
  font-size: 14px;
}
.dropdown li a:hover {
  background-color: var(--primary-light);
  color: var(--primary);

}
/* 显示下拉菜单时的状态 */
.username:hover .dropdown {
  opacity: 1;
  visibility: visible;
  /* 确保动画效果 */
  transform: translateY(0);
}
.username .el-icon {
  transition: all 0.3s ease-in-out;
}
.username:hover .el-icon {
  /* 确保图标旋转 */
  transform: rotate(180deg);
}

/* =======================底部内容区======================= */
/* 底部 */
.bottom {
  min-width: 1200px;
  position: relative;
  width: 100%;
}
/* ======================选择类型页==================== */
/* 用户类型选择 */
.type {
  padding-top: 45px;
  z-index: 99;
  position: absolute;
  min-width: 1000px;
  width: 100%;
  height: 80vh;
  background-color: var(--bg-page);
}
.type .title {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  margin: 50px 0;
}
.type .title h2 {
  margin-bottom: 20px;
  font-size: 60px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
}
.type .bigBox {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;
}

.type .left-type,
.type .middle-type,
.type .right-type {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 400px;
  height: 400px;
  border: 1.5px solid var(--border-color);
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border-radius: 12px;
  transition: all 0.3s ease-in-out;
}

.type .intro {
  display: flex;
  justify-content: center;
  width: 100%;
  height: 100px;
}
.type .intro h2 {
  font-size: 50px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

.type .svgicon {
  width: 200px;
  height: 200px;
}

.type .svgicon svg {
  /* 描边颜色 */
  stroke: var(--text-body);
  /* 描边宽度，可根据需要调整 */
  stroke-width: 8;
  transition: all 0.3s ease-in-out;
}

/* 强制覆盖 path 的填充，防止 SVG 内部属性干扰 */
.type .svgicon svg path {
  fill: none !important;
  transition: stroke-dashoffset 1s ease-in-out;
  /* 平滑过渡 */
}

.type div[class$=type]:hover .svgicon svg path {
  stroke: var(--primary);
}

.type div[class$=type]:hover {
  cursor: pointer;
  background-color: var(--primary-light);
  color: var(--primary);
  /* svg图标的缩放效果 */
  transform: scale(1.05);
  /* svg 图标的动画效果 */
  animation: move .5s;
}
@keyframes move {
  0% {
    stroke-dasharray: 50 300;
  }
  100% {
    stroke-dasharray: 300 0;
  }
}


/* ======================用户信息页==================== */
.content .head {
  width: 100px;
  height: 30px;
  /* border: 1px solid red; */
  font-size: 20px;
  color: var(--text-body);
  line-height: 30px;
}
.content .head:hover {
  cursor: pointer;
  color: var(--primary);
}
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 1000px;
  width: 100%;
  height: 80vh;
  padding-top: 40px;
  /* border: 1px solid red; */
}

/* =========管理员========= */


/* ================= 头像上传样式 ================= */
.avatarPart {
  width: 124px;
  height: 186px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
}

.avatar-uploader .imgAvatar {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--text-gray);
}

.avatar-uploader .el-upload {
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-uploader .el-upload:hover {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 50px;
  color: var(--primary);
}
:deep(.avatar-uploader .el-icon) {
  width: 124px;
  height: 186px;
  border-radius: 10px;
  border: 2px dashed var(--primary);
}
:deep(.avatar-uploader .el-icon:hover) {
  color: var(--primary-hv);
}
.avatar-controls {
  margin-top: 10px;
}
/* ================= 表单样式 ================= */
:deep(.el-button--primary) {
  --el-button-bg-color: var(--primary);
  --el-button-border-color: var(--primary);

  --el-button-hover-bg-color: var(--primary-hv);
  --el-button-hover-border-color: var(--primary-hv);

  --el-button-active-color: var(--primary-act);
  --el-button-active-bg-color: var(--primary-act);
  --el-button-active-border-color: var(--primary-act);

  --el-button-disabled-bg-color: var(--primary-disa-bgc);
  --el-button-disabled-border-color: var(--primary-disa-border);
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}


.btnPart {
  margin-top: 20px;
  width: 300px;
}
.btnPart .el-button {
  width: 300px;
}

/* 学生/管理员页标题 */
.subTitle {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.subTitle h2 {
  font-size: 40px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}
.subTitle h3 {
  font-size: 18px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

/* ================= 全屏加载样式 ================= */
.fullscreen-loading {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(5px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 40px 60px;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  min-width: 280px;
}

.loading-icon {
  color: var(--primary);
  animation: spin 1s linear infinite;
}

.loading-text {
  color: var(--text-title);
  font-size: 18px;
  font-weight: 500;
  margin: 0;
}

/* 三个点的加载动画 */
.loading-dots {
  display: flex;
  gap: 8px;
}

.loading-dots span {
  width: 10px;
  height: 10px;
  background-color: var(--primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0s;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* 淡入淡出过渡 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>