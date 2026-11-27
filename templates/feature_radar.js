/**
 * 学生8维度特征雷达图可视化模块
 * 功能：展示练题前后特征变化的对比效果
 */

// 8维度特征映射
const DIMENSION_MAP = {
    'academic_background': '学术背景',
    'learning_behavior': '学习行为',
    'goal_motivation': '目标动机',
    'cognitive_abilities': '认知能力',
    'emotional_state': '情绪状态',
    'social_interaction': '社交互动',
    'time_management': '时间管理',
    'creativity_innovation': '创新创造'
};

// 8维度排序（用于雷达图）
const DIMENSIONS_ORDER = [
    'academic_background',
    'learning_behavior',
    'goal_motivation',
    'cognitive_abilities',
    'emotional_state',
    'social_interaction',
    'time_management',
    'creativity_innovation'
];

/**
 * 初始化雷达图
 */
function initRadarChart() {
    if (radarChart) return; // 已初始化则跳过
    
    const chartDom = document.getElementById('radarChart');
    if (!chartDom) return;

    radarChart = echarts.init(chartDom);

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                return `${params.seriesName}<br/>${params.name}: ${params.value}`;
            }
        },
        legend: {
            show: false
        },
        radar: {
            indicator: DIMENSIONS_ORDER.map(dim => ({
                name: DIMENSION_MAP[dim],
                max: 100
            })),
            shape: 'polygon',
            splitNumber: 5,
            axisName: {
                color: '#333',
                fontSize: 13,
                fontWeight: 'bold'
            },
            splitLine: {
                lineStyle: {
                    color: '#e0e0e0'
                }
            },
            splitArea: {
                show: true,
                areaStyle: {
                    color: ['rgba(102, 126, 234, 0.05)', 'rgba(102, 126, 234, 0.1)']
                }
            },
            axisLine: {
                lineStyle: {
                    color: '#d0d0d0'
                }
            }
        },
        series: [
            {
                name: '特征对比',
                type: 'radar',
                data: [
                    {
                        value: [0, 0, 0, 0, 0, 0, 0, 0],
                        name: '更新前',
                        lineStyle: {
                            color: '#5470c6',
                            width: 3
                        },
                        itemStyle: {
                            color: '#5470c6'
                        },
                        areaStyle: {
                            color: 'rgba(84, 112, 198, 0.3)'
                        },
                        symbol: 'circle',
                        symbolSize: 8
                    },
                    {
                        value: [0, 0, 0, 0, 0, 0, 0, 0],
                        name: '更新后',
                        lineStyle: {
                            color: '#ee6666',
                            width: 3
                        },
                        itemStyle: {
                            color: '#ee6666'
                        },
                        areaStyle: {
                            color: 'rgba(238, 102, 102, 0.3)'
                        },
                        symbol: 'circle',
                        symbolSize: 8
                    }
                ]
            }
        ]
    };

    radarChart.setOption(option);
}

/**
 * 从API加载用户特征并显示雷达图
 */
async function updateRadarFromAPI() {
    const userId = document.getElementById('userId').value.trim();
    if (!userId) {
        alert('请先填写用户ID！');
        return;
    }

    try {
        // 保存更新前的特征
        previousFeatures = JSON.parse(JSON.stringify(currentFeatures));

        // 调用API获取最新特征
        const response = await fetch(`${API_BASE}/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                user_input: '查看我的特征',
                task_type: 'chat'
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.detail || '获取特征失败');
        }

        // 从响应中提取特征数据
        const result = data.data;
        if (result.data && result.data.student_features) {
            currentFeatures = result.data.student_features;
        } else {
            throw new Error('未找到特征数据');
        }

        // 显示雷达图区域
        const radarSection = document.getElementById('radarSection');
        radarSection.style.display = 'block';

        // 初始化雷达图
        initRadarChart();

        // 更新雷达图
        updateRadarDisplay();

        // 显示维度卡片
        displayDimensionCards();

        // 滚动到雷达图区域
        radarSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        console.log('✅ 雷达图已更新');

    } catch (error) {
        console.error('加载特征失败:', error);
        alert(`加载失败: ${error.message}`);
    }
}

/**
 * 更新雷达图显示
 */
function updateRadarDisplay() {
    if (!radarChart || !currentFeatures) return;

    const oldValues = previousFeatures ? 
        DIMENSIONS_ORDER.map(dim => previousFeatures[dim]?.score || 0) :
        DIMENSIONS_ORDER.map(() => 0);

    const newValues = DIMENSIONS_ORDER.map(dim => currentFeatures[dim]?.score || 0);

    const option = {
        series: [{
            data: [
                {
                    value: oldValues,
                    name: '更新前'
                },
                {
                    value: newValues,
                    name: '更新后'
                }
            ]
        }]
    };

    radarChart.setOption(option);
}

/**
 * 显示维度分数卡片
 */
function displayDimensionCards() {
    const container = document.getElementById('dimensionScores');
    if (!container || !currentFeatures) return;

    const dimensionIcons = {
        'academic_background': '📚',
        'learning_behavior': '🎯',
        'goal_motivation': '🎪',
        'cognitive_abilities': '🧠',
        'emotional_state': '😊',
        'social_interaction': '🤝',
        'time_management': '⏰',
        'creativity_innovation': '💡'
    };

    let html = '';
    DIMENSIONS_ORDER.forEach(dim => {
        const name = DIMENSION_MAP[dim];
        const icon = dimensionIcons[dim] || '📊';
        const newScore = currentFeatures[dim]?.score || 0;
        const oldScore = previousFeatures?.[dim]?.score || 0;
        const change = newScore - oldScore;

        let changeClass = 'change-neutral';
        let changeIcon = '→';
        if (change > 0) {
            changeClass = 'change-positive';
            changeIcon = '↑';
        } else if (change < 0) {
            changeClass = 'change-negative';
            changeIcon = '↓';
        }

        html += `
            <div class="dimension-card">
                <div class="dimension-name">${icon} ${name}</div>
                <div class="dimension-score-row">
                    <span class="score-label">更新前</span>
                    <span class="score-value">${oldScore}</span>
                </div>
                <div class="dimension-score-row">
                    <span class="score-label">更新后</span>
                    <span class="score-value">${newScore}</span>
                </div>
                <div class="score-change ${changeClass}">
                    ${changeIcon} ${Math.abs(change)}分
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * 在代码提交成功后自动更新雷达图
 */
function autoUpdateRadarAfterSubmit(judgeResult) {
    // 保存更新前的特征
    previousFeatures = currentFeatures ? JSON.parse(JSON.stringify(currentFeatures)) : null;

    // 从评判结果中获取更新后的特征
    if (judgeResult && judgeResult.updated_features) {
        currentFeatures = judgeResult.updated_features;
    }

    // 如果已经有雷达图显示，则更新它
    const radarSection = document.getElementById('radarSection');
    if (radarSection && radarSection.style.display !== 'none') {
        updateRadarDisplay();
        displayDimensionCards();
    }
}

/**
 * 监听评分结果并自动更新雷达图
 */
const originalDisplayJudgeResult = window.displayJudgeResult;
window.displayJudgeResult = function(data) {
    // 调用原函数
    if (originalDisplayJudgeResult) {
        originalDisplayJudgeResult(data);
    }

    // 自动更新雷达图
    if (data.success && data.judge_result) {
        setTimeout(() => {
            autoUpdateRadarAfterSubmit(data.judge_result);
        }, 1000);
    }
};

// 页面加载完成后初始化
window.addEventListener('load', function() {
    console.log('✅ 雷达图模块已加载');
});

// 窗口大小变化时重绘图表
window.addEventListener('resize', function() {
    if (radarChart) {
        radarChart.resize();
    }
});
