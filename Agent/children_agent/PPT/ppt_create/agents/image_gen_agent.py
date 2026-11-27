import os
import asyncio
from pathlib import Path
import requests
from dashscope import ImageSynthesis
from http import HTTPStatus

class ImageGenAgent:
    def __init__(self, api_key="sk-b524efccda47492d92168ed3470593a8"):
        self.api_key = api_key
        os.environ['DASHSCOPE_BASE_HTTP_API_URL'] = 'https://dashscope.aliyuncs.com/api/v1'
        self.save_dir = "ppt_images"
        Path(self.save_dir).mkdir(exist_ok=True)

    async def _download_img(self, url, save_name):
        data = await asyncio.to_thread(lambda: requests.get(url).content)
        full_path = os.path.join(self.save_dir, save_name)
        with open(full_path, "wb") as f:
            f.write(data)
        return full_path

    async def _call_image_synthesis(self, prompt, max_retries=3):
        import time
        for attempt in range(max_retries):
            try:
                rsp = await asyncio.to_thread(
                    ImageSynthesis.call,
                    api_key=self.api_key, model="wanx2.1-t2i-plus",
                    prompt=prompt, n=1, size="1280*720"
                )
                return rsp
            except Exception as e:
                err_msg = str(e)
                # 429 限流：指数退避重试
                if "429" in err_msg or "Throttling" in err_msg:
                    wait = 2 ** (attempt + 1)
                    print(f"  ⚠️ [图片生成] 限流，{wait}s后重试 ({attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                # 其他错误直接抛出
                raise
        return None

    async def gen_cover_and_last(self, prompt_data: dict):
        """只生成封面和尾页背景图（async 版本）"""
        cover_prompt = prompt_data.get("cover_bg_prompt", "")
        last_prompt = prompt_data.get("last_bg_prompt", "")

        cover_path = ""
        last_path = ""

        if cover_prompt:
            print("🎨 生成封面背景图")
            rsp = await self._call_image_synthesis(cover_prompt)
            if rsp and rsp.status_code == HTTPStatus.OK:
                cover_path = await self._download_img(rsp.output.results[0].url, "cover_bg.png")
            await asyncio.sleep(1)

        if last_prompt:
            print("🎨 生成尾页背景图")
            rsp = await self._call_image_synthesis(last_prompt)
            if rsp and rsp.status_code == HTTPStatus.OK:
                last_path = await self._download_img(rsp.output.results[0].url, "last_bg.png")
            await asyncio.sleep(1)

        print(f"📷 封面背景: {cover_path}, 尾页背景: {last_path}")
        return cover_path, last_path

    async def generate_images_async(self, prompts: list, image_dir: str) -> list:
        """为每页生成背景图（兼容 ppt_agent.py 调用方式），返回路径列表"""
        self.save_dir = image_dir
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)

        async def _gen_one(idx, prompt):
            rsp = await self._call_image_synthesis(prompt)
            if rsp is None:
                return None
            if rsp.status_code == HTTPStatus.OK:
                fname = f"page_{idx:03d}.png"
                return await self._download_img(rsp.output.results[0].url, fname)
            return None

        results = []
        for i, p in enumerate(prompts):
            path = await _gen_one(i, p)
            results.append(path)
            await asyncio.sleep(0.5)  # 每张间隔0.5s，避免触发限流
        return results

# 测试
if __name__ == "__main__":
    async def main():
        agent = ImageGenAgent()
        test_data = {
            "cover_bg_prompt": "Abstract blue gradient background, geometric shapes, professional corporate style, no text",
            "last_bg_prompt": "Simple light blue abstract background, minimalist, no text"
        }
        cover, last = await agent.gen_cover_and_last(test_data)
        print("封面:", cover)
        print("尾页:", last)
    asyncio.run(main())
