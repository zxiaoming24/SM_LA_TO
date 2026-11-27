import express from 'express';
import { GitHubApi } from 'utils/apis';
import { __DEV__ } from 'config/environments';

export type Release = {
  tag_name: string;
}

export abstract class Tracer {
  protected constructor(public lang: string) {
    // 开发环境下跳过 GitHub API 调用
    if (!__DEV__) {
      this.update().catch(error => {
        console.error(`Failed to update ${lang} tracer:`, error.message);
        console.warn(`Using local ${lang} tracer. Some features may be limited.`);
      });
    }
  }

  abstract build(release: Release): Promise<any>;

  abstract route(router: express.Router): void;

  async update(release?: Release) {
    if (release) {
      return this.build(release);
    }
    const {data} = await GitHubApi.getLatestRelease('algorithm-visualizer', `tracers.${this.lang}`);
    return this.build(data);
  }
}
