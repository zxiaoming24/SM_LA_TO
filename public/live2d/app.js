/**
 * Live2D 模型展示应用
 * 使用 pixi-live2d-display 库实现完整的模型渲染
 */

// 模型配置映射 - 用于处理不同模型的文件夹结构
const MODEL_CONFIGS = {
    'Mao': {
        path: './Mao/mao_pro.model3.json',
        motions: {
            'Idle': ['motions/mtn_01.motion3.json'],
            'TapBody': [
                'motions/mtn_02.motion3.json',
                'motions/mtn_03.motion3.json',
                'motions/mtn_04.motion3.json',
                'motions/special_01.motion3.json',
                'motions/special_02.motion3.json',
                'motions/special_03.motion3.json'
            ]
        },
        expressions: [
            'expressions/exp_01.exp3.json',
            'expressions/exp_02.exp3.json',
            'expressions/exp_03.exp3.json',
            'expressions/exp_04.exp3.json',
            'expressions/exp_05.exp3.json',
            'expressions/exp_06.exp3.json',
            'expressions/exp_07.exp3.json',
            'expressions/exp_08.exp3.json'
        ]
    },
    'asuka': {
        path: './asuka/Asuka.model3.json',
        motions: {
            'Idle': ['MODEL PREVIEW.motion3.json'],
            'Tap': [
                'ANIMATIONS/Hand wave.motion3.json',
                'ANIMATIONS/cry.motion3.json'
            ]
        },
        expressions: [
            'EXPRESSIONS/Gloom.exp3.json',
            'EXPRESSIONS/Happy Sparkle.exp3.json',
            'EXPRESSIONS/Star Eyes Toggle.exp3.json',
            'EXPRESSIONS/coat toggle.exp3.json'
        ]
    },
    'huohuo': {
        path: './huohuo/huohuo.model3.json',
        motions: {
            'Idle': [
                'Scene1.motion3.json',
                'haoqi.motion3.json',
                'keshui.motion3.json',
                'linghun.motion3.json',
                'qizi.motion3.json',
                'yaotou.motion3.json',
                'zhentou.motion3.json'
            ]
        },
        expressions: [
            'angry.exp3.json',
            'baozhen.exp3.json',
            'cry.exp3.json',
            'qizi1.exp3.json',
            'qizi2.exp3.json',
            'white eyes.exp3.json'
        ]
    },
    'icegirl': {
        path: './icegirl/IceGirl.model3.json',
        motions: {
            'Idle': [
                'DaiJi.motion3.json',
                'HuiShou.motion3.json',
                'MeiYan.motion3.json'
            ]
        },
        expressions: [
            '←歪嘴.exp3.json',
            '惊讶.exp3.json',
            '手柄.exp3.json',
            '披发.exp3.json',
            '星星眼.exp3.json',
            '歪嘴→.exp3.json',
            '流泪.exp3.json',
            '爱心眼.exp3.json',
            '猫耳.exp3.json',
            '王冠.exp3.json',
            '生气.exp3.json',
            '疑惑.exp3.json',
            '白眼.exp3.json',
            '直播套装.exp3.json',
            '翅膀.exp3.json',
            '脸红.exp3.json',
            '脸黑.exp3.json',
            '舌头.exp3.json',
            '金钱眼.exp3.json',
            '马尾.exp3.json'
        ]
    },
    'haihupu': {
        path: './haihupu/haihupu__nchan.model3.json',
        motions: {},
        expressions: []
    },
    'pachan': {
        path: './pachan/pachirisu anime girl - top half.model3.json',
        motions: {},
        expressions: []
    },
    'ren_pro_zh': {
        path: './haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json',
        motions: {
            'Idle': ['motion/haru_g_idle.motion3.json'],
            'TapBody': [
                'motion/haru_g_m01.motion3.json',
                'motion/haru_g_m02.motion3.json',
                'motion/haru_g_m03.motion3.json',
                'motion/haru_g_m04.motion3.json',
                'motion/haru_g_m05.motion3.json',
                'motion/haru_g_m06.motion3.json',
                'motion/haru_g_m07.motion3.json',
                'motion/haru_g_m08.motion3.json',
                'motion/haru_g_m09.motion3.json',
                'motion/haru_g_m10.motion3.json',
                'motion/haru_g_m11.motion3.json',
                'motion/haru_g_m12.motion3.json',
                'motion/haru_g_m13.motion3.json',
                'motion/haru_g_m14.motion3.json',
                'motion/haru_g_m15.motion3.json',
                'motion/haru_g_m16.motion3.json',
                'motion/haru_g_m17.motion3.json',
                'motion/haru_g_m18.motion3.json',
                'motion/haru_g_m19.motion3.json',
                'motion/haru_g_m20.motion3.json',
                'motion/haru_g_m21.motion3.json',
                'motion/haru_g_m22.motion3.json',
                'motion/haru_g_m23.motion3.json',
                'motion/haru_g_m24.motion3.json',
                'motion/haru_g_m25.motion3.json',
                'motion/haru_g_m26.motion3.json'
            ]
        },
        expressions: [
            'expressions/happy.exp3.json',
            'expressions/sad.exp3.json',
            'expressions/angry.exp3.json'
        ],
        note: '已将空字符串动作组重构为 Idle 和 TapBody 两个动作组，并添加了3个基础表情'
    }
};

class Live2DApp {
    constructor() {
        this.app = null;
        this.currentModel = null;
        this.currentModelName = '';
        this.autoBreath = true;
        this.motionGroups = {};
        this.expressionList = [];

        this.init();
    }

    async init() {
        // 创建 PixiJS 应用
        const canvas = document.getElementById('canvas');
        const container = canvas.parentElement;

        // 1. 确保 Canvas DOM 元素样式透明
        canvas.style.backgroundColor = 'transparent';
        canvas.style.display = 'block'; // 防止 inline 间隙

        this.app = new PIXI.Application({
            view: canvas,
            width: container.clientWidth,
            height: container.clientHeight,

            // 2. 标准透明配置
            transparent: true,      // 开启透明
            backgroundAlpha: 0,     // 背景透明度为 0
            autoDensity: true,
            resolution: window.devicePixelRatio || 1,
            antialias: true,

            // 3. 关键：不要手动设置 premultipliedAlpha: false
            // pixi-live2d-display 和大多数 Live2D 模型贴图都依赖预乘 Alpha (premultipliedAlpha: true)
            // 让 PixiJS 使用默认值（通常为 true）是最兼容的
        });

        // 4. 【关键修复】强制设置渲染器背景清除色
        // 这能确保在每一帧渲染前，缓冲区被清空为完全透明
        if (this.app.renderer && this.app.renderer.background) {
            this.app.renderer.background.color = 0x000000;
            this.app.renderer.background.alpha = 0;
        }

        // 5. 【底层修复】直接操作 WebGL 上下文
        // 针对 Chrome/Edge 某些版本不遵守 backgroundAlpha 的情况
        const gl = this.app.renderer.gl;
        gl.clearColor(0, 0, 0, 0); // R=0, G=0, B=0, Alpha=0 (完全透明)

        // 6. 监听渲染事件，确保每次渲染前都清除为透明
        // 防止某些情况下缓冲区残留上一帧的颜色
        this.app.ticker.add(() => {
            gl.clear(gl.COLOR_BUFFER_BIT);
        });

        // 响应式调整
        window.addEventListener('resize', () => this.handleResize());

        // 鼠标跟踪
        this.setupMouseTracking();

        // 加载默认模型
        await this.loadModel('Mao');

        console.log('✅ Live2D 应用初始化完成');
    }

    handleResize() {
        const container = this.app.view.parentElement;
        this.app.renderer.resize(container.clientWidth, container.clientHeight);

        // 重新定位模型
        if (this.currentModel) {
            this.centerModel();
        }
    }

    setupMouseTracking() {
        const canvas = this.app.view;

        canvas.addEventListener('mousemove', (e) => {
            if (!this.currentModel) return;

            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width * 2 - 1;
            const y = -(e.clientY - rect.top) / rect.height * 2 + 1;

            // 更新模型参数以实现目光跟踪
            this.updateModelFocus(x, y);
        });

        // 点击触发动作
        canvas.addEventListener('click', () => {
            this.playRandomMotion();
        });
    }

    updateModelFocus(x, y) {
        if (!this.currentModel || !this.currentModel.internalModel) return;

        const coreModel = this.currentModel.internalModel.coreModel;

        // 设置眼神跟踪参数（不同模型可能有不同的参数名）
        try {
            if (coreModel.setParameterValueById) {
                // Cubism 4
                const paramAngleX = coreModel.getParameterIds().find(id =>
                    id.includes('AngleX') || id.includes('ParamAngleX')
                );
                const paramAngleY = coreModel.getParameterIds().find(id =>
                    id.includes('AngleY') || id.includes('ParamAngleY')
                );

                if (paramAngleX) {
                    coreModel.setParameterValueById(paramAngleX, x * 30);
                }
                if (paramAngleY) {
                    coreModel.setParameterValueById(paramAngleY, y * 30);
                }
            }
        } catch (error) {
            // 忽略参数设置错误
        }
    }

    async loadModel(modelName) {
        const loading = document.getElementById('loading');
        loading.style.display = 'block';

        this.showStatus(`正在加载 ${modelName}...`);

        try {
            // 检查模型是否需要更新核心库
            const config = MODEL_CONFIGS[modelName];
            if (config && config.requiresUpdate) {
                console.warn(`⚠️ 模型 ${modelName} 需要更新的 Cubism Core 版本`);
                console.warn(`当前版本: 5.1.0, 需要版本: 5.3+`);
                this.showStatus(`⚠️ ${modelName} 需要更新核心库`);

                // 显示提示信息
                const shouldContinue = confirm(
                    `警告：${modelName} 是 Cubism 5.3 模型\n` +
                    `当前核心库版本为 5.1.0，可能无法正常工作\n\n` +
                    `是否继续尝试加载？`
                );

                if (!shouldContinue) {
                    loading.style.display = 'none';
                    this.showStatus('已取消加载');
                    return;
                }
            }

            // 销毁当前模型
            if (this.currentModel) {
                this.app.stage.removeChild(this.currentModel);
                this.currentModel.destroy();
                this.currentModel = null;
            }

            // 确定模型路径
            let modelPath = this.getModelPath(modelName);

            console.log(`加载模型: ${modelPath}`);

            // 使用 pixi-live2d-display 加载模型
            this.currentModel = await PIXI.live2d.Live2DModel.from(modelPath, {
                autoInteract: true,
                autoUpdate: true
            });

            // 添加到舞台
            this.app.stage.addChild(this.currentModel);

            // 居中并缩放模型
            this.centerModel();

            // 提取动作和表情信息
            this.extractModelInfo(modelName);

            this.currentModelName = modelName;

            loading.style.display = 'none';
            this.showStatus(`✅ ${modelName} 加载成功`);

            console.log('✅ 模型加载成功');
            console.log('可用动作组:', Object.keys(this.motionGroups));
            console.log('可用表情:', this.expressionList);

            // 播放待机动作
            this.playIdleMotion();

        } catch (error) {
            console.error('❌ 加载模型失败:', error);
            loading.style.display = 'none';

            // 提供更友好的错误信息
            let errorMessage = error.message;
            this.showStatus(`❌ 加载失败: ${errorMessage}`);
            alert(`加载模型失败: ${errorMessage}\n\n请确保已启动本地服务器`);
        }
    }

    getModelPath(modelName) {
        // 返回模型配置文件的路径
        const paths = {
            'Mao': './Mao/mao_pro.model3.json',
            'asuka': './asuka/Asuka.model3.json',
            'huohuo': './huohuo/huohuo.model3.json',
            'icegirl': './icegirl/IceGirl.model3.json',
            'haihupu': './haihupu/haihupu__nchan.model3.json',
            'pachan': './pachan/pachirisu anime girl - top half.model3.json',
            'ren_pro_zh': './haru_greeter_pro_jp/runtime/haru_greeter_t05.model3.json'
        };

        return paths[modelName] || `./${modelName}/${modelName}.model3.json`;
    }

    centerModel() {
        if (!this.currentModel) return;

        const stageWidth = this.app.screen.width;
        const stageHeight = this.app.screen.height;

        // 计算合适的缩放比例
        const scale = Math.min(
            stageWidth / this.currentModel.width * 0.6,
            stageHeight / this.currentModel.height * 0.8
        );

        this.currentModel.scale.set(Math.min(scale, 0.5));

        // 居中
        this.currentModel.x = (stageWidth - this.currentModel.width) / 2;
        this.currentModel.y = (stageHeight - this.currentModel.height) / 2;
    }

    extractModelInfo(modelName) {
        // 从模型内部提取动作组和表情列表
        if (!this.currentModel || !this.currentModel.internalModel) return;

        const internalModel = this.currentModel.internalModel;

        // 检查是否有手动配置
        const config = MODEL_CONFIGS[modelName];
        const hasManualConfig = config && config.motions && Object.keys(config.motions).length > 0;

        // 提取动作组 - 使用多种方式获取
        this.motionGroups = {};

        try {
            // 如果有手动配置，优先使用手动配置
            if (hasManualConfig) {
                this.setManualMotionGroups(modelName);
                console.log('ℹ️ 检测到手动配置，使用配置文件中的动作组信息');
            } else {
                // 方法1: 从 motionManager 获取
                if (internalModel.motionManager) {
                    const motionGroups = internalModel.motionManager.groups;
                    if (motionGroups) {
                        for (let group in motionGroups) {
                            // 保留所有组，包括 idle
                            if (motionGroups[group] && motionGroups[group].length > 0) {
                                this.motionGroups[group] = motionGroups[group].length;
                            }
                        }
                    }
                }

                // 方法2: 如果上面没获取到，尝试从 modelSettings 获取
                if (Object.keys(this.motionGroups).length === 0 && internalModel.modelSettings) {
                    const motions = internalModel.modelSettings.motions;
                    if (motions) {
                        for (let group in motions) {
                            if (motions[group] && motions[group].length > 0) {
                                this.motionGroups[group] = motions[group].length;
                            }
                        }
                    }
                }

                // 方法3: 如果还是没有，手动设置已知模型的动作
                if (Object.keys(this.motionGroups).length === 0) {
                    this.setManualMotionGroups(modelName);
                }
            }
        } catch (error) {
            console.error('提取动作组失败:', error);
            this.setManualMotionGroups(modelName);
        }

        // 提取表情列表
        this.expressionList = [];
        try {
            // 如果有手动配置的表情，优先使用
            if (config && config.expressions && config.expressions.length > 0) {
                this.setManualExpressionList(modelName);
            } else if (internalModel.expressionManager) {
                const expressions = internalModel.expressionManager.definitions;
                if (expressions) {
                    this.expressionList = expressions.map(expr => expr.name);
                }
            }

            // 如果没有获取到表情，手动设置
            if (this.expressionList.length === 0) {
                this.setManualExpressionList(modelName);
            }
        } catch (error) {
            console.error('提取表情列表失败:', error);
            this.setManualExpressionList(modelName);
        }

        console.log(`✅ 模型信息 - 动作组:`, this.motionGroups);
        console.log(`✅ 模型信息 - 表情:`, this.expressionList);

        // 显示友好的提示信息
        const totalMotions = Object.values(this.motionGroups).reduce((sum, count) => sum + count, 0);
        console.log(`📊 总共有 ${totalMotions} 个动作，${Object.keys(this.motionGroups).length} 个动作组`);

        if (totalMotions === 0) {
            console.warn('⚠️ 该模型没有可用的动作文件');
        }
    }

    setManualMotionGroups(modelName) {
        // 从 MODEL_CONFIGS 中获取配置
        const config = MODEL_CONFIGS[modelName];
        if (config && config.motions) {
            // 将文件列表转换为组名:数量的格式
            this.motionGroups = {};
            for (let group in config.motions) {
                this.motionGroups[group] = config.motions[group].length;
            }
            console.log('ℹ️ 使用配置文件中的动作组信息');
        } else {
            console.warn(`⚠️ 模型 ${modelName} 没有配置动作组`);
        }
    }

    setManualExpressionList(modelName) {
        // 从 MODEL_CONFIGS 中获取配置
        const config = MODEL_CONFIGS[modelName];
        if (config && config.expressions) {
            // 从文件路径提取表情名称
            this.expressionList = config.expressions.map(filePath => {
                // 从路径中提取文件名（不含扩展名）
                const fileName = filePath.split('/').pop();
                return fileName.replace('.exp3.json', '');
            });
            console.log('ℹ️ 使用配置文件中的表情列表');
        } else {
            console.warn(`⚠️ 模型 ${modelName} 没有配置表情`);
        }
    }

    playIdleMotion() {
        if (!this.currentModel) return;

        // 尝试播放 Idle 动作组
        try {
            if (this.motionGroups['Idle'] && this.motionGroups['Idle'] > 0) {
                this.currentModel.motion('Idle', 0);
            } else if (this.motionGroups['idle'] && this.motionGroups['idle'] > 0) {
                this.currentModel.motion('idle', 0);
            }
        } catch (error) {
            console.log('没有待机动作');
        }
    }

    async playRandomMotion() {
        if (!this.currentModel) {
            this.showStatus('⚠️ 模型未加载');
            return;
        }

        if (Object.keys(this.motionGroups).length === 0) {
            this.showStatus('⚠️ 没有可用的动作');
            console.warn('当前没有可用的动作组');
            return;
        }

        // 获取所有可用的动作组
        const groups = Object.keys(this.motionGroups).filter(g => {
            const count = this.motionGroups[g];
            return count > 0;
        });

        console.log('可用动作组:', groups);
        console.log('所有动作组:', this.motionGroups);

        if (groups.length === 0) {
            this.showStatus('⚠️ 没有可播放的动作');
            console.warn('没有任何动作组');
            return;
        }

        // 优先选择非 idle 的动作组，如果只有 idle 则使用 idle
        let selectedGroups = groups.filter(g => g.toLowerCase() !== 'idle');
        if (selectedGroups.length === 0) {
            selectedGroups = groups;
            console.log('只有 idle 动作组，将从中随机选择');
        }

        // 随机选择一个动作组和一个索引
        const randomGroup = selectedGroups[Math.floor(Math.random() * selectedGroups.length)];
        const maxIndex = this.motionGroups[randomGroup];
        const randomIndex = Math.floor(Math.random() * maxIndex);

        console.log(`🎬 播放动作: 组="${randomGroup}", 索引=${randomIndex}/${maxIndex}`);
        this.showStatus(`🎬 播放: ${randomGroup}[${randomIndex}]`);

        try {
            // 播放动作
            await this.currentModel.motion(randomGroup, randomIndex);
            console.log('✅ 动作播放成功');
        } catch (error) {
            console.error('❌ 播放动作失败:', error);
            this.showStatus('❌ 播放失败: ' + error.message);

            // 尝试备用方法
            try {
                console.log('尝试使用备用方法播放动作...');
                this.currentModel.motion(randomGroup, randomIndex, 1.0);
                console.log('✅ 动作播放成功（备用方法）');
            } catch (backupError) {
                console.error('❌ 备用方法也失败:', backupError);
            }
        }
    }

    async playRandomExpression() {
        if (!this.currentModel) {
            this.showStatus('⚠️ 模型未加载');
            return;
        }

        if (this.expressionList.length === 0) {
            this.showStatus('⚠️ 没有可用的表情');
            console.warn('当前没有可用的表情列表');
            return;
        }

        // 随机选择一个表情
        const randomExpr = this.expressionList[Math.floor(Math.random() * this.expressionList.length)];

        console.log(`😊 切换表情: ${randomExpr}`);
        this.showStatus(`😊 表情: ${randomExpr}`);

        // Mao 模型使用原始的标准方法，不进行验证
        if (this.currentModelName === 'Mao') {
            try {
                await this.currentModel.expression(randomExpr);
                console.log('✅ 表情切换成功（Mao - 标准方法）');
                return;
            } catch (error) {
                console.error('❌ Mao 表情切换失败:', error.message);
                this.showStatus('❌ 表情切换失败');
                return;
            }
        }

        // 其他模型使用智能验证机制
        try {
            console.log('尝试使用标准方法...');
            await this.currentModel.expression(randomExpr);

            // 验证标准方法是否真的生效
            await new Promise(resolve => setTimeout(resolve, 100)); // 等待100ms

            // 检查是否有内部表情管理器
            if (this.currentModel.internalModel && this.currentModel.internalModel.expressionManager) {
                const currentExpression = this.currentModel.internalModel.expressionManager.currentExpression;
                console.log('当前表情:', currentExpression?.name || '无');

                if (currentExpression && currentExpression.name === randomExpr) {
                    console.log('✅ 表情切换成功（标准方法 - 已验证）');
                    return;
                }
            }

            // 如果验证失败，降级使用手动方法
            console.log('⚠️ 标准方法可能未生效，尝试手动应用...');
            throw new Error('标准方法验证失败');

        } catch (error) {
            console.warn('标准方法失败或无效，使用手动应用:', error.message);

            try {
                await this.applyExpressionManually(randomExpr);
                console.log('✅ 表情切换成功（手动应用）');
            } catch (manualError) {
                console.error('❌ 手动应用表情也失败:', manualError);
                this.showStatus('❌ 表情切换失败');
            }
        }
    }

    async applyExpressionManually(expressionName) {
        // 从 MODEL_CONFIGS 中获取表情文件路径
        const config = MODEL_CONFIGS[this.currentModelName];
        if (!config || !config.expressions) {
            throw new Error('没有表情配置');
        }

        // 找到对应的表情文件路径
        const exprFile = config.expressions.find(path => {
            const fileName = path.split('/').pop();
            const name = fileName.replace('.exp3.json', '');
            return name === expressionName;
        });

        if (!exprFile) {
            throw new Error(`找不到表情文件: ${expressionName}`);
        }

        // 构建完整路径 - 使用模型配置中的路径作为基础
        const modelPath = this.getModelPath(this.currentModelName);
        const modelDir = modelPath.substring(0, modelPath.lastIndexOf('/') + 1);
        const fullPath = modelDir + exprFile;

        console.log('手动加载表情文件:', fullPath);

        // 加载表情文件
        const response = await fetch(fullPath);
        if (!response.ok) {
            throw new Error(`无法加载表情文件: ${fullPath} (HTTP ${response.status})`);
        }
        const exprData = await response.json();

        // 应用表情参数到模型
        if (!this.currentModel.internalModel || !this.currentModel.internalModel.coreModel) {
            throw new Error('无法访问模型核心');
        }

        const coreModel = this.currentModel.internalModel.coreModel;
        const internalModel = this.currentModel.internalModel;

        console.log('开始应用表情参数...');
        console.log('表情数据:', exprData);

        let appliedCount = 0;
        let failedCount = 0;

        // 遍历表情参数并应用
        if (exprData.Parameters) {
            for (const param of exprData.Parameters) {
                try {
                    // 检查参数是否存在
                    const paramIndex = coreModel.getParameterIndex(param.Id);
                    if (paramIndex !== -1) {
                        // 获取参数的当前值范围
                        const minValue = coreModel.getParameterMinimumValue(paramIndex);
                        const maxValue = coreModel.getParameterMaximumValue(paramIndex);
                        const defaultValue = coreModel.getParameterDefaultValue(paramIndex);

                        // 计算要设置的值（考虑混合模式）
                        let targetValue = param.Value;
                        if (param.Blend === 'Add') {
                            // Add 模式：在默认值基础上增加
                            targetValue = defaultValue + param.Value;
                        } else if (param.Blend === 'Multiply') {
                            // Multiply 模式：与默认值相乘
                            targetValue = defaultValue * param.Value;
                        }

                        // 确保值在有效范围内
                        targetValue = Math.max(minValue, Math.min(maxValue, targetValue));

                        // 设置参数值
                        coreModel.setParameterValueById(param.Id, targetValue);

                        // 验证是否设置成功
                        const actualValue = coreModel.getParameterValueById(param.Id);
                        console.log(`  📊 ${param.Id}: 目标=${targetValue.toFixed(2)}, 实际=${actualValue.toFixed(2)} (${param.Blend})`);

                        appliedCount++;
                    } else {
                        console.warn(`⚠️ 参数不存在: ${param.Id}`);
                        failedCount++;
                    }
                } catch (e) {
                    console.warn(`⚠️ 应用参数失败: ${param.Id}`, e.message);
                    failedCount++;
                }
            }
        }

        console.log(`✅ 成功应用 ${appliedCount} 个参数，${failedCount} 个失败`);

        // 强制刷新模型渲染
        if (internalModel.motionManager) {
            // 触发一次更新以确保参数生效
            internalModel.update(0.016); // 模拟一帧的更新
        }
    }

    resetModel() {
        if (!this.currentModel) return;

        console.log('重置模型');
        this.showStatus('🔄 重置中...');

        try {
            // 重置位置和缩放
            this.centerModel();

            // 重置表情
            if (this.expressionList.length > 0) {
                this.currentModel.expression(this.expressionList[0]);
            }

            // 播放待机动作
            this.playIdleMotion();

            this.showStatus('✅ 已重置');
        } catch (error) {
            console.error('重置失败:', error);
            this.showStatus('❌ 重置失败');
        }
    }

    toggleAutoBreath() {
        this.autoBreath = !this.autoBreath;

        if (this.currentModel && this.currentModel.internalModel) {
            try {
                // 这里可以控制自动呼吸相关的参数
                this.showStatus(this.autoBreath ? '💨 自动呼吸: 开' : '💨 自动呼吸: 关');
            } catch (error) {
                console.error('切换呼吸失败:', error);
            }
        }
    }

    showStatus(message) {
        const statusBar = document.getElementById('statusBar');
        statusBar.textContent = message;
        statusBar.style.display = 'block';

        // 3秒后隐藏
        setTimeout(() => {
            statusBar.style.display = 'none';
        }, 3000);
    }
}

// 全局实例
let app;

// 初始化应用
window.addEventListener('load', async () => {
    console.log('🚀 启动 Live2D 应用...');
    app = new Live2DApp();
});

// 全局控制函数
function playRandomMotion() {
    if (app) app.playRandomMotion();
}

function playRandomExpression() {
    if (app) app.playRandomExpression();
}

function resetModel() {
    if (app) app.resetModel();
}

function toggleAutoBreath() {
    if (app) app.toggleAutoBreath();
}

// 模型切换
document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('modelSelect');
    if (select) {
        select.addEventListener('change', async (e) => {
            if (app) {
                await app.loadModel(e.target.value);
            }
        });
    }
});

