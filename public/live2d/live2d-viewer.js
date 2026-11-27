/**
 * Live2D 模型加载器
 * 简化版本的 Live2D 模型展示实现
 */

class SimpleLive2DViewer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.currentModel = null;
        this.modelData = null;
        this.animations = [];
        this.expressions = [];
        this.currentAnimationIndex = 0;
        this.currentExpressionIndex = 0;
        this.isAnimating = false;

        this.init();
    }

    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());

        // 鼠标交互
        let isMouseDown = false;
        this.canvas.addEventListener('mousedown', () => isMouseDown = true);
        this.canvas.addEventListener('mouseup', () => isMouseDown = false);
        this.canvas.addEventListener('mousemove', (e) => {
            if (isMouseDown) {
                this.handleDrag(e);
            }
        });

        // 点击触发动作
        this.canvas.addEventListener('click', () => {
            this.playRandomAnimation();
        });
    }

    resizeCanvas() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
    }

    async loadModel(modelName) {
        console.log(`加载模型: ${modelName}`);

        try {
            // 确定模型路径
            let modelPath = '';
            switch (modelName) {
                case 'Mao':
                    modelPath = './Mao/mao_pro';
                    break;
                case 'haihupu':
                    modelPath = './haihupu/haihupu__nchan';
                    break;
                case 'pachan':
                    modelPath = './pachan/pachirisu anime girl - top half';
                    break;
                default:
                    modelPath = `./${modelName}/${modelName}`;
            }

            // 加载模型配置文件
            const response = await fetch(`${modelPath}.model3.json`);
            const modelJson = await response.json();

            this.modelData = modelJson;
            this.currentModel = modelName;

            // 提取动作和表情列表
            this.extractAssets(modelJson, modelName);

            console.log('模型加载成功:', modelJson);
            console.log('可用动作:', this.animations);
            console.log('可用表情:', this.expressions);

            // 显示模型信息
            this.displayModelInfo();

            return true;
        } catch (error) {
            console.error('加载模型失败:', error);
            alert(`加载模型失败: ${error.message}`);
            return false;
        }
    }

    extractAssets(modelJson, modelName) {
        this.animations = [];
        this.expressions = [];

        // 从模型配置中提取动作文件
        if (modelJson.FileReferences && modelJson.FileReferences.Motions) {
            const motions = modelJson.FileReferences.Motions;
            for (let group in motions) {
                motions[group].forEach(motion => {
                    this.animations.push({
                        group: group,
                        file: motion.File,
                        name: motion.File.replace('.motion3.json', '')
                    });
                });
            }
        }

        // 从模型配置中提取表情文件
        if (modelJson.FileReferences && modelJson.FileReferences.Expressions) {
            modelJson.FileReferences.Expressions.forEach(expr => {
                this.expressions.push({
                    name: expr.Name,
                    file: expr.File
                });
            });
        }

        // 如果没有从配置中找到，尝试从目录中扫描
        if (this.animations.length === 0 || this.expressions.length === 0) {
            this.scanDirectory(modelName);
        }
    }

    scanDirectory(modelName) {
        // 这里提供一个手动配置的映射，因为浏览器无法直接扫描文件系统
        const modelAssets = {
            'Mao': {
                animations: ['mtn_01', 'mtn_02', 'mtn_03', 'mtn_04', 'special_01', 'special_02', 'special_03'],
                expressions: ['exp_01', 'exp_02', 'exp_03', 'exp_04', 'exp_05', 'exp_06', 'exp_07', 'exp_08']
            },
            'asuka': {
                animations: ['Hand wave', 'cry', 'MODEL PREVIEW'],
                expressions: ['Gloom', 'Happy Sparkle', 'Star Eyes Toggle', 'coat toggle']
            },
            'huohuo': {
                animations: ['Scene1', 'haoqi', 'keshui', 'linghun', 'qizi', 'yaotou', 'zhentou'],
                expressions: ['angry', 'baozhen', 'cry', 'qizi1', 'qizi2', 'white eyes']
            },
            'icegirl': {
                animations: ['DaiJi', 'HuiShou', 'MeiYan'],
                expressions: ['←歪嘴', '惊讶', '手柄', '披发', '星星眼', '歪嘴→', '流泪', '爱心眼', '猫耳', '王冠', '生气', '疑惑', '白眼', '直播套装', '翅膀', '脸红', '脸黑', '舌头', '金钱眼', '马尾']
            },
            'haihupu': {
                animations: [],
                expressions: []
            },
            'pachan': {
                animations: [],
                expressions: []
            }
        };

        if (modelAssets[modelName]) {
            this.animations = modelAssets[modelName].animations.map(name => ({
                name: name,
                file: `${name}.motion3.json`
            }));

            this.expressions = modelAssets[modelName].expressions.map(name => ({
                name: name,
                file: `${name}.exp3.json`
            }));
        }
    }

    displayModelInfo() {
        const info = `
当前模型: ${this.currentModel}
可用动作: ${this.animations.length} 个
可用表情: ${this.expressions.length} 个
        `.trim();

        console.log(info);
    }

    playRandomAnimation() {
        if (this.animations.length === 0) {
            alert('该模型没有可用的动作');
            return;
        }

        const randomIndex = Math.floor(Math.random() * this.animations.length);
        const animation = this.animations[randomIndex];

        console.log(`播放动作: ${animation.name}`);
        this.playAnimation(animation);
    }

    playAnimation(animation) {
        // 在实际实现中，这里需要加载并播放 motion3.json 文件
        console.log('播放动画:', animation);

        // 模拟动画播放效果
        this.animateCanvas();
    }

    playRandomExpression() {
        if (this.expressions.length === 0) {
            alert('该模型没有可用的表情');
            return;
        }

        const randomIndex = Math.floor(Math.random() * this.expressions.length);
        const expression = this.expressions[randomIndex];

        console.log(`切换表情: ${expression.name}`);
        this.applyExpression(expression);
    }

    applyExpression(expression) {
        // 在实际实现中，这里需要加载并应用 exp3.json 文件
        console.log('应用表情:', expression);

        // 模拟表情变化效果
        this.flashCanvas();
    }

    animateCanvas() {
        // 简单的动画效果演示
        let frame = 0;
        const maxFrames = 60;

        const animate = () => {
            frame++;
            this.render(frame / maxFrames);

            if (frame < maxFrames) {
                requestAnimationFrame(animate);
            }
        };

        animate();
    }

    flashCanvas() {
        // 简单的闪光效果
        this.canvas.style.filter = 'brightness(1.5)';
        setTimeout(() => {
            this.canvas.style.filter = 'brightness(1)';
        }, 200);
    }

    handleDrag(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // 在这里可以添加拖拽交互逻辑
        console.log(`鼠标位置: (${x}, ${y})`);
    }

    render(progress = 0) {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        // 清除画布
        ctx.clearRect(0, 0, width, height);

        // 绘制背景渐变
        const gradient = ctx.createRadialGradient(
            width / 2, height / 2, 0,
            width / 2, height / 2, width / 2
        );
        gradient.addColorStop(0, 'rgba(255, 255, 255, 0.1)');
        gradient.addColorStop(1, 'rgba(255, 255, 255, 0.05)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        // 绘制模型占位符
        ctx.save();
        ctx.translate(width / 2, height / 2);

        // 根据进度添加轻微的摆动效果
        const sway = Math.sin(progress * Math.PI * 2) * 5;
        ctx.rotate(sway * Math.PI / 180);

        // 绘制圆形占位符
        ctx.beginPath();
        ctx.arc(0, 0, 100, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 绘制文本
        ctx.fillStyle = 'white';
        ctx.font = '16px Microsoft YaHei';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(this.currentModel || '未加载模型', 0, -10);
        ctx.font = '12px Microsoft YaHei';
        ctx.fillText('点击播放随机动作', 0, 20);

        ctx.restore();
    }

    reset() {
        this.currentAnimationIndex = 0;
        this.currentExpressionIndex = 0;
        this.render();
    }
}

// 全局实例
let viewer;

// 初始化
window.addEventListener('load', () => {
    viewer = new SimpleLive2DViewer('canvas');

    // 加载默认模型
    viewer.loadModel('Mao');
});

// 控制函数
function playRandomMotion() {
    if (viewer) {
        viewer.playRandomAnimation();
    }
}

function playRandomExpression() {
    if (viewer) {
        viewer.playRandomExpression();
    }
}

function resetModel() {
    if (viewer) {
        viewer.reset();
    }
}

// 模型切换
document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('modelSelect');
    if (select) {
        select.addEventListener('change', (e) => {
            if (viewer) {
                viewer.loadModel(e.target.value);
            }
        });
    }
});
