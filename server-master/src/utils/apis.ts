import axios, { AxiosResponse } from 'axios';

const instance = axios.create();

const request = (url: string, process: (mappedUrl: string, args: any[]) => Promise<AxiosResponse<any>>) => {
  const tokens = url.split('/');
  const baseURL = /^https?:\/\//i.test(url) ? '' : 'https://api.github.com';
  return (...args: any[]) => {
    const mappedUrl = baseURL + tokens.map(token => token.startsWith(':') ? args.shift() : token).join('/');
    return process(mappedUrl, args);
  };
};

export const GitHubApi = {
  listCommits: (owner: string, repo: string, params?: any) =>
    instance.get(`https://api.github.com/repos/${owner}/${repo}/commits`, { params }),

  getLatestRelease: (owner: string, repo: string) =>
    instance.get(`https://api.github.com/repos/${owner}/${repo}/releases/latest`),
};
