import path from 'path';
import { Release, Tracer } from 'tracers/Tracer';
import express from 'express';
import fs from 'fs';

export class JsTracer extends Tracer {
  readonly workerPath: string;
  tagName?: string;

  constructor() {
    super('js');
    this.workerPath = path.resolve(__dirname, 'worker.js');
  }

  async build(release: Release) {
    const {tag_name} = release;
    this.tagName = tag_name;
  }

  route(router: express.Router) {
    router.get(`/${this.lang}`, (req, res) => {
      // 从 node_modules 直接读取文件
      const libPath = path.resolve(__dirname, '../../../node_modules/algorithm-visualizer/dist/algorithm-visualizer.umd.js');
      res.sendFile(libPath);
    });
    router.get(`/${this.lang}/worker`, (req, res) => {
      // 设置正确的 Content-Type，避免重定向
      res.setHeader('Content-Type', 'application/javascript');
      res.sendFile(this.workerPath);
    });
  }
}
