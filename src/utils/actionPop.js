// src/utils/actionPop.js
// 全局弹窗：hover行为
//Pinia 状态文件
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage, ElMessageBox, ElNotification, ElButton } from 'element-plus'
import { collectApi, shareApi, studyTogetherApi } from '@/api/mainApi/pop.js'// 弹窗接口
import { partnersListApi } from '@/api/mainApi/partners.js'//获取学伴列表
import { getUserInfoApi } from '@/api/mainApi/index.js'//获取用户信息

// 为所传数组/对象加username,avatar字段
const userIdInfo = ref({ userIdList: [] })
const addUserInfo = async (arr) => {
  // 兼容单个对象{} 或 数组[]
  let list = Array.isArray(arr) ? arr : [arr];
  //把arr中所有user_id取出，保存在数组中，不重复
  const userIdList = [...new Set(list.map(item => item.user_id))]
  userIdInfo.value.userIdList = userIdList
  //把userIdList传给getUserInfoApi接口
  try {
    const res = await getUserInfoApi(userIdInfo.value)
    if (res.code) {
      const userMap = {}
      res.data.forEach(u => {
        userMap[u.userId] = u
      })
      // 直接修改原对象/原数组里的对象，无返回
      list.forEach(item => {
        const user = userMap[item.user_id]
        if (user) {
          item.username = user.username
          item.avatar = user.avatar
        }
      })
    }

  } catch (e) {
    console.error('获取用户信息失败：', e)
  }
}


export const useActionPopStore = defineStore('actionPop', {
  state: () => ({
    popVisible: false,
    popLeft: 0,
    popTop: 0,
    currentData: null,
    timer: null,

    shareConfirmVisible: false,
    partnerListVisible: false,
    postCommunityVisible: false,
    studyInviteVisible: false,

    partnerList: []
  }),

  actions: {
    showPop(left, top, data) {
      this.clearTimer()
      this.popLeft = left
      this.popTop = top

      // ✅ 确保 data 是有效对象
      if (data && typeof data === 'object') {
        this.currentData = data
        this.popVisible = true
        console.log('✅ 显示弹窗:', this.currentData)
      } else {
        console.warn('⚠️ showPop 接收到无效数据:', data)
        this.currentData = null
        this.popVisible = false
      }
    },

    delayHidePop() {
      this.clearTimer()
      this.timer = setTimeout(() => {
        this.popVisible = false
        // ⚠️ 不要在这里清空 currentData
      }, 200)
    },

    clearTimer() {
      if (this.timer) {
        clearTimeout(this.timer)
        this.timer = null
      }
    },

    // ✅ 辅助方法：安全获取数据
    getCurrentData() {
      return this.currentData
    },

    // ✅ 辅助方法：安全获取 ID
    getCurrentId() {
      return this.currentData?.id ?? null
    },

    // ✅ 修复 handleCollect (收藏)
    async handleCollect() {
      console.log('📌 收藏操作 - currentData:', this.currentData)

      // 防御性检查
      if (!this.currentData) {
        console.warn('⚠️ 无法收藏：currentData 为空')
        this.popVisible = false
        return
      }


      console.log('✅ userId:', this.currentData.userId)
      console.log('✅ 收藏条目 rsId:', this.currentData.rsId, '类型：', this.currentData.rsType)

      // 收藏逻辑
      try {
        const res = await collectApi({
          userId: this.currentData.userId,
          resourceType: this.currentData.rsType,
          resourceId: this.currentData.rsId
        })
        if (res.code) {
          ElMessage.success(res.data.message)
        } else {
          ElMessage.error(res.data.message)
        }

      } catch (error) {
        console.error('请求收藏失败：', error)
        ElMessage.error('请求收藏失败')
      }

      // 先关闭弹窗
      this.popVisible = false

    },

    // ✅ 修复 openShareConfirm（分享到社区）
    openShareConfirm() {
      if (!this.currentData) {
        console.warn('⚠️ 无法分享：currentData 为空')
        this.popVisible = false
        return
      }

      console.log('📌 打开分享确认 - rsId:', this.currentData.rsId)
      this.popVisible = false
      this.shareConfirmVisible = true
    },
    closeShareConfirm(choose) {
      this.shareConfirmVisible = false

      if (this.currentData) {
        console.log('📌 确认分享给社区 - rsId:', this.currentData.rsId)

        if (choose) {
          console.log('✅ 用户选择了分享')
          shareApi({
            sharer_id: this.currentData.userId,
            receiver_id: '__community__',
            resource_type: this.currentData.rsType,
            resource_id: this.currentData.rsId
          })
            .then(function (res) {
              if (res.code) {
                ElMessage.success(res.data.message);
              } else {
                ElMessage.error(res.data.message);
              }
            })
            .catch(function (error) {
              console.error('请求分享失败：', error);
              ElMessage.error('请求分享失败');
            });
        } else {
          console.log('取消分享')
        }
      }

    },

    // ✅ 修复 openPartnerList(分享给学伴列表查询)
    async openPartnerList() {
      if (!this.currentData) {
        console.warn('⚠️ 无法分享给学伴：currentData 为空')
        this.popVisible = false
        return
      }

      console.log('📌 打开学伴列表 - 分享rsId:', this.currentData.rsId)
      try {
        const res = await partnersListApi(this.currentData.userId)
        if (res.code) {
          console.log('✅ 获取学伴列表成功')
          this.partnerList = res.data.companions
          addUserInfo(this.partnerList)
          console.log('学伴列表:', this.partnerList)
        }
      } catch (error) {
        console.error('请求学伴列表失败：', error)
        ElMessage.error('请求学伴列表失败')
      }
      this.popVisible = false
      this.partnerListVisible = true
    },

    closePartnerList() {
      this.partnerListVisible = false
      this.partnerList = []
    },

    // ✅ 修复 shareToPartner(分享给学伴具体分享逻辑)
    shareToPartner(partnerId) {
      if (!this.currentData) {
        console.warn('⚠️ 无法分享给学伴：currentData 为空')
        this.closePartnerList()
        return
      }

      console.log('📌 分享给学伴:', partnerId, '条目 rsId:', this.currentData.rsId, '类型：', this.currentData.rsType)
      ElMessageBox.confirm('确认要分享吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => {
        shareApi({
          sharer_id: this.currentData.userId,
          receiver_id: partnerId,
          resource_type: this.currentData.rsType,
          resource_id: this.currentData.rsId
        })
          .then(function (res) {
            if (res.code) {
              ElMessage.success(res.data.message);
            } else {
              ElMessage.error(res.data.message);
            }
          })
          .catch(function (error) {
            console.error('请求分享失败：', error);
            ElMessage.error('请求分享失败');
          });
      })
      this.closePartnerList()

    },

    // ✅ 修复 openPostCommunity
    openPostCommunity() {
      if (!this.currentData) {
        console.warn('⚠️ 无法发帖：currentData 为空')
        this.popVisible = false
        return
      }

      console.log('📌 发帖到社区 - rsId:', this.currentData.rsId, '类型：', this.currentData.rsType)
      this.popVisible = false
      this.postCommunityVisible = true
    },

    closePostCommunity() {
      this.postCommunityVisible = false
    },

    // ✅ 修复 openStudyInvite(共学的学伴列表查询)
    async openStudyInvite() {
      if (!this.currentData) {
        console.warn('⚠️ 无法发起邀请：currentData 为空')
        this.popVisible = false
        return
      }

      console.log('📌 打开学伴列表 - 分享rsId:', this.currentData.rsId)
      try {
        const res = await partnersListApi(this.currentData.userId)
        if (res.code) {
          console.log('✅ 获取学伴列表成功')
          this.partnerList = res.data.companions
          addUserInfo(this.partnerList)
          console.log('学伴列表:', this.partnerList)
        }
      } catch (error) {
        console.error('请求学伴列表失败：', error)
        ElMessage.error('请求学伴列表失败')
      }
      this.popVisible = false
      this.studyInviteVisible = true

    },

    closeStudyInvite() {
      this.studyInviteVisible = false
      this.partnerList = []
    },

    // ✅ 修复 studyToPartner(共学发送邀请具体逻辑)
    studyToPartner(partnerId, mode = 'separate') {
      if (!this.currentData) {
        console.warn('⚠️ 无法分享给学伴：currentData 为空')
        this.closePartnerList()
        return
      }

      console.log('📌 分享给学伴:', partnerId, '条目 rsId:', this.currentData.rsId, '类型：', this.currentData.rsType)
      ElMessageBox.confirm('确认要发送邀请吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => {
        // 发送邀请
        studyTogetherApi({
          inviterId: this.currentData.userId,
          inviteeId: partnerId,
          resourceType: this.currentData.rsType,
          resourceId: this.currentData.rsId,
          mode: mode
        })
          .then(function (res) {
            // 提示
            if (res.code) {
              ElMessage.success(res.data.message);
            } else {
              ElMessage.error(res.data.message);
            }
          })
          .catch(function (error) {
            console.error('请求发送失败：', error);
            ElMessage.error('请求发送失败');
          });
      })
      this.closePartnerList()
      this.studyInviteVisible = false

    },

    resetAll() {
      this.clearTimer()
      this.popVisible = false
      this.popLeft = 0
      this.popTop = 0
      this.currentData = null
      this.shareConfirmVisible = false
      this.partnerListVisible = false
      this.postCommunityVisible = false
      this.studyInviteVisible = false
    }
  }
})