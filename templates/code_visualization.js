/**
 * 代码可视化组件
 * 从 agent_test.html 抽离的可视化预览功能
 * 支持：数组排序/查找、矩阵运算、图遍历、树遍历
 */

// ========== 全局状态 ==========
let preVizWorker = null;
let preVizTransformedCode = '';
let preVizOriginalCode = '';
let preVizOriginalLang = '';
let preVizFrameSrcLineMap = [];  // 帧索引 → 原始代码行号
let preVizFrameLineMap = [];

let preVizState = {
    commands: [], currentFrame: 0, isPlaying: false,
    playTimer: null, animTimer: null, speed: 180, vizType: 'array1d'
};
let preVizAnim = { startTime: 0, duration: 250, prevState: null, targetState: null, rafId: null };

// ========== 语法高亮 ==========
function highlightJsCode(code) {
    return code.split('\n').map(line => {
        let h = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        h = h.replace(/(\/\/.*)$/gm, '<span style="color:#6a737d;font-style:italic">$1</span>');
        h = h.replace(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`)/g, '<span style="color:#032f62">$1</span>');
        h = h.replace(/\b(const|let|var|function|for|while|if|else|return|new|true|false|null|undefined|typeof|break|continue|switch|case|default|class|extends|this|super|try|catch|throw|async|await|yield)\b/g, '<span style="color:#d73a49;font-weight:bold">$1</span>');
        h = h.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#005cc5">$1</span>');
        h = h.replace(/\b([A-Z]\w*)\b/g, '<span style="color:#6f42c1">$1</span>');
        return h;
    }).join('\n');
}

// 多语言语法高亮
function highlightCode(line, lang) {
    let s = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    
    // 字符串
    s = s.replace(/(["'])(?:(?!\1|\\).|\\.)*\1/g, '<span style="color:#032f62">$&</span>');
    // 注释
    if (lang === 'python') {
        s = s.replace(/(#.*)$/gm, '<span style="color:#6a737d;font-style:italic">$1</span>');
    } else {
        s = s.replace(/(\/\/.*)$/gm, '<span style="color:#6a737d;font-style:italic">$1</span>');
    }
    // 数字
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#005cc5">$1</span>');
    // 关键字
    const kw = lang === 'python' 
        ? /\b(def|class|if|elif|else|for|while|return|import|from|in|not|and|or|True|False|None|range|len|print|append|self|pass|break|continue|try|except|finally|with|as|lambda|yield|global|nonlocal)\b/g
        : lang === 'java' || lang === 'c' || lang === 'cpp'
        ? /\b(public|private|protected|static|final|void|int|long|float|double|char|boolean|String|class|interface|extends|implements|new|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|throws|import|package|this|super|null|true|false)\b/g
        : /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|class|extends|import|export|from|default|true|false|null|undefined|this|super|async|await|try|catch|finally|throw)\b/g;
    s = s.replace(kw, '<span style="color:#d73a49;font-weight:bold">$&</span>');
    
    return s;
}

// ========== 帧→源行号映射 ==========
function buildSrcLineMap(transformedCode, commands) {
    const map = [];
    const jsLines = transformedCode.split('\n');
    
    const jsToSrc = {};
    jsLines.forEach((line, idx) => {
        const m = line.match(/\/\/src:(\d+)/);
        if (m) {
            jsToSrc[idx] = parseInt(m[1]) - 1;
        }
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
    
    // 兜底：静态扫描
    jsLines.forEach(line => {
        if (/Tracer\.delay\s*\(/.test(line)) {
            const m = line.match(/\/\/src:(\d+)/);
            map.push(m ? parseInt(m[1]) - 1 : 0);
        }
    });
    return map;
}

// ========== 代码面板渲染 ==========
function updatePreVizCodePanel(highlightFrame) {
    const code = preVizOriginalCode || preVizTransformedCode;
    if (!code) return;
    const lang = preVizOriginalLang || 'javascript';
    const lines = code.split('\n');

    let currentSrcLine = -1;
    if (highlightFrame >= 0 && highlightFrame < preVizFrameSrcLineMap.length) {
        currentSrcLine = preVizFrameSrcLineMap[highlightFrame];
    }

    const html = lines.map((line, i) => {
        const hl = highlightCode(line, lang);
        const num = String(i + 1).padStart(3, ' ');
        const isCurrent = (i === currentSrcLine);
        const bg = isCurrent ? '#fff3bf' : '';
        const border = isCurrent ? 'border-left:3px solid #e67700;' : '';
        const numColor = isCurrent ? '#e67700' : '#8b949e';
        const fontWeight = isCurrent ? 'font-weight:bold;' : '';

        return `<div style="padding:1px 10px 1px 0;white-space:pre;background:${bg};${border}${fontWeight}transition:background 0.15s;" class="code-line" data-line="${i}"><span style="color:${numColor};user-select:none;display:inline-block;width:36px;text-align:right;margin-right:12px;font-size:11px;">${num}</span><span style="color:#24292f">${hl}</span></div>`;
    }).join('');

    const el = document.getElementById('preVizCodeContent');
    if (el) {
        el.innerHTML = html;
        if (currentSrcLine >= 0) {
            const lineEl = el.querySelector(`[data-line="${currentSrcLine}"]`);
            if (lineEl) lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

// ========== 日志 ==========
function preVizLogMsg(msg, type) {
    const el = document.getElementById('preVizLog');
    if (!el) return;
    const div = document.createElement('div');
    div.style.cssText = 'padding: 3px 8px; border-radius: 4px; margin: 2px 0; font-size: 13px;';
    if (type === 'ok') { div.style.background = '#0a3d0a'; div.style.color = '#00ff88'; }
    else if (type === 'err') { div.style.background = '#3d0a0a'; div.style.color = '#ff6666'; }
    else { div.style.background = '#0a1a3d'; div.style.color = '#88aaff'; }
    div.textContent = msg;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

// ========== Worker 控制 ==========
function stopPreVizWorker() {
    if (preVizWorker) { preVizWorker.terminate(); preVizWorker = null; }
    const btn = document.getElementById('stopPreVizBtn');
    if (btn) btn.style.display = 'none';
    preVizLogMsg('⏹️ Worker已停止', 'info');
}

function closePreViz() {
    stopPreVizWorker();
    if (preVizAnim.rafId) { cancelAnimationFrame(preVizAnim.rafId); preVizAnim.rafId = null; }
    if (preVizState.playTimer) { clearTimeout(preVizState.playTimer); preVizState.playTimer = null; }
    preVizState.isPlaying = false;
    preVizTransformedCode = '';
    preVizOriginalCode = '';
    preVizOriginalLang = '';
    preVizFrameSrcLineMap = [];
    const section = document.getElementById('preVizSection');
    if (section) section.style.display = 'none';
    const codePanel = document.getElementById('preVizCodePanel');
    if (codePanel) codePanel.style.display = 'none';
}

// ========== 主入口：预览可视化 ==========
async function previewVisualization() {
    const code = document.getElementById('codeEditor').value.trim();
    const lang = document.getElementById('languageSelector').value;
    if (!code) { alert('请先编写代码！'); return; }

    const btn = document.getElementById('preVizBtn');
    const section = document.getElementById('preVizSection');
    const statusEl = document.getElementById('preVizStatus');

    section.style.display = 'block';
    document.getElementById('preVizLog').innerHTML = '';
    statusEl.textContent = '⏳ 正在调用 LLM 转换代码...';
    btn.disabled = true; btn.textContent = '⏳ 转换中...';

    if (lang !== 'javascript') {
        preVizLogMsg(`ℹ️ 检测到语言: ${lang}，将通过 LLM 转换为 JS 可视化代码`, 'info');
    }

    // 自动使用题目的示例测试数据
    let testData = '';
    if (typeof currentProblemData !== 'undefined' && currentProblemData && currentProblemData.examples && currentProblemData.examples.length > 0) {
        testData = currentProblemData.examples[0].input || '';
        if (testData) {
            preVizLogMsg(`📥 自动使用题目示例数据: ${testData.substring(0, 80)}${testData.length > 80 ? '...' : ''}`, 'info');
        }
    }

    try {
        const API_BASE = window.API_BASE || '';
        const res = await fetch(`${API_BASE}/api/visualize/transform`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, algorithmType: 'auto', language: lang, testData: testData })
        });
        const data = await res.json();
        if (!data.success) { throw new Error(data.error || 'LLM转换失败'); }

        preVizLogMsg(`✅ LLM转换成功！检测类型: ${data.detectedType}`, 'ok');
        statusEl.textContent = '⏳ 正在执行可视化代码...';

        if (!data.code.includes('Array1DTracer') && !data.code.includes('Array2DTracer') && !data.code.includes('GraphTracer')) {
            console.warn('⚠️ 警告：代码中未检测到 Tracer 构造');
        }
        if (data.code.includes('好的，我将') || data.code.includes('以下是转换后的代码')) {
            console.error('❌ 错误：代码中包含自然语言文本，不是纯 JS！');
            preVizLogMsg('❌ LLM返回了非代码文本，请重试', 'err');
            btn.disabled = false; btn.textContent = '🎨 可视化预览';
            return;
        }

        stopPreVizWorker();
        preVizLogMsg('🚀 正在加载 Worker 脚本和可视化库...', 'info');

        const [workerRes, libRes] = await Promise.all([
            fetch(`${API_BASE}/api/tracers/js/worker`),
            fetch(`${API_BASE}/api/tracers/js`)
        ]);
        let workerText = await workerRes.text();
        const libText = await libRes.text();

        // 将 Worker 内部的库加载块替换为直接嵌入的库代码
        const matchResult = workerText.match(/if\s*\(!AlgorithmVisualizer\)\s*\{[\s\S]*?throw new Error\('Failed to load algorithm-visualizer library'\);\s*\}\s*\}/);
        if (matchResult) {
            preVizLogMsg('📝 匹配到库加载块，正在替换...', 'info');
            workerText = workerText.replace(
                /if\s*\(!AlgorithmVisualizer\)\s*\{[\s\S]*?throw new Error\('Failed to load algorithm-visualizer library'\);\s*\}\s*\}/,
                `if (!AlgorithmVisualizer) {
    eval(${JSON.stringify(libText)});
    AlgorithmVisualizer = self.AlgorithmVisualizer || this.AlgorithmVisualizer;
  }`
            );
        } else {
            preVizLogMsg('⚠️ 未匹配到库加载块，尝试备用方案', 'info');
            workerText = workerText.replace(
                /const xhr = new XMLHttpRequest\(\);[\s\S]*?eval\(xhr\.responseText\);/,
                `eval(${JSON.stringify(libText)});`
            );
        }

        // 修复：TreeTracer 不存在，映射为 GraphTracer
        workerText = workerText.replace(
            /const TreeTracer = AlgorithmVisualizer\.TreeTracer;[^\n]*/,
            'const TreeTracer = AlgorithmVisualizer.GraphTracer;'
        );

        // 注入 layoutTree 命令处理
        workerText = workerText.replace(
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

        const workerBlob = new Blob([workerText], { type: 'application/javascript' });
        const workerUrl = URL.createObjectURL(workerBlob);
        preVizWorker = new Worker(workerUrl);
        URL.revokeObjectURL(workerUrl);
        document.getElementById('stopPreVizBtn').style.display = 'inline-block';

        preVizWorker.onmessage = function(e) {
            const commands = e.data;
            if (commands && commands.error) {
                preVizLogMsg('❌ Worker错误: ' + commands.error, 'err');
                statusEl.textContent = '❌ Worker执行失败';
                btn.disabled = false; btn.textContent = '🎨 可视化预览';
                return;
            }
            preVizLogMsg(`✅ 收到 ${commands.length} 个可视化命令`, 'ok');
            statusEl.textContent = `✅ 渲染中... (${commands.length}帧)`;
            preVizTransformedCode = data.code;
            preVizOriginalCode = data.originalCode || '';
            preVizOriginalLang = data.language || 'javascript';
            preVizFrameSrcLineMap = buildSrcLineMap(data.code, commands);
            preVizLogMsg(`📝 源行号映射: ${preVizFrameSrcLineMap.length} 帧, 显示${preVizOriginalLang}原始代码`, 'info');
            const renderCmds = commands.filter(c => c.type !== 'delay');
            const codePanel = document.getElementById('preVizCodePanel');
            if (codePanel) codePanel.style.display = 'block';
            updatePreVizCodePanel(-1);
            preVizRenderCommands(renderCmds);
            btn.disabled = false; btn.textContent = '🎨 可视化预览';
        };

        preVizWorker.onerror = function(e) {
            preVizLogMsg('❌ Worker异常: ' + e.message, 'err');
            statusEl.textContent = '❌ 执行失败';
            btn.disabled = false; btn.textContent = '🎨 可视化预览';
        };

        preVizWorker.postMessage(data.code);
        preVizLogMsg('🚀 Worker已启动，正在执行...', 'info');

    } catch (e) {
        preVizLogMsg('❌ 失败: ' + e.message, 'err');
        statusEl.textContent = '❌ 转换失败';
        btn.disabled = false; btn.textContent = '🎨 可视化预览';
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
    const cmds = preVizState.commands;
    const s = { data: null, highlights: {}, vizType: 'array1d',
                nodes: null, edges: null, treeRoot: null, lastLog: '' };
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
                    s.nodes = (c.nodes || []).map(n => ({...n}));
                    s.edges = (c.edges || []).map(e => ({...e}));
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

// ========== 动画渲染引擎 ==========
function renderFrameAnimated(frameIndex) {
    const canvas = document.getElementById('preVizCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const target = applyCommandsUpTo(frameIndex);
    preVizState.vizType = target.vizType;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    switch (target.vizType) {
        case 'array1d': renderArray1D(ctx, canvas, target); break;
        case 'array2d': renderArray2D(ctx, canvas, target); break;
        case 'graph':   renderGraph(ctx, canvas, target);   break;
        case 'tree':    renderTree(ctx, canvas, target);    break;
        default:
            ctx.fillStyle = '#666'; ctx.font = '14px monospace'; ctx.textAlign = 'center';
            ctx.fillText('不支持的可视化类型: ' + target.vizType, canvas.width/2, canvas.height/2);
    }
    ctx.fillStyle = '#555'; ctx.textAlign = 'right'; ctx.font = '11px monospace';
    ctx.fillText(`帧: ${frameIndex}/${preVizState.commands.length - 1}`, canvas.width - 12, 18);
    document.getElementById('preVizFrameInfo').textContent = `帧: ${frameIndex}/${preVizState.commands.length - 1}`;
    updatePreVizCodePanel(frameIndex);
}

// ========== Array1D 渲染器（柱状图） ==========
function renderArray1D(ctx, canvas, state, lerpT) {
    if (!state.data || !state.data.length) {
        ctx.fillStyle='#666'; ctx.font='16px monospace'; ctx.textAlign='center';
        ctx.fillText('等待数据...', canvas.width/2, canvas.height/2); return;
    }
    const data = state.data, n = data.length, hl = state.highlights;
    const maxVal = Math.max(...data, 1);
    const barW = Math.min(80, (canvas.width - 40) / n - 4);
    const maxH = canvas.height - 70;
    const startX = (canvas.width - n * (barW + 4)) / 2;
    const t = (lerpT !== undefined) ? lerpT : 1;
    const prev = preVizAnim.prevState;

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
        const r = Math.min(4, barW/4);
        ctx.moveTo(x, y + barH); ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.lineTo(x + barW - r, y);
        ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
        ctx.lineTo(x + barW, y + barH); ctx.closePath(); ctx.fill();

        ctx.fillStyle = '#fff'; ctx.font = 'bold 13px monospace'; ctx.textAlign = 'center';
        ctx.fillText(Math.round(dispVal), x + barW/2, y - 8);
        ctx.fillStyle = '#888'; ctx.font = '11px monospace';
        ctx.fillText(i, x + barW/2, canvas.height - 22);
    }
}

// ========== Array2D 渲染器（矩阵/网格） ==========
function renderArray2D(ctx, canvas, state) {
    if (!state.data || !state.data.length) return;
    const data = state.data, rows = data.length, cols = data[0].length, hl = state.highlights;
    const pad = 30;
    const cellW = Math.min(60, (canvas.width - pad*2) / cols);
    const cellH = Math.min(40, (canvas.height - pad*2) / rows);
    const oX = (canvas.width - cols * cellW) / 2;
    const oY = (canvas.height - rows * cellH) / 2;

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const x = oX + c * cellW, y = oY + r * cellH;
            const key = `${r},${c}`, key2 = `${r * cols + c}`;
            const hColor = hl[key] || hl[key2];
            ctx.fillStyle = hColor || '#1a2332';
            ctx.fillRect(x+1, y+1, cellW-2, cellH-2);
            ctx.strokeStyle = '#3a4a5a'; ctx.lineWidth = 1;
            ctx.strokeRect(x, y, cellW, cellH);
            ctx.fillStyle = '#e0e0e0'; ctx.font = `${Math.min(14, cellH*0.45)}px monospace`;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(String(data[r][c]), x + cellW/2, y + cellH/2);
        }
    }
}

// ========== Graph 渲染器（圆形布局） ==========
function renderGraph(ctx, canvas, state) {
    if (!state.nodes || !state.nodes.length) {
        ctx.fillStyle='#666'; ctx.font='14px monospace'; ctx.textAlign='center';
        ctx.fillText('等待图数据...', canvas.width/2, canvas.height/2); return;
    }
    const nodes = state.nodes, edges = state.edges || [], hl = state.highlights;
    const cX = canvas.width/2, cY = canvas.height/2;
    const radius = Math.min(cX, cY) - 60;
    const positions = [];
    for (let i = 0; i < nodes.length; i++) {
        const a = (2*Math.PI*i/nodes.length) - Math.PI/2;
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
            const mx = (f.x+t.x)/2, my = (f.y+t.y)/2;
            ctx.fillStyle='#0d1117'; ctx.fillRect(mx-12, my-8, 24, 16);
            ctx.fillStyle='#aaa'; ctx.font='10px monospace'; ctx.textAlign='center'; ctx.textBaseline='middle';
            ctx.fillText(String(e.weight), mx, my);
        }
        const dx = t.x-f.x, dy = t.y-f.y, angle = Math.atan2(dy, dx);
        const aL = 10, nR = 22;
        const ax = t.x - Math.cos(angle)*nR, ay = t.y - Math.sin(angle)*nR;
        ctx.beginPath(); ctx.moveTo(ax, ay);
        ctx.lineTo(ax - aL*Math.cos(angle-0.4), ay - aL*Math.sin(angle-0.4));
        ctx.lineTo(ax - aL*Math.cos(angle+0.4), ay - aL*Math.sin(angle+0.4));
        ctx.closePath(); ctx.fillStyle = isHl || '#4a5568'; ctx.fill();
    });
    const nR = 22;
    nodes.forEach((node, i) => {
        const p = positions[i];
        const nKey = String(node.id), nKey2 = String(i);
        const isHl = hl[nKey] || hl[nKey2];
        ctx.beginPath(); ctx.arc(p.x, p.y, nR, 0, Math.PI*2);
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
        ctx.fillStyle='#666'; ctx.font='14px monospace'; ctx.textAlign='center';
        ctx.fillText('等待树数据...', canvas.width/2, canvas.height/2); return;
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
        for (const c of ch) { const l = layout(c, depth+1, cur); if (l) { laid.push(l); cur += countW(c); } }
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
        ctx.beginPath(); ctx.arc(np.x, np.y, nR, 0, Math.PI*2);
        ctx.fillStyle = isHl || '#2d3748'; ctx.fill();
        ctx.strokeStyle = isHl || '#4ec9b0'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = '#fff'; ctx.font = 'bold 13px monospace';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const label = np.node ? (np.node.value !== undefined ? np.node.value : np.node.id) : np.id;
        ctx.fillText(String(label), np.x, np.y);
    });
}

// ========== 播放控制 ==========
function preVizRenderCommands(commands) {
    preVizState.commands = commands;
    preVizState.currentFrame = 0;
    preVizState.vizType = 'array1d';
    preVizAnim.prevState = null;
    document.getElementById('preVizControls').style.display = 'flex';
    document.getElementById('preVizPlayBtn').style.display = 'inline-block';
    document.getElementById('preVizPauseBtn').style.display = 'none';
    document.getElementById('preVizFrameInfo').textContent = `帧: 0/${commands.length}`;
    renderFrameAnimated(0);
    preVizLogMsg(`✅ 加载完成，共 ${commands.length} 帧，点击 ▶️ 开始播放`, 'ok');
}

function preVizAdvanceFrame() {
    if (preVizState.currentFrame >= preVizState.commands.length) {
        preVizState.isPlaying = false;
        document.getElementById('preVizPlayBtn').style.display = 'inline-block';
        document.getElementById('preVizPauseBtn').style.display = 'none';
        preVizLogMsg(`✅ 回放完成，共 ${preVizState.commands.length} 帧`, 'ok');
        document.getElementById('preVizStatus').textContent = `✅ 完成 (${preVizState.commands.length}帧)`;
        return;
    }
    preVizAnim.prevState = applyCommandsUpTo(preVizState.currentFrame - 1);
    preVizAnim.targetState = applyCommandsUpTo(preVizState.currentFrame);
    preVizAnim.startTime = performance.now();
    updatePreVizCodePanel(preVizState.currentFrame);

    function animate(time) {
        const elapsed = time - preVizAnim.startTime;
        const t = Math.min(elapsed / preVizAnim.duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        const canvas = document.getElementById('preVizCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, canvas.width, canvas.height);
        const tgt = preVizAnim.targetState;
        switch (tgt.vizType) {
            case 'array1d': renderArray1D(ctx, canvas, tgt, eased); break;
            case 'array2d': renderArray2D(ctx, canvas, tgt); break;
            case 'graph':   renderGraph(ctx, canvas, tgt); break;
            case 'tree':    renderTree(ctx, canvas, tgt); break;
        }
        const fi = preVizState.currentFrame;
        ctx.fillStyle='#555'; ctx.textAlign='right'; ctx.font='11px monospace';
        ctx.fillText(`帧: ${fi}/${preVizState.commands.length - 1}`, canvas.width-12, 18);
        document.getElementById('preVizFrameInfo').textContent = `帧: ${fi}/${preVizState.commands.length - 1}`;
        if (t < 1) {
            preVizAnim.rafId = requestAnimationFrame(animate);
        } else {
            preVizAnim.prevState = preVizAnim.targetState;
            preVizState.currentFrame++;
            if (preVizState.isPlaying) {
                preVizState.playTimer = setTimeout(preVizAdvanceFrame, Math.max(0, preVizState.speed - preVizAnim.duration));
            }
        }
    }
    preVizAnim.rafId = requestAnimationFrame(animate);
}

function preVizPlay() {
    if (preVizState.isPlaying) return;
    preVizState.isPlaying = true;
    document.getElementById('preVizPlayBtn').style.display = 'none';
    document.getElementById('preVizPauseBtn').style.display = 'inline-block';
    preVizLogMsg('▶️ 开始播放', 'info');
    preVizAdvanceFrame();
}

function preVizPause() {
    preVizState.isPlaying = false;
    if (preVizState.playTimer) { clearTimeout(preVizState.playTimer); preVizState.playTimer = null; }
    if (preVizAnim.rafId) { cancelAnimationFrame(preVizAnim.rafId); preVizAnim.rafId = null; }
    document.getElementById('preVizPlayBtn').style.display = 'inline-block';
    document.getElementById('preVizPauseBtn').style.display = 'none';
    preVizLogMsg('⏸️ 已暂停', 'info');
}

function preVizReset() {
    preVizState.isPlaying = false;
    if (preVizState.playTimer) { clearTimeout(preVizState.playTimer); preVizState.playTimer = null; }
    if (preVizAnim.rafId) { cancelAnimationFrame(preVizAnim.rafId); preVizAnim.rafId = null; }
    preVizState.currentFrame = 0;
    preVizAnim.prevState = null;
    document.getElementById('preVizPlayBtn').style.display = 'inline-block';
    document.getElementById('preVizPauseBtn').style.display = 'none';
    document.getElementById('preVizStatus').textContent = '⏸️ 已重置';
    if (preVizState.commands.length > 0) renderFrameAnimated(0);
    updatePreVizCodePanel(-1);
    preVizLogMsg('🔄 已重置', 'info');
}

function updatePreVizSpeed(speedValue) {
    preVizState.speed = parseInt(speedValue);
    document.getElementById('preVizSpeed').value = speedValue;
    document.getElementById('preVizSpeedLabel').textContent = speedValue + 'ms';
    preVizLogMsg(`⚡ 速度已调整为 ${speedValue}ms/帧`, 'info');
}

function updatePreVizSpeedFromSlider(speedValue) {
    preVizState.speed = parseInt(speedValue);
    document.getElementById('preVizSpeedLabel').textContent = speedValue + 'ms';

    const select = document.getElementById('preVizSpeedSelect');
    const options = select.options;
    let matched = false;
    for (let i = 0; i < options.length; i++) {
        if (parseInt(options[i].value) === parseInt(speedValue)) {
            select.selectedIndex = i;
            matched = true;
            break;
        }
    }
    if (!matched) {
        select.selectedIndex = -1;
    }
}

console.log('✅ code_visualization.js 加载完成');
