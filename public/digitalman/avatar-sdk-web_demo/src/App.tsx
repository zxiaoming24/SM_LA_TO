import { useEffect, useRef, useState } from 'react'
import './App.css'
import {
  Button,
  ColorPicker,
  Divider,
  Drawer,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Slider,
  Space,
  Spin,
  Switch,
  message,
} from 'antd'
import { useForm } from 'antd/es/form/Form.js'
// import { PlayerEvents, SDKEvents } from './lib/enums/events'
// import AvatarPlatform from './lib/core'
import cloneDeep from 'lodash/cloneDeep'
import AvatarPlatform, {
  PlayerEvents,
  SDKEvents,
} from './testSdk/3.1.2.1002/avatar-sdk-web_3.1.2.1002/index.js'

const InitAppInfo = {
  serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
  // serverUrl: 'wss://test.xfyousheng.com/apigateway/avatar_ray/v1/avatar',
  // serverUrl: 'wss://test.xfyousheng.com/apigateway/avatar/v1/avatar',
  // 以下信息为交互平台 创建接口服务 后 服务项目页面获取
  // appId: '',
  // apiKey: '',
  // apiSecret: '',
  // sceneId: '',
  appId: 'fe897b77',
  apiKey: '3a29b78e4acda78488bd09220d8f1b98',
  apiSecret: 'YmY4YTViN2Y5MDY1MjUyOGQxMGU2NTY3',
  sceneId: '325229986007093248',
}

const avatarOptions = [
  { value: '111192001', label: '诸葛亮' },
  { value: '111181002', label: '医生' },
  { value: '111227001', label: '西施' },
]

const voiceOptions = [
  { value: 'x4_yuexiaoni_assist', label: '月小妮助手' },
  { value: 'x4_chaoge', label: '超哥' },
  { value: 'x4_lingxiaoyue_oral', label: '聆小媛' },
]

const backgroundOptions = [
  { value: '', label: '默认' },
  { value: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/1699420292376169.png', label: '荒漠' },
  { value: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/d391b27fbc2fce203c65437ad280ada130f684ca24f89-W9M5GP_fw658.webp', label: '天晴' },
  { value: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/dealshubanshuiwenbolanghuawen202311220061.png', label: '海洋' },
  { value: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/dealshubanxiangyunguochao202311240181.png', label: '中国红' },
]
function App() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [loglevel, setLoglevel] = useState(0)
  const [loading, setLoading] = useState(false)
  const [isStarted, setIsStarted] = useState(false)
  const [initForm] = useForm()
  const [apiInfoForm] = useForm()
  const [avatarConfigForm] = useForm()
  const [startAvatarForm] = useForm()
  const [textDriverForm] = useForm()
  const [audioDriverForm] = useForm()
  const [actionDriverForm] = useForm()
  const [quickStartForm] = useForm()

  const [subtitle, setSubtitle] = useState('')
  const interativeRef = useRef<any>(null)

  // ★★★ Agent 对话状态 ★★★
  const [agentInput, setAgentInput] = useState('')
  const [agentUserId, setAgentUserId] = useState('user_001')
  const [agentServerUrl, setAgentServerUrl] = useState('/api')
  const [agentChatLoading, setAgentChatLoading] = useState(false)
  const [agentConversation, setAgentConversation] = useState<{ role: string; text: string }[]>([])
  const extractedInfoRef = useRef<any>(null)
  const voiceIdRef = useRef('x4_yuexiaoni_assist')
  const [isSpeaking, setIsSpeaking] = useState(false)
  useEffect(() => {
    return () => {
      interativeRef.current?.stop()
    }
  }, [])

  const InitSDK = () => {
    try {
      let interative = interativeRef.current
      if (!interative) {
        interativeRef.current = interative = new (AvatarPlatform as any)({
          ...initForm.getFieldsValue(),
        })
        // 初始化后自动设置 API 凭据
        interativeRef.current.setApiInfo({
          serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
          appId: 'fe897b77',
          apiKey: '3a29b78e4acda78488bd09220d8f1b98',
          apiSecret: 'YmY4YTViN2Y5MDY1MjUyOGQxMGU2NTY3',
          sceneId: '325229986007093248',
        })
        message.success('初始化成功 凭据已自动配置 可以直接 start')
      } else {
        message.warning('请勿多次初始化 或先销毁当前实例')
      }
    } catch (e: any) {
      console.error(e)
      message.error('初始化失败' + e?.message)
    }
  }
  const bindInteractEvent = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    interativeRef.current.removeAllListeners()
    interativeRef.current
      .on(SDKEvents.connected, (initResp: any) => {
        console.log('sdk event: connected', initResp)
      })
      .on(SDKEvents.stream_start, () => {
        console.log('sdk event: stream_start')
      })
      .on(SDKEvents.disconnected, (e: any) => {
        setLoading(false)
        console.log('sdk event: disconnected')
        if (e) {
          message.error('ws link disconnected')
          console.error(e.code, e.message, e.name, e.stack)
        }
      })
      .on(SDKEvents.asr, (asrData: any) => {
        console.log('sdk event: asr', asrData)
      })
      .on(SDKEvents.nlp, (nlpData: any) => {
        console.log('sdk event: nlp', nlpData)
      })
      .on(SDKEvents.frame_start, (frameData: any) => {
        console.log('sdk event: frameBegin', frameData)
      })
      .on(SDKEvents.frame_stop, (frameData: any) => {
        console.log('sdk event: frameEnd', frameData)
      })
      .on(SDKEvents.action_start, (actionData: any) => {
        console.log('sdk event: actionBegin', actionData)
      })
      .on(SDKEvents.action_stop, (actionData: any) => {
        console.log('sdk event: actionEnd', actionData)
      })
      .on(SDKEvents.stream_start, () => {
        console.log('sdk event: stream_start')
        setIsSpeaking(true)
      })
      .on(SDKEvents.tts_duration, (sessionData: any) => {
        console.log('sdk event: duration', sessionData)
      })
      .on(SDKEvents.subtitle_info, (subtitleData: any) => {
        console.log('sdk event: subtitle', subtitleData)
        setSubtitle(subtitleData?.text || '')
        if (!subtitleData?.text) {
          setIsSpeaking(false)
        }
      })
      .on(SDKEvents.error, (error: any) => {
        console.log('sdk event: error', error)
      })

    message.success(
      'SDK 交互事件监听绑定成功 可以打开控制台 查看事件日志 [sdk event:]'
    )
  }
  const UnInitSDK = () => {
    interativeRef.current?.destroy()
    interativeRef.current = undefined

    message.success('UnInitSDK成功')
  }
  const getPlayer = () => {
    const player = interativeRef.current.player
    console.log('player', player)
  }
  const createPlayer = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    const player =
      interativeRef.current.player || interativeRef.current.createPlayer()
    console.log('player', player)
    return player
  }
  const bindPlayerEvent = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    const player = interativeRef.current.player
    if (!player) {
      return message.warning('当前不存在player 实例 请调用create 创建')
    }
    player.removeAllListeners()
    player
      .on(PlayerEvents.error /* "error" */, (err: any) => {
        console.log('sdk player event: player error', err)
        if (err?.code === '700005') {
          // 不支持h264
          console.log('sdk player event: player h264 not supported')
        }
      })
      ?.on(PlayerEvents.play, () => {
        console.log('sdk player event: player play')
      })
      .on(PlayerEvents.waiting, () => {
        console.log('sdk player event: player waiting')
      })
      .on(PlayerEvents.playing, () => {
        console.log('sdk player event: player playing')
      })
      .on(PlayerEvents.playNotAllowed, () => {
        console.log(
          'sdk player event: play not allowed, muted play， player call resume after user gusture'
        )
      })

    message.success(
      'SDK Player 事件监听绑定成功 可以打开控制台 查看事件日志 [sdk player event:]'
    )
  }
  const setApiInfo = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    interativeRef.current.setApiInfo({
      ...apiInfoForm.getFieldsValue(),
    })

    message.success('Api 服务信息设置成功 ')
  }
  const setGlobalParams = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    const fcolor = avatarConfigForm.getFieldsValue().subtitle.font_color
    const subtitle_font_color =
      Object.prototype.toString.call(fcolor) === '[object String]'
        ? fcolor
        : fcolor?.toHexString?.()
    const values = cloneDeep(avatarConfigForm.getFieldsValue())

    if (values.avatar.mask_region) {
      values.avatar.mask_region = JSON.parse(values.avatar.mask_region)
    } else {
      delete values.avatar.mask_region
    }
    if (!values.subtitle?.subtitle) {
      delete values.subtitle
    }
    if (!values.background?.enabled) {
      delete values.background
    } else {
      delete values.background.enabled
    }
    if (values.subtitle) {
      values.subtitle.width = values.avatar.width
      values.subtitle.font_color = subtitle_font_color
    }
    interativeRef.current.setGlobalParams({
      ...values,
    })
    message.success('全局 start 信息 设置成功 服务信息设置成功 ')
  }

  const startAvatar = async () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }

    const fcolor = avatarConfigForm.getFieldsValue().subtitle.font_color
    const subtitle_font_color =
      Object.prototype.toString.call(fcolor) === '[object String]'
        ? fcolor
        : fcolor?.toHexString?.()
    const avatarValues = cloneDeep(avatarConfigForm.getFieldsValue())

    if (avatarValues.avatar.mask_region) {
      avatarValues.avatar.mask_region = JSON.parse(avatarValues.avatar.mask_region)
    } else {
      delete avatarValues.avatar.mask_region
    }
    if (!avatarValues.subtitle?.subtitle) {
      delete avatarValues.subtitle
    }
    if (!avatarValues.background?.enabled) {
      delete avatarValues.background
    } else {
      delete avatarValues.background.enabled
    }
    if (avatarValues.subtitle) {
      avatarValues.subtitle.width = avatarValues.avatar.width
      avatarValues.subtitle.font_color = subtitle_font_color
    }

    await interativeRef.current.setGlobalParams({
      ...avatarValues,
    })

    const values = startAvatarForm.getFieldsValue()
    setLoading(true)
    await interativeRef.current
      ?.start({
        wrapper: document.querySelector(
          '.' + values.container
        ) as HTMLDivElement,
        preRes: {
          image: [
            {
              url: '22SLM2teIw+aqR6Xsm2JbH6Ng310kDam2NiCY/RQ9n6s3nYJXloZWW1l64/g32vrn7d2lJQR7m9xD5EHYkVs1+bLdJQ42I5SCCMphdtQC/KdIR9lQZl6Ryymh/CEiDdSSRND1SuiX8pjrFjxk/WMtJ+pDS5JT7P/8c0lxcMB6+IjTLQvgz41Fdhb1/sAGtES7HCMZepV5nNwisTvd8PhztpmXX+lIS1LQcPHJy2HW4/XrrKKf4AI8nj2lbocKniDJDk5cQtsOjY7raVi6fSp/9Zmz0eVr0UXa/wA65nxXD+I6VF6TxI1Er4wvKVTlpItpT2RDIDaanYWDZ3hyMDupH4MJcEev3sE9Tfl8tDtZ2c=',
            },
          ],
        },
      })
      .then(() => {
        console.warn('player fetch stream ed')
        message.success('连接成功 & 拉流订阅成功 & 流播放成功')
        setLoading(false)
        setIsStarted(true)

        const ttsConfig = avatarConfigForm.getFieldValue('tts')
        interativeRef.current
          .writeText('你好！我是你的数字人助手，请问有什么可以帮助你的吗？', {
            tts: ttsConfig,
          })
          .then((reqId: string) => {
            console.log(`自动欢迎语发送成功 request_id: ${reqId}`)
          })
          .catch((err: any) => {
            console.error('自动欢迎语发送失败:', err)
          })
      })
      .catch((e: any) => {
        message.error('连接失败，可以打开控制台查看信息')
        console.error(e.code, e.message, e.name, e.stack)
        setLoading(false)
      })
  }
  const driveAction = async () => {
    const { actionId } = actionDriverForm.getFieldsValue()
    if (!interativeRef.current) {
      return message.warning('请初始化sdk & 连接')
    }
    if (!actionId?.trim()) {
      return message.warning('请输入actionId')
    }
    interativeRef.current.writeCmd('action', actionId?.trim())
  }
  const writeText = async () => {
    const { text, tts, ...extend } = textDriverForm.getFieldsValue()
    if (!interativeRef.current) {
      return message.warning('请初始化sdk & 连接')
    }
    if (!text?.trim()) {
      return message.warning('请输入文本')
    }
    if (tts && !tts?.vcn) {
      delete tts.vcn
    }
    interativeRef.current
      .writeText(text, {
        tts,
        ...extend,
      })
      .then((reqId: string) => {
        message.success(`发送成功request_id: ${reqId}`)
      })
      .catch((err: any) => {
        console.error(err)
        message.error('发送失败，可以打开控制台查看信息')
      })
  }
  const interrupt = async () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk & 连接')
    }
    interativeRef.current.interrupt()
  }

  const startRecord = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk & 连接')
    }
    const { nlp, full_duplex, single_seconds } =
      audioDriverForm.getFieldsValue()

    const audio_format = avatarConfigForm.getFieldValue([
      'avatar',
      'audio_format',
    ])
    const destSampleRate: any = {
      1: 16000,
      2: 24000,
    }
    if (interativeRef.current?.recorder) {
      if (nlp && interativeRef.current?.recorder?.sampleRate !== 16000) {
        // 交互拾音只支持16k 16bit
        interativeRef.current.destroyRecorder()
      } else if (
        !nlp &&
        interativeRef.current?.recorder &&
        interativeRef.current?.recorder?.sampleRate !==
        destSampleRate[audio_format]
      ) {
        // 驱动必须与 形象设置的输出声音采样率一致,
        interativeRef.current.destroyRecorder()
      }
    }
    if (!interativeRef.current?.recorder) {
      // 交互播放器必须是16000， 音频驱动 一定要与setGloableParams 全局参数avatar.audio_format
      interativeRef.current?.createRecorder({
        sampleRate: nlp ? 16000 : destSampleRate[audio_format] || 16000,
      })
    }
    const recorder = interativeRef.current?.recorder
    recorder?.startRecord(
      full_duplex ? 0 : single_seconds * 1000,
      () => {
        console.log('recorder auto stopped')
      },
      {
        nlp: nlp,
      }
    )
  }
  const stopRecorder = () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk & 连接')
    }
    const recorder = interativeRef.current?.recorder
    recorder?.stopRecord()
  }
  const stopAvatar = async () => {
    if (!interativeRef.current) {
      return message.warning('请初始化sdk')
    }
    interativeRef.current?.stop()
    setIsStarted(false)
  }

  const quickStart = async () => {
    const { avatarId, voiceId, backgroundUrl } = quickStartForm.getFieldsValue()

    if (!avatarId || !voiceId) {
      return message.warning('请选择形象和语音')
    }

    // ★★★ 记住选中的语音，Agent 追问时使用同样的语音 ★★★
    voiceIdRef.current = voiceId

    try {
      setLoading(true)

      let interative = interativeRef.current
      if (!interative) {
        interativeRef.current = interative = new (AvatarPlatform as any)({
          useInlinePlayer: true,
          binaryData: false,
        })

        interativeRef.current.setApiInfo({
          serverUrl: 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact',
          appId: 'fe897b77',
          apiKey: '3a29b78e4acda78488bd09220d8f1b98',
          apiSecret: 'YmY4YTViN2Y5MDY1MjUyOGQxMGU2NTY3',
          sceneId: '325229986007093248',
        })
      }

      interativeRef.current.removeAllListeners()
      interativeRef.current
        .on(SDKEvents.connected, (initResp: any) => {
          console.log('sdk event: connected', initResp)
        })
        .on(SDKEvents.stream_start, () => {
          console.log('sdk event: stream_start')
          setIsSpeaking(true)
        })
        .on(SDKEvents.disconnected, (e: any) => {
          setLoading(false)
          setIsStarted(false)
          console.log('sdk event: disconnected')
          if (e) {
            message.error('ws link disconnected')
            console.error(e.code, e.message, e.name, e.stack)
          }
        })
        .on(SDKEvents.asr, (asrData: any) => {
          console.log('sdk event: asr', asrData)
        })
        .on(SDKEvents.nlp, (nlpData: any) => {
          console.log('sdk event: nlp', nlpData)
        })
        .on(SDKEvents.frame_start, (frameData: any) => {
          console.log('sdk event: frameBegin', frameData)
        })
        .on(SDKEvents.frame_stop, (frameData: any) => {
          console.log('sdk event: frameEnd', frameData)
        })
        .on(SDKEvents.action_start, (actionData: any) => {
          console.log('sdk event: actionBegin', actionData)
        })
        .on(SDKEvents.action_stop, (actionData: any) => {
          console.log('sdk event: actionEnd', actionData)
        })
        .on(SDKEvents.tts_duration, (sessionData: any) => {
          console.log('sdk event: duration', sessionData)
        })
        .on(SDKEvents.subtitle_info, (subtitleData: any) => {
          console.log('sdk event: subtitle', subtitleData)
          setSubtitle(subtitleData?.text || '')
          if (!subtitleData?.text) {
            setIsSpeaking(false)
          }
        })
        .on(SDKEvents.error, (error: any) => {
          console.log('sdk event: error', error)
        })

      const player = interativeRef.current.player || interativeRef.current.createPlayer()
      player.removeAllListeners()
      player
        .on(PlayerEvents.error, (err: any) => {
          console.log('sdk player event: player error', err)
        })
        ?.on(PlayerEvents.play, () => {
          console.log('sdk player event: player play')
        })
        .on(PlayerEvents.waiting, () => {
          console.log('sdk player event: player waiting')
        })
        .on(PlayerEvents.playing, () => {
          console.log('sdk player event: player playing')
        })

      await interativeRef.current.setGlobalParams({
        avatar_dispatch: { interactive_mode: 0, content_analysis: 0 },
        stream: {
          protocol: 'xrtc',
          alpha: 0,
          bitrate: 1000000,
          fps: 25,
        },
        avatar: {
          avatar_id: avatarId,
          width: 720,
          height: 1280,
          mask_region: '[0, 0, 1080, 1920]',
          scale: 1,
          move_h: 0,
          move_v: 0,
          audio_format: 1,
        },
        tts: {
          vcn: voiceId,
          speed: 50,
          pitch: 50,
          volume: 100,
        },
        subtitle: {
          subtitle: 0,
          font_color: '#ffffff',
        },
        ...(backgroundUrl ? {
          background: {
            enabled: true,
            type: 'url',
            data: backgroundUrl,
          },
        } : {}),
      })

      await interativeRef.current.start({
        wrapper: document.querySelector('.wrapper1') as HTMLDivElement,
        preRes: {
          image: [
            {
              url: '22SLM2teIw+aqR6Xsm2JbH6Ng310kDam2NiCY/RQ9n6s3nYJXloZWW1l64/g32vrn7d2lJQR7m9xD5EHYkVs1+bLdJQ42I5SCCMphdtQC/KdIR9lQZl6Ryymh/CEiDdSSRND1SuiX8pjrFjxk/WMtJ+pDS5JT7P/8c0lxcMB6+IjTLQvgz41Fdhb1/sAGtES7HCMZepV5nNwisTvd8PhztpmXX+lIS1LQcPHJy2HW4/XrrKKf4AI8nj2lbocKniDJDk5cQtsOjY7raVi6fSp/9Zmz0eVr0UXa/wA65nxXD+I6VF6TxI1Er4wvKVTlpItpT2RDIDaanYWDZ3hyMDupH4MJcEev3sE9Tfl8tDtZ2c=',
            },
          ],
        },
      })

      message.success('连接成功 & 拉流订阅成功 & 流播放成功')
      setLoading(false)
      setIsStarted(true)

      interativeRef.current
        .writeText('你好！我是你的数字人助手，请问有什么可以帮助你的吗？', {
          tts: {
            vcn: voiceId,
            speed: 50,
            pitch: 50,
            volume: 100,
          },
        })
        .then((reqId: string) => {
          console.log(`自动欢迎语发送成功 request_id: ${reqId}`)
        })
        .catch((err: any) => {
          console.error('自动欢迎语发送失败:', err)
        })
    } catch (e: any) {
      console.error(e)
      message.error('启动失败: ' + e?.message)
      setLoading(false)
      setIsStarted(false)
    }
  }
  // ★★★ 向教育 Agent 发送消息，让数字人播报追问/回答 ★★★
  const sendToAgent = async () => {
    const text = agentInput.trim()
    if (!text) return message.warning('请输入你想问的学习问题')
    if (!interativeRef.current) return message.warning('请先启动数字人')

    setAgentChatLoading(true)
    setAgentInput('')

    // 在对话记录中显示用户输入
    setAgentConversation(prev => [...prev, { role: 'user', text }])

    try {
      const res = await fetch(`${agentServerUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Token': 'eyJhbGciOiJIUzI1NiJ9.eyJlbXBJZCI6MiwiZXhwIjoxNzgxNzU4NjIzfQ.gEqYkaA1P6irzFoISsQO6WhmjYjiPWDP2nK4LaXoRb8'
        },
        body: JSON.stringify({
          user_id: agentUserId,
          user_input: text,
          // userId: 2,
          // text: text,
        }),
      })
      const json = await res.json()

      if (!json.success) {  // 假设 code: 1 表示成功
        message.error('Agent 调用失败: ' + JSON.stringify(json))
        setAgentChatLoading(false)
        return
      }

      // 提取 Agent 返回的数据
      const agentData = json.data?.data || json.data
      const status = agentData?.status || json.data?.status
      const followUpQuestions = agentData?.follow_up_questions
      const guidance = agentData?.guidance || json.data?.guidance || ''

      if (status === 'need_more_info' && followUpQuestions?.length > 0) {
        // ★★★ 信息不足 → 让数字人说出第一个追问问题 ★★★
        const firstQuestion = followUpQuestions[0]
        setAgentConversation(prev => [
          ...prev,
          { role: 'agent', text: firstQuestion },
        ])

        await interativeRef.current.writeText(firstQuestion, {
          tts: {
            vcn: voiceIdRef.current,
            speed: 50,
            pitch: 50,
            volume: 100,
          },
        })

        // 保存 extracted_info 供后续轮次使用（内部已通过 MasterController 缓存）
        extractedInfoRef.current = agentData.extracted_info || null
      } else if (status === 'success' || guidance) {
        // ★★★ 区分正常chat回复 vs 资源生成完成 ★★★
        let speakText
        if (agentData?.reply) {
          // 日常对话(casual_chat) → 说出回复内容
          speakText = agentData.reply
        } else if (guidance) {
          if (agentData?.des_stage === 'registration_complete') {
            // DES注册完成 → 先播报画像构建成功，再说教师指导
            speakText = `初次画像构建成功！${guidance}`
          } else {
            // DES资源生成完成 → 说出教师指导内容
            speakText = guidance
          }
        } else {
          // 兜底
          speakText = '分析完成'
        }
        // ★★★ TTS 长度限制：超过 2000 字符时截断，避免接口报错 ★★★
        const ttsText = speakText.length > 1800 ? speakText.slice(0, 1800) + '...' : speakText
        setAgentConversation(prev => [...prev, { role: 'agent', text: speakText }])

        await interativeRef.current.writeText(ttsText, {
          tts: {
            vcn: voiceIdRef.current,
            speed: 50,
            pitch: 50,
            volume: 100,
          },
        })

        extractedInfoRef.current = null
      } else {
        // 兜底：把返回内容说出来
        const fallbackText = JSON.stringify(agentData || json).slice(0, 200)
        setAgentConversation(prev => [...prev, { role: 'agent', text: fallbackText }])
        await interativeRef.current.writeText(fallbackText, {
          tts: { vcn: voiceIdRef.current, speed: 50, pitch: 50, volume: 100 },
        })
      }
    } catch (e: any) {
      console.error(e)
      message.error('请求失败: ' + e?.message)
    }

    setAgentChatLoading(false)
  }

  useEffect(() => {
    return () => {
      interativeRef.current?.destroy()
    }
  }, [])

  return (
    <Spin spinning={loading} tip="Loading...">
      <div className={'wrapper'}>
        <div className="wp wrapper1"></div>
        <div className="wp wrapper2"></div>
        <p className="subtitle">{subtitle}</p>
      </div>

      <div style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: 'white',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        minWidth: '300px',
        maxWidth: '380px',
        maxHeight: '70vh',
        overflowY: 'auto'
      }}>
        <h3 style={{ marginBottom: '15px' }}>快速启动</h3>
        <Form
          form={quickStartForm}
          layout="vertical"
        >
          <Form.Item
            label="选择形象"
            name="avatarId"
            rules={[{ required: true, message: '请选择形象' }]}
          >
            <Select
              placeholder="请选择形象"
              options={avatarOptions}
            />
          </Form.Item>
          <Form.Item
            label="选择语音"
            name="voiceId"
            rules={[{ required: true, message: '请选择语音' }]}
          >
            <Select
              placeholder="请选择语音"
              options={voiceOptions}
            />
          </Form.Item>
          <Form.Item
            label="选择背景"
            name="backgroundUrl"
          >
            <Select
              placeholder="请选择背景（可选）"
              options={backgroundOptions}
            />
          </Form.Item>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button
              type="primary"
              block
              onClick={quickStart}
              disabled={isStarted}
            >
              {isStarted ? '已启动' : '一键启动数字人'}
            </Button>
            <Button
              block
              onClick={stopAvatar}
              disabled={!isStarted}
            >
              停止
            </Button>
          </Space>
        </Form>

        {/* ★★★ Agent 对话区域 ★★★ */}
        <Divider style={{ margin: '12px 0' }} />
        <h4 style={{ marginBottom: '8px' }}>🎓 教育 Agent 对话</h4>
        <Form layout="vertical" style={{ marginBottom: 0 }}>
          <Form.Item label="后端地址" style={{ marginBottom: 8 }}>
            <Input
              size="small"
              value={agentServerUrl}
              onChange={e => setAgentServerUrl(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="用户 ID" style={{ marginBottom: 8 }}>
            <Input
              size="small"
              value={agentUserId}
              onChange={e => setAgentUserId(e.target.value)}
            />
          </Form.Item>
        </Form>

        {/* 对话记录 */}
        <div
          style={{
            height: 200,
            overflowY: 'auto',
            background: '#f0f7ff',
            borderRadius: 8,
            padding: '10px 12px',
            marginBottom: 10,
            fontSize: 13,
            lineHeight: 1.6,
            border: '1px solid #e0e7ff',
          }}
        >
          {agentConversation.length === 0 && (
            <span style={{ color: '#6b7280' }}>输入问题后发送，Agent 的追问会让数字人说出</span>
          )}
          {agentConversation.map((msg, i) => (
            <div
              key={i}
              style={{
                textAlign: msg.role === 'user' ? 'right' : 'left',
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  display: 'inline-block',
                  padding: '6px 12px',
                  borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                  background: msg.role === 'user' ? '#3b82f6' : '#ffffff',
                  color: msg.role === 'user' ? '#ffffff' : '#1f2937',
                  maxWidth: '85%',
                  maxHeight: 150,
                  overflowY: 'auto',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                  boxShadow: msg.role === 'agent' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                {msg.role === 'user' ? '👤 ' : '🤖 '}
                {msg.text}
              </span>
            </div>
          ))}
          {agentChatLoading && (
            <div style={{ textAlign: 'left', color: '#6b7280' }}>🤖 思考中...</div>
          )}
        </div>

        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="输入你的学习问题..."
            value={agentInput}
            onChange={e => setAgentInput(e.target.value)}
            onPressEnter={sendToAgent}
            disabled={agentChatLoading || !isStarted}
          />
          <Button
            type="primary"
            onClick={sendToAgent}
            loading={agentChatLoading}
            disabled={!isStarted}
          >
            发送
          </Button>
          {isSpeaking && (
            <Button
              danger
              type="default"
              onClick={interrupt}
            >
              打断
            </Button>
          )}
        </Space.Compact>
      </div>

      <Button className="hdl" onClick={() => setDrawerOpen(true)}>
        打开调试面板
      </Button>
      <Drawer
        title="API"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={450}
        maskClosable={false}
      >
        <Space direction="vertical">
          <Button onClick={() => message.success(AvatarPlatform.getVersion())}>
            static getVersion
          </Button>
          <Space>
            <Select
              style={{ width: '100px' }}
              options={[
                { value: 0, label: 'verbose' },
                { value: 1, label: 'debug' },
                { value: 2, label: 'info' },
                { value: 3, label: 'warn' },
                { value: 4, label: 'error' },
                { value: 5, label: 'none' },
              ]}
              value={loglevel}
              onChange={(va) => setLoglevel(va)}
            ></Select>
            <Button
              onClick={() => {
                AvatarPlatform.setLogLevel(loglevel)
                message.success('日志级别设置成功 可以开启控制台查看')
              }}
            >
              static setLogLevel
            </Button>
          </Space>
          <Divider>SDK 初始化参数（初始化前设置）</Divider>
          <Form
            form={initForm}
            initialValues={{
              useInlinePlayer: true,
              binaryData: false,
            }}
          >
            <Form.Item label="使用内敛播放器" name="useInlinePlayer">
              <Switch></Switch>
            </Form.Item>
            {/* <Form.Item label="binary发送" name="binaryData">
              <Switch></Switch>
            </Form.Item> */}
            {/* <Form.Item label="静音续连" name="keepAliveTime">
              <InputNumber min={0} step={1} addonAfter="毫秒"></InputNumber>
            </Form.Item> */}
          </Form>
          <Button onClick={InitSDK} block type="primary">
            初始化SDK
          </Button>
          <Button onClick={bindInteractEvent} block type="primary">
            监听SDK交互事件
          </Button>
          <Divider>播放器</Divider>
          <Space>
            <Button onClick={getPlayer}>获取player实例</Button>
            <Button onClick={createPlayer}>create player实例</Button>
          </Space>
          <Button onClick={bindPlayerEvent} block type="primary">
            监听player事件
          </Button>
          <Divider>SDK 环境参数（start前设置）</Divider>
          <Form
            form={apiInfoForm}
            initialValues={{
              ...InitAppInfo,
            }}
          >
            <Form.Item label="serverUrl" name="serverUrl">
              <Input></Input>
            </Form.Item>
            <Form.Item label="appId" name="appId">
              <Input></Input>
            </Form.Item>
            <Form.Item label="apiKey" name="apiKey">
              <Input></Input>
            </Form.Item>
            <Form.Item label="apiSecret" name="apiSecret">
              <Input></Input>
            </Form.Item>
            <Form.Item label="sceneId" name="sceneId">
              <Input></Input>
            </Form.Item>
          </Form>
          <Button onClick={setApiInfo} block type="primary">
            SDK setApiInfo
          </Button>
          <Divider>SDK startAvatar 参数（startAvatar前设置）</Divider>
          <Form
            form={avatarConfigForm}
            initialValues={{
              avatar_dispatch: { interactive_mode: 0, content_analysis: 0 },
              stream: {
                protocol: 'xrtc',
                alpha: 0,
                bitrate: 1000000,
                fps: 25,
              },
              avatar: {
                avatar_id: '111192001',
                width: 720,
                height: 1280,
                mask_region: '[0, 0, 1080, 1920]',
                scale: 1,
                move_h: 0,
                move_v: 0,
                audio_format: 1,
              },
              tts: {
                vcn: 'x4_yuexiaoni_assist',
                speed: 50,
                pitch: 50,
                volume: 100,
              },
              subtitle: {
                subtitle: 0,
                font_color: '#ffffff',
              },
              background: {
                enabled: true,
                type: 'url',
                data: 'https://all-tame-max-oss.oss-cn-beijing.aliyuncs.com/et/dealshubanxiangyunguochao202311240181.png',
              },
            }}
          >
            <Divider>打断模式全局设置</Divider>
            <Form.Item
              label="文本打断模式"
              name={['avatar_dispatch', 'interactive_mode']}
            >
              <Radio.Group>
                <Radio value={1}>打断模式</Radio>
                <Radio value={0}>追加模式</Radio>
              </Radio.Group>
            </Form.Item>
            <Divider>推流信息</Divider>
            <Form.Item label="推流格式" name={['stream', 'protocol']}>
              <Select
                style={{ width: '100px' }}
                options={[
                  { value: 'webrtc', label: 'webrtc' },
                  { value: 'xrtc', label: 'xrtc' },
                  { value: 'rtmp', label: 'rtmp 不支持播放' },
                ]}
              ></Select>
            </Form.Item>
            <Form.Item label="透明通道(xrtc)" name={['stream', 'alpha']}>
              <Radio.Group>
                <Radio value={1}>开启</Radio>
                <Radio value={0}>关闭</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="码率" name={['stream', 'bitrate']}>
              <InputNumber min={500000} max={5000000} step={1}></InputNumber>
            </Form.Item>
            <Form.Item label="fps" name={['stream', 'fps']}>
              <Slider
                min={15}
                max={25}
                step={1}
                marks={{ 15: '15', 20: '20', 25: '25' }}
              ></Slider>
            </Form.Item>
            <Divider>形象信息</Divider>
            <Form.Item label="形象ID" name={['avatar', 'avatar_id']}>
              <Input></Input>
            </Form.Item>

            <Form.Item
              label="情感分析"
              name={['avatar_dispatch', 'content_analysis']}
              extra="该参数仅超拟人非语音驱动时支持，常规请关闭"
            >
              <Radio.Group>
                <Radio value={1}>开启</Radio>
                <Radio value={0}>关闭</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="流宽" name={['avatar', 'width']}>
              <InputNumber></InputNumber>
            </Form.Item>
            <Form.Item label="流高" name={['avatar', 'height']}>
              <InputNumber></InputNumber>
            </Form.Item>
            <Form.Item label="mask_region" name={['avatar', 'mask_region']}>
              <Input></Input>
            </Form.Item>
            <Form.Item label="scale" name={['avatar', 'scale']}>
              <InputNumber min={0.1} max={1}></InputNumber>
            </Form.Item>
            <Form.Item label="move_h" name={['avatar', 'move_h']}>
              <InputNumber></InputNumber>
            </Form.Item>
            <Form.Item label="move_v" name={['avatar', 'move_v']}>
              <InputNumber></InputNumber>
            </Form.Item>
            <Form.Item
              label="音频驱动/音频输出采样率"
              name={['avatar', 'audio_format']}
            >
              <Radio.Group>
                <Radio value={1}>16k</Radio>
                <Radio value={2}>24k</Radio>
              </Radio.Group>
            </Form.Item>

            <Divider>形象信息</Divider>
            <Form.Item label="声音" name={['tts', 'vcn']}>
              <Input></Input>
            </Form.Item>
            <Form.Item label="语速" name={['tts', 'speed']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
            <Form.Item label="语调" name={['tts', 'pitch']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
            <Form.Item label="音量" name={['tts', 'volume']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
            <Divider>字幕信息</Divider>
            <Form.Item
              label="字幕"
              name={['subtitle', 'subtitle']}
              extra="不启用 sdk 内部默认未启用"
            >
              <Select
                options={[
                  { value: 0, label: '关闭' },
                  { value: 1, label: '服务端字幕' },
                  // { value: 2, label: '响应字幕' },
                ]}
              ></Select>
            </Form.Item>
            <Form.Item label="字体颜色" name={['subtitle', 'font_color']}>
              <ColorPicker disabledAlpha format="hex"></ColorPicker>
            </Form.Item>
            <Divider>背景</Divider>
            <Form.Item
              label="背景"
              name={['background', 'enabled']}
              extra="不启用（默认原始训练）"
            >
              <Switch></Switch>
            </Form.Item>
            <Form.Item label="数据类型" name={['background', 'type']}>
              <Radio.Group>
                <Radio value={'url'}>url</Radio>
                <Radio value={'res_id'}>resId</Radio>
                <Radio value={'data'}>base64</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item label="图片数据" name={['background', 'data']}>
              <Input></Input>
            </Form.Item>
            {/* <Divider>全局上行音频配置</Divider> */}
            {/* <Form.Item
              label="采样率"
              name={['audio', 'sample_rate']}
              extra="sdk 内部默认 16000"
            >
              <Radio.Group>
                <Radio value={16000}>16000</Radio>
                <Radio value={24000}>24000</Radio>
              </Radio.Group>
            </Form.Item> */}
          </Form>
          <Button onClick={setGlobalParams} block type="primary">
            SDK setGlobalParams
          </Button>
          <Form
            form={startAvatarForm}
            initialValues={{
              container: 'wrapper1',
            }}
          >
            <Form.Item label="选择渲染区域dom" name="container">
              <Radio.Group>
                <Radio value={'wrapper1'}>左侧容器</Radio>
                <Radio value={'wrapper2'}>右侧容器</Radio>
              </Radio.Group>
            </Form.Item>
          </Form>
          <Button onClick={startAvatar} block type="primary">
            SDK start
          </Button>
          <Divider>交互 / 虚拟人驱动</Divider>
          <Form
            form={textDriverForm}
            initialValues={{
              avatar_dispatch: {
                interactive_mode: 0,
                content_analysis: 0,
              },
              text: '你好[[action=A_W_walk_left_O]]',
              tts: {
                vcn: '',
                speed: 50,
                pitch: 50,
                volume: 100,
              },
              nlp: false,
            }}
          >
            <Form.Item label="文本是否理解" name="nlp">
              <Switch></Switch>
            </Form.Item>
            <Form.Item
              label="文本打断模式"
              name={['avatar_dispatch', 'interactive_mode']}
            >
              <Radio.Group>
                <Radio value={1}>打断模式</Radio>
                <Radio value={0}>追加模式</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item
              label="情感分析"
              name={['avatar_dispatch', 'content_analysis']}
              extra="该参数仅超拟人非语音驱动时支持，常规请关闭"
            >
              <Radio.Group>
                <Radio value={1}>开启</Radio>
                <Radio value={0}>关闭</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item label="文本" name="text">
              <Input.TextArea></Input.TextArea>
            </Form.Item>
            <Form.Item label="声音" name={['tts', 'vcn']}>
              <Input></Input>
            </Form.Item>
            <Form.Item label="语速" name={['tts', 'speed']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
            <Form.Item label="语调" name={['tts', 'pitch']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
            <Form.Item label="音量" name={['tts', 'volume']}>
              <Slider min={1} max={100}></Slider>
            </Form.Item>
          </Form>
          <Button onClick={writeText} type="primary">
            文本驱动/交互 writeText
          </Button>
          <Divider>立即驱动指定动作</Divider>
          <Form
            form={actionDriverForm}
            initialValues={{
              actionId: '',
            }}
          >
            <Form.Item label="动作ID" name="actionId">
              <Input></Input>
            </Form.Item>
          </Form>
          <Button block onClick={driveAction} type="primary">
            立即执行动作 API driveAction
          </Button>

          <Divider>全局打断当前播报</Divider>
          <Button block onClick={interrupt} type="primary">
            发送打断 SDK API interrupt
          </Button>
          <Divider>语音交互 / 语音驱动</Divider>
          <Form
            form={audioDriverForm}
            initialValues={{
              full_duplex: 0,
              nlp: false,
              single_seconds: 20,
            }}
          >
            <Form.Item label="是否理解" name="nlp">
              <Switch></Switch>
            </Form.Item>
            <Form.Item label="语音模式" name="full_duplex">
              <Radio.Group>
                <Radio value={1}>全双工</Radio>
                <Radio value={0}>单轮</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item
              label="单轮模式端语音自动停止时间"
              name="single_seconds"
              extra="单轮模式 该时间内 用户未主动停止录音，则自动停止；sdk startRecord 支持设置时间"
            >
              <Slider min={5} max={30}></Slider>
            </Form.Item>
          </Form>
          <Button onClick={startRecord} type="primary">
            开始录音 SDK API startRecord
          </Button>
          <Button onClick={stopRecorder} type="primary">
            结束录音 SDK API stopRecord
          </Button>
          <Divider>播放器方法--前端</Divider>
          <Button
            onClick={() => {
              interativeRef.current?.player?.resume()
            }}
            type="primary"
          >
            恢复播放 SDK player API resume
          </Button>
          <p>
            由于浏览器限制，无法自动播放时，需要引导用户手动点击 并 调用 resume
            恢复播放
          </p>
          <Button
            onClick={() => {
              interativeRef.current?.player?.resize()
            }}
          >
            手动刷新渲染 SDK player API resize
          </Button>
          <Button
            onClick={() => {
              if (interativeRef.current?.player)
                interativeRef.current.player.muted = true
            }}
            type="primary"
          >
            静音 SDK player player.muted = true
          </Button>
          <Button
            onClick={() => {
              if (interativeRef.current?.player)
                interativeRef.current.player.muted = false
            }}
            type="primary"
          >
            解除静音 SDK player.muted = false
          </Button>
          <div>
            设置播放外放音量：
            <Slider
              min={0}
              max={100}
              defaultValue={100}
              onChange={(v: number) => {
                if (interativeRef.current?.player)
                  interativeRef.current.player.volume = v / 100
              }}
            ></Slider>
          </div>
          <Divider>断开链接</Divider>
          <Button onClick={stopAvatar} block type="primary">
            SDK API stop
          </Button>
          <Divider>逆初始化 销毁SDK实例</Divider>
          <Button onClick={UnInitSDK} block type="primary">
            SDK API destroy
          </Button>
        </Space>
      </Drawer>
      <div className={'panel'}>
        {/* <div
          onClick={() => {
            console.log(UserMedia.getEnumerateDevices('audiooutput'))
          }}
        >
          get output Devices
        </div>
        <div
          onClick={() => {
            console.log(UserMedia.getEnumerateDevices('audioinput'))
          }}
        >
          get input Devices
        </div>
        <div
          onClick={async () => {
            const outputs = await UserMedia.getEnumerateDevices('audiooutput')
            const output = outputs[Math.floor(Math.random() * outputs.length)]
            console.log(output)
            if (interativeRef.current?.player)
              interativeRef.current.player.setSinkId(output.deviceId)
          }}
        >
          switch Devices
        </div> */}

        {/* <div
          onClick={async () => {
            const inputs = await UserMedia.getEnumerateDevices('audioinput')
            const input = inputs[Math.floor(Math.random() * inputs.length)]
            console.log(input)
            if (interativeRef.current?.player)
              interativeRef.current.recorder?.switchDevice(input.deviceId)
          }}
        >
          switch recorder Devices
        </div> */}
      </div>
    </Spin>
  )
}

export default App
