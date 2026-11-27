import express from 'express';
import { Controller } from 'controllers/Controller';
import Server from 'Server';
import { LLMSerializer } from 'utils/LLMSerializer';

export class VisualizeController extends Controller {
  private llmSerializer: LLMSerializer;

  constructor(server: Server) {
    super(server);
    this.llmSerializer = new LLMSerializer();
    this.router.post('/transform', this.transformCode);
  }

  route = (router: express.Router): void => {
    router.use('/visualize', this.router);
  };

  transformCode = async (req: express.Request, res: express.Response, next: express.NextFunction) => {
    const { code, algorithmType } = req.body;
    
    if (!code) {
      return res.status(400).json({ 
        success: false, 
        error: '代码不能为空' 
      });
    }

    try {
      // 自动检测算法类型（如果未提供）
      const detectedType = algorithmType || this.llmSerializer.detectAlgorithmType(code);
      
      console.log(`🤖 开始 LLM 代码转换 (类型: ${detectedType})`);
      
      // 调用 LLM 进行代码转换
      const transformedCode = await this.llmSerializer.transformCode(code, detectedType);
      
      console.log('✅ 代码转换成功');
      
      res.json({ 
        success: true, 
        code: transformedCode,
        detectedType: detectedType
      });
    } catch (error) {
      console.error('❌ 代码转换失败:', error);
      next(error);
    }
  };
}
