// src/utils/typewriter.js

/**
 * aiAnswer的打字机效果工具类
 * 支持逐字显示文本、暂停、继续、停止、重置等功能
 */
class Typewriter {
  constructor(options = {}) {
    // 默认配置
    this.defaultSpeed = options.speed || 30 // 每字符间隔(ms)
    this.minSpeed = options.minSpeed || 10
    this.maxSpeed = options.maxSpeed || 100

    // 状态
    this.timer = null
    this.isRunning = false
    this.isPaused = false
    this.isCompleted = false

    // 当前任务
    this.currentTask = null
    this.callbacks = {
      onStart: options.onStart || null,
      onProgress: options.onProgress || null,
      onComplete: options.onComplete || null,
      onPause: options.onPause || null,
      onResume: options.onResume || null,
      onStop: options.onStop || null,
    }
  }

  /**
   * 开始打字机效果
   * @param {string|HTMLElement} target - 目标元素或文本内容
   * @param {string} fullText - 完整文本（如果target是元素，则此参数为要显示的文本）
   * @param {Object} options - 配置项
   * @param {number} options.speed - 每字符间隔(ms)
   * @param {Function} options.onChar - 每输出一个字符的回调
   * @param {Function} options.onComplete - 完成回调
   * @param {Function} options.onProgress - 进度回调
   * @returns {Promise}
   */
  start(target, fullText, options = {}) {
    return new Promise((resolve) => {
      // 停止之前的任务
      this.stop()

      // 解析参数
      let element = null
      let text = fullText

      if (typeof target === 'string' && !fullText) {
        // 如果只有一个字符串参数，直接输出到控制台或返回
        text = target
      } else if (typeof target === 'string' && fullText) {
        // target是元素选择器或元素本身
        element = typeof target === 'string'
          ? document.querySelector(target)
          : target
        text = fullText
      } else if (target && target.nodeType) {
        // target是DOM元素
        element = target
        text = fullText
      }

      // 如果传入的是纯文本，直接返回文本
      if (!element) {
        // 纯文本模式，返回Promise但直接resolve
        resolve(text)
        return
      }

      // 合并配置
      const speed = options.speed || this.defaultSpeed
      const onChar = options.onChar || null
      const onComplete = options.onComplete || null
      const onProgress = options.onProgress || null

      // 重置状态
      this.isRunning = true
      this.isPaused = false
      this.isCompleted = false
      this.currentTask = {
        element,
        text,
        speed,
        currentIndex: 0,
        totalLength: text.length,
        startTime: Date.now(),
      }

      // 清空元素内容
      element.textContent = ''

      // 触发开始回调
      if (this.callbacks.onStart) {
        this.callbacks.onStart(text)
      }

      // 如果文本为空
      if (!text || text.length === 0) {
        this.isCompleted = true
        this.isRunning = false
        if (this.callbacks.onComplete) {
          this.callbacks.onComplete(text)
        }
        if (onComplete) onComplete(text)
        resolve(text)
        return
      }

      // 如果文本很短，加速显示
      const actualSpeed = text.length < 20 ? Math.max(this.minSpeed, speed / 2) : speed

      // 开始逐字显示
      this.timer = setInterval(() => {
        // 如果暂停，不执行
        if (this.isPaused) return

        const task = this.currentTask
        if (!task) {
          this.stop()
          return
        }

        // 增加索引
        task.currentIndex++

        // 更新显示
        const displayText = task.text.substring(0, task.currentIndex)
        task.element.textContent = displayText

        // 触发字符回调
        if (onChar) {
          onChar(displayText, task.currentIndex, task.totalLength)
        }

        // 触发进度回调
        if (this.callbacks.onProgress) {
          const progress = task.currentIndex / task.totalLength
          this.callbacks.onProgress(progress, displayText)
        }
        if (onProgress) {
          const progress = task.currentIndex / task.totalLength
          onProgress(progress, displayText)
        }

        // 完成
        if (task.currentIndex >= task.totalLength) {
          this.isCompleted = true
          this.isRunning = false
          clearInterval(this.timer)
          this.timer = null

          // 触发完成回调
          if (this.callbacks.onComplete) {
            this.callbacks.onComplete(task.text)
          }
          if (onComplete) {
            onComplete(task.text)
          }
          resolve(task.text)
        }
      }, actualSpeed)
    })
  }

  /**
   * 暂停打字机
   */
  pause() {
    if (!this.isRunning || this.isCompleted || this.isPaused) {
      return
    }
    this.isPaused = true
    if (this.callbacks.onPause) {
      const task = this.currentTask
      const progress = task ? task.currentIndex / task.totalLength : 0
      this.callbacks.onPause(progress)
    }
  }

  /**
   * 继续打字机
   */
  resume() {
    if (!this.isRunning || this.isCompleted || !this.isPaused) {
      return
    }
    this.isPaused = false
    if (this.callbacks.onResume) {
      const task = this.currentTask
      const progress = task ? task.currentIndex / task.totalLength : 0
      this.callbacks.onResume(progress)
    }
  }

  /**
   * 停止打字机
   */
  stop() {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    this.isRunning = false
    this.isPaused = false
    this.isCompleted = false
    this.currentTask = null

    if (this.callbacks.onStop) {
      this.callbacks.onStop()
    }
  }

  /**
   * 重置打字机
   */
  reset() {
    this.stop()
    if (this.currentTask && this.currentTask.element) {
      this.currentTask.element.textContent = ''
    }
    this.currentTask = null
  }

  /**
   * 跳到指定进度 (0-1)
   * @param {number} progress - 进度值 0-1
   */
  seek(progress) {
    const task = this.currentTask
    if (!task) return

    const targetIndex = Math.min(
      Math.floor(progress * task.totalLength),
      task.totalLength
    )
    task.currentIndex = targetIndex
    task.element.textContent = task.text.substring(0, targetIndex)

    if (targetIndex >= task.totalLength) {
      this.isCompleted = true
      this.isRunning = false
      if (this.timer) {
        clearInterval(this.timer)
        this.timer = null
      }
    }
  }

  /**
   * 获取当前状态
   */
  getStatus() {
    const task = this.currentTask
    return {
      isRunning: this.isRunning,
      isPaused: this.isPaused,
      isCompleted: this.isCompleted,
      progress: task ? task.currentIndex / task.totalLength : 0,
      currentIndex: task ? task.currentIndex : 0,
      totalLength: task ? task.totalLength : 0,
    }
  }

  /**
   * 设置回调函数
   * @param {Object} callbacks
   */
  on(callbacks) {
    this.callbacks = {
      ...this.callbacks,
      ...callbacks,
    }
    return this
  }

  /**
   * 设置速度
   * @param {number} speed - 每字符间隔(ms)
   */
  setSpeed(speed) {
    this.defaultSpeed = Math.max(this.minSpeed, Math.min(this.maxSpeed, speed))
    return this
  }

  /**
   * 销毁实例
   */
  destroy() {
    this.stop()
    this.currentTask = null
    this.callbacks = {}
  }
}

/**
 * 创建打字机实例（单例模式）
 */
let instance = null

export function createTypewriter(options = {}) {
  if (!instance) {
    instance = new Typewriter(options)
  }
  return instance
}

/**
 * 快速使用 - 在指定元素中显示打字机效果
 * @param {string|HTMLElement} element - 目标元素
 * @param {string} text - 要显示的文本
 * @param {Object} options - 配置项
 * @returns {Promise}
 */
export function typewriterToElement(element, text, options = {}) {
  const tw = new Typewriter(options)
  return tw.start(element, text, options)
}

/**
 * 快速使用 - 获取打字机效果的文本（纯文本模式）
 * @param {string} text - 要显示的文本
 * @param {Function} onChar - 每字符回调
 * @param {number} speed - 速度
 * @returns {Promise<string>}
 */
export function typewriterText(text, onChar, speed = 30) {
  return new Promise((resolve) => {
    let index = 0
    const total = text.length
    let result = ''

    if (!text || total === 0) {
      resolve(text)
      return
    }

    const actualSpeed = total < 20 ? Math.max(10, speed / 2) : speed

    const timer = setInterval(() => {
      index++
      result = text.substring(0, index)
      if (onChar) {
        onChar(result, index, total)
      }
      if (index >= total) {
        clearInterval(timer)
        resolve(text)
      }
    }, actualSpeed)
  })
}

/**
 * 批量打字机 - 多个元素依次显示
 * @param {Array} tasks - 任务列表 [{ element, text, speed }]
 * @param {Object} options - 全局配置
 * @returns {Promise}
 */
export function typewriterBatch(tasks, options = {}) {
  return new Promise(async (resolve) => {
    const tw = new Typewriter(options)
    for (const task of tasks) {
      await tw.start(task.element, task.text, {
        speed: task.speed || options.speed,
      })
    }
    tw.destroy()
    resolve()
  })
}

// 导出类本身，方便实例化
export default Typewriter