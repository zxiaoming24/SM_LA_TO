<!-- 笔记本组件 -->
<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listNotesApi, createNoteApi, getNoteApi, updateNoteApi, deleteNoteApi, organizeNoteApi, exportNoteApi, uploadImageApi, searchNotesApi, getGraphDataApi, getKnowledgeUniverseApi, generateMindmapApi, organizePreviewApi } from '@/api/mainApi/noteApi'
import { Network, DataSet } from 'vis-network/standalone'
import NoteMindMap from './noteMindMap/NoteMindMap.vue'

const props = defineProps({
  visible: Boolean,
  userId: { type: String, required: true }
})

const emit = defineEmits(['close'])

// 页面状态：'list' 或 'detail'
const currentPage = ref('list')
const notes = ref([])
const currentNoteId = ref(null)
const noteTitle = ref('')
const kpInput = ref('')
const searchQuery = ref('')
const aiPanelOpen = ref(false)
const aiLoading = ref(false)
const aiResult = ref(null)
const editorRef = ref(null)
const fileInputRef = ref(null)
const selectedImage = ref(null)
const resizeHandleEl = ref(null)

const filteredNotes = ref([])

// 笔记内容变化检测
const originalContent = ref('')
const originalTitle = ref('')

// ==================== 笔记图谱相关 ====================
const graphVisible = ref(false)
const graphInfo = ref('')
const graphNodes = ref([])
const graphEdges = ref([])
const graphContainerRef = ref(null)
let graphNetwork = null

// 节点详情面板
const nodePanelVisible = ref(false)
const selectedNode = ref(null)

// 宇宙视图相关
const universeVisible = ref(false)
const universeCanvasRef = ref(null)
const universeBtnText = ref('切换为 ✨ 知识点宇宙')
let universeInstance = null

// ==================== 关联笔记相关 ====================
const linkNoteVisible = ref(false)
const linkNoteSearchQuery = ref('')
const linkNoteList = ref([])

// ==================== [[ 提及自动补全相关 ====================
const mentionVisible = ref(false)
const mentionSearchQuery = ref('')
const mentionResults = ref([])
const mentionSelectedIndex = ref(-1)
const mentionStartPos = ref(null) // { node, offset, endOffset }
const mentionJustInserted = ref(false) // 防止插入后重复触发

// ==================== 思维导图相关 ====================
const mindmapVisible = ref(false)
const mindmapData = ref(null)
const mindMapRef = ref(null)

// ==================== AI 整理 Diff 对比相关 ====================
const diffModalVisible = ref(false)
const diffLoading = ref(false)
const diffPreviewData = ref(null)
const diffStats = ref({ added: 0, removed: 0, total: 0 })
const diffLines = ref([])
const diffSummary = ref('')
const diffViewUnified = ref(false)

// 计算左右两侧的 diff 数据
const origDiffLines = computed(() => {
  const lines = []
  let lineNum = 1
  diffLines.value.forEach(d => {
    if (d.type === 'same') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'same' })
    } else if (d.type === 'removed') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'removed' })
    } else if (d.type === 'added') {
      lines.push({ lineNum: '&nbsp;', content: '&nbsp;', type: '' })
    }
  })
  return lines
})

const newDiffLines = computed(() => {
  const lines = []
  let lineNum = 1
  diffLines.value.forEach(d => {
    if (d.type === 'same') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'same' })
    } else if (d.type === 'removed') {
      lines.push({ lineNum: '&nbsp;', content: '&nbsp;', type: '' })
    } else if (d.type === 'added') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'added' })
    }
  })
  return lines
})

// 统一视图：展示AI整理后的内容，保留所有diff标记
const unifiedDiffLines = computed(() => {
  const lines = []
  let lineNum = 1
  diffLines.value.forEach(d => {
    if (d.type === 'same') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'same' })
    } else if (d.type === 'removed') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'removed' })
    } else if (d.type === 'added') {
      lines.push({ lineNum: lineNum++, content: d.line, type: 'added' })
    }
  })
  return lines
})

// 图片拖拽调整大小
let resizeState = null

const handleEditorClick = (e) => {
  if (selectedImage.value) {
    selectedImage.value.classList.remove('img-selected')
  }

  const img = e.target.closest('img')
  if (img && editorRef.value?.contains(img)) {
    selectedImage.value = img
    img.classList.add('img-selected')
    updateHandlePosition(img)
  } else {
    selectedImage.value = null
    if (resizeHandleEl.value) resizeHandleEl.value.style.display = 'none'
  }
}

const hideHandle = () => {
  if (resizeHandleEl.value) resizeHandleEl.value.style.display = 'none'
}

const handleEditorScroll = () => {
  if (selectedImage.value) {
    updateHandlePosition(selectedImage.value)
  }
}

const updateHandlePosition = (img) => {
  if (!resizeHandleEl.value) return
  const imgRect = img.getBoundingClientRect()
  const areaRect = resizeHandleEl.value.parentElement.getBoundingClientRect()
  resizeHandleEl.value.style.display = 'block'
  resizeHandleEl.value.style.left = (imgRect.right - areaRect.left - 10) + 'px'
  resizeHandleEl.value.style.top = (imgRect.bottom - areaRect.top - 10) + 'px'
}

const startResizeDrag = (e) => {
  e.preventDefault()
  e.stopPropagation()
  if (!selectedImage.value) return
  const img = selectedImage.value
  const startX = e.clientX
  const startWidth = img.getBoundingClientRect().width
  resizeState = { img, startX, startWidth }
  document.addEventListener('mousemove', onResizeDrag)
  document.addEventListener('mouseup', stopResizeDrag)
}

const onResizeDrag = (e) => {
  if (!resizeState) return
  const dx = e.clientX - resizeState.startX
  let newWidth = Math.max(40, resizeState.startWidth + dx)
  const editorWidth = editorRef.value ? editorRef.value.clientWidth - 28 : 400
  newWidth = Math.min(newWidth, editorWidth)
  resizeState.img.style.width = newWidth + 'px'
  resizeState.img.style.maxWidth = '100%'
  updateHandlePosition(resizeState.img)
}

const stopResizeDrag = () => {
  resizeState = null
  document.removeEventListener('mousemove', onResizeDrag)
  document.removeEventListener('mouseup', stopResizeDrag)
  autoSave()
}


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

watch(() => props.visible, (newVal) => {
  if (newVal && props.userId) {
    hideHandle()
    selectedImage.value = null
    currentPage.value = 'list'
    loadNotes()
  }
})

const loadNotes = async () => {
  if (!props.userId) return
  try {
    const res = await listNotesApi(props.userId)
    notes.value = res.notes || []
    filteredNotes.value = notes.value
  } catch (e) {
    console.error('加载笔记列表失败:', e)
  }
}

const selectNote = async (noteId) => {
  // 检查当前笔记是否有未保存的更改
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      const action = await ElMessageBox.confirm(
        '当前笔记有未保存的更改，是否保存？',
        '提示',
        {
          confirmButtonText: '保存',
          cancelButtonText: '不保存',
          type: 'warning',
          distinguishCancelAndClose: true
        }
      )
      if (action === 'confirm') {
        await saveNote()
      }
    } catch (e) {
      if (e === 'cancel') {
        // 用户选择不保存，更新原始内容以避免重复提示
        originalContent.value = getEditorContent()
        originalTitle.value = noteTitle.value.trim() || '未命名笔记'
      } else if (e !== 'close') {
        // 其他情况不执行任何操作
      }
    }
  }
  
  hideHandle()
  selectedImage.value = null
  currentNoteId.value = noteId
  try {
    const res = await getNoteApi(props.userId, noteId)
    const note = res.note
    noteTitle.value = note.title || ''
    aiResult.value = note.ai_organization_result || null
    aiPanelOpen.value = !!aiResult.value
    kpInput.value = ''
    currentPage.value = 'detail'
    await nextTick()
    await nextTick()
    if (editorRef.value) {
      setEditorContent(note.content || '')
    }
    // 保存当前内容作为原始内容（在设置编辑器内容后，获取实际的编辑器内容作为原始内容）
    originalContent.value = getEditorContent()
    originalTitle.value = note.title || ''
  } catch (e) {
    ElMessage.error('加载笔记失败: ' + e.message)
  }
}

const newNote = async () => {
  // 检查当前笔记是否有未保存的更改
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      const action = await ElMessageBox.confirm(
        '当前笔记有未保存的更改，是否保存？',
        '提示',
        {
          confirmButtonText: '保存',
          cancelButtonText: '不保存',
          type: 'warning',
          distinguishCancelAndClose: true
        }
      )
      if (action === 'confirm') {
        await saveNote()
      }
    } catch (e) {
      if (e === 'cancel') {
        // 用户选择不保存，更新原始内容以避免重复提示
        originalContent.value = getEditorContent()
        originalTitle.value = noteTitle.value.trim() || '未命名笔记'
      } else if (e !== 'close') {
        // 其他情况不执行任何操作
      }
    }
  }
  
  hideHandle()
  selectedImage.value = null
  currentNoteId.value = null
  noteTitle.value = ''
  aiResult.value = null
  aiPanelOpen.value = false
  currentPage.value = 'detail'
  await nextTick()
  await nextTick()
  if (editorRef.value) {
    editorRef.value.innerHTML = ''
  }
  // 新建笔记时重置原始内容
  originalContent.value = getEditorContent()
  originalTitle.value = ''
}

// 检查是否有未保存的更改
const hasUnsavedChanges = () => {
  const currentContent = getEditorContent()
  const currentTitle = noteTitle.value.trim() || '未命名笔记'
  return currentContent !== originalContent.value || currentTitle !== originalTitle.value
}

const goBack = async () => {
  // 检查当前笔记是否有未保存的更改
  if (currentPage.value === 'detail' && hasUnsavedChanges()) {
    try {
      const action = await ElMessageBox.confirm(
        '当前笔记有未保存的更改，是否保存？',
        '提示',
        {
          confirmButtonText: '保存',
          cancelButtonText: '不保存',
          type: 'warning',
          distinguishCancelAndClose: true
        }
      )
      if (action === 'confirm') {
        // 调用 saveNote 会弹出 AI 整理确认框，用户选择后自动保存
        await saveNote()
        // 保存完成后再返回列表
      }
    } catch (e) {
      if (e === 'cancel') {
        // 用户选择不保存，更新原始内容以避免重复提示，然后返回列表
        originalContent.value = getEditorContent()
        originalTitle.value = noteTitle.value.trim() || '未命名笔记'
      } else if (e !== 'close') {
        return
      }
    }
  }
  hideHandle()
  selectedImage.value = null
  currentPage.value = 'list'
  loadNotes()
}

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
  // 改进图片处理：匹配 <img> 标签，支持各种格式
  md = md.replace(/<img[\s\S]*?(?:>|\/>)/gi, (tag) => {
    const srcMatch = tag.match(/src=["']([^"']*)["']/i)
    if (!srcMatch) return ''
    const src = srcMatch[1]
    // 检查是否有宽度设置（style中的width或width属性）
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

const getEditorContent = () => {
  if (!editorRef.value) return ''
  return htmlToMarkdown(editorRef.value.innerHTML)
}

const markdownToHtml = (md) => {
  if (!md) return ''
  let html = md
  // 先用占位符替换图片（避免后续HTML转义破坏<img>标签）
  const imgPlaceholders = []
  html = html.replace(/!\[([^\]]*)\]\((\S+?)\s*=\s*(\d+)x\s*\)/g, (m, alt, url, w) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${url.trim()}" alt="image" loading="lazy" style="width:${w}px;max-width:100%;border-radius:6px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)">`)
    return token
  })
  html = html.replace(/!\[([^\]]*)\]\((\S+)\)/g, (m, alt, url) => {
    const token = `__IMG_${imgPlaceholders.length}__`
    imgPlaceholders.push(`<img src="${url}" alt="image" loading="lazy" style="max-width:100%;border-radius:6px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)">`)
    return token
  })
  // HTML转义（不会影响占位符）
  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^######\s+(.*)$/gm, '<h6>$1</h6>')
  html = html.replace(/^#####\s+(.*)$/gm, '<h5>$1</h5>')
  html = html.replace(/^####\s+(.*)$/gm, '<h4>$1</h4>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2>$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1>$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
  // 还原图片占位符（在分行处理之前，让占位符行也能被识别为块级元素）
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

const setEditorContent = (markdown) => {
  if (editorRef.value) {
    editorRef.value.innerHTML = markdownToHtml(markdown)
  }
}

const saveNote = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) {
    ElMessage.warning('请输入笔记内容')
    return
  }
  await doSaveNote(title, content, false)
}

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
        res = await organizeNoteApi(props.userId, currentNoteId.value, { title, content })
        ElMessage.success('AI 整理并保存成功！')
      } else {
        res = await updateNoteApi(props.userId, currentNoteId.value, { title, content })
        ElMessage.success('保存成功！')
      }
    } else {
      res = await createNoteApi(props.userId, { title, content, use_ai: useAi })
      ElMessage.success(useAi ? 'AI 整理并创建成功！' : '创建成功！')
      currentNoteId.value = res.note.note_id
    }
    if (res.note) {
      noteTitle.value = res.note.title || title
      setEditorContent(res.note.content || content)
      if (res.note.ai_organization_result) {
        aiResult.value = res.note.ai_organization_result
        aiPanelOpen.value = true
      }
      // 更新原始内容
      originalContent.value = res.note.content || content
      originalTitle.value = res.note.title || title
    }
    await loadNotes()
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    if (useAi) {
      aiLoading.value = false
    }
  }
}

// ==================== 思维导图功能 ====================
const openMindmap = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) {
    ElMessage.warning('请先输入笔记内容')
    return
  }
  mindmapData.value = null
  mindmapVisible.value = true
  document.body.style.overflow = 'hidden'
  
  try {
    const res = await generateMindmapApi(title, content)
    mindmapData.value = res.mindmap
  } catch (e) {
    ElMessage.error('生成思维导图失败: ' + e.message)
  }
}

const closeMindmap = () => {
  mindmapVisible.value = false
  mindmapData.value = null
  document.body.style.overflow = ''
}

// ==================== AI 整理 Diff 对比功能 ====================
const organizeNote = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) {
    ElMessage.warning('请先输入笔记内容')
    return
  }

  // 如果还没有 note_id，先创建
  if (!currentNoteId.value) {
    try {
      const createRes = await createNoteApi(props.userId, { title, content, use_ai: false })
      currentNoteId.value = createRes.note.note_id
    } catch (e) {
      ElMessage.error('创建笔记失败: ' + e.message)
      return
    }
  }

  aiLoading.value = true

  try {
    const res = await organizePreviewApi(props.userId, currentNoteId.value, { title, content })
    const preview = res.preview
    diffPreviewData.value = preview
    diffStats.value = {
      added: preview.diff_stats?.added || 0,
      removed: preview.diff_stats?.removed || 0,
      total: preview.diff_stats?.total_organized || 0
    }
    diffLines.value = preview.diff_lines || []
    diffSummary.value = preview.ai_result?.summary || ''
    diffViewUnified.value = false
    diffModalVisible.value = true
    document.body.style.overflow = 'hidden'
  } catch (e) {
    ElMessage.error('AI 整理失败: ' + e.message)
  } finally {
    aiLoading.value = false
  }
}

const closeDiffModal = () => {
  diffModalVisible.value = false
  diffPreviewData.value = null
  document.body.style.overflow = ''
}

const toggleDiffView = () => {
  diffViewUnified.value = !diffViewUnified.value
}

const acceptDiff = async () => {
  if (!diffPreviewData.value || !currentNoteId.value) return

  const title = diffPreviewData.value.organized_title || noteTitle.value.trim() || '未命名笔记'

  diffLoading.value = true
  try {
    const res = await organizeNoteApi(props.userId, currentNoteId.value, {
      title: title,
      organized_content: diffPreviewData.value.organized_content || diffPreviewData.value.organized,
      ai_result: diffPreviewData.value.ai_result
    })

    noteTitle.value = res.note.title || title
    setEditorContent(res.note.content || (diffPreviewData.value.organized_content || diffPreviewData.value.organized))
    aiResult.value = res.note.ai_organization_result
    aiPanelOpen.value = true

    closeDiffModal()
    ElMessage.success('✓ 已接受 AI 整理结果！')
    await loadNotes()
    originalContent.value = getEditorContent()
    originalTitle.value = res.note.title || title
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    diffLoading.value = false
  }
}

const rejectDiff = () => {
  closeDiffModal()
  ElMessage.info('已拒绝 AI 整理结果')
}

const deleteNote = async () => {
  if (!currentNoteId.value) return
  try {
    await ElMessageBox.confirm('确定要删除这篇笔记吗？', '删除笔记', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteNoteApi(props.userId, currentNoteId.value)
    ElMessage.success('笔记已删除')
    currentNoteId.value = null
    noteTitle.value = ''
    aiResult.value = null
    aiPanelOpen.value = false
    currentPage.value = 'list'
    await loadNotes()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + e.message)
    }
  }
}

const exportNote = async () => {
  if (!currentNoteId.value) return
  try {
    const action = await ElMessageBox.confirm('导出为 PDF 格式？\n点击「确定」导出 PDF，点击「取消」导出 Word', '导出笔记', {
      confirmButtonText: 'PDF',
      cancelButtonText: 'Word',
      type: 'info',
      distinguishCancelAndClose: true
    })
    await doExport('pdf')
  } catch (action) {
    if (action === 'cancel') {
      await doExport('docx')
    }
  }
}

const doExport = async (fmt) => {
  try {
    const res = await exportNoteApi(props.userId, currentNoteId.value, { note_id: currentNoteId.value, format: fmt })
    const blob = new Blob([res], { type: fmt === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `笔记.${fmt}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(`导出 ${fmt.toUpperCase()} 成功！`)
  } catch (e) {
    ElMessage.error('导出失败: ' + e.message)
  }
}

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
    ElMessage.success('上传成功！')
    const editor = editorRef.value
    if (editor) {
      editor.appendChild(document.createElement('br'))
      if (file.type.startsWith('image/')) {
        const img = document.createElement('img')
        img.src = imageUrl
        img.alt = 'image'
        img.style.cssText = 'max-width:100%;border-radius:6px;margin:8px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)'
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
    // 上传图片后自动保存
    await autoSave()
    event.target.value = ''
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
    event.target.value = ''
  }
}

// 自动保存（用于上传图片后等场景，不弹确认框）
const autoSave = async () => {
  const title = noteTitle.value.trim() || '未命名笔记'
  const content = getEditorContent()
  if (!content.trim()) return
  try {
    if (currentNoteId.value) {
      await updateNoteApi(props.userId, currentNoteId.value, { title, content })
      // 更新原始内容
      originalContent.value = content
      originalTitle.value = title
    } else {
      const res = await createNoteApi(props.userId, { title, content, use_ai: false })
      currentNoteId.value = res.note.note_id
      // 更新原始内容
      originalContent.value = content
      originalTitle.value = title
    }
    await loadNotes()
  } catch (e) {
    console.error('自动保存失败:', e)
  }
}

const formatTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return iso }
}

const handleClose = () => {
  emit('close')
}

// 拖拽移动笔记框
const phoneX = ref(0)
const phoneY = ref(0)
const phonePosInit = ref(false)
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragStartLeft = 0
let dragStartTop = 0

// 编辑器内容变化监听
let editorObserver = null

const initPhonePos = () => {
  if (!phonePosInit.value) {
    phoneX.value = (window.innerWidth - 390) / 2
    phoneY.value = (window.innerHeight - 680) / 2
    phonePosInit.value = true
  }
}

const startDrag = (e) => {
  // 只允许通过头部拖拽
  if (!e.currentTarget.classList.contains('phone-header')) return
  initPhonePos()
  isDragging = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragStartLeft = phoneX.value
  dragStartTop = phoneY.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

const onDrag = (e) => {
  if (!isDragging) return
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  phoneX.value = Math.max(0, Math.min(dragStartLeft + dx, window.innerWidth - 390))
  phoneY.value = Math.max(0, Math.min(dragStartTop + dy, window.innerHeight - 680))
}

const stopDrag = () => {
  isDragging = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 初始化编辑器内容监听器
const initEditorObserver = () => {
  if (editorObserver) {
    editorObserver.disconnect()
  }
  
  if (editorRef.value) {
    editorObserver = new MutationObserver(() => {
      // 当编辑器内容发生变化时，可以在这里执行相关逻辑
      // 目前我们只需要确保 hasUnsavedChanges 函数能正确工作
    })
    
    editorObserver.observe(editorRef.value, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style', 'class', 'src', 'alt']
    })
  }
}

onMounted(() => {
  if (props.visible && props.userId) {
    loadNotes()
    initPhonePos()
  }
  // 初始化编辑器监听器
  initEditorObserver()
})

watch(() => props.visible, (val) => {
  if (val) initPhonePos()
})

// 监听标题变化
watch(noteTitle, () => {
  // 标题变化也会导致未保存更改
}, { immediate: true })

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  // 清理编辑器监听器
  if (editorObserver) {
    editorObserver.disconnect()
    editorObserver = null
  }
  // 清理图谱
  if (graphNetwork) {
    graphNetwork.destroy()
    graphNetwork = null
  }
})

// ==================== 笔记图谱 ====================
const openGraph = async () => {
  graphVisible.value = true
  graphInfo.value = '加载中...'
  await nextTick()
  await nextTick()
  await loadGraph()
}

const closeGraph = () => {
  graphVisible.value = false
  nodePanelVisible.value = false
  selectedNode.value = null
  if (graphNetwork) {
    graphNetwork.destroy()
    graphNetwork = null
  }
}

const closeNodePanel = () => {
  nodePanelVisible.value = false
  selectedNode.value = null
}

const openNoteFromGraph = () => {
  if (selectedNode.value) {
    const noteId = selectedNode.value.note_id || selectedNode.value.id
    closeGraph()
    selectNote(noteId)
  }
}

const getContentPreview = (content) => {
  const text = content.replace(/[#*`>\-\[\]()]/g, '').replace(/!\[.*?\]\(.*?\)/g, '').trim()
  const lines = text.split('\n').filter(line => line.trim())
  const previewLines = lines.slice(0, 5)
  return previewLines.join('\n').slice(0, 200) + (text.length > 200 ? '...' : '')
}

const getMasteryColor = (level) => {
  const colors = [
    'rgba(136,136,153,0.8)',
    'rgba(74,222,128,0.9)',
    'rgba(96,165,250,0.9)',
    'rgba(251,146,60,0.9)',
    'rgba(244,114,182,0.9)',
  ]
  return colors[level] || colors[0]
}

const getMasteryProgress = (points) => {
  const KP_TARGET = 5
  return Math.min(100, Math.round((points / KP_TARGET) * 100))
}

const getMasteryGradient = (level) => {
  const colors = [
    'linear-gradient(90deg, rgba(136,136,153,0.8), rgba(255,255,255,0.6))',
    'linear-gradient(90deg, rgba(74,222,128,0.9), rgba(255,255,255,0.6))',
    'linear-gradient(90deg, rgba(96,165,250,0.9), rgba(255,255,255,0.6))',
    'linear-gradient(90deg, rgba(251,146,60,0.9), rgba(255,255,255,0.6))',
    'linear-gradient(90deg, rgba(244,114,182,0.9), rgba(255,255,255,0.6))',
  ]
  return colors[level] || colors[0]
}

const openLinkNote = async (noteId) => {
  try {
    const res = await getNoteApi(props.userId, noteId)
    if (res.note) {
      selectedNode.value = res.note
      if (graphNetwork) {
        graphNetwork.selectNodes([noteId])
        graphNetwork.focus(noteId, { scale: 1.3, animation: { duration: 500 } })
      }
    }
  } catch (e) {
    console.error('获取笔记详情失败:', e)
    ElMessage.error('获取笔记详情失败')
  }
}

const fitGraph = () => {
  if (graphNetwork) {
    graphNetwork.fit({ animation: true })
  }
}

const loadGraph = async () => {
  try {
    const res = await getGraphDataApi(props.userId)
    const data = res.data
    graphNodes.value = data.nodes || []
    graphEdges.value = data.edges || []

    graphInfo.value = `${graphNodes.value.length} 篇笔记 · ${graphEdges.value.length} 条链接`

    if (graphNodes.value.length === 0) {
      return
    }

    // 计算每个节点的连接数
    const linkCount = {}
    graphNodes.value.forEach(n => linkCount[n.id] = 0)
    graphEdges.value.forEach(e => {
      linkCount[e.source] = (linkCount[e.source] || 0) + 1
      linkCount[e.target] = (linkCount[e.target] || 0) + 1
    })
    const maxLinks = Math.max(1, ...Object.values(linkCount))

    // 构建 vis.js 节点
    const visNodes = graphNodes.value.map(n => {
      const count = linkCount[n.id] || 0
      const size = 12 + (count / maxLinks) * 20
      return {
        id: n.id,
        label: n.title || '未命名',
        title: `${n.title || '未命名'}\n📌 ${(n.knowledge_points || []).join(', ') || '无标签'}\n🔗 ${count} 条连接`,
        size: Math.max(14, Math.min(40, size)),
        color: n.has_ai_organized
          ? { background: '#667eea', border: '#8b9cf7', highlight: { background: '#764ba2', border: '#9b6fc0' } }
          : { background: '#2d2d4a', border: '#4a4a7a', highlight: { background: '#667eea', border: '#8b9cf7' } },
        font: { color: '#e0e0e0', size: 12, strokeWidth: 2, strokeColor: '#0f0f1a' },
        borderWidth: 2,
        shape: 'dot',
      }
    })

    // 构建 vis.js 边
    const visEdges = graphEdges.value.map(e => ({
      from: e.source,
      to: e.target,
      color: { color: 'rgba(102,126,234,0.35)', hover: 'rgba(102,126,234,0.8)', highlight: 'rgba(102,126,234,0.8)' },
      width: 1.5,
      hoverWidth: 3,
      smooth: { type: 'continuous' },
    }))

    const container = graphContainerRef.value
    if (!container) return
    container.innerHTML = ''

    const options = {
      nodes: { scaling: { min: 14, max: 40 } },
      edges: { arrows: { to: { enabled: false } } },
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -40,
          centralGravity: 0.005,
          springLength: 200,
          springConstant: 0.04,
          damping: 0.5,
        },
        stabilization: { iterations: 100 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        navigationButtons: false,
        zoomView: true,
        dragView: true,
      },
      layout: { improvedLayout: true },
    }

    graphNetwork = new Network(container, { nodes: new DataSet(visNodes), edges: new DataSet(visEdges) }, options)

    // 点击节点显示详情面板
    graphNetwork.on('click', async function(params) {
      if (params.nodes.length > 0) {
        const noteId = params.nodes[0]
        try {
          const res = await getNoteApi(props.userId, noteId)
          if (res.note) {
            selectedNode.value = res.note
            nodePanelVisible.value = true
          }
        } catch (e) {
          console.error('获取笔记详情失败:', e)
          ElMessage.error('获取笔记详情失败')
        }
      } else {
        nodePanelVisible.value = false
        selectedNode.value = null
      }
    })

    // 双击节点放大
    graphNetwork.on('doubleClick', function(params) {
      if (params.nodes.length > 0) {
        graphNetwork.focus(params.nodes[0], { scale: 1.5, animation: true })
      }
    })
  } catch (e) {
    graphInfo.value = '加载失败'
    ElMessage.error('图谱加载失败: ' + e.message)
  }
}

// ==================== 知识宇宙（3D立体版）（该行到1834左右） ====================
const toggleUniverseView = () => {
  const canvas = universeCanvasRef.value
  const graph = graphContainerRef.value
  if (!canvas || !graph) return

  if (universeVisible.value) {
    closeNodePanel()
    graph.style.display = ''
    canvas.style.display = 'none'
    universeBtnText.value = '切换为 ✨ 知识点宇宙'
    universeVisible.value = false
    if (universeInstance) {
      universeInstance.destroy()
      universeInstance = null
    }
    return
  }

  closeNodePanel()
  graph.style.display = 'none'
  canvas.style.display = 'block'
  universeBtnText.value = '切换为 🕸 笔记图谱'
  universeVisible.value = true

  if (!universeInstance) {
    universeInstance = new KnowledgeUniverse(canvas)
  }
  universeInstance.init(props.userId)
}

class KnowledgeUniverse {
  constructor(canvas) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')
    this.stars = []
    this.starMap = {}
    this.edges = []
    this.animId = null
    this.startTime = 0
    this.resizeObserver = null
    this.dpr = window.devicePixelRatio || 1
    this.W = 0
    this.H = 0

    this.cam = { x: 0, y: 0, z: 300 }
    this.camTarget = { x: 0, y: 0, z: 300 }
    this.rotX = 0.3
    this.rotY = 0
    this.rotXTarget = 0.3
    this.rotYTarget = 0

    this.autoRotate = true
    this.autoRotateSpeed = 0.0008

    this.dragging = false
    this.dragStart = { x: 0, y: 0 }
    this.dragRotStart = { x: 0.3, y: 0 }
    this.hasDragged = false

    this.draggingStar = null
    this.dragStarOffset = { x: 0, y: 0, z: 0 }

    this.hoveredStar = null
    this.clickedStar = null
    this.userInteracting = false

    this.bgStars = []
    this.focalLength = 300

    this._bgCanvas = null
    this._bgDirty = true

    this._lastHoverTime = 0
    this._hoverThrottleMs = 30
    this._colorCache = {}

    this.masteryColors = {
      0: { core: 'rgb(136,136,153)', glow: 'rgb(85,85,102)', label: '未接触' },
      1: { core: 'rgb(74,222,128)', glow: 'rgb(34,197,94)', label: '已了解' },
      2: { core: 'rgb(96,165,250)', glow: 'rgb(59,130,246)', label: '已理解' },
      3: { core: 'rgb(251,146,60)', glow: 'rgb(249,115,22)', label: '已应用' },
      4: { core: 'rgb(244,114,182)', glow: 'rgb(236,72,153)', label: '已掌握' },
    }

    this._starTypeConfig = [
      { name: 'dwarf', baseMul: 0.7, glowMul: 1.0, coronaMul: 1.2, lightOff: 0.25 },
      { name: 'mainseq', baseMul: 0.85, glowMul: 1.3, coronaMul: 1.5, lightOff: 0.3 },
      { name: 'bluewhite', baseMul: 1.0, glowMul: 1.6, coronaMul: 2.0, lightOff: 0.3 },
      { name: 'giant', baseMul: 1.15, glowMul: 2.0, coronaMul: 2.5, lightOff: 0.35 },
      { name: 'supergiant', baseMul: 1.3, glowMul: 2.5, coronaMul: 3.2, lightOff: 0.35 },
    ]

    this._masteryIcons = ['⚪', '🟢', '🔵', '🟠', '🟣']

    this._createTooltip()
    this._setupResize()
    this._resizeCanvas()
  }

  async init(userId) {
    this.startTime = performance.now()
    try {
      const res = await getKnowledgeUniverseApi(userId)
      const data = res.data || res
      if (!data.success && !data.stars) return

      this._buildData(data.stars || [], data.dependencies || [])
      this._generateBgStars()
      this._buildBgCanvas()
      this._bindEvents()
      this._startAnimation()
    } catch (e) {
      console.error('知识宇宙初始化失败:', e)
    }
  }

  destroy() {
    if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null }
    this._unbindEvents()
    if (this.tooltip) this.tooltip.style.opacity = '0'
    this._bgCanvas = null
  }

  _setupResize() {
    this.resizeObserver = new ResizeObserver(() => this._resizeCanvas())
    this.resizeObserver.observe(this.canvas.parentElement)
  }

  _resizeCanvas() {
    const parent = this.canvas.parentElement
    const w = parent.clientWidth
    const h = parent.clientHeight
    this.canvas.width = w * this.dpr
    this.canvas.height = h * this.dpr
    this.canvas.style.width = w + 'px'
    this.canvas.style.height = h + 'px'
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    this.W = w
    this.H = h
    this._bgDirty = true
  }

  _buildData(rawStars, deps) {
    const accentColors = [
      'rgb(168,85,247)', 'rgb(59,130,246)', 'rgb(6,182,212)',
      'rgb(16,185,129)', 'rgb(245,158,11)', 'rgb(239,68,68)',
      'rgb(236,72,153)', 'rgb(132,204,22)', 'rgb(139,92,246)',
      'rgb(249,115,22)', 'rgb(20,184,166)', 'rgb(244,63,94)',
      'rgb(99,102,241)', 'rgb(168,162,158)', 'rgb(34,197,94)',
    ]

    this.stars = rawStars.map((s, i) => {
      const level = Math.min(4, Math.max(0, s.mastery_level || 0))
      const points = s.mastery_points || 0
      const size = 4 + points * 1.5 + level * 1.5
      const star = {
        id: i,
        name: s.name,
        level: level,
        points: points,
        label: s.mastery_label || this.masteryColors[level].label,
        baseSize: Math.min(14, size),
        color: this.masteryColors[level],
        accent: accentColors[i % accentColors.length],
        x: 0, y: 0, z: 0,
        sx: 0, sy: 0, sScale: 1, sDepth: 0,
        pulsePhase: Math.random() * Math.PI * 2,
        connections: [],
        surfaceSpots: this._generateSurfaceSpots(),
        isBeingDragged: false,
      }
      this.starMap[s.name] = star
      return star
    })

    deps.forEach(d => {
      const a = this.starMap[d.knowledge_point]
      const b = this.starMap[d.prerequisite]
      if (a && b && a !== b) {
        if (!a.connections.includes(b)) a.connections.push(b)
        if (!b.connections.includes(a)) b.connections.push(a)
        this.edges.push({ from: a, to: b, edgePhase: Math.random() * Math.PI * 2 })
      }
    })

    this._forceLayout3D()
  }

  _generateSurfaceSpots() {
    const spots = []
    const count = 5 + Math.floor(Math.random() * 6)
    for (let i = 0; i < count; i++) {
      spots.push({
        angle: Math.random() * Math.PI * 2,
        dist: Math.random() * 0.7,
        r: 0.08 + Math.random() * 0.15,
        alpha: 0.05 + Math.random() * 0.15,
      })
    }
    return spots
  }

  _forceLayout3D() {
    const n = this.stars.length
    if (n === 0) return

    const spread = 150

    this.stars.forEach(s => {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = spread * Math.cbrt(Math.random())
      s.x = r * Math.sin(phi) * Math.cos(theta)
      s.y = r * Math.sin(phi) * Math.sin(theta)
      s.z = r * Math.cos(phi) * 0.6
    })

    for (let iter = 0; iter < 100; iter++) {
      const alpha = 0.4 * (1 - iter / 100)

      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const dx = this.stars[j].x - this.stars[i].x
          const dy = this.stars[j].y - this.stars[i].y
          const dz = this.stars[j].z - this.stars[i].z
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1
          const minDist = 100
          if (dist < minDist * 2.5) {
            const force = (minDist * minDist) / (dist * dist) * alpha * 0.3
            const fx = (dx / dist) * force
            const fy = (dy / dist) * force
            const fz = (dz / dist) * force
            this.stars[i].x -= fx; this.stars[i].y -= fy; this.stars[i].z -= fz
            this.stars[j].x += fx; this.stars[j].y += fy; this.stars[j].z += fz
          }
        }
      }

      this.edges.forEach(e => {
        const dx = e.to.x - e.from.x
        const dy = e.to.y - e.from.y
        const dz = e.to.z - e.from.z
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1
        const idealDist = 180
        const force = (dist - idealDist) / dist * alpha * 0.015
        e.from.x += dx * force; e.from.y += dy * force; e.from.z += dz * force
        e.to.x -= dx * force; e.to.y -= dy * force; e.to.z -= dz * force
      })

      this.stars.forEach(s => {
        s.x *= (1 - alpha * 0.01)
        s.y *= (1 - alpha * 0.01)
        s.z *= (1 - alpha * 0.015)
      })
    }
  }

  _generateBgStars() {
    this.bgStars = []
    const bgColors = [
      'rgb(180,200,255)', 'rgb(255,255,240)', 'rgb(255,240,200)', 'rgb(255,200,180)', 'rgb(200,210,255)',
    ]
    for (let i = 0; i < 500; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = 800 + Math.random() * 1500
      this.bgStars.push({
        x: r * Math.sin(phi) * Math.cos(theta),
        y: r * Math.sin(phi) * Math.sin(theta),
        z: r * Math.cos(phi),
        r: 0.3 + Math.random() * 1.2,
        alpha: 0.15 + Math.random() * 0.5,
        speed: 0.3 + Math.random() * 1.5,
        phase: Math.random() * Math.PI * 2,
        color: bgColors[Math.floor(Math.random() * bgColors.length)],
      })
    }
  }

  _buildBgCanvas() {
    const w = this.W
    const h = this.H
    if (w === 0 || h === 0) return
    this._bgCanvas = document.createElement('canvas')
    this._bgCanvas.width = w * this.dpr
    this._bgCanvas.height = h * this.dpr
    const bctx = this._bgCanvas.getContext('2d')
    bctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)

    const bg = bctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.7)
    bg.addColorStop(0, '#0e0e24')
    bg.addColorStop(0.3, '#0a0a1e')
    bg.addColorStop(0.6, '#0d0b28')
    bg.addColorStop(1, '#08061a')
    bctx.fillStyle = bg
    bctx.fillRect(0, 0, w, h)

    const nebulaConfigs = [
      { cx: w * 0.25, cy: h * 0.35, rx: w * 0.4, ry: h * 0.35, color: [80, 40, 140], alpha: 0.06 },
      { cx: w * 0.72, cy: h * 0.6, rx: w * 0.35, ry: h * 0.3, color: [30, 60, 130], alpha: 0.05 },
      { cx: w * 0.5, cy: h * 0.15, rx: w * 0.3, ry: h * 0.25, color: [120, 30, 80], alpha: 0.04 },
    ]
    nebulaConfigs.forEach(nb => {
      bctx.save()
      bctx.translate(nb.cx, nb.cy)
      bctx.scale(nb.rx / Math.max(nb.rx, nb.ry), nb.ry / Math.max(nb.rx, nb.ry))
      const g = bctx.createRadialGradient(0, 0, 0, 0, 0, Math.max(nb.rx, nb.ry))
      g.addColorStop(0, 'rgba(' + nb.color[0] + ',' + nb.color[1] + ',' + nb.color[2] + ',' + nb.alpha + ')')
      g.addColorStop(0.5, 'rgba(' + nb.color[0] + ',' + nb.color[1] + ',' + nb.color[2] + ',' + (nb.alpha * 0.4) + ')')
      g.addColorStop(1, 'rgba(0,0,0,0)')
      bctx.fillStyle = g
      bctx.beginPath()
      bctx.arc(0, 0, Math.max(nb.rx, nb.ry), 0, Math.PI * 2)
      bctx.fill()
      bctx.restore()
    })

    this._bgDirty = false
  }

  _createTooltip() {
    this.tooltip = document.createElement('div')
    this.tooltip.className = 'universe-tooltip'
    this.tooltip.style.cssText =
      'position:fixed;pointer-events:none;z-index:10000;' +
      'background:rgba(10,10,30,0.92);color:#e2e8f0;' +
      'border:1px solid rgba(139,92,246,0.4);border-radius:10px;' +
      'padding:10px 14px;font-size:13px;line-height:1.6;' +
      'box-shadow:0 4px 24px rgba(0,0,0,0.6),0 0 15px rgba(139,92,246,0.15);backdrop-filter:blur(10px);' +
      'opacity:0;transition:opacity 0.2s ease, transform 0.2s ease;' +
      'transform:translateY(4px);max-width:220px;'
    document.body.appendChild(this.tooltip)
  }

  _showTooltip(html, mx, my) {
    this.tooltip.innerHTML = html
    this.tooltip.style.opacity = '1'
    this.tooltip.style.transform = 'translateY(0)'
    this.tooltip.style.left = (mx + 15) + 'px'
    this.tooltip.style.top = (my - 10) + 'px'
  }

  _hideTooltip() {
    if (this.tooltip) {
      this.tooltip.style.opacity = '0'
      this.tooltip.style.transform = 'translateY(4px)'
    }
  }

  _rotate3D(x, y, z) {
    let cosY = Math.cos(this.rotY), sinY = Math.sin(this.rotY)
    let x1 = x * cosY - z * sinY
    let z1 = x * sinY + z * cosY
    let cosX = Math.cos(this.rotX), sinX = Math.sin(this.rotX)
    let y1 = y * cosX - z1 * sinX
    let z2 = y * sinX + z1 * cosX
    return { x: x1, y: y1, z: z2 }
  }

  _project(x, y, z) {
    const fov = this.focalLength
    const dist = this.cam.z - z
    if (dist < 10) return { sx: 0, sy: 0, scale: 0, depth: 0 }
    const scale = fov / dist
    return {
      sx: x * scale + this.W / 2 - this.cam.x * scale,
      sy: y * scale + this.H / 2 - this.cam.y * scale,
      scale: scale,
      depth: dist,
    }
  }

  _bindEvents() {
    this._unbindEvents()

    this._onMouseDown = (e) => {
      const rect = this.canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const hit = this._hitTest(mx, my)

      if (hit) {
        this.draggingStar = hit
        hit.isBeingDragged = true
        this.hasDragged = false
        this.dragStart = { x: e.clientX, y: e.clientY }
        this.dragStarOrigin = { x: hit.x, y: hit.y, z: hit.z }
        this.clickedStar = null
        this.userInteracting = true
        this.autoRotate = false
        this.canvas.style.cursor = 'grabbing'
        return
      }

      this.dragging = true
      this.hasDragged = false
      this.dragStart = { x: e.clientX, y: e.clientY }
      this.dragRotStart = { x: this.rotXTarget, y: this.rotYTarget }
      this.userInteracting = true
      this.autoRotate = false
    }

    this._onMouseMove = (e) => {
      const now = performance.now()
      const rect = this.canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top

      if (this.draggingStar) {
        const dx = e.clientX - this.dragStart.x
        const dy = e.clientY - this.dragStart.y
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) this.hasDragged = true
        
        const depth = this.cam.z - this.draggingStar.z
        if (depth < 10) return
        const scale = this.focalLength / depth
        
        const cosY = Math.cos(this.rotY), sinY = Math.sin(this.rotY)
        const cosX = Math.cos(this.rotX), sinX = Math.sin(this.rotX)
        
        const worldDx = dx / scale
        const worldDy = dy / scale
        
        const wx = worldDx * cosY + worldDy * sinX * sinY
        const wy = worldDy * cosX
        const wz = -worldDx * sinY + worldDy * sinX * cosY
        
        this.draggingStar.x = this.dragStarOrigin.x + wx
        this.draggingStar.y = this.dragStarOrigin.y + wy
        this.draggingStar.z = this.dragStarOrigin.z + wz
        return
      }

      if (this.dragging) {
        const dx = e.clientX - this.dragStart.x
        const dy = e.clientY - this.dragStart.y
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) this.hasDragged = true
        this.rotYTarget = this.dragRotStart.y + dx * 0.005
        this.rotXTarget = this.dragRotStart.x + dy * 0.005
        this.rotXTarget = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.rotXTarget))
        return
      }

      if (now - this._lastHoverTime < this._hoverThrottleMs) return
      this._lastHoverTime = now

      const hit = this._hitTest(mx, my)
      if (hit) {
        this.canvas.style.cursor = 'pointer'
        this.hoveredStar = hit
        const c = hit.color
        const icon = this._masteryIcons[hit.level] || '⚪'
        const connCount = hit.connections.length
        const html = '<div style="margin-bottom:4px"><strong style="color:' + c.core + ';font-size:14px">' + hit.name + '</strong></div>' +
          '<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">' +
          '<span style="font-size:16px">' + icon + '</span>' +
          '<span style="color:' + c.core + '">' + hit.label + '</span></div>' +
          '<div style="opacity:0.7">积分：' + hit.points.toFixed(1) + '</div>' +
          '<div style="opacity:0.5;font-size:11px">关联：' + connCount + ' 个知识点</div>'
        this._showTooltip(html, e.clientX, e.clientY)
      } else {
        this.canvas.style.cursor = 'grab'
        this.hoveredStar = null
        this._hideTooltip()
      }
    }

    this._onMouseUp = (e) => {
      if (this.draggingStar) {
        this.draggingStar.isBeingDragged = false
        if (!this.hasDragged) {
          this._onStarClick(this.draggingStar)
        }
        this.draggingStar = null
        this.userInteracting = false
        return
      }

      if (this.dragging && !this.hasDragged) {
        const rect = this.canvas.getBoundingClientRect()
        const mx = e.clientX - rect.left
        const my = e.clientY - rect.top
        const hit = this._hitTest(mx, my)
        if (hit) {
          this._onStarClick(hit)
        } else {
          closeNodePanel()
          this.clickedStar = null
          this.userInteracting = false
          this.autoRotate = true
        }
      }
      this.dragging = false
      this.userInteracting = false
      if (!this.clickedStar) {
        setTimeout(() => {
          if (!this.userInteracting && !this.clickedStar) this.autoRotate = true
        }, 3000)
      }
    }

    this._onDblClick = (e) => {
      const rect = this.canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const hit = this._hitTest(mx, my)
      if (hit) {
        this.clickedStar = hit
        this.autoRotate = false
        this._showStarDetail(hit)
      }
    }

    this._onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY > 0 ? 1.1 : 0.9
      this.camTarget.z = Math.max(50, Math.min(800, this.camTarget.z * factor))
      this.userInteracting = true
      this.autoRotate = false
      clearTimeout(this._autoRotateTimer)
      this._autoRotateTimer = setTimeout(() => {
        if (!this.clickedStar) this.autoRotate = true
        this.userInteracting = false
      }, 3000)
    }

    this._onKeyDown = (e) => {
      if (e.key === 'Escape') {
        this.camTarget = { x: 0, y: 0, z: 300 }
        this.clickedStar = null
        this.autoRotate = true
        this.userInteracting = false
        closeNodePanel()
      }
    }

    this.canvas.addEventListener('mousedown', this._onMouseDown)
    this.canvas.addEventListener('mousemove', this._onMouseMove)
    this.canvas.addEventListener('mouseup', this._onMouseUp)
    this.canvas.addEventListener('mouseleave', this._onMouseLeave = () => {
      this.dragging = false
      if (this.draggingStar) {
        this.draggingStar.isBeingDragged = false
        this.draggingStar = null
      }
      this._hideTooltip()
    })
    this.canvas.addEventListener('wheel', this._onWheel, { passive: false })
    this.canvas.addEventListener('dblclick', this._onDblClick)
    document.addEventListener('keydown', this._onKeyDown)
  }

  _unbindEvents() {
    if (this._onMouseDown) this.canvas.removeEventListener('mousedown', this._onMouseDown)
    if (this._onMouseMove) this.canvas.removeEventListener('mousemove', this._onMouseMove)
    if (this._onMouseUp) this.canvas.removeEventListener('mouseup', this._onMouseUp)
    if (this._onMouseLeave) this.canvas.removeEventListener('mouseleave', this._onMouseLeave)
    if (this._onWheel) this.canvas.removeEventListener('wheel', this._onWheel)
    if (this._onDblClick) this.canvas.removeEventListener('dblclick', this._onDblClick)
    if (this._onKeyDown) document.removeEventListener('keydown', this._onKeyDown)
  }

  _hitTest(mx, my) {
    const sorted = this.stars.slice().sort((a, b) => b.sDepth - a.sDepth)
    for (const s of sorted) {
      const dx = mx - s.sx
      const dy = my - s.sy
      const hitR = s.baseSize * s.sScale + 15
      if (dx * dx + dy * dy < hitR * hitR) return s
    }
    return null
  }

  _onStarClick(star) {
    this.clickedStar = star
    this.autoRotate = false
    this.userInteracting = true
    this._showStarDetail(star)
  }

  _showStarDetail(star) {
    selectedNode.value = {
      title: star.name,
      knowledge_points: [],
      mastery_level: star.level,
      mastery_points: star.points,
      mastery_label: star.label,
      connections: star.connections.map(c => ({ title: c.name, note_id: c.id, mastery_level: c.level, mastery_points: c.points, mastery_label: c.label })),
      relatedNotes: [],
    }
    nodePanelVisible.value = true
    this._loadRelatedNotes(star)
  }

  async _loadRelatedNotes(star) {
    try {
      const res = await listNotesApi(props.userId)
      const allNotes = (res.notes || [])
      const matched = allNotes.filter(n => {
        const kps = n.knowledge_points || []
        return kps.includes(star.name)
      })
      selectedNode.value.relatedNotes = matched
    } catch (err) {
      selectedNode.value.relatedNotes = []
    }
  }

  _startAnimation() {
    if (this.animId) cancelAnimationFrame(this.animId)
    const loop = (now) => {
      this.animId = requestAnimationFrame(loop)

      if (this.clickedStar) {
        const cr = this._rotate3D(this.clickedStar.x, this.clickedStar.y, this.clickedStar.z)
        this.camTarget.x = cr.x
        this.camTarget.y = cr.y
        this.camTarget.z = 150
      }

      const lerpSpeed = this.clickedStar ? 0.15 : 0.08
      this.cam.x += (this.camTarget.x - this.cam.x) * lerpSpeed
      this.cam.y += (this.camTarget.y - this.cam.y) * lerpSpeed
      this.cam.z += (this.camTarget.z - this.cam.z) * lerpSpeed

      this.rotX += (this.rotXTarget - this.rotX) * lerpSpeed
      this.rotY += (this.rotYTarget - this.rotY) * lerpSpeed

      if (this.autoRotate && !this.userInteracting && !this.clickedStar) {
        this.rotYTarget += this.autoRotateSpeed
      }

      this.stars.forEach(s => {
        const r = this._rotate3D(s.x, s.y, s.z)
        const p = this._project(r.x, r.y, r.z)
        s.sx = p.sx
        s.sy = p.sy
        s.sScale = p.scale
        s.sDepth = p.depth
      })

      this._render(now)
    }
    this.animId = requestAnimationFrame(loop)
  }

  _render(now) {
    const ctx = this.ctx
    const w = this.W
    const h = this.H
    const elapsed = (now - this.startTime) / 1000

    ctx.clearRect(0, 0, w, h)

    if (this._bgDirty || !this._bgCanvas) {
      this._buildBgCanvas()
    }
    if (this._bgCanvas) {
      ctx.drawImage(this._bgCanvas, 0, 0, w, h)
    }

    this.bgStars.forEach(s => {
      const r = this._rotate3D(s.x, s.y, s.z)
      const p = this._project(r.x, r.y, r.z)
      if (p.scale < 0.05) return
      const twinkle = 0.5 + 0.5 * Math.sin(elapsed * s.speed + s.phase)
      ctx.globalAlpha = s.alpha * twinkle * p.scale
      ctx.fillStyle = s.color
      ctx.beginPath()
      ctx.arc(p.sx, p.sy, s.r * p.scale, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.globalAlpha = 1

    const sortedStars = this.stars.slice().sort((a, b) => b.sDepth - a.sDepth)
    const sortedEdges = this.edges.slice().sort((a, b) => {
      const avgA = (a.from.sDepth + a.to.sDepth) / 2
      const avgB = (b.from.sDepth + b.to.sDepth) / 2
      return avgB - avgA
    })

    const focusStar = this.hoveredStar || this.clickedStar
    const connectedSet = new Set()
    if (focusStar) {
      connectedSet.add(focusStar)
      focusStar.connections.forEach(c => connectedSet.add(c))
    }

    sortedEdges.forEach(e => this._drawEdge3D(ctx, e, elapsed, focusStar, connectedSet))
    sortedStars.forEach(s => this._drawStar3D(ctx, s, elapsed, now, focusStar, connectedSet))

    ctx.save()
    ctx.textAlign = 'center'
    ctx.font = '12px "Microsoft YaHei", sans-serif'
    ctx.fillStyle = 'rgba(160,160,200,0.4)'
    ctx.fillText('拖拽旋转 · 滚轮缩放 · 点击星点查看 · 双击特写 · ESC复位 · 拖拽星点', w / 2, h - 16)
    ctx.restore()
  }

  _drawEdge3D(ctx, e, elapsed, focusStar, connectedSet) {
    const f = e.from, t = e.to
    const mx3d = (f.x + t.x) / 2
    const my3d = (f.y + t.y) / 2
    const mz3d = (f.z + t.z) / 2

    const dx = t.x - f.x, dy = t.y - f.y, dz = t.z - f.z
    const perpX = -dy * 0.08
    const perpY = dx * 0.08
    const perpZ = dz * 0.04

    const cpx = mx3d + perpX
    const cpy = my3d + perpY
    const cpz = mz3d + perpZ

    const rF = this._rotate3D(f.x, f.y, f.z)
    const pF = this._project(rF.x, rF.y, rF.z)
    const rT = this._rotate3D(t.x, t.y, t.z)
    const pT = this._project(rT.x, rT.y, rT.z)
    const rC = this._rotate3D(cpx, cpy, cpz)
    const pC = this._project(rC.x, rC.y, rC.z)

    if (pF.scale < 0.05 && pT.scale < 0.05) return

    const avgDepth = (f.sDepth + t.sDepth) / 2
    const depthFade = Math.max(0.15, Math.min(1, 300 / avgDepth))
    const avgScale = (pF.scale + pT.scale) / 2

    const isHighlighted = focusStar && (focusStar === f || focusStar === t)
    const isDimmed = focusStar && !isHighlighted

    const cFrgb = this._parseRgb(f.color.core)
    const cTrgb = this._parseRgb(t.color.core)

    const breathPhase = elapsed * 2.0 + e.edgePhase * Math.PI * 2
    const breathAlpha = 0.7 + 0.3 * Math.sin(breathPhase)

    ctx.save()

    {
      ctx.globalCompositeOperation = 'lighter'
      const glowAlpha = (isDimmed ? 0.03 : (isHighlighted ? 0.18 : 0.05)) * depthFade * breathAlpha
      const glowWidth = isDimmed ? 3 : (isHighlighted ? 10 : 4)
      const gGrad = ctx.createLinearGradient(pF.sx, pF.sy, pT.sx, pT.sy)
      gGrad.addColorStop(0, 'rgba(' + cFrgb.r + ',' + cFrgb.g + ',' + cFrgb.b + ',' + glowAlpha + ')')
      gGrad.addColorStop(1, 'rgba(' + cTrgb.r + ',' + cTrgb.g + ',' + cTrgb.b + ',' + glowAlpha + ')')
      ctx.beginPath()
      ctx.moveTo(pF.sx, pF.sy)
      ctx.quadraticCurveTo(pC.sx, pC.sy, pT.sx, pT.sy)
      ctx.strokeStyle = gGrad
      ctx.lineWidth = Math.max(2, glowWidth * avgScale * depthFade)
      ctx.stroke()
    }

    {
      ctx.globalCompositeOperation = 'lighter'
      const beamAlpha = (isDimmed ? 0.15 : (isHighlighted ? 0.7 : 0.25)) * depthFade * breathAlpha
      const beamWidth = isDimmed ? 0.8 : (isHighlighted ? 2.0 : 1.2)
      const bGrad = ctx.createLinearGradient(pF.sx, pF.sy, pT.sx, pT.sy)
      bGrad.addColorStop(0, 'rgba(' + cFrgb.r + ',' + cFrgb.g + ',' + cFrgb.b + ',' + beamAlpha + ')')
      bGrad.addColorStop(0.5, 'rgba(255,255,255,' + (beamAlpha * 0.9) + ')')
      bGrad.addColorStop(1, 'rgba(' + cTrgb.r + ',' + cTrgb.g + ',' + cTrgb.b + ',' + beamAlpha + ')')
      ctx.beginPath()
      ctx.moveTo(pF.sx, pF.sy)
      ctx.quadraticCurveTo(pC.sx, pC.sy, pT.sx, pT.sy)
      ctx.strokeStyle = bGrad
      ctx.lineWidth = Math.max(0.5, beamWidth * avgScale * depthFade)
      ctx.stroke()
    }

    if (isHighlighted && !isDimmed) {
      ctx.globalCompositeOperation = 'lighter'
      const coreAlpha = 0.4 * depthFade * breathAlpha
      const coreWidth = 0.6
      ctx.beginPath()
      ctx.moveTo(pF.sx, pF.sy)
      ctx.quadraticCurveTo(pC.sx, pC.sy, pT.sx, pT.sy)
      ctx.strokeStyle = 'rgba(255,255,255,' + coreAlpha + ')'
      ctx.lineWidth = Math.max(0.3, coreWidth * avgScale * depthFade)
      ctx.stroke()
    }

    if (isHighlighted && !isDimmed) {
      ctx.globalCompositeOperation = 'lighter'
      const pulseCount = 2
      const baseSpeed = 0.4
      for (let i = 0; i < pulseCount; i++) {
        const speed = baseSpeed * (0.8 + i * 0.3)
        const t01 = ((elapsed * speed + i / pulseCount + e.edgePhase) % 1)
        const mt = 1 - t01

        const px = mt * mt * pF.sx + 2 * mt * t01 * pC.sx + t01 * t01 * pT.sx
        const py = mt * mt * pF.sy + 2 * mt * t01 * pC.sy + t01 * t01 * pT.sy

        const pAlpha = 0.8 * depthFade * Math.sin(t01 * Math.PI)

        const dotR = 3 * avgScale * depthFade
        const dotGrad = ctx.createRadialGradient(px, py, 0, px, py, dotR)
        dotGrad.addColorStop(0, 'rgba(255,255,255,' + pAlpha + ')')
        const mr = Math.round(cFrgb.r * (1 - t01) + cTrgb.r * t01)
        const mg = Math.round(cFrgb.g * (1 - t01) + cTrgb.g * t01)
        const mb = Math.round(cFrgb.b * (1 - t01) + cTrgb.b * t01)
        dotGrad.addColorStop(0.3, 'rgba(' + mr + ',' + mg + ',' + mb + ',' + (pAlpha * 0.7) + ')')
        dotGrad.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.beginPath()
        ctx.arc(px, py, dotR, 0, Math.PI * 2)
        ctx.fillStyle = dotGrad
        ctx.fill()
      }
    }

    ctx.restore()
  }

  _drawStar3D(ctx, s, elapsed, now, focusStar, connectedSet) {
    const x = s.sx
    const y = s.sy
    const scale = s.sScale
    const baseR = s.baseSize * scale
    const c = s.color
    const accent = s.accent || c.core
    const level = s.level
    const cfg = this._starTypeConfig[level]

    const depthFade = Math.max(0.15, Math.min(1, 400 / s.sDepth))

    let brightMul = 1.0
    if (focusStar) {
      brightMul = connectedSet.has(s) ? 1.3 : 0.3
    }

    const pr = baseR * cfg.baseMul * (1 + 0.1 * Math.sin(elapsed * 1.5 + s.pulsePhase))
    const dragMul = s.isBeingDragged ? 1.3 : 1.0
    const finalR = pr * dragMul

    const accentRgb = this._parseRgb(accent)
    const coreRgb = this._parseRgb(c.core)

    ctx.save()

    ctx.globalCompositeOperation = 'lighter'
    const atmR = finalR * cfg.coronaMul
    const atmGrad = ctx.createRadialGradient(x, y, finalR * 0.8, x, y, atmR)
    const atmAlpha = (0.04 + level * 0.02) * depthFade * brightMul
    atmGrad.addColorStop(0, 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + (atmAlpha * 0.6) + ')')
    atmGrad.addColorStop(0.5, 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + (atmAlpha * 0.2) + ')')
    atmGrad.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.beginPath()
    ctx.arc(x, y, atmR, 0, Math.PI * 2)
    ctx.fillStyle = atmGrad
    ctx.fill()

    const coronaR = finalR * cfg.glowMul
    const coronaGrad = ctx.createRadialGradient(x, y, 0, x, y, coronaR)
    const coronaAlpha = (0.06 + level * 0.03) * depthFade * brightMul
    coronaGrad.addColorStop(0, 'rgba(' + coreRgb.r + ',' + coreRgb.g + ',' + coreRgb.b + ',' + coronaAlpha + ')')
    coronaGrad.addColorStop(0.4, 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + (coronaAlpha * 0.4) + ')')
    coronaGrad.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.beginPath()
    ctx.arc(x, y, coronaR, 0, Math.PI * 2)
    ctx.fillStyle = coronaGrad
    ctx.fill()

    if (level >= 4) {
      const ring2R = finalR * 2.8
      const ringGrad = ctx.createRadialGradient(x, y, finalR * 1.5, x, y, ring2R)
      const ringAlpha = 0.06 * depthFade * brightMul
      ringGrad.addColorStop(0, 'rgba(255,100,150,' + ringAlpha + ')')
      ringGrad.addColorStop(0.5, 'rgba(255,50,100,' + (ringAlpha * 0.3) + ')')
      ringGrad.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.beginPath()
      ctx.arc(x, y, ring2R, 0, Math.PI * 2)
      ctx.fillStyle = ringGrad
      ctx.fill()
    }

    ctx.globalCompositeOperation = 'source-over'
    const lightOffX = -finalR * cfg.lightOff
    const lightOffY = -finalR * cfg.lightOff
    const sphereGrad = ctx.createRadialGradient(
      x + lightOffX, y + lightOffY, finalR * 0.05,
      x, y, finalR
    )

    const sphereAlpha = depthFade * brightMul
    const mixR = Math.round(accentRgb.r * 0.7 + coreRgb.r * 0.3)
    const mixG = Math.round(accentRgb.g * 0.7 + coreRgb.g * 0.3)
    const mixB = Math.round(accentRgb.b * 0.7 + coreRgb.b * 0.3)
    sphereGrad.addColorStop(0, 'rgba(255,255,255,' + (0.95 * sphereAlpha) + ')')
    sphereGrad.addColorStop(0.15, 'rgba(' + Math.min(255, mixR + 60) + ',' + Math.min(255, mixG + 60) + ',' + Math.min(255, mixB + 60) + ',' + (0.9 * sphereAlpha) + ')')
    sphereGrad.addColorStop(0.5, 'rgba(' + mixR + ',' + mixG + ',' + mixB + ',' + (0.85 * sphereAlpha) + ')')
    sphereGrad.addColorStop(0.85, 'rgba(' + Math.round(mixR * 0.4) + ',' + Math.round(mixG * 0.4) + ',' + Math.round(mixB * 0.4) + ',' + (0.7 * sphereAlpha) + ')')
    sphereGrad.addColorStop(1, 'rgba(' + Math.round(mixR * 0.15) + ',' + Math.round(mixG * 0.15) + ',' + Math.round(mixB * 0.15) + ',' + (0.4 * sphereAlpha) + ')')

    ctx.beginPath()
    ctx.arc(x, y, finalR, 0, Math.PI * 2)
    ctx.fillStyle = sphereGrad
    ctx.fill()

    if (finalR > 3) {
      ctx.globalCompositeOperation = 'source-over'
      s.surfaceSpots.forEach(spot => {
        const sx2 = x + Math.cos(spot.angle) * spot.dist * finalR
        const sy2 = y + Math.sin(spot.angle) * spot.dist * finalR
        const spotR = spot.r * finalR
        ctx.beginPath()
        ctx.arc(sx2, sy2, spotR, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(0,0,0,' + (spot.alpha * sphereAlpha * 0.5) + ')'
        ctx.fill()
      })
    }

    ctx.globalCompositeOperation = 'lighter'
    const edgeGrad = ctx.createRadialGradient(x, y, finalR * 0.85, x, y, finalR * 1.1)
    const edgeAlpha = 0.15 * depthFade * brightMul
    edgeGrad.addColorStop(0, 'rgba(0,0,0,0)')
    edgeGrad.addColorStop(0.5, 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + edgeAlpha + ')')
    edgeGrad.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.beginPath()
    ctx.arc(x, y, finalR * 1.1, 0, Math.PI * 2)
    ctx.fillStyle = edgeGrad
    ctx.fill()

    if (level >= 3 && brightMul > 0.5) {
      const flareLen = finalR * (2.5 + level * 0.5)
      const flareAlpha = (0.08 + (level - 3) * 0.04) * depthFade * brightMul
      ctx.globalCompositeOperation = 'lighter'
      ctx.strokeStyle = 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + flareAlpha + ')'
      ctx.lineWidth = Math.max(0.5, 0.8 * scale)
      ctx.beginPath()
      ctx.moveTo(x - flareLen, y)
      ctx.lineTo(x + flareLen, y)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(x, y - flareLen)
      ctx.lineTo(x, y + flareLen)
      ctx.stroke()
      const diagLen = flareLen * 0.6
      ctx.strokeStyle = 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + (flareAlpha * 0.4) + ')'
      ctx.beginPath()
      ctx.moveTo(x - diagLen, y - diagLen)
      ctx.lineTo(x + diagLen, y + diagLen)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(x + diagLen, y - diagLen)
      ctx.lineTo(x - diagLen, y + diagLen)
      ctx.stroke()
    }

    ctx.restore()

    if (depthFade > 0.35 && brightMul > 0.4) {
      ctx.save()
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      const labelAlpha = (0.5 + level * 0.15) * depthFade * brightMul
      const fontSize = Math.max(9, Math.min(14, (10 + level * 1) * scale))
      ctx.font = fontSize + 'px "Microsoft YaHei", sans-serif'

      ctx.strokeStyle = 'rgba(255,255,255,0.1)'
      ctx.lineWidth = 3
      ctx.lineJoin = 'round'
      ctx.strokeText(s.name, x, y + finalR + 14)

      ctx.fillStyle = 'rgba(' + accentRgb.r + ',' + accentRgb.g + ',' + accentRgb.b + ',' + labelAlpha + ')'
      ctx.fillText(s.name, x, y + finalR + 14)
      ctx.restore()
    }
  }

  _parseRgb(color) {
    if (this._colorCache[color]) return this._colorCache[color]
    let r = 128, g = 128, b = 128
    if (color.startsWith('rgb(') || color.startsWith('rgba(')) {
      const m = color.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
      if (m) { r = +m[1]; g = +m[2]; b = +m[3] }
    } else if (color.startsWith('#')) {
      r = parseInt(color.slice(1, 3), 16)
      g = parseInt(color.slice(3, 5), 16)
      b = parseInt(color.slice(5, 7), 16)
    }
    const result = { r: r, g: g, b: b }
    this._colorCache[color] = result
    return result
  }

  _hexToRgba(color, alpha) {
    if (color.startsWith('rgb(')) {
      return color.replace('rgb(', 'rgba(').replace(')', ',' + alpha + ')')
    }
    if (color.startsWith('rgba(')) {
      return color.replace(/,\s*[\d.]+\)$/, ',' + alpha + ')')
    }
    const rgb = this._parseRgb(color)
    return 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')'
  }
}

// ==================== 关联笔记 ====================
const openLinkNoteDialog = async () => {
  linkNoteSearchQuery.value = ''
  linkNoteVisible.value = true
  await nextTick()
  await fetchLinkNotes('')
}

const closeLinkNoteDialog = () => {
  linkNoteVisible.value = false
}

const fetchLinkNotes = async (query) => {
  try {
    const res = await searchNotesApi(props.userId, query)
    linkNoteList.value = res.notes || []
  } catch (e) {
    linkNoteList.value = []
  }
}

const filterLinkNotes = () => {
  fetchLinkNotes(linkNoteSearchQuery.value)
}

const linkNote = async (noteId, title) => {
  if (!currentNoteId.value) {
    ElMessage.warning('请先选择或创建一篇笔记')
    return
  }

  // 在当前笔记内容最顶部插入 [[其它笔记标题]]
  const linkText = `[[${title}]]\n`
  const currentContent = getEditorContent()
  const newContent = linkText + currentContent

  // 立即保存
  try {
    await updateNoteApi(props.userId, currentNoteId.value, {
      title: noteTitle.value.trim() || '未命名笔记',
      content: newContent
    })
    // 更新编辑器内容和原始内容
    setEditorContent(newContent)
    originalContent.value = newContent
    ElMessage.success(`已关联笔记「${title}」`)
    await loadNotes()
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
    return
  }

  closeLinkNoteDialog()
}

// ==================== [[ 提及自动补全 ====================
// 提及下拉框位置计算
const mentionDropdownStyle = computed(() => {
  if (!mentionStartPos.value || !editorRef.value) {
    return { display: 'none' }
  }
  const { node, offset } = mentionStartPos.value
  const sel = window.getSelection()
  if (!sel.rangeCount) return { display: 'none' }

  // 创建临时range定位到[[位置
  const range = document.createRange()
  range.setStart(node, offset)
  range.collapse(true)
  const rect = range.getBoundingClientRect()

  const left = Math.max(4, Math.min(rect.left, window.innerWidth - 220))
  const top = rect.bottom + 4

  return {
    left: left + 'px',
    top: top + 'px',
    display: 'block'
  }
})

const hideMention = () => {
  mentionVisible.value = false
  mentionResults.value = []
  mentionSelectedIndex.value = -1
  mentionStartPos.value = null
}

const fetchAndShowMention = async (query) => {
  try {
    const res = await searchNotesApi(props.userId, query)
    mentionResults.value = res.notes || []
  } catch {
    mentionResults.value = []
  }
}

const selectMention = (index) => {
  if (index < 0 || index >= mentionResults.value.length) return
  const title = mentionResults.value[index].title
  if (!mentionVisible.value || !mentionStartPos.value || !editorRef.value) return

  const { node, offset, endOffset } = mentionStartPos.value
  const text = node.textContent
  // 替换 [[query 为 [[title]]
  const newText = text.substring(0, offset) + '[[' + title + ']]' + text.substring(endOffset)
  node.textContent = newText

  // 将光标移到 ]] 后面
  const sel = window.getSelection()
  const newPos = offset + title.length + 4
  const newRange = document.createRange()
  newRange.setStart(node, Math.min(newPos, newText.length))
  newRange.collapse(true)
  sel.removeAllRanges()
  sel.addRange(newRange)

  mentionJustInserted.value = true
  setTimeout(() => { mentionJustInserted.value = false }, 100)

  // 触发 editor 的 input 事件
  editorRef.value.dispatchEvent(new Event('input', { bubbles: true }))

  hideMention()
}

const detectMention = () => {
  if (!editorRef.value) return
  const sel = window.getSelection()
  if (!sel.rangeCount) { hideMention(); return }

  const range = sel.getRangeAt(0)
  const node = range.startContainer

  if (node.nodeType !== Node.TEXT_NODE) { hideMention(); return }

  const text = node.textContent
  const pos = range.startOffset
  const before = text.substring(0, pos)

  const match = before.match(/\[\[([^\]]*)$/)
  if (match) {
    const newQuery = match[1]
    const wasInactive = !mentionVisible.value
    const changed = newQuery !== mentionSearchQuery.value
    mentionVisible.value = true
    mentionStartPos.value = { node, offset: pos - match[0].length, endOffset: pos }
    mentionSearchQuery.value = newQuery
    mentionSelectedIndex.value = -1

    if (wasInactive || changed) fetchAndShowMention(mentionSearchQuery.value)
  } else {
    hideMention()
  }
}

// 编辑器键盘事件处理 [[ 提及
const handleEditorKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }

  // [[ 提及键盘导航
  if (mentionVisible.value) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      mentionSelectedIndex.value = Math.min(mentionSelectedIndex.value + 1, mentionResults.value.length - 1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      mentionSelectedIndex.value = Math.max(mentionSelectedIndex.value - 1, 0)
    } else if (e.key === 'Enter' && mentionSelectedIndex.value >= 0) {
      e.preventDefault()
      selectMention(mentionSelectedIndex.value)
    } else if (e.key === 'Escape') {
      hideMention()
    }
  }
}

// 编辑器输入事件 - 检测 [[
const handleEditorInput = () => {
  detectMention()
}
</script>

<template>
  <div v-if="visible" class="notebook-phone" :style="{ left: phoneX + 'px', top: phoneY + 'px' }">
    <!-- AI整理加载遮罩 -->
    <div v-if="aiLoading" class="ai-loading-overlay">
      <div class="ai-loading-content">
        <div class="ai-loading-spinner"></div>
        <div class="ai-loading-text">AI 正在分析整理...</div>
      </div>
    </div>
    <!-- 页面一：笔记列表 -->
    <div class="page page-list" :class="{ active: currentPage === 'list' }">
      <div class="phone-header" @mousedown="startDrag">
        <h2>学习笔记</h2>
        <div class="header-actions">
          <button class="icon-btn graph-btn" @click="openGraph" title="查看笔记关系">
            <span class="graph-icon">🌀</span>
            <span class="graph-text">查看笔记关系</span>
          </button>
          <button class="icon-btn" @click="handleClose">×</button>
        </div>
      </div>
        <div class="search-bar">
          <input v-model="searchQuery" type="text" placeholder="搜索笔记..." />
        </div>
        <div class="note-list">
          <div v-if="filteredNotes.length === 0" class="empty-hint">
            <div class="empty-icon"><svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg></div>
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
        <button class="fab-btn" @click="newNote">+ 新建笔记</button>
      </div>

      <!-- 页面二：笔记详情 -->
      <div class="page page-detail" :class="{ active: currentPage === 'detail' }">
        <div class="phone-header" @mousedown="startDrag">
          <button class="back-btn" @click="goBack">&#8249; 返回</button>
          <div class="detail-actions">
            <button class="text-btn sm" @click="saveNote">保存</button>
            <button class="text-btn sm" @click="exportNote">导出</button>
            <button class="text-btn sm danger" @click="deleteNote">删除</button>
          </div>
        </div>
        <div class="title-bar">
          <input v-model="noteTitle" type="text" placeholder="输入笔记标题..." />
        </div>
        <div class="toolbar-bar">
          <button @click="fileInputRef?.click()">插入图片</button>
          <button @click="openLinkNoteDialog" title="关联笔记">🔗 关联</button>
          <button @click="openMindmap" title="以思维导图查看">🧠 导图</button>
          <button @click="organizeNote">AI整理</button>
          <button @click="aiPanelOpen = !aiPanelOpen" :class="{ active: aiPanelOpen }">整理结果</button>
          <input ref="fileInputRef" type="file" accept="image/*" style="display:none" @change="uploadAttachment" />
        </div>
        <div class="editor-area">
          <div class="editor-div" ref="editorRef" contenteditable="true" data-placeholder="开始记录你的学习笔记..." @click="handleEditorClick" @scroll="handleEditorScroll" @keydown="handleEditorKeydown" @input="handleEditorInput">
          </div>
          <!-- 图片调整大小圆圈（放在editor-area内，editor-div外） -->
          <div class="img-resize-handle" ref="resizeHandleEl" style="display: none;" @mousedown="startResizeDrag"></div>
          <!-- 关联笔记弹窗 -->
          <div v-if="linkNoteVisible" class="note-link-popover">
            <div class="note-link-header">
              <h3>🔗 关联笔记</h3>
              <button class="close-btn" @click="closeLinkNoteDialog">×</button>
            </div>
            <div class="note-link-search">
              <input v-model="linkNoteSearchQuery" type="text" placeholder="搜索笔记..." @input="filterLinkNotes" />
            </div>
            <div class="note-link-list">
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
        </div>
        <!-- AI整理面板（底部滑出） -->
        <div class="ai-drawer" :class="{ open: aiPanelOpen }">
          <div class="ai-drawer-handle" @click="aiPanelOpen = false">
            <div class="handle-bar"></div>
          </div>
          <div class="ai-drawer-header">
          </div>
          <div class="ai-drawer-body">
            <div v-if="aiLoading" class="loading">
              <div class="spinner"></div>
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

      <!-- [[ 提及自动补全下拉 -->
      <div v-if="mentionVisible && mentionResults.length > 0" class="mention-dropdown" :style="mentionDropdownStyle">
          <div
            v-for="(note, index) in mentionResults"
            :key="note.note_id"
            class="mention-item"
            :class="{ active: index === mentionSelectedIndex }"
            @click="selectMention(index)"
            @mouseenter="mentionSelectedIndex = index"
          >
            <span class="kp-dot" :class="{ ai: note.has_ai_organized }"></span>
            <span>{{ note.title || '未命名' }}</span>
          </div>
        </div>
        <div v-else-if="mentionVisible && mentionResults.length === 0" class="mention-dropdown mention-empty-dropdown">
          <div class="mention-item empty">没有匹配的笔记</div>
        </div>

        <!-- 笔记图谱弹窗 -->
        <Teleport to="body">
        <div v-if="graphVisible" class="graph-overlay" @click.self="closeGraph">
          <div class="graph-header">
            <div class="graph-title">
              <h3>{{ universeVisible ? '✨ 知识点宇宙' : '🕸 笔记图谱' }}</h3>
              <span class="graph-info" v-if="!universeVisible">{{ graphInfo }}</span>
            </div>
            <div class="graph-actions">
              <button class="graph-btn-sm" @click="fitGraph">⊞ 适应</button>
      <button class="graph-btn-sm universe-toggle-btn" @click="toggleUniverseView">{{ universeBtnText }}</button>
      <button class="graph-btn-sm close-graph-btn" @click="closeGraph">×</button>
            </div>
          </div>
          <div class="graph-body">
            <div ref="graphContainerRef" class="graph-container"></div>
            <canvas ref="universeCanvasRef" class="universe-canvas"></canvas>
            <div v-if="nodePanelVisible && selectedNode" class="node-panel">
              <div class="node-panel-header">
                <h4>{{ selectedNode.title || '未命名笔记' }}</h4>
                <button class="panel-close-btn" @click="closeNodePanel">×</button>
              </div>
              <div class="node-panel-body">
                <template v-if="selectedNode.mastery_level !== undefined">
                  <div class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Star /></el-icon>
                      <span>掌握等级</span>
                    </div>
                    <div class="mastery-info">
                      <span class="mastery-label" :style="{ color: getMasteryColor(selectedNode.mastery_level) }">
                        {{ selectedNode.mastery_label }}
                      </span>
                      <span class="mastery-points">{{ selectedNode.mastery_points.toFixed(1) }} 积分</span>
                    </div>
                  </div>
                  <div class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><DataLine /></el-icon>
                      <span>掌握进度</span>
                    </div>
                    <div class="progress-bar">
                      <div class="progress-fill" :style="{ width: getMasteryProgress(selectedNode.mastery_points) + '%', background: getMasteryGradient(selectedNode.mastery_level) }"></div>
                    </div>
                    <div class="progress-text">{{ getMasteryProgress(selectedNode.mastery_points) }}%</div>
                  </div>
                  <div v-if="selectedNode.connections && selectedNode.connections.length" class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Link /></el-icon>
                      <span>关联知识点（{{ selectedNode.connections.length }}）</span>
                    </div>
                    <div class="related-kp-list">
                      <div v-for="conn in selectedNode.connections" :key="conn.note_id" class="related-kp-item">
                        <span class="kp-name" :style="{ color: getMasteryColor(conn.mastery_level) }">{{ conn.title }}</span>
                        <span class="kp-rel">{{ conn.mastery_label }} · {{ conn.mastery_points.toFixed(1) }}分</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="selectedNode.mastery_level === undefined" class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><FileText /></el-icon>
                      <span>关联笔记</span>
                    </div>
                    <div v-if="selectedNode.relatedNotes && selectedNode.relatedNotes.length" class="related-notes-list">
                      <div v-for="note in selectedNode.relatedNotes" :key="note.note_id" class="related-note-item" @click="selectNote(note.note_id)">
                        <span class="related-note-title">{{ note.title || '未命名笔记' }}</span>
                        <span v-if="note.has_ai_organized" class="ai-badge-sm">AI</span>
                      </div>
                    </div>
                    <div v-else class="empty-rel">暂无关联笔记</div>
                  </div>
                </template>
                <template v-else>
                  <div v-if="selectedNode.knowledge_points && selectedNode.knowledge_points.length" class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Aim /></el-icon>
                      <span>知识点</span>
                    </div>
                    <div class="kp-list">
                      <span v-for="kp in selectedNode.knowledge_points" :key="kp" class="kp-tag">{{ kp }}</span>
                    </div>
                  </div>
                  <div class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Clock /></el-icon>
                      <span>创建时间</span>
                      <div class="node-meta">
                        <span class="meta-item">{{ formatTime(selectedNode.created_at) }}</span>
                        <span v-if="selectedNode.ai_organized" class="ai-badge-sm">AI整理</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="selectedNode.content" class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Document /></el-icon>
                      <span>内容预览</span>
                    </div>
                    <div class="node-summary">
                      {{ getContentPreview(selectedNode.content) }}
                    </div>
                  </div>
                  <div v-if="selectedNode.links && selectedNode.links.length" class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Link /></el-icon>
                      <span>关联笔记（{{ selectedNode.links.length }}）</span>
                    </div>
                    <div class="links-list">
                      <div v-for="link in selectedNode.links" :key="link.note_id" class="link-item" @click="openLinkNote(link.note_id)">
                        <span class="link-title">{{ link.title }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="section">
                    <div class="section-title">
                      <el-icon class="section-icon"><Refresh /></el-icon>
                      <span>更新时间</span>
                      <div class="node-meta">
                        <span class="meta-item">{{ formatTime(selectedNode.updated_at) }}</span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
              <div class="node-panel-footer">
                <button v-if="selectedNode.mastery_level === undefined" class="panel-btn primary" @click="openNoteFromGraph">打开笔记</button>
                <button class="panel-btn secondary" @click="closeNodePanel">关闭</button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- 思维导图弹窗 -->
      <NoteMindMap
        ref="mindMapRef"
        :visible="mindmapVisible"
        :data="mindmapData"
        @close="closeMindmap"
      />

      <!-- AI 整理 Diff 对比弹窗 -->
      <Teleport to="body">
        <div v-if="diffModalVisible" class="diff-modal-overlay" @click="rejectDiff">
          <div class="diff-modal" @click.stop>
            <!-- 加载遮罩 -->
            <div v-if="diffLoading" class="diff-loading-overlay">
              <div class="diff-loading-content">
                <div class="diff-loading-spinner"></div>
                <div class="diff-loading-text">正在保存...</div>
              </div>
            </div>
            <div class="diff-modal-header">
              <h3>🤖 AI 整理对比</h3>
              <div class="diff-stats">
                <span class="added">+{{ diffStats.added }}</span>
                <span class="removed">-{{ diffStats.removed }}</span>
                <span>共 {{ diffStats.total }} 行</span>
              </div>
            </div>
            <div class="diff-modal-body" :class="{ unified: diffViewUnified }">
              <div class="diff-pane diff-pane-orig" v-show="!diffViewUnified">
                <div class="diff-pane-header">📄 原始内容</div>
                <div class="diff-pane-content">
                  <div v-for="(line, index) in origDiffLines" :key="'orig-' + index" :class="['diff-line', line.type]">
                    <span class="diff-line-num" v-html="line.lineNum"></span>
                    <span class="diff-line-content" v-html="line.content"></span>
                  </div>
                </div>
              </div>
              <div class="diff-pane diff-pane-new" :class="{ unified: diffViewUnified }">
                <div class="diff-pane-header">{{ diffViewUnified ? '✨ AI 整理结果' : '✨ AI 整理后' }}</div>
                <div class="diff-pane-content">
                  <div v-for="(line, index) in (diffViewUnified ? unifiedDiffLines : newDiffLines)" :key="'new-' + index" :class="['diff-line', line.type]">
                    <span class="diff-line-num" v-html="line.lineNum"></span>
                    <span class="diff-line-content" v-html="line.content"></span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="diffSummary" class="diff-summary">
              <span class="summary-icon">📌</span>
              <span>{{ diffSummary }}</span>
            </div>
            <div class="diff-modal-footer">
              <button class="btn-switch" @click="toggleDiffView">{{ diffViewUnified ? '切换为左右对比' : '切换为统一视图' }}</button>
              <button class="btn btn-reject" @click="rejectDiff">✕ 拒绝</button>
              <button class="btn btn-accept" @click="acceptDiff">✓ 一键接受</button>
            </div>
          </div>
        </div>
      </Teleport>

  </div>
</template>

<style scoped>
/* 手机外框 */
.notebook-phone {
  position: fixed;
  width: 390px;
  height: 680px;
  background: var(--bg-page);
  border-radius: 32px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2), 0 0 0 2px var(--border-color);
  overflow: hidden;
  z-index: 999;
}

/* 两页切换 */
.page {
  position: absolute;
  inset: 0;
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

/* 通用头部 */
.phone-header {
  background: var(--grad-primary);
  color: #fff;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  cursor: grab;
}
.phone-header:active {
  cursor: grabbing;
}
.phone-header h2 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}
.icon-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 22px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  opacity: 0.8;
  transition: opacity 0.2s;
}
.icon-btn:hover { opacity: 1; }
.text-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}
.text-btn.sm {
  font-size: 12px;
  padding: 4px 8px;
  background: rgba(255,255,255,0.15);
}
.text-btn.sm:hover {
  background: rgba(255,255,255,0.3);
}
.text-btn.danger:hover {
  background: var(--main-delete-hover);
}

/* === 列表页 === */
.search-bar {
  padding: 10px 14px 6px;
  background: var(--bg-card);
}
.search-bar input {
  width: 100%;
  padding: 9px 14px;
  border: 1.5px solid var(--border-color);
  border-radius: 20px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
  background: var(--bg-card);
  color: var(--text-body);
}
.search-bar input:focus {
  border-color: var(--primary);
}

.note-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 14px;
  background: var(--bg-card);
}

.empty-hint {
  text-align: center;
  padding: 60px 0;
  color: var(--text-gray);
}
.empty-icon {
  margin-bottom: 12px;
  color: var(--border-color);
}
.empty-hint p {
  margin: 4px 0;
  font-size: 14px;
}
.empty-hint .sub {
  font-size: 12px;
  color: var(--text-gray);
}

.note-card {
  background: var(--bgc-light);
  border-radius: var(--radius-lg);
  padding: 12px 14px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1.5px solid transparent;
}
.note-card:hover {
  background: var(--primary-light);
  border-color: var(--primary);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.card-title {
  font-size: 14px;
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
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 6px;
  flex-shrink: 0;
}
.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin: 4px 0;
}
.tag {
  background: var(--coming-bg-color);
  color: var(--coming);
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 8px;
  line-height: 1.6;
}
.tag.more {
  background: var(--bgc-light);
  color: var(--text-gray);
}
.card-footer {
  display: flex;
  justify-content: flex-end;
}
.card-time {
  font-size: 11px;
  color: var(--text-gray);
}

.fab-btn {
  margin: 10px 14px 14px;
  padding: 12px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: var(--shadow-brand);
}
.fab-btn:hover {
  transform: translateY(-1px);
  background: var(--primary-hv);
  box-shadow: 0 6px 16px rgba(45,125,219,0.35);
}
.fab-btn:active {
  transform: translateY(0);
  background: var(--primary-act);
}

/* === 详情页 === */
.back-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 15px;
  cursor: pointer;
  padding: 0;
  font-weight: 500;
  opacity: 0.9;
}
.back-btn:hover { opacity: 1; }

.detail-actions {
  display: flex;
  gap: 6px;
}

.title-bar {
  padding: 8px 14px 0;
  background: var(--bg-card);
}
.title-bar input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  padding: 6px 0;
  border-bottom: 2px solid var(--border-color);
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.title-bar input:focus {
  border-bottom-color: var(--primary);
}

.toolbar-bar {
  padding: 4px 14px;
  background: var(--bg-card);
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.toolbar-bar button {
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  color: var(--text-body);
}
.toolbar-bar button:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
}
.toolbar-bar button.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.editor-area {
  flex: 1;
  overflow: hidden;
  background: var(--bg-card);
  position: relative;
}
.editor-div {
  width: 100%;
  height: 100%;
  padding: 12px 14px;
  border: none;
  outline: none;
  overflow-y: auto;
  font-size: 14px;
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
  border-radius: var(--radius-sm);
  margin: 8px 0;
  box-shadow: var(--shadow-normal);
  display: block;
  cursor: pointer;
  transition: outline 0.15s;
}
.editor-div img.img-selected {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}
/* 图片右下角拖拽圆圈 */
.img-resize-handle {
  position: absolute;
  width: 18px;
  height: 18px;
  background: var(--primary);
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: nwse-resize;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
  z-index: 20;
  transition: transform 0.15s;
}
.img-resize-handle:hover {
  transform: scale(1.2);
  background: var(--primary-hv);
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
  background: var(--bgc-light);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: Consolas, monospace;
}
.editor-div blockquote {
  border-left: 3px solid var(--primary);
  padding: 6px 12px;
  margin: 8px 0;
  background: var(--primary-light);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px;
  color: var(--text-body);
}
.editor-div a { color: var(--primary); text-decoration: underline; }
.editor-div hr { border: none; border-top: 1px solid var(--border-color); margin: 12px 0; }

/* === AI抽屉 === */
.ai-drawer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.1);
  max-height: 55%;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.3s ease;
  z-index: 10;
}
.ai-drawer.open {
  transform: translateY(0);
}
.ai-drawer-handle {
  text-align: center;
  padding: 8px 0 4px;
  cursor: pointer;
}
.handle-bar {
  width: 36px;
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  margin: 0 auto;
}
.ai-drawer-header {
  padding: 4px 14px 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
}
.ai-drawer-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
  margin: 0;
}
.ai-drawer-header button {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--text-gray);
  cursor: pointer;
  padding: 0 4px;
}
.ai-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px;
  font-size: 13px;
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
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.no-ai {
  text-align: center;
  color: var(--text-gray);
  padding: 30px 0;
  font-size: 13px;
}
.summary-box {
  background: var(--primary-light);
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-body);
  margin-bottom: 12px;
}
.section {
  margin-bottom: 14px;
}
.section h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin: 0 0 6px;
  padding-bottom: 3px;
  border-bottom: 1.5px solid var(--primary-fade);
}
.section .item {
  padding: 6px 10px;
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  margin-bottom: 4px;
  font-size: 12px;
  line-height: 1.5;
}
.item .label { font-weight: 600; color: var(--text-title); }
.item .desc { color: var(--text-body); margin-top: 2px; }
.item .original { color: var(--main-delete); text-decoration: line-through; font-size: 11px; }
.item .corrected { color: var(--pass); font-size: 11px; }

/* 列表页header按钮组 */
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.graph-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 12px;
  font-size: 12px;
  transition: all 0.2s;
  border: 1px dotted black;
}
.graph-icon {
  font-size: 16px;
}
.graph-text {
  font-size: 16px;
  white-space: nowrap;
}
.graph-btn:hover {
  opacity: 1 !important;
  background: rgba(255, 255, 255, 0.15);
}

/* 关联笔记弹窗（浮动在编辑器内） */
.note-link-popover {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 340px;
  background: var(--bg-card);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.22);
  z-index: 100;
  overflow: hidden;
  animation: popoverIn 0.25s ease;
  max-height: 380px;
  display: flex;
  flex-direction: column;
}

@keyframes popoverIn {
  from { opacity: 0; transform: translate(-50%, calc(-50% - 8px)); }
  to { opacity: 1; transform: translate(-50%, -50%); }
}

.note-link-header {
  background: var(--grad-primary);
  color: #fff;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.note-link-header h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.note-link-header .close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.8);
  font-size: 18px;
  cursor: pointer;
  padding: 0 2px;
}

.note-link-header .close-btn:hover {
  color: #fff;
}

.note-link-search {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.note-link-search input {
  width: 100%;
  padding: 7px 12px;
  border: 1.5px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  outline: none;
  background: var(--bg-card);
  color: var(--text-body);
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.note-link-search input:focus {
  border-color: var(--primary);
}

.note-link-list {
  max-height: 280px;
  overflow-y: auto;
  padding: 6px 0;
  flex: 1;
}

.link-empty {
  text-align: center;
  padding: 20px 0;
  color: var(--text-gray);
  font-size: 12px;
}

.link-note-item {
  padding: 8px 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.link-note-item:hover:not(.disabled) {
  background: var(--primary-light);
}

.link-note-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.link-note-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-note-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  font-size: 10px;
  color: var(--text-gray);
}

.ai-badge-sm {
  background: var(--primary);
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 4px;
}

/* [[ 提及自动补全下拉 */
.mention-dropdown {
  position: fixed;
  z-index: 9999;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
  max-height: 220px;
  overflow-y: auto;
  min-width: 200px;
  max-width: 360px;
  padding: 4px;
}

.mention-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-body);
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.15s;
}

.mention-item:hover,
.mention-item.active {
  background: var(--primary-light);
  color: var(--primary);
}

.mention-item.empty {
  color: var(--text-gray);
  cursor: default;
  text-align: center;
}

.kp-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--coming);
  flex-shrink: 0;
}

.kp-dot.ai {
  background: var(--primary);
}

/* 笔记图谱弹窗 */
.graph-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 10001;
  display: flex;
  flex-direction: column;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.graph-header {
  background: #1a1a2e;
  color: #fff;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.graph-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.graph-title h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.graph-header .graph-info {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

.graph-actions {
  display: flex;
  gap: 8px;
}

.graph-btn-sm {
  padding: 5px 14px;
  border: none;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;
}

.graph-btn-sm:hover {
  background: rgba(255, 255, 255, 0.3);
}

.close-graph-btn {
  font-size: 18px;
  padding: 2px 10px;
  background: rgba(255, 255, 255, 0.1);
}

.graph-body {
  flex: 1;
  background: #0f0f1a;
  position: relative;
  overflow: hidden;
}

.graph-container {
  width: 100%;
  height: 100%;
}

.universe-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  cursor: crosshair;
  display: none;
}

.universe-toggle-btn {
  background: linear-gradient(135deg, rgba(138, 43, 226, 0.4), rgba(30, 144, 255, 0.4)) !important;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
}

.universe-toggle-btn:hover {
  background: linear-gradient(135deg, rgba(138, 43, 226, 0.6), rgba(30, 144, 255, 0.6)) !important;
}

.universe-tooltip {
  position: fixed;
  pointer-events: none;
  z-index: 10010;
  background: rgba(10, 10, 30, 0.92);
  color: #e2e8f0;
  border: 1px solid rgba(139, 92, 246, 0.4);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.6), 0 0 15px rgba(139, 92, 246, 0.15);
  backdrop-filter: blur(10px);
  opacity: 0;
  transition: opacity 0.2s ease, transform 0.2s ease;
  transform: translateY(4px);
  max-width: 220px;
}

/* 节点详情面板 */
.node-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 420px;
  background: var(--bg-card);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  animation: panelSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 10;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
}

@keyframes panelSlideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.node-panel-header {
  padding: 16px 18px;
  background: var(--grad-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.node-panel-header h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  padding-right: 12px;
}

.panel-close-btn {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: rgba(255, 255, 255, 0.9);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.2s;
  flex-shrink: 0;
  line-height: 1;
}

.panel-close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  color: #fff;
}

.node-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

.section {
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.section:first-child {
  padding-top: 0;
  border-top: none;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 18px;
  font-weight: 700;
  font-family: '抖音美好体', sans-serif;
  color: var(--text-title);
}

.section-icon {
  font-size: 20px;
  color: var(--primary);
}

.mastery-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.mastery-label {
  font-size: 14px;
  font-weight: 600;
}

.mastery-points {
  font-size: 13px;
  color: var(--text-secondary);
}

.progress-bar {
  height: 6px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 8px;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-align: right;
}

.related-kp-list {
  margin-top: 10px;
}

.related-kp-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.related-kp-item:hover {
  background: rgba(0, 0, 0, 0.1);
}

.kp-name {
  font-size: 13px;
  font-weight: 500;
}

.kp-rel {
  font-size: 11px;
  color: var(--text-secondary);
}

.related-notes-list {
  margin-top: 10px;
}

.related-note-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.related-note-item:hover {
  background: rgba(0, 0, 0, 0.1);
}

.related-note-title {
  font-size: 13px;
  color: var(--text-primary);
}

.empty-rel {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  padding: 16px;
}

.kp-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kp-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background: var(--coming-bg-color);
  color: var(--coming);
  border: 1px solid var(--coming-shadow);
  line-height: 1.5;
  transition: all 0.2s;
}

.kp-tag:hover {
  background: var(--coming);
  color: #fff;
  border-color: var(--coming);
}

.node-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.meta-item {
  font-size: 15px;
  color: var(--text-gray);
}

.ai-badge-sm {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  background: rgba(45, 125, 219, 0.1);
  color: var(--primary);
  border: 1px solid rgba(45, 125, 219, 0.2);
}

.node-summary {
  margin-top: 14px;
  padding: 14px;
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  border-left: 3px solid var(--primary);
}

.links-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-color);
}

.links-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}

.links-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.link-item {
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.25s;
  border: 1px solid var(--border-color);
  position: relative;
}

.link-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--primary);
  border-radius: 0 2px 2px 0;
  transition: height 0.25s;
}

.link-item:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  transform: translateX(4px);
}

.link-item:hover::before {
  height: 60%;
}

.link-title {
  font-size: 12px;
  color: var(--text-body);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s;
}

.link-item:hover .link-title {
  color: var(--primary);
}



.node-panel-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.panel-btn {
  flex: 1;
  padding: 10px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.panel-btn.primary {
  background: var(--primary);
  color: #fff;
}

.panel-btn.primary:hover {
  background: var(--primary-hv);
}

.panel-btn.secondary {
  background: var(--bgc-light);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.panel-btn.secondary:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
}

/* ============ 夜间模式适配 ============ */

/* 笔记标题输入框 */
.dark .title-bar input {
  background: var(--bg-card);
  color: var(--text-title);
  border-bottom-color: var(--border-color);
}

.dark .title-bar input::placeholder {
  color: var(--text-gray);
}

/* 搜索输入框 */
.dark .search-bar input {
  background: var(--bg-page);
  color: var(--text-body);
  border-color: var(--border-color);
}

.dark .search-bar input::placeholder {
  color: var(--text-gray);
}

/* 关联笔记搜索输入框 */
.dark .note-link-popover input {
  background: var(--bg-page);
  color: var(--text-body);
  border-color: var(--border-color);
}

.dark .note-link-popover input::placeholder {
  color: var(--text-gray);
}

/* 进度条 */
.dark .progress-bar {
  background: rgba(255, 255, 255, 0.1);
}

/* ==================== AI整理加载遮罩 ==================== */
.ai-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  backdrop-filter: blur(2px);
}
.ai-loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.ai-loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: ai-spin 0.8s linear infinite;
}
@keyframes ai-spin {
  to { transform: rotate(360deg); }
}
.ai-loading-text {
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  text-shadow: 0 1px 4px rgba(0,0,0,0.3);
}

.dark .ai-loading-overlay {
  background: rgba(0, 0, 0, 0.6);
}
.dark .ai-loading-spinner {
  border-color: rgba(255, 255, 255, 0.15);
  border-top-color: #667eea;
}

/* ==================== AI 整理 Diff 对比弹窗样式 ==================== */
.diff-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.diff-modal {
  position: relative;
  width: 90%;
  max-width: 1200px;
  max-height: 85vh;
  background: var(--bg-page);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Diff 弹窗加载遮罩 */
.diff-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  backdrop-filter: blur(2px);
}
.diff-loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.diff-loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: diff-spin 0.8s linear infinite;
}
@keyframes diff-spin {
  to { transform: rotate(360deg); }
}
.diff-loading-text {
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  text-shadow: 0 1px 4px rgba(0,0,0,0.3);
}

.dark .diff-loading-overlay {
  background: rgba(0, 0, 0, 0.7);
}
.dark .diff-loading-spinner {
  border-color: rgba(255, 255, 255, 0.15);
  border-top-color: #667eea;
}

.diff-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: var(--grad-primary);
  color: #fff;
  flex-shrink: 0;
}

.diff-modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.diff-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
}

.diff-stats .added {
  color: #4ade80;
  font-weight: 600;
}

.diff-stats .removed {
  color: #f87171;
  font-weight: 600;
}

.diff-modal-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 400px;
}

.diff-modal-body.unified {
  flex-direction: column;
}

.diff-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--border-color);
}

.diff-pane:last-child {
  border-right: none;
}

.diff-pane-header {
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  flex-shrink: 0;
}

.diff-pane-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.diff-line {
  display: flex;
  min-height: 24px;
}

.diff-line-num {
  width: 48px;
  padding: 0 8px;
  text-align: right;
  color: var(--text-gray);
  background: var(--bg-page);
  border-right: 1px solid var(--border-color);
  flex-shrink: 0;
}

.diff-line-content {
  flex: 1;
  padding: 0 12px;
  color: var(--text-body);
}

.diff-line.added {
  background: rgba(74, 222, 128, 0.15);
}

.diff-line.added .diff-line-content {
  color: #4ade80;
}

.diff-line.removed {
  background: rgba(248, 113, 113, 0.15);
}

.diff-line.removed .diff-line-content {
  color: #f87171;
  text-decoration: line-through;
}

.diff-summary {
  padding: 12px 16px;
  background: var(--primary-light);
  border-top: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-body);
  flex-shrink: 0;
}

.summary-icon {
  margin-right: 6px;
  font-size: 14px;
}

.diff-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 20px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.btn-switch {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-page);
  color: var(--text-body);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-switch:hover {
  background: var(--bgc-light);
  border-color: var(--primary);
}

.btn {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-reject {
  background: var(--bgc-light);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.btn-reject:hover {
  background: rgba(248, 113, 113, 0.1);
  border-color: #f87171;
  color: #f87171;
}

.btn-accept {
  background: var(--primary);
  color: #fff;
}

.btn-accept:hover {
  background: var(--primary-hv);
}

/* 夜间模式适配 */
.dark .diff-line.added {
  background: rgba(74, 222, 128, 0.1);
}

.dark .diff-line.removed {
  background: rgba(248, 113, 113, 0.1);
}

.dark .diff-line-num {
  background: var(--bg-page);
}

</style>
