/**
 * 代码可视化模块
 * 基于 agent_test.html + code_visualization.js 重构
 * 支持：数组排序/查找、矩阵运算、图遍历、树遍历
 * 适配 Vue 组件，通过 initVizModule(container) 初始化
 */

// ========== 本地文件导入（Vite ?raw 模式）==========
import workerText from './worker.js?raw';
import libText from 'algorithm-visualizer/dist/algorithm-visualizer.umd.js?raw';

// ========== 模块内部状态 ==========
let _container = null;
let _worker = null;
let _transformedCode = '';
let _originalCode = '';
let _originalLang = '';
let _frameSrcLineMap = [];
let _callbacks = { onPlay: null, onComplete: null };

let _state = {
    commands: [], currentFrame: 0, isPlaying: false,
    playTimer: null, animTimer: null, speed: 180, vizType: 'array1d'
};
let _anim = { startTime: 0, duration: 250, prevState: null, targetState: null, rafId: null };

// ========== DOM 查询辅助 ==========
function $(id) {
    return _container ? _container.querySelector('#' + id) : document.getElementById(id);
}

// ========== 日志 ==========
function logMsg(msg, type) {
    const el = $('vizLog');
    if (!el) return;
    const div = document.createElement('div');
    div.className = 'log-entry';
    if (type === 'ok') div.classList.add('log-ok');
    else if (type === 'err') div.classList.add('log-err');
    else div.classList.add('log-info');
    div.textContent = msg;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

// ========== Worker 控制 ==========
function stopWorker() {
    if (_worker) { _worker.terminate(); _worker = null; }
    const btn = $('stopVizBtn');
    if (btn) btn.style.display = 'none';
    logMsg('⏹️ Worker已停止', 'info');
}

function closeViz() {
    stopWorker();
    if (_anim.rafId) { cancelAnimationFrame(_anim.rafId); _anim.rafId = null; }
    if (_state.playTimer) { clearTimeout(_state.playTimer); _state.playTimer = null; }
    // 彻底重置状态对象（原地修改，避免外部引用不一致）
    _state.commands = [];
    _state.currentFrame = 0;
    _state.isPlaying = false;
    _state.playTimer = null;
    _state.animTimer = null;
    _state.speed = 180;
    _state.vizType = 'array1d';
    _anim.startTime = 0;
    _anim.duration = 250;
    _anim.prevState = null;
    _anim.targetState = null;
    _anim.rafId = null;
    _transformedCode = '';
    _originalCode = '';
    _originalLang = '';
    _frameSrcLineMap = [];
    // 恢复滚动
    if (_callbacks.onComplete) { _callbacks.onComplete(); }
    // 检查 _container 是否仍在 DOM 中（防止 v-if 销毁后修改已脱离的节点）
    const containerConnected = _container && document.body.contains(_container);
    if (!containerConnected) {
        // 容器已被 v-if 销毁，只清理状态即可，跳过 DOM 操作
        return;
    }
    // 清空画布
    const canvas = $('vizCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    // 清空代码内容
    const codeContent = $('vizCodeContent');
    if (codeContent) codeContent.innerHTML = '';
    // 清空日志
    const logEl = $('vizLog');
    if (logEl) logEl.innerHTML = '';
    // 重置状态文案
    const statusEl = $('vizStatus');
    if (statusEl) statusEl.textContent = '等待转换...';
    const frameInfo = $('vizFrameInfo');
    if (frameInfo) frameInfo.textContent = '帧: 0/0';
    // 重置按钮状态
    const playBtn = $('vizPlayBtn');
    if (playBtn) playBtn.style.display = 'inline-block';
    const pauseBtn = $('vizPauseBtn');
    if (pauseBtn) pauseBtn.style.display = 'none';
    const controls = $('vizControls');
    if (controls) controls.style.display = 'none';
    // 隐藏 UI 元素
    const section = $('vizSection');
    if (section) section.style.display = 'none';
    const codePanel = $('vizCodePanel');
    if (codePanel) codePanel.style.display = 'none';
    // 隐藏父容器（vsArea）
    if (_container) _container.style.display = 'none';
}

function destroy() {
    closeViz();
    _container = null;
}

// ========== 语法高亮 ==========
function highlightCode(line, lang) {
    let s = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // 暗色模式配色
    s = s.replace(/(["'])(?:(?!\1|\\).|\\.)*\1/g, '<span style="color:#a5d6ff">$&</span>');
    if (lang === 'python') {
        s = s.replace(/(#.*)$/gm, '<span style="color:#8b949e;font-style:italic">$1</span>');
    } else {
        s = s.replace(/(\/\/.*)$/gm, '<span style="color:#8b949e;font-style:italic">$1</span>');
    }
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#79c0ff">$1</span>');
    const kw = lang === 'python'
        ? /\b(def|class|if|elif|else|for|while|return|import|from|in|not|and|or|True|False|None|range|len|print|append|self|pass|break|continue|try|except|finally|with|as|lambda|yield|global|nonlocal)\b/g
        : lang === 'java' || lang === 'c' || lang === 'cpp'
            ? /\b(public|private|protected|static|final|void|int|long|float|double|char|boolean|String|class|interface|extends|implements|new|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|throws|import|package|this|super|null|true|false)\b/g
            : /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|class|extends|import|export|from|default|true|false|null|undefined|this|super|async|await|try|catch|finally|throw)\b/g;
    s = s.replace(kw, '<span style="color:#ff7b72;font-weight:bold">$&</span>');
    return s;
}

// ========== 帧→源行号映射 ==========
function buildSrcLineMap(transformedCode, commands) {
    const map = [];
    const jsLines = transformedCode.split('\n');
    const jsToSrc = {};
    jsLines.forEach((line, idx) => {
        const m = line.match(/\/\/src:(\d+)/);
        if (m) jsToSrc[idx] = parseInt(m[1]) - 1;
    });
    if (commands && commands.length > 0) {
        for (const cmd of commands) {
            if (cmd.type === 'delay') {
                const jsLine = cmd.lineNumber || 0;
                const srcLine = (jsToSrc[jsLine] !== undefined) ? jsToSrc[jsLine] : 0;
                map.push(srcLine);
            }
        }
        if (map.length > 0) return map;
    }
    jsLines.forEach(line => {
        if (/Tracer\.delay\s*\(/.test(line)) {
            const m = line.match(/\/\/src:(\d+)/);
            map.push(m ? parseInt(m[1]) - 1 : 0);
        }
    });
    return map;
}

// ========== 代码面板渲染 ==========
function updateCodePanel(highlightFrame) {
    const code = _originalCode || _transformedCode;
    if (!code) return;
    const lang = _originalLang || 'javascript';
    const lines = code.split('\n');
    let currentSrcLine = -1;
    if (highlightFrame >= 0 && highlightFrame < _frameSrcLineMap.length) {
        currentSrcLine = _frameSrcLineMap[highlightFrame];
    }
    const html = lines.map((line, i) => {
        const hl = highlightCode(line, lang);
        const num = String(i + 1).padStart(3, ' ');
        const isCurrent = (i === currentSrcLine);
        // 暗色模式配色
        const bg = isCurrent ? 'rgba(251,146,60,0.15)' : '';
        const border = isCurrent ? 'border-left:3px solid #FB923C;' : '';
        const numColor = isCurrent ? '#FB923C' : '#6e7681';
        const fontWeight = isCurrent ? 'font-weight:bold;' : '';
        return `<div style="padding:1px 10px 1px 0;white-space:pre;background:${bg};${border}${fontWeight}transition:background 0.15s;" class="code-line" data-line="${i}"><span style="color:${numColor};user-select:none;display:inline-block;width:36px;text-align:right;margin-right:12px;font-size:11px;">${num}</span><span style="color:#E2E8F0">${hl}</span></div>`;
    }).join('');
    const el = $('vizCodeContent');
    if (el) {
        el.innerHTML = html;
        if (currentSrcLine >= 0) {
            const lineEl = el.querySelector(`[data-line="${currentSrcLine}"]`);
            if (lineEl) {
                // 手动滚动 #vizCodePanel 让高亮行居中，避免 scrollIntoView 带动外部页面滚动
                const panel = $('vizCodePanel') || el.parentElement;
                if (panel && panel.clientHeight < panel.scrollHeight) {
                    const targetTop = lineEl.offsetTop - panel.clientHeight / 2 + lineEl.clientHeight / 2;
                    panel.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
                }
            }
        }
    }
}

// ========== 图→树转换 ==========
function buildTreeFromGraph(nodes, edges, rootId) {
    if (!nodes || !nodes.length) return null;
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.id] = { id: n.id, value: n.label !== undefined ? n.label : n.id, children: [] }; });
    const adj = {};
    nodes.forEach(n => { adj[n.id] = []; });
    edges.forEach(e => {
        if (adj[e.from]) adj[e.from].push(e.to);
        if (adj[e.to]) adj[e.to].push(e.from);
    });
    const visited = new Set();
    const queue = [rootId];
    visited.add(rootId);
    while (queue.length > 0) {
        const cur = queue.shift();
        const parent = nodeMap[cur];
        if (!parent) continue;
        (adj[cur] || []).forEach(neighbor => {
            if (!visited.has(neighbor) && nodeMap[neighbor]) {
                visited.add(neighbor);
                parent.children.push(nodeMap[neighbor]);
                queue.push(neighbor);
            }
        });
    }
    return nodeMap[rootId] || null;
}

// ========== 命令处理：计算目标状态 ==========
function applyCommandsUpTo(frameIndex) {
    const cmds = _state.commands;
    const s = { data: null, highlights: {}, vizType: 'array1d', nodes: null, edges: null, treeRoot: null, lastLog: '' };
    for (let i = 0; i <= frameIndex && i < cmds.length; i++) {
        const c = cmds[i];
        switch (c.type) {
            case 'set':
                if (c.visualizationType) s.vizType = c.visualizationType;
                if (c.visualizationType === 'array1d' && Array.isArray(c.data)) {
                    s.data = [...c.data]; s.highlights = {};
                } else if (c.visualizationType === 'array2d' && Array.isArray(c.data)) {
                    s.data = c.data.map(r => [...r]); s.highlights = {};
                } else if (c.visualizationType === 'graph') {
                    s.nodes = (c.nodes || []).map(n => ({ ...n }));
                    s.edges = (c.edges || []).map(e => ({ ...e }));
                    s.highlights = {};
                    if (s.vizType === 'tree' && s.nodes && s.edges) {
                        s.treeRoot = buildTreeFromGraph(s.nodes, s.edges, s.treeRootId || 0);
                    }
                } else if (c.visualizationType === 'tree' && c.root) {
                    s.treeRoot = JSON.parse(JSON.stringify(c.root));
                    s.highlights = {};
                }
                break;
            case 'select':
                (c.indices || []).forEach(idx => { s.highlights[String(idx)] = '#ff6600'; });
                break;
            case 'deselect':
                (c.indices || []).forEach(idx => { delete s.highlights[String(idx)]; });
                break;
            case 'patch':
                if (s.data && c.index !== undefined && c.value !== undefined) {
                    const pKey = String(c.index);
                    if (pKey.includes(',')) {
                        const [pr, pc] = pKey.split(',').map(Number);
                        if (Array.isArray(s.data) && Array.isArray(s.data[pr])) {
                            s.data[pr][pc] = c.value;
                        }
                    } else if (Array.isArray(s.data) && !Array.isArray(s.data[0])) {
                        s.data[c.index] = c.value;
                    }
                    s.highlights[pKey] = '#ffff00';
                }
                break;
            case 'depatch':
                if (c.index !== undefined) delete s.highlights[String(c.index)];
                break;
            case 'layoutTree':
                s.vizType = 'tree';
                s.treeRootId = c.root || 0;
                if (s.nodes && s.edges) {
                    s.treeRoot = buildTreeFromGraph(s.nodes, s.edges, s.treeRootId);
                }
                break;
            case 'addNode':
                if (!s.nodes) s.nodes = [];
                if (c.id !== undefined) {
                    s.nodes.push({ id: c.id, label: String(c.label !== undefined ? c.label : c.id), weight: c.weight || null });
                }
                break;
            case 'addEdge':
                if (!s.edges) s.edges = [];
                if (c.from !== undefined && c.to !== undefined) {
                    s.edges.push({ from: c.from, to: c.to, weight: c.weight || null });
                }
                break;
            case 'removeEdge':
                if (s.edges && c.from !== undefined && c.to !== undefined) {
                    s.edges = s.edges.filter(e => !(e.from === c.from && e.to === c.to));
                }
                break;
            case 'log':
                s.lastLog = c.message || '';
                break;
        }
    }
    return s;
}

// ========== 渲染引擎 ==========
function renderFrameAnimated(frameIndex) {
    const canvas = $('vizCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const target = applyCommandsUpTo(frameIndex);
    _state.vizType = target.vizType;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    switch (target.vizType) {
        case 'array1d': renderArray1D(ctx, canvas, target); break;
        case 'array2d': renderArray2D(ctx, canvas, target); break;
        case 'graph': renderGraph(ctx, canvas, target); break;
        case 'tree': renderTree(ctx, canvas, target); break;
        default:
            ctx.fillStyle = '#666'; ctx.font = '14px monospace'; ctx.textAlign = 'center';
            ctx.fillText('不支持的可视化类型: ' + target.vizType, canvas.width / 2, canvas.height / 2);
    }
    ctx.fillStyle = '#555'; ctx.textAlign = 'right'; ctx.font = '11px monospace';
    ctx.fillText(`帧: ${frameIndex}/${_state.commands.length - 1}`, canvas.width - 12, 18);
    const frameInfo = $('vizFrameInfo');
    if (frameInfo) frameInfo.textContent = `帧: ${frameIndex}/${_state.commands.length - 1}`;
    updateCodePanel(frameIndex);
}

// ========== Array1D 渲染器（柱状图） ==========
function renderArray1D(ctx, canvas, state, lerpT) {
    if (!state.data || !state.data.length) {
        ctx.fillStyle = '#666'; ctx.font = '16px monospace'; ctx.textAlign = 'center';
        ctx.fillText('等待数据...', canvas.width / 2, canvas.height / 2); return;
    }
    const data = state.data, n = data.length, hl = state.highlights;
    const maxVal = Math.max(...data, 1);
    const barW = Math.min(80, (canvas.width - 40) / n - 4);
    const maxH = canvas.height - 70;
    const startX = (canvas.width - n * (barW + 4)) / 2;
    const t = (lerpT !== undefined) ? lerpT : 1;
    const prev = _anim.prevState;
    for (let i = 0; i < n; i++) {
        const val = data[i];
        let dispVal = val;
        if (prev && prev.data && prev.data.length === n && t < 1) {
            dispVal = prev.data[i] + (val - prev.data[i]) * t;
        }
        const barH = (Math.max(dispVal, 0) / maxVal) * maxH;
        const x = startX + i * (barW + 4), y = canvas.height - 40 - barH;
        const hColor = hl[String(i)];
        if (hColor) { ctx.fillStyle = hColor; }
        else {
            const g = ctx.createLinearGradient(x, y, x, y + barH);
            g.addColorStop(0, '#4ec9b0'); g.addColorStop(1, '#2d8a7a'); ctx.fillStyle = g;
        }
        ctx.beginPath();
        const r = Math.min(4, barW / 4);
        ctx.moveTo(x, y + barH); ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.lineTo(x + barW - r, y);
        ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
        ctx.lineTo(x + barW, y + barH); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 13px monospace'; ctx.textAlign = 'center';
        ctx.fillText(Math.round(dispVal), x + barW / 2, y - 8);
        ctx.fillStyle = '#888'; ctx.font = '11px monospace';
        ctx.fillText(i, x + barW / 2, canvas.height - 22);
    }
}

// ========== Array2D 渲染器（矩阵/网格） ==========
function renderArray2D(ctx, canvas, state) {
    if (!state.data || !state.data.length) return;
    const data = state.data, rows = data.length, cols = data[0].length, hl = state.highlights;
    const pad = 30;
    const cellW = Math.min(60, (canvas.width - pad * 2) / cols);
    const cellH = Math.min(40, (canvas.height - pad * 2) / rows);
    const oX = (canvas.width - cols * cellW) / 2;
    const oY = (canvas.height - rows * cellH) / 2;
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const x = oX + c * cellW, y = oY + r * cellH;
            const key = `${r},${c}`, key2 = `${r * cols + c}`;
            const hColor = hl[key] || hl[key2];
            ctx.fillStyle = hColor || '#1a2332';
            ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);
            ctx.strokeStyle = '#3a4a5a'; ctx.lineWidth = 1;
            ctx.strokeRect(x, y, cellW, cellH);
            ctx.fillStyle = '#e0e0e0'; ctx.font = `${Math.min(14, cellH * 0.45)}px monospace`;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(String(data[r][c]), x + cellW / 2, y + cellH / 2);
        }
    }
}

// ========== Graph 渲染器（圆形布局） ==========
function renderGraph(ctx, canvas, state) {
    if (!state.nodes || !state.nodes.length) {
        ctx.fillStyle = '#666'; ctx.font = '14px monospace'; ctx.textAlign = 'center';
        ctx.fillText('等待图数据...', canvas.width / 2, canvas.height / 2); return;
    }
    const nodes = state.nodes, edges = state.edges || [], hl = state.highlights;
    const cX = canvas.width / 2, cY = canvas.height / 2;
    const radius = Math.min(cX, cY) - 60;
    const positions = [];
    for (let i = 0; i < nodes.length; i++) {
        const a = (2 * Math.PI * i / nodes.length) - Math.PI / 2;
        positions.push({ x: cX + radius * Math.cos(a), y: cY + radius * Math.sin(a) });
    }
    edges.forEach(e => {
        const fi = typeof e.from === 'number' ? e.from : nodes.findIndex(n => n.id === e.from);
        const ti = typeof e.to === 'number' ? e.to : nodes.findIndex(n => n.id === e.to);
        if (fi < 0 || ti < 0 || fi >= positions.length || ti >= positions.length) return;
        const f = positions[fi], t = positions[ti];
        const eKey1 = `${e.from},${e.to}`, eKey2 = `${fi},${ti}`;
        const isHl = hl[eKey1] || hl[eKey2] || hl[String(fi)] || hl[String(ti)];
        ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = isHl || '#4a5568'; ctx.lineWidth = isHl ? 3 : 1.5; ctx.stroke();
        if (e.weight !== undefined && e.weight !== null) {
            const mx = (f.x + t.x) / 2, my = (f.y + t.y) / 2;
            ctx.fillStyle = '#0d1117'; ctx.fillRect(mx - 12, my - 8, 24, 16);
            ctx.fillStyle = '#aaa'; ctx.font = '10px monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(String(e.weight), mx, my);
        }
        const dx = t.x - f.x, dy = t.y - f.y, angle = Math.atan2(dy, dx);
        const aL = 10, nR = 22;
        const ax = t.x - Math.cos(angle) * nR, ay = t.y - Math.sin(angle) * nR;
        ctx.beginPath(); ctx.moveTo(ax, ay);
        ctx.lineTo(ax - aL * Math.cos(angle - 0.4), ay - aL * Math.sin(angle - 0.4));
        ctx.lineTo(ax - aL * Math.cos(angle + 0.4), ay - aL * Math.sin(angle + 0.4));
        ctx.closePath(); ctx.fillStyle = isHl || '#4a5568'; ctx.fill();
    });
    const nR = 22;
    nodes.forEach((node, i) => {
        const p = positions[i];
        const nKey = String(node.id), nKey2 = String(i);
        const isHl = hl[nKey] || hl[nKey2];
        ctx.beginPath(); ctx.arc(p.x, p.y, nR, 0, Math.PI * 2);
        ctx.fillStyle = isHl || '#2d3748'; ctx.fill();
        ctx.strokeStyle = isHl || '#667eea'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 14px monospace';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const nLabel = (node && node.label !== undefined) ? node.label : (node ? node.id : i);
        ctx.fillText(String(nLabel), p.x, p.y);
    });
}

// ========== Tree 渲染器 ==========
function renderTree(ctx, canvas, state) {
    if (!state.treeRoot) {
        ctx.fillStyle = '#666'; ctx.font = '14px monospace'; ctx.textAlign = 'center';
        ctx.fillText('等待树数据...', canvas.width / 2, canvas.height / 2); return;
    }
    const hl = state.highlights;
    const nodePos = [];
    function countW(node) {
        if (!node) return 0;
        const ch = node.children || [];
        if (!ch.length) return 1;
        return ch.reduce((s, c) => s + countW(c), 0);
    }
    function layout(node, depth, leftOff) {
        if (!node) return null;
        const ch = node.children || [];
        if (!ch.length) return { node, x: leftOff + 0.5, depth, children: [] };
        let cur = leftOff;
        const laid = [];
        for (const c of ch) { const l = layout(c, depth + 1, cur); if (l) { laid.push(l); cur += countW(c); } }
        const xs = laid.map(l => l.x);
        return { node, x: (Math.min(...xs) + Math.max(...xs)) / 2, depth, children: laid };
    }
    const totalW = countW(state.treeRoot);
    const tree = layout(state.treeRoot, 0, 0);
    if (!tree) return;
    function maxD(t) { return Math.max(t.depth, ...(t.children || []).map(maxD)); }
    const mD = maxD(tree) + 1;
    const hGap = (canvas.width - 80) / Math.max(totalW, 1);
    const vGap = (canvas.height - 80) / Math.max(mD, 1);
    function drawT(laid) {
        if (!laid) return;
        const node = laid.node || {};
        const x = 40 + laid.x * hGap, y = 40 + laid.depth * vGap;
        nodePos.push({ id: node.id, x, y, node });
        (laid.children || []).forEach(ch => {
            if (!ch) return;
            const cx = 40 + ch.x * hGap, cy = 40 + ch.depth * vGap;
            ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(cx, cy);
            ctx.strokeStyle = '#4a5568'; ctx.lineWidth = 2; ctx.stroke();
            drawT(ch);
        });
    }
    drawT(tree);
    const nR = 20;
    nodePos.forEach(np => {
        const isHl = hl[String(np.id)];
        ctx.beginPath(); ctx.arc(np.x, np.y, nR, 0, Math.PI * 2);
        ctx.fillStyle = isHl || '#2d3748'; ctx.fill();
        ctx.strokeStyle = isHl || '#4ec9b0'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 13px monospace';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const label = np.node ? (np.node.value !== undefined ? np.node.value : np.node.id) : np.id;
        ctx.fillText(String(label), np.x, np.y);
    });
}

// ========== 播放控制 ==========
function renderCommands(commands) {
    _state.commands = commands;
    _state.currentFrame = 0;
    _state.vizType = 'array1d';
    _anim.prevState = null;
    const controls = $('vizControls');
    if (controls) controls.style.display = 'flex';
    const playBtn = $('vizPlayBtn');
    if (playBtn) playBtn.style.display = 'inline-block';
    const pauseBtn = $('vizPauseBtn');
    if (pauseBtn) pauseBtn.style.display = 'none';
    const frameInfo = $('vizFrameInfo');
    if (frameInfo) frameInfo.textContent = `帧: 0/${commands.length}`;
    renderFrameAnimated(0);
    logMsg(`✅ 加载完成，共 ${commands.length} 帧，点击 ▶️ 开始播放`, 'ok');
}

function advanceFrame() {
    if (_state.currentFrame >= _state.commands.length) {
        _state.isPlaying = false;
        const playBtn = $('vizPlayBtn');
        if (playBtn) playBtn.style.display = 'inline-block';
        const pauseBtn = $('vizPauseBtn');
        if (pauseBtn) pauseBtn.style.display = 'none';
        logMsg(`✅ 回放完成，共 ${_state.commands.length} 帧`, 'ok');
        const statusEl = $('vizStatus');
        if (statusEl) statusEl.textContent = `✅ 完成 (${_state.commands.length}帧)`;
        if (_callbacks.onComplete) { _callbacks.onComplete(); }
        return;
    }
    _anim.prevState = applyCommandsUpTo(_state.currentFrame - 1);
    _anim.targetState = applyCommandsUpTo(_state.currentFrame);
    _anim.startTime = performance.now();
    updateCodePanel(_state.currentFrame);

    function animate(time) {
        const elapsed = time - _anim.startTime;
        const t = Math.min(elapsed / _anim.duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        const canvas = $('vizCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, canvas.width, canvas.height);
        const tgt = _anim.targetState;
        switch (tgt.vizType) {
            case 'array1d': renderArray1D(ctx, canvas, tgt, eased); break;
            case 'array2d': renderArray2D(ctx, canvas, tgt); break;
            case 'graph': renderGraph(ctx, canvas, tgt); break;
            case 'tree': renderTree(ctx, canvas, tgt); break;
        }
        const fi = _state.currentFrame;
        ctx.fillStyle = '#555'; ctx.textAlign = 'right'; ctx.font = '11px monospace';
        ctx.fillText(`帧: ${fi}/${_state.commands.length - 1}`, canvas.width - 12, 18);
        const frameInfo = $('vizFrameInfo');
        if (frameInfo) frameInfo.textContent = `帧: ${fi}/${_state.commands.length - 1}`;
        if (t < 1) {
            _anim.rafId = requestAnimationFrame(animate);
        } else {
            _anim.prevState = _anim.targetState;
            _state.currentFrame++;
            if (_state.isPlaying) {
                _state.playTimer = setTimeout(advanceFrame, Math.max(0, _state.speed - _anim.duration));
            }
        }
    }
    _anim.rafId = requestAnimationFrame(animate);
}

function play() {
    if (_state.isPlaying) return;
    _state.isPlaying = true;
    const playBtn = $('vizPlayBtn');
    if (playBtn) playBtn.style.display = 'none';
    const pauseBtn = $('vizPauseBtn');
    if (pauseBtn) pauseBtn.style.display = 'inline-block';
    logMsg('▶️ 开始播放', 'info');
    if (_callbacks.onPlay) { _callbacks.onPlay(); }
    advanceFrame();
}

function pause() {
    _state.isPlaying = false;
    if (_state.playTimer) { clearTimeout(_state.playTimer); _state.playTimer = null; }
    if (_anim.rafId) { cancelAnimationFrame(_anim.rafId); _anim.rafId = null; }
    const playBtn = $('vizPlayBtn');
    if (playBtn) playBtn.style.display = 'inline-block';
    const pauseBtn = $('vizPauseBtn');
    if (pauseBtn) pauseBtn.style.display = 'none';
    logMsg('⏸️ 已暂停', 'info');
    if (_callbacks.onComplete) { _callbacks.onComplete(); }
}

function reset() {
    _state.isPlaying = false;
    if (_state.playTimer) { clearTimeout(_state.playTimer); _state.playTimer = null; }
    if (_anim.rafId) { cancelAnimationFrame(_anim.rafId); _anim.rafId = null; }
    _state.currentFrame = 0;
    _anim.prevState = null;
    const playBtn = $('vizPlayBtn');
    if (playBtn) playBtn.style.display = 'inline-block';
    const pauseBtn = $('vizPauseBtn');
    if (pauseBtn) pauseBtn.style.display = 'none';
    const statusEl = $('vizStatus');
    if (statusEl) statusEl.textContent = '⏸️ 已重置';
    if (_state.commands.length > 0) renderFrameAnimated(0);
    updateCodePanel(-1);
    logMsg('🔄 已重置', 'info');
    if (_callbacks.onComplete) { _callbacks.onComplete(); }
}

function updateSpeed(speedValue) {
    _state.speed = parseInt(speedValue);
    const label = $('vizSpeedLabel');
    if (label) label.textContent = speedValue + 'ms';
    logMsg(`⚡ 速度已调整为 ${speedValue}ms/帧`, 'info');
}

function updateSpeedFromSlider(speedValue) {
    _state.speed = parseInt(speedValue);
    const label = $('vizSpeedLabel');
    if (label) label.textContent = speedValue + 'ms';
    const select = $('vizSpeedSelect');
    if (select) {
        const options = select.options;
        let matched = false;
        for (let i = 0; i < options.length; i++) {
            if (parseInt(options[i].value) === parseInt(speedValue)) {
                select.selectedIndex = i;
                matched = true;
                break;
            }
        }
        if (!matched) select.selectedIndex = -1;
    }
}

// ========== 主入口：启动可视化 ==========
async function start(apiData, statusCallback) {
    // apiData 为 codeVisualApi 返回的 res.data，格式：
    // { code, detectedType, originalCode, language, ... }
    // 强制清理残留动画/定时器（应对异常关闭场景）
    if (_anim.rafId) { cancelAnimationFrame(_anim.rafId); _anim.rafId = null; }
    if (_state.playTimer) { clearTimeout(_state.playTimer); _state.playTimer = null; }
    _state.isPlaying = false;
    _state.commands = [];
    _state.currentFrame = 0;
    _anim.prevState = null;
    _anim.targetState = null;

    const statusEl = $('vizStatus');
    const section = $('vizSection');
    if (section) section.style.display = 'block';
    // 显示父容器（vsArea）
    if (_container) _container.style.display = 'block';

    const setStatus = (msg) => {
        if (statusEl) statusEl.textContent = msg;
        if (statusCallback) statusCallback(msg);
    };

    const jsCode = apiData.code;
    const detectedType = apiData.detectedType || '未知算法';
    const originalCode = apiData.originalCode || '';
    const language = apiData.language || 'javascript';

    logMsg(`✅ 接口转换成功！检测类型: ${detectedType}`, 'ok');
    setStatus('⏳ 正在执行可视化代码...');

    if (!jsCode || jsCode.includes('好的，我将') || jsCode.includes('以下是转换后的代码')) {
        logMsg('❌ LLM返回了非代码文本，请重试', 'err');
        return { success: false, error: 'LLM返回了非代码文本' };
    }

    stopWorker();
    logMsg('🚀 正在加载 Worker 脚本和可视化库...', 'info');

    // 创建 workerText 副本用于后续 replace 操作
    let workerCode = workerText;

    // 将 Worker 内部的库加载块替换为直接嵌入的库代码
    const matchResult = workerCode.match(/if\s*\(!AlgorithmVisualizer\)\s*\{[\s\S]*?throw new Error\('Failed to load algorithm-visualizer library'\);\s*\}\s*\}/);
    if (matchResult) {
        logMsg('📝 匹配到库加载块，正在替换...', 'info');
        workerCode = workerCode.replace(
            /if\s*\(!AlgorithmVisualizer\)\s*\{[\s\S]*?throw new Error\('Failed to load algorithm-visualizer library'\);\s*\}\s*\}/,
            `if (!AlgorithmVisualizer) {
    eval(${JSON.stringify(libText)});
    AlgorithmVisualizer = self.AlgorithmVisualizer || this.AlgorithmVisualizer;
  }`
        );
    } else {
        logMsg('⚠️ 未匹配到库加载块，尝试备用方案', 'info');
        workerCode = workerCode.replace(
            /const xhr = new XMLHttpRequest\(\);[\s\S]*?eval\(xhr\.responseText\);/,
            `eval(${JSON.stringify(libText)});`
        );
    }

    // 修复：TreeTracer 不存在，映射为 GraphTracer
    workerCode = workerCode.replace(
        /const TreeTracer = AlgorithmVisualizer\.TreeTracer;[^\n]*/,
        'const TreeTracer = AlgorithmVisualizer.GraphTracer;'
    );

    // 注入 layoutTree 命令处理
    workerCode = workerCode.replace(
        /case 'delay':/,
        `case 'layoutTree':
        formattedCommands.push({ type: 'layoutTree', root: cmd.args[0] || 0 });
        break;
      case 'addNode':
        if (cmd.args.length >= 1) {
          formattedCommands.push({ type: 'addNode', id: cmd.args[0], weight: cmd.args[1] || null });
        }
        break;
      case 'delay':`
    );

    const workerBlob = new Blob([workerCode], { type: 'application/javascript' });
    const workerUrl = URL.createObjectURL(workerBlob);
    _worker = new Worker(workerUrl);
    URL.revokeObjectURL(workerUrl);
    const stopBtn = $('stopVizBtn');
    if (stopBtn) stopBtn.style.display = 'inline-block';

    _worker.onmessage = function (e) {
        const commands = e.data;
        if (commands && commands.error) {
            logMsg('❌ Worker错误: ' + commands.error, 'err');
            setStatus('❌ Worker执行失败');
            return;
        }
        logMsg(`✅ 收到 ${commands.length} 个可视化命令`, 'ok');
        setStatus(`✅ 渲染中... (${commands.length}帧)`);
        _transformedCode = jsCode;
        _originalCode = originalCode;
        _originalLang = language;
        _frameSrcLineMap = buildSrcLineMap(jsCode, commands);
        logMsg(`📝 源行号映射: ${_frameSrcLineMap.length} 帧, 显示${_originalLang}原始代码`, 'info');
        const renderCmds = commands.filter(c => c.type !== 'delay');
        const codePanel = $('vizCodePanel');
        if (codePanel) codePanel.style.display = 'block';
        updateCodePanel(-1);
        renderCommands(renderCmds);
    };

    _worker.onerror = function (e) {
        logMsg('❌ Worker异常: ' + e.message, 'err');
        setStatus('❌ 执行失败');
    };

    _worker.postMessage(jsCode);
    logMsg('🚀 Worker已启动，正在执行...', 'info');
    return { success: true };
}

// ========== 初始化模块 ==========
export function initVizModule(container, options = {}) {
    // 重置所有模块级状态（确保组件重建后无残留）
    if (_anim.rafId) { cancelAnimationFrame(_anim.rafId); _anim.rafId = null; }
    if (_state.playTimer) { clearTimeout(_state.playTimer); _state.playTimer = null; }
    _state = {
        commands: [], currentFrame: 0, isPlaying: false,
        playTimer: null, animTimer: null, speed: 180, vizType: 'array1d'
    };
    _anim = { startTime: 0, duration: 250, prevState: null, targetState: null, rafId: null };
    _transformedCode = '';
    _originalCode = '';
    _originalLang = '';
    _frameSrcLineMap = [];
    _callbacks = {
        onPlay: options.onPlay || null,
        onComplete: options.onComplete || null
    };
    _container = container;
    return {
        start,
        close: closeViz,
        stopWorker,
        destroy,
        play,
        pause,
        reset,
        updateSpeed,
        updateSpeedFromSlider,
        logMsg,
        setContainer(el) { _container = el; },
        getContainer() { return _container; },
        setCallbacks(cb) { _callbacks = { onPlay: cb.onPlay || null, onComplete: cb.onComplete || null }; },
        getState: () => _state,
        getCommandCount: () => _state.commands.length,
        isPlaying: () => _state.isPlaying
    };
}
