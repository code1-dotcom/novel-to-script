"""bailian_client.py — 百炼 API 客户端封装
封装百炼平台 OpenAI 兼容 API 的调用逻辑，提供统一调用接口。
支持指数退避重试、超时异常处理和结构化 JSON 输出。
支持流式输出（stream=True）。

重试策略：使用有界 for 循环（最多 config.MAX_RETRIES=3 次），
采用指数退避（1s, 2s, 4s），无 while True 或递归重试逻辑。
"""

import time
import json
import logging
from typing import Generator
from openai import OpenAI

import config

logger = logging.getLogger(__name__)


class BailianAPIError(Exception):
    """百炼 API 调用异常基类"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class BailianTimeoutError(BailianAPIError):
    """API 调用超时异常"""


class BailianRateLimitError(BailianAPIError):
    """API 限流异常"""


class BailianFormatError(BailianAPIError):
    """API 返回格式异常"""


class BailianClient:
    """百炼平台 API 客户端，封装 OpenAI 兼容接口"""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        max_retries: int = None,
        timeout: int = None,
    ):
        self.api_key = api_key or config.BAILIAN_API_KEY
        self.base_url = base_url or config.BAILIAN_BASE_URL
        self.max_retries = max_retries if max_retries is not None else config.MAX_RETRIES
        self.timeout = timeout if timeout is not None else config.TIMEOUT_SECONDS

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        统一调用接口，发送消息到百炼模型并返回生成文本。

        参数:
            model: 模型名称，如 "qwen-max" 或 "qwen-plus"
            messages: OpenAI 格式的消息列表
            temperature: 生成温度 (0.0 ~ 2.0)
            max_tokens: 最大生成 token 数

        返回:
            模型生成的文本字符串

        异常:
            BailianTimeoutError: 调用超时
            BailianRateLimitError: API 限流
            BailianAPIError: 其他 API 错误
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "API 调用 [%s] 第 %d/%d 次尝试, model=%s",
                    model, attempt + 1, self.max_retries, model,
                )
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                logger.info("API 调用 [%s] 成功, 返回 %d 字符", model, len(content) if content else 0)
                return content or ""

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "timeout" in error_str or "timed out" in error_str:
                    logger.warning("API 超时 [%s] 第 %d 次尝试: %s", model, attempt + 1, e)
                elif "rate" in error_str or "429" in error_str or "limit" in error_str:
                    logger.warning("API 限流 [%s] 第 %d 次尝试: %s", model, attempt + 1, e)
                else:
                    logger.warning("API 错误 [%s] 第 %d 次尝试: %s", model, attempt + 1, e)

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info("等待 %.1f 秒后重试...", wait_time)
                    time.sleep(wait_time)

        error_str = str(last_error).lower()
        if "timeout" in error_str or "timed out" in error_str:
            raise BailianTimeoutError(
                f"API 调用超时，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )
        elif "rate" in error_str or "429" in error_str or "limit" in error_str:
            raise BailianRateLimitError(
                f"API 限流，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )
        else:
            raise BailianAPIError(
                f"API 调用失败，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )

    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """
        流式调用接口，逐块返回生成文本。

        参数:
            model: 模型名称
            messages: OpenAI 格式的消息列表
            temperature: 生成温度 (0.0 ~ 2.0)
            max_tokens: 最大生成 token 数

        Yields:
            每次 yield 一段文本增量

        异常:
            BailianTimeoutError: 调用超时
            BailianRateLimitError: API 限流
            BailianAPIError: 其他 API 错误
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "Stream API 调用 [%s] 第 %d/%d 次尝试",
                    model, attempt + 1, self.max_retries,
                )
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                logger.info("Stream API 调用 [%s] 完成", model)
                return

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                logger.warning("Stream API 错误 [%s] 第 %d 次尝试: %s", model, attempt + 1, e)

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info("等待 %.1f 秒后重试...", wait_time)
                    time.sleep(wait_time)

        error_str = str(last_error).lower()
        if "timeout" in error_str or "timed out" in error_str:
            raise BailianTimeoutError(
                f"流式 API 调用超时，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )
        elif "rate" in error_str or "429" in error_str or "limit" in error_str:
            raise BailianRateLimitError(
                f"流式 API 限流，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )
        else:
            raise BailianAPIError(
                f"流式 API 调用失败，已重试 {self.max_retries} 次: {last_error}",
                original_error=last_error,
            )

    def chat_json(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """
        调用 API 并尝试解析 JSON 输出，适用于需要结构化输出的场景。

        参数:
            model: 模型名称
            messages: OpenAI 格式的消息列表
            temperature: 生成温度（默认较低以保证 JSON 格式规范）
            max_tokens: 最大生成 token 数

        返回:
            解析后的 dict 对象

        异常:
            BailianFormatError: 返回内容无法解析为 JSON
        """
        raw_text = self.chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        json_text = raw_text.strip()

        if "```json" in json_text:
            start = json_text.find("```json") + len("```json")
            end = json_text.find("```", start)
            if end != -1:
                json_text = json_text[start:end].strip()
        elif "```" in json_text:
            start = json_text.find("```") + len("```")
            end = json_text.find("```", start)
            if end != -1:
                json_text = json_text[start:end].strip()

        try:
            result = json.loads(json_text)
            logger.info("chat_json 解析成功")
            return result
        except json.JSONDecodeError as e:
            logger.error("chat_json JSON 解析失败: %s", e)
            raise BailianFormatError(
                f"API 返回内容无法解析为 JSON: {e}\n原始返回前200字符: {raw_text[:200]}",
                original_error=e,
            ) from e