# /app/providers/goblin_provider.py
import time
import json
import uuid
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator

import cloudscraper
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.config import settings
from app.providers.base_provider import BaseProvider
from app.utils.sse_utils import create_sse_data, create_chat_completion_chunk, DONE_CHUNK

logger = logging.getLogger(__name__)

class GoblinProvider(BaseProvider):
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()

    def _prepare_headers(self) -> Dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://goblin.tools",
            "Referer": "https://goblin.tools/Judge",
            "Cookie": "gt_lang=zh-CN",
        }

    def _prepare_payload(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        messages = request_data.get("messages", [])
        last_user_message = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), None)
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="请求中未找到用户消息。")
            
        return {"Texts": [last_user_message]}

    async def chat_completion(self, request_data: Dict[str, Any]) -> StreamingResponse:
        model = request_data.get("model", settings.DEFAULT_MODEL)
        upstream_url = settings.MODEL_MAPPING.get(model)

        if not upstream_url:
            raise HTTPException(status_code=400, detail=f"不支持的模型: {model}")

        payload = self._prepare_payload(request_data)
        headers = self._prepare_headers()
        
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            request_id = f"chatcmpl-{uuid.uuid4()}"
            loop = asyncio.get_running_loop()
            
            try:
                logger.info(f"向 {upstream_url} 发送请求...")
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.scraper.post(
                        upstream_url,
                        headers=headers,
                        json=payload,
                        timeout=settings.API_REQUEST_TIMEOUT
                    )
                )
                
                logger.info(f"上游服务返回状态码: {response.status_code}")
                response.raise_for_status()
                
                full_text = response.text
                logger.info(f"收到完整响应: {full_text[:100]}...")

                # 模式：伪流式生成 (Pseudo-Stream-Generation)
                for char in full_text:
                    chunk = create_chat_completion_chunk(request_id, model, char)
                    yield create_sse_data(chunk)
                    await asyncio.sleep(0.01) # 控制打字机速度

                final_chunk = create_chat_completion_chunk(request_id, model, "", "stop")
                yield create_sse_data(final_chunk)
                yield DONE_CHUNK
                logger.info("伪流式传输完成。")

            except Exception as e:
                logger.error(f"处理流时发生错误: {e}", exc_info=True)
                error_message = f"内部服务器错误: {str(e)}"
                error_chunk = create_chat_completion_chunk(request_id, model, error_message, "stop")
                yield create_sse_data(error_chunk)
                yield DONE_CHUNK

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    async def get_models(self) -> JSONResponse:
        model_data = {
            "object": "list",
            "data": [
                {"id": name, "object": "model", "created": int(time.time()), "owned_by": "lzA6"}
                for name in settings.KNOWN_MODELS
            ]
        }
        return JSONResponse(content=model_data)
