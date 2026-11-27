// src/views/main/resourceNav/codeInput.js
//========================代码编辑器===================
import { nextTick } from 'vue'

/**
 * 创建符合 IDE 习惯的代码编辑器快捷键处理函数
 * @param {Ref} modelRef - v-model 绑定的响应式对象
 * @param {String} fieldName - 需要更新的字段名
 * @returns {Function} keydown 事件处理函数
 */
export const createCodeKeydownHandler = (modelRef, fieldName = 'answer') => {
  // 定义成对符号
  const pairs = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'"
  }

  return (e) => {
    const textarea = e.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = modelRef.value[fieldName]

    // 辅助函数：更新值并设置光标
    const updateValue = (newValue, newCursorPos) => {
      modelRef.value[fieldName] = newValue
      nextTick(() => {
        textarea.selectionStart = textarea.selectionEnd = newCursorPos
      })
    }

    // ================= 1. Tab 键：插入 4 个空格 =================
    if (e.key === 'Tab') {
      e.preventDefault()
      const spaces = '    '
      const newValue = value.substring(0, start) + spaces + value.substring(end)
      updateValue(newValue, start + 4)
      return
    }

    // ================= 2. Enter 键：智能换行与缩进 =================
    if (e.key === 'Enter') {
      e.preventDefault()

      // 获取当前行内容
      const lastNewLineIndex = value.lastIndexOf('\n', start - 1)
      const currentLineStart = lastNewLineIndex + 1
      const currentLineContent = value.substring(currentLineStart, start)

      // 获取当前行前导空白（基础缩进）
      const indentMatch = currentLineContent.match(/^\s*/)
      const baseIndent = indentMatch ? indentMatch[0] : ''

      // 获取光标后的字符（去除中间可能的空格，看第一个有效字符）
      // 注意：这里我们只关心紧邻的下一个非空字符是否是闭合符号
      const textAfterCursor = value.substring(end)
      // 找到第一个非空白字符
      const nextNonWhitespaceChar = textAfterCursor.match(/\S/)?.[0]

      // 判断当前行末尾是否以开符号结尾（主要是 {）
      const trimmedLineEnd = currentLineContent.trimEnd()
      const lastChar = trimmedLineEnd.charAt(trimmedLineEnd.length - 1)

      let newIndent = baseIndent

      // 场景 A: 当前行以 { 结尾，且光标后紧跟 } (例如: { | } 或 { |  \n  } )
      // 行为: 换行，中间行缩进+1，} 换行到下一行并恢复原缩进
      if (lastChar === '{' && nextNonWhitespaceChar === '}') {

        // 1. 找到那个闭合符号 } 的确切索引
        const closeCharIndex = value.indexOf('}', end)

        if (closeCharIndex !== -1) {
          // 2. 构建新内容
          // 第一部分: 光标前的内容 (包含 { )
          const before = value.substring(0, start)

          // 第二部分: 新行的缩进 (比基础缩进多一级)
          const middleIndent = baseIndent + '    '

          // 第三部分: 闭合符号所在的行 (基础缩进 + } )
          const afterIndent = baseIndent
          const closeLine = '\n' + afterIndent + '}'

          // 第四部分: 闭合符号之后的所有内容
          const rest = value.substring(closeCharIndex + 1)

          // 组合: before + \n + middleIndent + \n + afterIndent + } + rest
          // 注意：这里我们插入了两个换行符，一个用于中间行，一个用于闭合符号行
          const newValue = before + '\n' + middleIndent + '\n' + afterIndent + '}' + rest

          // 光标位置: 在中间行的开头
          const newCursorPos = before.length + 1 + middleIndent.length

          updateValue(newValue, newCursorPos)
          return
        }
      }

      // 场景 B: 当前行以 { 结尾，但后面没有紧跟 } (例如: if () { | )
      // 行为: 换行，新行缩进+1
      if (lastChar === '{') {
        newIndent = baseIndent + '    '
      }

      // 场景 C: 普通回车，保持当前缩进
      const insertion = '\n' + newIndent
      const newValue = value.substring(0, start) + insertion + value.substring(end)

      updateValue(newValue, start + insertion.length)
      return
    }

    // ================= 3. 自动补全成对符号 =================
    if (pairs[e.key]) {
      e.preventDefault()
      const openChar = e.key
      const closeChar = pairs[e.key]

      // 如果选中了文本，则包裹文本
      if (start !== end) {
        const selectedText = value.substring(start, end)
        const newValue = value.substring(0, start) + openChar + selectedText + closeChar + value.substring(end)
        updateValue(newValue, start + 1 + selectedText.length + 1)
      } else {
        // 未选中文本，插入一对，光标在中间
        const newValue = value.substring(0, start) + openChar + closeChar + value.substring(end)
        updateValue(newValue, start + 1)
      }
      return
    }

    // ================= 4. Backspace: 智能删除 =================
    if (e.key === 'Backspace') {
      // 只有当没有选中文本时才触发特殊逻辑
      if (start === end && start > 0) {
        const charBefore = value.charAt(start - 1)
        const charAfter = value.charAt(start)

        // 逻辑 A: 智能删除成对符号 (如 "|)" -> 删除 () )
        if (pairs[charBefore] === charAfter) {
          e.preventDefault()
          const newValue = value.substring(0, start - 1) + value.substring(start + 1)
          updateValue(newValue, start - 1)
          return
        }

        // 逻辑 B: 智能删除缩进 (如果光标前是空格，且这些空格构成缩进的一部分)
        if (charBefore === ' ') {
          const lastNewLineIndex = value.lastIndexOf('\n', start - 1)
          const currentLineStart = lastNewLineIndex + 1
          const currentLineContentBeforeCursor = value.substring(currentLineStart, start)

          if (/^\s*$/.test(currentLineContentBeforeCursor)) {
            e.preventDefault()

            const indentUnit = 4
            const spacesToDelete = Math.min(indentUnit, currentLineContentBeforeCursor.length)

            const deleteStartPos = start - spacesToDelete
            const newValue = value.substring(0, deleteStartPos) + value.substring(start)

            updateValue(newValue, deleteStartPos)
            return
          }
        }
      }
    }
  }
}