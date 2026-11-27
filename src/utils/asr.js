// @/utils/asr.js
/**
 * ASR (语音识别) 工具模块
 * 提供音频录制、WebM转WAV、语音识别等功能
 */

import { postAudioApi } from '@/api/mainApi/aiAnswer.js'

/**
 * 将 WebM 音频 Blob 转换为 WAV 格式
 * @param {Blob} webmBlob - WebM 格式的音频 Blob
 * @returns {Promise<Blob>} WAV 格式的音频 Blob
 */
const convertWebMToWav = (webmBlob) => {
  return new Promise((resolve, reject) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 16000
    })

    const reader = new FileReader()
    reader.onload = async (event) => {
      try {
        const arrayBuffer = event.target.result
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
        const wavBuffer = audioBufferToWav(audioBuffer)
        const wavBlob = new Blob([wavBuffer], { type: 'audio/wav' })
        resolve(wavBlob)
      } catch (e) {
        reject(e)
      }
    }
    reader.onerror = reject
    reader.readAsArrayBuffer(webmBlob)
  })
}

/**
 * 将 AudioBuffer 转换为 WAV 格式的 ArrayBuffer
 * @param {AudioBuffer} buffer - 音频缓冲区
 * @returns {ArrayBuffer} WAV 格式的数据
 */
const audioBufferToWav = (buffer) => {
  const numChannels = buffer.numberOfChannels
  const sampleRate = buffer.sampleRate
  const format = 1
  const bitDepth = 16

  const samples = buffer.length * numChannels
  const dataSize = samples * (bitDepth / 8)
  const headerSize = 44
  const totalSize = headerSize + dataSize

  const wavData = new ArrayBuffer(totalSize)
  const view = new DataView(wavData)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, totalSize - 8, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, format, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * numChannels * (bitDepth / 8), true)
  view.setUint16(32, numChannels * (bitDepth / 8), true)
  view.setUint16(34, bitDepth, true)
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  const offset = 44
  let index = 0
  const channelData = buffer.getChannelData(0)

  for (let i = 0; i < buffer.length; i++) {
    const sample = Math.max(-1, Math.min(1, channelData[i]))
    const int16Sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF
    view.setInt16(offset + index * 2, int16Sample, true)
    index++
  }

  return wavData
}

/**
 * 向 DataView 写入字符串
 * @param {DataView} view - DataView 实例
 * @param {number} offset - 偏移量
 * @param {string} string - 要写入的字符串
 */
const writeString = (view, offset, string) => {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

/**
 * 繁体中文转简体中文映射表
 * 只包含需要转换的繁体字，与简体一致的字符不映射
 */
const TRADITIONAL_TO_SIMPLIFIED_MAP = {
  // 常用字（高频）
  '這': '这', '個': '个', '們': '们', '會': '会',
  '來': '来', '說': '说', '話': '话', '聽': '听',
  '問': '问', '題': '题', '學': '学', '習': '习',
  '時': '时', '間': '间', '點': '点', '線': '线',
  '書': '书', '寫': '写', '讀': '读', '講': '讲',
  '課': '课', '業': '业', '師': '师', '級': '级',
  '數': '数', '據': '据', '資': '资', '訊': '讯',
  '體': '体', '驗': '验', '經': '经', '結': '结',
  '果': '果', '碼': '码', '網': '网', '頁': '页',
  '瀏': '浏', '覽': '览', '視': '视', '頻': '频',
  '圖': '图', '檔': '档', '案': '案', '徑': '径',
  '層': '层', '統': '统', '計': '计', '畫': '画',
  '佈': '布', '顏': '颜', '樣': '样', '標': '标',
  '準': '准', '確': '确', '認': '认', '識': '识',
  '別': '别', '區': '区', '塊': '块', '組': '组',
  '織': '织', '構': '构', '設': '设', '開': '开',
  '發': '发', '維': '维', '護': '护', '測': '测',
  '試': '试', '錯': '错', '偵': '侦', '監': '监',
  '控': '控', '錄': '录', '紀': '纪', '載': '载',
  '儲': '储', '備': '备', '複': '复', '製': '制',
  '對': '对', '齊': '齐', '動': '动', '縮': '缩',
  '轉': '转', '鏡': '镜', '濾': '滤', '過': '过',
  '變': '变', '換': '换', '選': '选', '擇': '择',
  '項': '项', '單': '单', '鈕': '钮', '鍵': '键',
  '盤': '盘', '窗': '窗', '息': '息', '警': '警',
  '告': '告', '誤': '误', '敗': '败', '遞': '递',
  '態': '态', '啟': '启', '執': '执', '續': '续',
  '暫': '暂', '復': '复', '關': '关', '閉': '闭',
  '註': '注', '冊': '册', '證': '证', '權': '权',
  '許': '许', '絕': '绝', '審': '审', '核': '核',
  '簽': '签', '稱': '称', '喚': '唤', '麼': '么',
  '裡': '里', '邊': '边', '後': '后', '內': '内',
  '於': '于', '與': '与', '並': '并', '還': '还',
  '將': '将', '夠': '够', '從': '从', '著': '着',
  '隨': '随', '儘': '尽', '週': '周', '節': '节',
  '慶': '庆', '賀': '贺', '禮': '礼', '質': '质',
  '價': '价', '幣': '币', '買': '买', '賣': '卖',
  '購': '购', '訂': '订', '貨': '货', '務': '务',
  '銷': '销', '售': '售', '應': '应', '該': '该',
  '當': '当', '現': '现', '實': '实', '報': '报',
  '導': '导', '編': '编', '輯': '辑', '採': '采',
  '訪': '访', '談': '谈', '論': '论', '評': '评',
  '優': '优', '麗': '丽', '強': '强', '壯': '壮',
  '偉': '伟', '傑': '杰', '樂': '乐', '愛': '爱',
  '憶': '忆', '懷': '怀', '願': '愿', '離': '离',
  '團': '团', '圓': '圆', '滿': '满', '實': '实',
  '富': '富', '裕': '裕', '寧': '宁', '靜': '静',
  '穩': '稳', '戀': '恋', '癡': '痴', '熱': '热',
  '敵': '敌', '誼': '谊', '義': '义', '靈': '灵',
  '夢': '梦', '幻': '幻', '狀': '状', '勢': '势',
  '源': '源', '濃': '浓', '輕': '轻', '緩': '缓',
  '晝': '昼', '聲': '声', '響': '响', '樂': '乐',
  '業': '业', '務': '务', '幹': '干', '辦': '办',
  '廠': '厂', '廳': '厅', '曆': '历', '歷': '历',
  '婦': '妇', '兒': '儿', '黨': '党', '團': '团',
  '擁': '拥', '護': '护', '擊': '击', '戰': '战',
  '鬥': '斗', '爭': '争', '勝': '胜', '負': '负',
  '敗': '败', '榮': '荣', '譽': '誉', '恥': '耻',
  '辱': '辱', '謙': '谦', '虛': '虚', '誠': '诚',
  '信': '信', '義': '义', '禮': '礼', '智': '智',
  '仁': '仁', '勇': '勇', '毅': '毅', '堅': '坚',
  '韌': '韧', '恆': '恒', '久': '久', '遠': '远',
  // 动词和形容词
  '見': '见', '觀': '观', '賞': '赏', '析': '析',
  '研': '研', '究': '究', '探': '探', '索': '索',
  '創': '创', '新': '新', '革': '革', '命': '命',
  '改': '改', '善': '善', '修': '修', '復': '复',
  '整': '整', '理': '理', '歸': '归', '納': '纳',
  '總': '总', '結': '结', '概': '概', '括': '括',
  '含': '含', '蓋': '盖', '涉': '涉', '及': '及',
  '達': '达', '成': '成', '完': '完', '畢': '毕',
  '終': '终', '止': '止', '開': '开', '始': '始',
  '啟': '启', '動': '动', '運': '运', '行': '行',
  '停': '停', '頓': '顿', '繼': '继', '續': '续',
  '中': '中', '斷': '断', '連': '连', '接': '接',
  '聯': '联', '繫': '系', '關': '关', '係': '系',
  '處': '处', '理': '理', '解': '解', '決': '决',
  '協': '协', '調': '调', '配': '配', '合': '合',
  '適': '适', '應': '应', '對': '对', '付': '付',
  '抗': '抗', '拒': '拒', '抵': '抵', '制': '制',
  '壓': '压', '縮': '缩', '擴': '扩', '展': '展',
  '延': '延', '伸': '伸', '彎': '弯', '曲': '曲',
  '直': '直', '接': '接', '間': '间', '隔': '隔',
  '分': '分', '裂': '裂', '合': '合', '併': '并',
  '聚': '聚', '散': '散', '集': '集', '中': '中',
  '離': '离', '開': '开', '進': '进', '入': '入',
  '退': '退', '出': '出', '升': '升', '降': '降',
  '增': '增', '減': '减', '乘': '乘', '除': '除',
  // 名词和术语
  '環': '环', '境': '境', '氣': '气', '候': '候',
  '天': '天', '氣': '气', '溫': '温', '度': '度',
  '濕': '湿', '度': '度', '壓': '压', '力': '力',
  '電': '电', '子': '子', '機': '机', '器': '器',
  '電': '电', '腦': '脑', '軟': '软', '件': '件',
  '硬': '硬', '件': '件', '網': '网', '路': '路',
  '資': '资', '料': '料', '庫': '库', '系': '系',
  '統': '统', '程': '程', '式': '式', '碼': '码',
  '編': '编', '譯': '译', '除': '除', '錯': '错',
  '調': '调', '試': '试', '部': '部', '署': '署',
  '發': '发', '佈': '布', '版': '版', '權': '权',
  '商': '商', '標': '标', '專': '专', '利': '利',
  '合': '合', '約': '约', '契': '契', '約': '约',
  '條': '条', '款': '款', '政': '政', '策': '策',
  '法': '法', '律': '律', '規': '规', '則': '则',
  '制': '制', '度': '度', '標': '标', '準': '准',
  '規': '规', '範': '范', '步': '步', '驟': '骤',
  '流': '流', '程': '程', '方': '方', '法': '法',
  '技': '技', '術': '术', '工': '工', '具': '具',
  '材': '材', '料': '料', '資': '资', '源': '源',
  '幫': '帮', '語': '语', '礎': '础', '績': '绩',
  '爲': '为', '劃': '划', '為': '为'
}

/**
 * 繁体中文转简体中文
 * @param {string} text - 繁体中文文本
 * @returns {string} 简体中文文本
 */
const traditionalToSimplified = (text) => {
  if (!text) return text

  let result = ''
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    result += TRADITIONAL_TO_SIMPLIFIED_MAP[char] || char
  }
  return result
}

/**
 * ASR 语音识别类
 * 提供语音录制、识别功能
 * 
 * @example
 * // 基本使用
 * const asr = new ASR({
 *   onResult: (text) => {
 *     console.log('识别结果:', text) // 自动转为简体中文
 *     // 填入输入框: input.value = text
 *   }
 * })
 * await asr.startRecording()
 * // ... 录音中
 * await asr.stopAndRecognize()
 */
export class ASR {
  /**
   * 创建 ASR 实例
   * @param {Object} options - 配置选项
   * @param {number} options.sampleRate - 采样率，默认 16000
   * @param {boolean} options.echoCancellation - 回声消除，默认 true
   * @param {boolean} options.noiseSuppression - 降噪，默认 true
   * @param {boolean} options.convertToSimplified - 是否将繁体转简体，默认 true (强烈建议开启)
   * @param {Function} options.onStart - 录音开始回调
   * @param {Function} options.onStop - 录音停止回调
   * @param {Function} options.onData - 录音数据回调
   * @param {Function} options.onResult - 识别结果回调 (返回简体中文)
   * @param {Function} options.onError - 错误回调
   */
  constructor(options = {}) {
    this.options = {
      sampleRate: options.sampleRate || 16000,
      echoCancellation: options.echoCancellation !== undefined ? options.echoCancellation : true,
      noiseSuppression: options.noiseSuppression !== undefined ? options.noiseSuppression : true,
      // 默认开启繁体转简体
      convertToSimplified: options.convertToSimplified !== undefined ? options.convertToSimplified : true,
      onStart: options.onStart || null,
      onStop: options.onStop || null,
      onData: options.onData || null,
      onResult: options.onResult || null,
      onError: options.onError || null,
    }

    this.mediaRecorder = null
    this.audioChunks = []
    this.stream = null
    this.isRecording = false
    this.isRecognizing = false
    this.rawResult = null // 保存原始识别结果
  }

  /**
   * 开始录音
   * @returns {Promise<void>}
   */
  async startRecording() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: this.options.sampleRate,
          channelCount: 1,
          echoCancellation: this.options.echoCancellation,
          noiseSuppression: this.options.noiseSuppression,
        }
      })

      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType: 'audio/webm;codecs=opus'
      })
      this.audioChunks = []

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data)
          if (this.options.onData) {
            this.options.onData(event.data)
          }
        }
      }

      this.mediaRecorder.start(1000)
      this.isRecording = true

      if (this.options.onStart) {
        this.options.onStart()
      }
    } catch (e) {
      this.isRecording = false
      if (this.options.onError) {
        this.options.onError(e)
      }
      throw e
    }
  }

  /**
   * 停止录音并识别（使用 postAudioApi）
   * @returns {Promise<string>} 识别结果文本 (简体中文)
   */
  async stopAndRecognize() {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder || !this.isRecording) {
        const error = new Error('未在录音中')
        if (this.options.onError) {
          this.options.onError(error)
        }
        reject(error)
        return
      }

      this.isRecognizing = true

      this.mediaRecorder.onstop = async () => {
        this.isRecording = false

        if (this.options.onStop) {
          this.options.onStop()
        }

        if (this.audioChunks.length === 0) {
          const error = new Error('未录制到有效音频')
          if (this.options.onError) {
            this.options.onError(error)
          }
          this.isRecognizing = false
          reject(error)
          return
        }

        try {
          const webmBlob = new Blob(this.audioChunks, { type: 'audio/webm' })
          const wavBlob = await convertWebMToWav(webmBlob)

          const formData = new FormData()
          formData.append('audio_file', wavBlob, 'recording.wav')

          const result = await postAudioApi(formData)

          let recognizedText = result?.text?.trim() || ''
          this.rawResult = recognizedText // 保存原始结果

          // 默认开启繁体转简体
          if (this.options.convertToSimplified && recognizedText) {
            recognizedText = traditionalToSimplified(recognizedText)
          }

          // 回调返回简体中文
          if (this.options.onResult) {
            this.options.onResult(recognizedText)
          }

          this.isRecognizing = false
          resolve(recognizedText)
        } catch (e) {
          this.isRecognizing = false
          if (this.options.onError) {
            this.options.onError(e)
          }
          reject(e)
        } finally {
          this.cleanup()
        }
      }

      this.mediaRecorder.stop()
    })
  }

  /**
   * 停止录音（不识别）
   * @returns {Promise<void>}
   */
  async stopRecording() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || !this.isRecording) {
        this.cleanup()
        resolve()
        return
      }

      this.mediaRecorder.onstop = () => {
        this.isRecording = false
        if (this.options.onStop) {
          this.options.onStop()
        }
        this.cleanup()
        resolve()
      }

      this.mediaRecorder.stop()
    })
  }

  /**
   * 取消录音（释放资源）
   */
  cancel() {
    if (this.mediaRecorder && this.isRecording) {
      try {
        this.mediaRecorder.stop()
      } catch (e) {
        // ignore
      }
    }
    this.cleanup()
    this.isRecording = false
    this.isRecognizing = false
  }

  /**
   * 清理资源
   */
  cleanup() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
      this.stream = null
    }
    this.mediaRecorder = null
    this.audioChunks = []
  }

  /**
   * 获取原始识别结果（繁体）
   * @returns {string|null} 原始识别结果
   */
  getRawResult() {
    return this.rawResult
  }

  /**
   * 手动将繁体文本转为简体
   * @param {string} text - 繁体文本
   * @returns {string} 简体文本
   */
  static toSimplified(text) {
    return traditionalToSimplified(text)
  }

  /**
   * 检查浏览器是否支持录音
   * @returns {boolean}
   */
  static isSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  }

  /**
   * 检查麦克风权限
   * @returns {Promise<boolean>}
   */
  static async checkPermission() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(track => track.stop())
      return true
    } catch (e) {
      return false
    }
  }

  /**
   * 获取错误信息
   * @param {Error} error - 错误对象
   * @returns {string} 用户友好的错误信息
   */
  static getErrorMessage(error) {
    if (!error) return '未知错误'
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
      return '无法访问麦克风，请在浏览器中允许麦克风权限'
    }
    if (error.name === 'NotFoundError') {
      return '未检测到麦克风设备，请检查连接'
    }
    if (error.name === 'NotReadableError') {
      return '麦克风被占用，请检查其他应用是否正在使用麦克风'
    }
    if (error.name === 'SecurityError') {
      return '安全错误，请使用 HTTPS 协议访问页面'
    }
    if (error.message && error.message.includes('timeout')) {
      return '语音识别超时，请重试'
    }
    return error.message || '录音启动失败'
  }
}

/**
 * 快捷函数：录制并识别
 * @param {Object} options - 配置选项
 * @param {Function} options.onStart - 录音开始回调
 * @param {Function} options.onStop - 录音停止回调
 * @param {Function} options.onData - 录音数据回调
 * @param {Function} options.onProgress - 进度回调
 * @param {Function} options.onResult - 识别结果回调 (返回简体中文)
 * @param {Function} options.onError - 错误回调
 * @param {number} options.sampleRate - 采样率
 * @param {boolean} options.convertToSimplified - 是否将繁体转简体，默认 true
 * @returns {Promise<{ asr: ASR, result: string }>}
 */
export async function recordAndRecognize(options = {}) {
  const asr = new ASR({
    sampleRate: options.sampleRate || 16000,
    echoCancellation: options.echoCancellation !== undefined ? options.echoCancellation : true,
    noiseSuppression: options.noiseSuppression !== undefined ? options.noiseSuppression : true,
    convertToSimplified: options.convertToSimplified !== undefined ? options.convertToSimplified : true,
    onStart: options.onStart || null,
    onStop: options.onStop || null,
    onData: options.onData || null,
    onResult: options.onResult || null,
    onError: options.onError || null,
  })

  try {
    await asr.startRecording()
    const result = await asr.stopAndRecognize()
    return { asr, result }
  } catch (e) {
    throw e
  }
}

export default {
  ASR,
  recordAndRecognize,
}