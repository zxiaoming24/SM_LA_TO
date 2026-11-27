<!-- 移动端笔记组件 -->
<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { listNotesApi, createNoteApi, getNoteApi, updateNoteApi, deleteNoteApi, organizePreviewApi, exportNoteApi, uploadImageApi, searchNotesApi } from '@/api/mainApi/noteApi'

const router = useRouter()

// 用户ID
const userId = ref('')

// 页面状态：'list' 或 'detail'
const currentPage = ref('list')
const notes = ref([])
const currentNoteId = ref(null)
const noteTitle = ref('')
const searchQuery = ref('')
const aiPanelOpen = ref(false)
const aiLoading = ref(false)
const aiResult = ref(null)
const editorRef = ref(null)
const fileInputRef = ref(null)

const filteredNotes = ref([])

// 笔记内容变化检测
const originalContent = ref('')
const originalTitle = ref('')

// 图片预览
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// 关联笔记
const linkNoteVisible = ref(false)
const linkNoteSearchQuery = ref('')
const linkNoteList = ref([])

// 搜索过滤
watch(searchQuery, (val) => {
  if (!val.trim()) {
    filteredNotes.value = notes.value
  } else {
    filteredNotes.value = notes.value.filter(n =>
      (n.title || '').toLowerCase().includes(val.toLowerCase()) ||
      (n.summary || '').toLowerCase().includes(val.toLowerCase())
    )
  }
})

// 加载笔记列表
const loadNotes = async () => {
  if (!userId.value) return
  try {
    const res = await listNotesApi(userId.value)
    notes.value = res.notes || []
    filteredNotes.value = notes.value
  } catch (e) {
    console.error('加载笔记列表失败:', e)
    showToast('加载失败')
  }
}

// 选择笔记
const selectNote = async (noteId) => {
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      await showConfirmDialog({
        title: '提示',
        message: '当前笔记有未保存的更改，是否保存？',
        confirmButtonText: '保存',
        cancelButtonText: '不保存'
      })
      await saveNote()
    } catch (e) {
      // 用户点击"不保存"或关闭弹窗，继续执行
      originalContent.value = getEditorContent()
      originalTitle.value = noteTitle.value.trim() || '未命名笔记'
    }
  }
  
  currentNoteId.value = noteId
  try {
    const res = await getNoteApi(userId.value, noteId)
    const note = res.note
    noteTitle.value = note.title || ''
    aiResult.value = note.ai_organization_result || null
    aiPanelOpen.value = !!aiResult.value
    currentPage.value = 'detail'
    await nextTick()
    if (editorRef.value) {
      setEditorContent(note.content || '')
    }
    originalContent.value = getEditorContent()
    originalTitle.value = note.title || ''
  } catch (e) {
    showToast('加载笔记失败')
  }
}

// 新建笔记
const newNote = async () => {
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      await showConfirmDialog({
        title: '提示',
        message: '当前笔记有未保存的更改，是否保存？',
        confirmButtonText: '保存',
        cancelButtonText: '不保存'
      })
      await saveNote()
    } catch (e) {
      // 用户点击"不保存"或关闭弹窗，继续执行
      originalContent.value = getEditorContent()
      originalTitle.value = noteTitle.value.trim() || '未命名笔记'
    }
  }
  
  currentNoteId.value = null
  noteTitle.value = ''
  aiResult.value = null
  aiPanelOpen.value = false
  currentPage.value = 'detail'
  await nextTick()
  if (editorRef.value) {
    editorRef.value.innerHTML = ''
  }
  originalContent.value = getEditorContent()
  originalTitle.value = ''
}

// 检查是否有未保存的更改
const hasUnsavedChanges = () => {
  const currentContent = getEditorContent()
  const currentTitle = noteTitle.value.trim() || '未命名笔记'
  return currentContent !== originalContent.value || currentTitle !== originalTitle.value
}

// 返回列表
const goBack = async () => {
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      await showConfirmDialog({
        title: '提示',
        message: '当前笔记有未保存的更改，是否保存？',
        confirmButtonText: '保存',
        cancelButtonText: '不保存'
      })
      await saveNote()
    } catch (e) {
      // 用户点击"不保存"或关闭弹窗，继续返回列表
      originalContent.value = getEditorContent()
      originalTitle.value = noteTitle.value.trim() || '未命名笔记'
    }
  }
  currentPage.value = 'list'
  loadNotes()
}

// HTML转Markdown
const htmlToMarkdown = (html) => {
  if (!html) return ''
  let md = html
  md = md.replace(/<div[^>]*>/gi, '\n')
  md = md.replace(/<\/div>/gi, '\n')
  md = md.replace(/<p[^>]*>/gi, '')
  md = md.replace(/<\/p>/gi, '\n')
  md = md.replace(/<br\s*\/?>/gi, '\n')
  md = md.replace(/<span[^>]*>/gi, '')
  md = md.replace(/<\/span>/gi, '')
  md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, '# $1\n')
  md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, '## $1\n')
  md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, '### $1\n')
  md = md.replace(/<img[\s\S]*?(?:>|\/>)/gi, (tag) => {
    const srcMatch = tag.match(/src=["']([^"']*)["']/i)
    if (!srcMatch) return ''
    const src = srcMatch[1]
    const styleWidth = tag.match(/width\s*:\s*(\d+)\s*px/i)
    const attrWidth = tag.match(/\bwidth=["'](\d+)["']/i)
    const width = styleWidth ? styleWidth[1] : (attrWidth ? attrWidth[1] : null)
    if (width) {
      return `![image](${src} =${width}x)`
    }
    return `![image](${src})`
  })
  md = md.replace(/<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, '[$2]($1)')
  md = md.replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, '**$1**')
  md = md.replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, '**$1**')
  md = md.replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, '*$1*')
  md = md.replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, '*$1*')
  md = md.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, '`$1`')
  md = md.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi, '> $1\n')
  md = md.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, '- $1\n')
  md = md.replace(/<hr[^>]*\/?>/gi, '\n---\n')
  md = md.replace(/<[^>]+>/g, '')
  md = md.replace(/\n{3,}/g, '\n\n')
  return md.split('\n').map(line => line.trim()).join('\n').trim()
}

// 获取编辑器内容
const getEditorContent = () => {
  if (!editorRef.value) return ''
  return htmlToMarkdown(editorRef.value.innerHTML)
}

// Markdown转HTML
const markdownToHtml = (md) => {
  if (!md) return ''
  let html = md
  const imgPlaceholders = []
  html = html.replace(/!\[([^\]]*)\]\((\S+?)\s*=\s*(\d+)x\s*\)/g, (m, alt, url, w) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${url.trim()}" alt="image" loading="lazy" style="width:${w}px;max-width:100%;border-radius:6px;margin:8px 0;">`)
    return token
  })
  html = html.replace(/!\[([^\]]*)\]\((\S+)\)/g, (m, alt, url) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${url}" alt="image" loading="lazy" style="max-width:100%;border-radius:6px;margin:8px 0;">`)
    return token
  })
  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2>$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1>$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
  html = html.replace(/__IMG_(\d+)__/g, (m, idx) => imgPlaceholders[parseInt(idx)] || '')
  const lines = html.split('\n')
  const out = []
  for (const line of lines) {
    const t = line.trim()
    if (!t) continue
    if (/^<(h[1-6]|ul|\/ul|li|blockquote|\/blockquote|hr|img|p|code|a)/.test(t)) {
      out.push(t)
    } else {
      out.push('<p>' + t + '</p>')
    }
  }
  html = out.join('\n')
  html = html.replace(/<p><ul>/g, '<ul>')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p><li>/g, '<li>')
  html = html.replace(/<\/li><\/p>/g, '</li>')
  return html
}

// 设置编辑器内容
const setEditorContent = (markdown) => {
  if (editorRef.value) {
    editorRef.value.innerHTML = markdownToHtml(markdown)
  }
}

// 保存笔记
const saveNote = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) {
    showToast('请输入笔记内容')
    return
  }
  await doSaveNote(title, content, false)
}

// 保存笔记（内部）
const doSaveNote = async (title, content, useAi) => {
  try {
    if (useAi) {
      aiPanelOpen.value = true
      aiLoading.value = true
      aiResult.value = null
    }
    let res
    if (currentNoteId.value) {
      if (useAi) {
        res = await organizeNoteApi(userId.value, currentNoteId.value, { title, content })
        showToast('AI 整理并保存成功')
      } else {
        res = await updateNoteApi(userId.value, currentNoteId.value, { title, content })
        showToast('保存成功')
      }
    } else {
      res = await createNoteApi(userId.value, { title, content, use_ai: useAi })
      showToast(useAi ? 'AI 整理并创建成功' : '创建成功')
      currentNoteId.value = res.note.note_id
    }
    if (res.note) {
      noteTitle.value = res.note.title || title
      setEditorContent(res.note.content || content)
      if (res.note.ai_organization_result) {
        aiResult.value = res.note.ai_organization_result
        aiPanelOpen.value = true
      }
      originalContent.value = res.note.content || content
      originalTitle.value = res.note.title || title
    }
    await loadNotes()
  } catch (e) {
    console.error('保存笔记失败:', e)
    showToast('保存失败: ' + (e.message || '未知错误'))
  } finally {
    if (useAi) {
      aiLoading.value = false
    }
  }
}

// AI整理
const organizeNote = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) {
    showToast('请先输入笔记内容')
    return
  }

  if (!userId.value) {
    showToast('用户ID为空，请重新登录')
    return
  }

  if (!currentNoteId.value) {
    try {
      const createRes = await createNoteApi(userId.value, { title, content, use_ai: false })
      currentNoteId.value = createRes.note.note_id
    } catch (e) {
      console.error('创建笔记失败:', e)
      showToast('创建笔记失败: ' + (e.message || '未知错误'))
      return
    }
  }

  aiLoading.value = true
  try {
    const res = await organizePreviewApi(userId.value, currentNoteId.value, { title, content })
    const preview = res.preview
    if (preview) {
      const organizedContent = preview.organized_content || preview.content || content
      const organizedTitle = preview.organized_title || preview.title || title
      noteTitle.value = organizedTitle
      setEditorContent(organizedContent)
      if (preview.ai_result) {
        aiResult.value = preview.ai_result
        aiPanelOpen.value = true
      }
      originalContent.value = getEditorContent()
      originalTitle.value = organizedTitle
      // 同步更新到服务器
      await updateNoteApi(userId.value, currentNoteId.value, { title: organizedTitle, content: organizedContent })
    }
    showToast('AI 整理完成')
    await loadNotes()
  } catch (e) {
    console.error('AI 整理失败:', e)
    showToast('AI 整理失败: ' + (e.message || '未知错误'))
  } finally {
    aiLoading.value = false
  }
}

// 删除笔记
const deleteNote = async () => {
  if (!currentNoteId.value) return
  try {
    await showConfirmDialog({
      title: '删除笔记',
      message: '确定要删除这篇笔记吗？'
    })
    await deleteNoteApi(userId.value, currentNoteId.value)
    showToast('笔记已删除')
    currentNoteId.value = null
    noteTitle.value = ''
    aiResult.value = null
    aiPanelOpen.value = false
    currentPage.value = 'list'
    await loadNotes()
  } catch (e) {
    // 用户取消删除，不做任何操作
  }
}

// 导出笔记
const exportNote = async () => {
  if (!currentNoteId.value) return
  try {
    await showConfirmDialog({
      title: '导出笔记',
      message: '点击确定导出PDF，点击取消导出Word',
      confirmButtonText: 'PDF',
      cancelButtonText: 'Word'
    })
    await doExport('pdf')
  } catch (e) {
    // 用户点击取消，导出Word
    await doExport('docx')
  }
}

// 执行导出
const doExport = async (fmt) => {
  try {
    const res = await exportNoteApi(userId.value, currentNoteId.value, { note_id: currentNoteId.value, format: fmt })
    const blob = new Blob([res], { type: fmt === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `笔记.${fmt}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast(`导出 ${fmt.toUpperCase()} 成功`)
  } catch (e) {
    showToast('导出失败')
  }
}

// 上传图片
const uploadAttachment = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await uploadImageApi(formData)
    if (res.code !== 1) {
      throw new Error(res.msg || '上传失败')
    }
    const imageUrl = res.data
    showToast('上传成功')
    const editor = editorRef.value
    if (editor) {
      editor.appendChild(document.createElement('br'))
      if (file.type.startsWith('image/')) {
        const img = document.createElement('img')
        img.src = imageUrl
        img.alt = 'image'
        img.style.cssText = 'max-width:100%;border-radius:6px;margin:8px 0;'
        img.onclick = () => {
          previewImageUrl.value = imageUrl
          showImagePreview.value = true
        }
        editor.appendChild(img)
      } else {
        const a = document.createElement('a')
        a.href = imageUrl
        a.target = '_blank'
        a.rel = 'noopener'
        a.textContent = file.name
        editor.appendChild(a)
      }
      editor.appendChild(document.createElement('br'))
    }
    await autoSave()
    event.target.value = ''
  } catch (e) {
    showToast('上传失败')
    event.target.value = ''
  }
}

// 自动保存
const autoSave = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) return
  try {
    if (currentNoteId.value) {
      await updateNoteApi(userId.value, currentNoteId.value, { title, content })
      originalContent.value = content
      originalTitle.value = title
    } else {
      const res = await createNoteApi(userId.value, { title, content, use_ai: false })
      currentNoteId.value = res.note.note_id
      originalContent.value = content
      originalTitle.value = title
    }
    await loadNotes()
  } catch (e) {
    console.error('自动保存失败:', e)
  }
}

// 格式化时间
const formatTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return iso }
}

// 关联笔记
const openLinkNoteDialog = async () => {
  linkNoteSearchQuery.value = ''
  linkNoteVisible.value = true
  await fetchLinkNotes('')
}

const closeLinkNoteDialog = () => {
  linkNoteVisible.value = false
}

const fetchLinkNotes = async (query) => {
  try {
    const res = await searchNotesApi(userId.value, query)
    linkNoteList.value = res.notes || []
  } catch {
    linkNoteList.value = []
  }
}

const filterLinkNotes = () => {
  fetchLinkNotes(linkNoteSearchQuery.value)
}

const linkNote = async (noteId, title) => {
  if (!currentNoteId.value) {
    showToast('请先选择或创建一篇笔记')
    return
  }

  const linkText = `[[${title}]]\n`
  const currentContent = getEditorContent()
  const newContent = linkText + currentContent

  try {
    await updateNoteApi(userId.value, currentNoteId.value, {
      title: noteTitle.value.trim() || '未命名笔记',
      content: newContent
    })
    setEditorContent(newContent)
    originalContent.value = newContent
    showToast(`已关联笔记「${title}」`)
    await loadNotes()
  } catch (e) {
    showToast('保存失败')
    return
  }

  closeLinkNoteDialog()
}

// 返回上一页
const handleBack = () => {
  router.back()
}

// 初始化
onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser) {
        const id = loginUser.id
        userId.value = id ? (typeof id === 'string' ? id : String(id)) : ''
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  if (userId.value) {
    loadNotes()
  }
})
</script>

<template>
  <div class="phone-note">
    <!-- AI整理加载遮罩 -->
    <div v-if="aiLoading" class="ai-loading-overlay">
      <div class="ai-loading-content">
        <van-loading type="spinner" size="36px" color="var(--primary)" />
        <div class="ai-loading-text">AI 正在分析整理...</div>
      </div>
    </div>

    <!-- 固定顶部导航 -->
    <div class="note-header">
      <van-icon name="arrow-left" size="20" @click="currentPage === 'detail' ? goBack() : handleBack()" />
      <span class="header-title">{{ currentPage === 'list' ? '学习笔记' : (currentNoteId ? '编辑笔记' : '新建笔记') }}</span>
      <div class="header-placeholder"></div>
    </div>

    <!-- 页面一：笔记列表 -->
    <div class="page page-list" :class="{ active: currentPage === 'list' }">
      <div class="search-bar">
        <van-search v-model="searchQuery" placeholder="搜索笔记..." shape="round" />
      </div>
      <div class="note-list">
        <div v-if="filteredNotes.length === 0" class="empty-hint">
          <van-icon name="notes-o" size="48" color="var(--text-gray)" />
          <p>暂无笔记</p>
          <p class="sub">点击下方按钮开始记录</p>
        </div>
        <div
          v-for="note in filteredNotes"
          :key="note.note_id"
          class="note-card"
          @click="selectNote(note.note_id)"
        >
          <div class="card-header">
            <span class="card-title">{{ note.title || '未命名笔记' }}</span>
            <span v-if="note.has_ai_organized" class="ai-badge">AI</span>
          </div>
          <div v-if="note.knowledge_points && note.knowledge_points.length" class="card-tags">
            <span v-for="kp in note.knowledge_points.slice(0, 3)" :key="kp" class="tag">{{ kp }}</span>
            <span v-if="note.knowledge_points.length > 3" class="tag more">+{{ note.knowledge_points.length - 3 }}</span>
          </div>
          <div class="card-footer">
            <span class="card-time">{{ formatTime(note.updated_at || note.created_at) }}</span>
          </div>
        </div>
      </div>
      <div class="fab-btn" @click="newNote">+</div>
    </div>

    <!-- 页面二：笔记详情 -->
    <div class="page page-detail" :class="{ active: currentPage === 'detail' }">
      <div class="toolbar-bar">
        <van-button size="small" plain @click="fileInputRef?.click()">
          <van-icon name="photo-o" /> 图片
        </van-button>
        <van-button size="small" plain @click="openLinkNoteDialog">
          <van-icon name="link-o" /> 关联
        </van-button>
        <van-button size="small" plain @click="organizeNote">
          <van-icon name="fire-o" /> AI整理
        </van-button>
        <van-button size="small" :type="aiPanelOpen ? 'primary' : 'default'" plain @click="aiPanelOpen = !aiPanelOpen">
          <van-icon name="info-o" /> 结果
        </van-button>
        <input ref="fileInputRef" type="file" accept="image/*" style="display:none" @change="uploadAttachment" />
      </div>
      <div class="title-bar">
        <input v-model="noteTitle" type="text" placeholder="输入笔记标题..." />
      </div>
      <div class="editor-area">
        <div class="editor-div" ref="editorRef" contenteditable="true" data-placeholder="开始记录你的学习笔记..."></div>
      </div>
      <div class="bottom-actions">
        <van-button type="primary" block @click="saveNote">保存</van-button>
        <div class="action-row">
          <van-button size="small" plain @click="exportNote">导出</van-button>
          <van-button size="small" plain type="danger" @click="deleteNote">删除</van-button>
        </div>
      </div>

      <!-- AI整理面板（底部滑出） -->
      <div class="ai-drawer" :class="{ open: aiPanelOpen }">
        <div class="ai-drawer-handle" @click="aiPanelOpen = false">
          <div class="handle-bar"></div>
        </div>
        <div class="ai-drawer-body">
          <div v-if="aiLoading" class="loading">
            <van-loading type="spinner" />
            <span>AI 正在分析整理中...</span>
          </div>
          <div v-else-if="aiResult">
            <div v-if="aiResult.summary" class="summary-box">{{ aiResult.summary }}</div>
            <div v-if="aiResult.terms && aiResult.terms.length" class="section">
              <h4>术语补充</h4>
              <div v-for="t in aiResult.terms" :key="t.term" class="item">
                <div class="label">{{ t.term }}</div>
                <div class="desc">{{ t.explanation }}</div>
              </div>
            </div>
            <div v-if="aiResult.error_prone_points && aiResult.error_prone_points.length" class="section">
              <h4>易错点</h4>
              <div v-for="e in aiResult.error_prone_points" :key="e.point" class="item">
                <div class="label">{{ e.point }}</div>
                <div class="desc">{{ e.suggestion }}</div>
              </div>
            </div>
            <div v-if="aiResult.corrections && aiResult.corrections.length" class="section">
              <h4>错误纠正</h4>
              <div v-for="c in aiResult.corrections" :key="c.original" class="item">
                <div class="original">{{ c.original }}</div>
                <div class="corrected">{{ c.corrected }}</div>
              </div>
            </div>
          </div>
          <div v-else class="no-ai">暂无AI整理结果</div>
        </div>
      </div>
    </div>

    <!-- 关联笔记弹窗 -->
    <van-popup v-model:show="linkNoteVisible" position="bottom" round :style="{ height: '60%' }">
      <div class="link-note-popup">
        <div class="popup-header">
          <h3>关联笔记</h3>
          <van-icon name="cross" size="20" @click="closeLinkNoteDialog" />
        </div>
        <van-search v-model="linkNoteSearchQuery" placeholder="搜索笔记..." shape="round" @search="filterLinkNotes" />
        <div class="link-note-list">
          <div v-if="linkNoteList.length === 0" class="link-empty">
            <p>没有匹配的笔记</p>
          </div>
          <div
            v-for="note in linkNoteList"
            :key="note.note_id"
            class="link-note-item"
            :class="{ disabled: note.note_id === currentNoteId }"
            @click="note.note_id !== currentNoteId && linkNote(note.note_id, note.title)"
          >
            <div class="link-note-title">{{ note.title || '未命名笔记' }}</div>
            <div class="link-note-meta">
              <span v-if="note.has_ai_organized" class="ai-badge-sm">AI</span>
              <span>{{ formatTime(note.updated_at || note.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 图片预览 -->
    <van-image-preview v-model:show="showImagePreview" :images="[previewImageUrl]" />
  </div>
</template>

<style scoped>
.phone-note {
  position: relative;
  height: 100vh;
  background: var(--bg-page);
  overflow: hidden;
}

/* 固定顶部导航 */
.note-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  z-index: 100;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.header-placeholder {
  width: 20px;
}

/* AI整理加载遮罩 */
.ai-loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(2px);
}

.ai-loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  background: var(--bg-card);
  padding: 30px 40px;
  border-radius: 16px;
}

.ai-loading-text {
  color: var(--text-body);
  font-size: 14px;
  font-weight: 500;
}

/* 页面切换 */
.page {
  position: absolute;
  top: 56px;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.page-list {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
}

.page-list:not(.active) {
  transform: translateX(-100%);
  opacity: 0;
  pointer-events: none;
}

.page-detail {
  transform: translateX(100%);
  opacity: 0;
  pointer-events: none;
}

.page-detail.active {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
}

/* 搜索栏 */
.search-bar {
  flex-shrink: 0;
}

/* 笔记列表 */
.note-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 14px;
}

.empty-hint {
  text-align: center;
  padding: 60px 0;
  color: var(--text-gray);
}

.empty-hint p {
  margin: 8px 0 4px;
  font-size: 14px;
}

.empty-hint .sub {
  font-size: 12px;
  color: var(--text-gray);
}

.note-card {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--border-color);
}

.note-card:active {
  background: var(--bg-hover);
  transform: scale(0.98);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.ai-badge {
  background: var(--primary);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 8px;
  margin-left: 8px;
  flex-shrink: 0;
}

.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin: 6px 0;
}

.tag {
  background: var(--coming-bg-color);
  color: var(--coming);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}

.tag.more {
  background: var(--bg-hover);
  color: var(--text-gray);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
}

.card-time {
  font-size: 12px;
  color: var(--text-gray);
}

/* 新建按钮 */
.fab-btn {
  position: fixed;
  right: 20px;
  bottom: 100px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  border: none;
  font-size: 28px;
  font-weight: 300;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 50;
}

.fab-btn:active {
  background: var(--primary-hv);
  transform: scale(0.92);
}

/* 工具栏 */
.toolbar-bar {
  padding: 8px 12px;
  background: var(--bg-card);
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  overflow-x: auto;
}

.toolbar-bar::-webkit-scrollbar {
  display: none;
}

/* 标题栏 */
.title-bar {
  padding: 10px 14px;
  background: var(--bg-card);
}

.title-bar input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
  padding: 8px 0;
  border-bottom: 2px solid var(--border-color);
  transition: border-color 0.2s;
  box-sizing: border-box;
  background: transparent;
}

.title-bar input:focus {
  border-bottom-color: var(--primary);
}

/* 编辑器 */
.editor-area {
  flex: 1;
  overflow: hidden;
  background: var(--bg-card);
  position: relative;
}

.editor-div {
  width: 100%;
  height: 100%;
  padding: 14px;
  border: none;
  outline: none;
  overflow-y: auto;
  font-size: 15px;
  line-height: 1.7;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--text-body);
  box-sizing: border-box;
}

.editor-div:empty:before {
  content: attr(data-placeholder);
  color: var(--text-gray);
  pointer-events: none;
}

.editor-div img {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
  display: block;
}

.editor-div h1 { font-size: 20px; margin: 12px 0 6px; font-weight: 700; color: var(--text-title); }
.editor-div h2 { font-size: 17px; margin: 10px 0 4px; font-weight: 600; color: var(--text-title); }
.editor-div h3 { font-size: 15px; margin: 8px 0 4px; font-weight: 600; color: var(--text-title); }
.editor-div p { margin: 4px 0; min-height: 1.2em; }
.editor-div ul, .editor-div ol { padding-left: 20px; margin: 4px 0; }
.editor-div li { margin: 2px 0; }
.editor-div strong { font-weight: 700; }
.editor-div em { font-style: italic; }
.editor-div code {
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: Consolas, monospace;
}
.editor-div blockquote {
  border-left: 3px solid var(--primary);
  padding: 8px 12px;
  margin: 8px 0;
  background: var(--primary-light);
  border-radius: 0 8px 8px 0;
  font-size: 14px;
  color: var(--text-body);
}
.editor-div a { color: var(--primary); text-decoration: underline; }
.editor-div hr { border: none; border-top: 1px solid var(--border-color); margin: 12px 0; }

/* 底部操作区 */
.bottom-actions {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  padding: 12px 14px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  z-index: 10;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.action-row .van-button {
  flex: 1;
}

/* AI抽屉 */
.ai-drawer {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
  max-height: 50%;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.3s ease;
  z-index: 11;
}

.ai-drawer.open {
  transform: translateY(0);
}

.ai-drawer-handle {
  text-align: center;
  padding: 10px 0 6px;
  cursor: pointer;
}

.handle-bar {
  width: 40px;
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  margin: 0 auto;
}

.ai-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  font-size: 14px;
}

.loading {
  text-align: center;
  padding: 30px 0;
  color: var(--text-gray);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.no-ai {
  text-align: center;
  color: var(--text-gray);
  padding: 30px 0;
  font-size: 13px;
}

.summary-box {
  background: var(--primary-light);
  padding: 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-body);
  margin-bottom: 12px;
}

.section {
  margin-bottom: 14px;
}

.section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  margin: 0 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--primary-light);
}

.section .item {
  padding: 8px 10px;
  background: var(--bg-hover);
  border-radius: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.5;
}

.item .label { font-weight: 600; color: var(--text-title); }
.item .desc { color: var(--text-body); margin-top: 2px; }
.item .original { color: var(--main-delete); text-decoration: line-through; font-size: 12px; }
.item .corrected { color: var(--pass); font-size: 12px; }

/* 关联笔记弹窗 */
.link-note-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.popup-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
}

.popup-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.link-note-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.link-empty {
  text-align: center;
  padding: 30px 0;
  color: var(--text-gray);
  font-size: 13px;
}

.link-note-item {
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.link-note-item:active {
  background: var(--bg-hover);
}

.link-note-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.link-note-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-note-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-gray);
}

.ai-badge-sm {
  background: var(--primary);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
}
</style>
