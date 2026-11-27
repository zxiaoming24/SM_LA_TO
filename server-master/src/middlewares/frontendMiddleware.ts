import express, { NextFunction, Request, Response } from 'express';
import path from 'path';
import fs from 'fs-extra';
import url from 'url';
import Server from 'Server';
import { frontendBuiltDir } from 'config/paths';

const packageJson = require('../../package.json');

export function frontendMiddleware(server: Server) {
  const staticMiddleware = express.static(frontendBuiltDir, {index: false});

  if (!fs.pathExistsSync(frontendBuiltDir)) {
    console.warn('Frontend build not found. Will attempt to build on first request.');
    // 不在启动时构建，而是在第一次请求时尝试
  }

  return (req: Request, res: Response, next: NextFunction) => {
    staticMiddleware(req, res, (err: any) => {
      if (err) return next(err);
      if (req.method !== 'GET') return next();

      const filePath = path.resolve(frontendBuiltDir, 'index.html');
      
      // 如果文件不存在，返回友好的错误信息
      if (!fs.pathExistsSync(filePath)) {
        return res.status(404).send(`
          <h1>Frontend Not Available</h1>
          <p>The frontend has not been built yet.</p>
          <p>Please run the frontend build process or wait for initialization.</p>
        `);
      }
      
      fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) return next(err);

        const {pathname} = url.parse(req.originalUrl);
        if (!pathname) return next(new Error('Failed to get `pathname`.'));
        const [, categoryKey, algorithmKey] = pathname.split('/');
        let {title, description} = packageJson;
        let algorithm = undefined;
        if (categoryKey && categoryKey !== 'scratch-paper') {
          algorithm = server.hierarchy.find(categoryKey, algorithmKey) || null;
          if (algorithm) {
            title = [algorithm.categoryName, algorithm.algorithmName].join(' - ');
            description = algorithm.description;
          } else {
            res.status(404);
            return;
          }
        }

        const indexFile = data
          .replace(/\$TITLE/g, title)
          .replace(/\$DESCRIPTION/g, description)
          .replace(/\$ALGORITHM/g, algorithm === undefined ? 'undefined' :
            JSON.stringify(algorithm).replace(/</g, '\\u003c'));
        res.send(indexFile);
      });
    });
  };
}
