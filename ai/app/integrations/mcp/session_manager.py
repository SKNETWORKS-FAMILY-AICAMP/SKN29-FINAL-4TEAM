"""Process-lifetime MCP stdio session manager.

One dedicated worker task owns the full MCP stdio lifecycle:
connect -> tool calls -> close.

This is important because the MCP SDK / AnyIO stdio context contains task-bound
cancel scopes. Opening the context in one asyncio Task and closing it from
another Task is invalid even if both Tasks run on the same event loop.
"""

from __future__ import annotations

import atexit
import asyncio
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Any, Callable

from .client import WaterBridgeMCPClient


@dataclass(slots=True)
class _ToolRequest:
    tool_name: str
    arguments: dict[str, Any]
    future: Future[Any]


@dataclass(slots=True)
class _ConnectRequest:
    future: Future[None]


@dataclass(slots=True)
class _StopRequest:
    future: Future[None]


class McpStdioSessionManager:
    """Keep one MCP stdio subprocess and ClientSession alive per process."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], WaterBridgeMCPClient] = WaterBridgeMCPClient,
        startup_timeout_seconds: float = 10.0,
    ) -> None:
        self._client_factory = client_factory
        self._startup_timeout_seconds = startup_timeout_seconds
        self._start_lock = Lock()
        self._ready = Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[
            _ConnectRequest | _ToolRequest | _StopRequest
        ] | None = None
        self._thread: Thread | None = None
        self._worker_error: BaseException | None = None

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue()
        self._worker_error = None
        self._ready.set()

        try:
            loop.run_until_complete(self._worker())
        except BaseException as exc:
            self._worker_error = exc
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()

    async def _safe_close_client(
        self,
        client: WaterBridgeMCPClient | None,
    ) -> None:
        if client is None:
            return
        try:
            await client.close()
        except BaseException:
            pass

    @staticmethod
    def _complete_result(future: Future[Any], result: Any) -> None:
        if not future.cancelled() and not future.done():
            future.set_result(result)

    @staticmethod
    def _complete_exception(
        future: Future[Any],
        exc: BaseException,
    ) -> None:
        if not future.cancelled() and not future.done():
            future.set_exception(exc)

    async def _worker(self) -> None:
        queue = self._queue
        if queue is None:
            raise RuntimeError("MCP request queue is unavailable")

        client: WaterBridgeMCPClient | None = None

        try:
            while True:
                request = await queue.get()

                if isinstance(request, _StopRequest):
                    await self._safe_close_client(client)
                    client = None
                    self._complete_result(request.future, None)
                    return

                try:
                    if client is None:
                        client = self._client_factory()
                        await client.connect()

                    if isinstance(request, _ConnectRequest):
                        self._complete_result(request.future, None)
                        continue

                    result = await client.call_tool(
                        request.tool_name,
                        request.arguments,
                    )
                except BaseException as exc:
                    await self._safe_close_client(client)
                    client = None
                    self._complete_exception(request.future, exc)
                else:
                    self._complete_result(request.future, result)
        finally:
            await self._safe_close_client(client)

    def _ensure_worker(self):
        thread = self._thread
        loop = self._loop
        queue = self._queue

        if (
            thread is not None
            and thread.is_alive()
            and loop is not None
            and queue is not None
        ):
            return loop, queue

        with self._start_lock:
            thread = self._thread
            loop = self._loop
            queue = self._queue
            if (
                thread is None
                or not thread.is_alive()
                or loop is None
                or queue is None
            ):
                self._ready.clear()
                self._loop = None
                self._queue = None
                self._worker_error = None
                thread = Thread(
                    target=self._thread_main,
                    name="waterbridge-mcp-stdio",
                    daemon=True,
                )
                self._thread = thread
                thread.start()

        if not self._ready.wait(self._startup_timeout_seconds):
            raise TimeoutError("MCP stdio worker startup timed out")

        loop = self._loop
        queue = self._queue
        thread = self._thread

        if (
            loop is None
            or queue is None
            or thread is None
            or not thread.is_alive()
        ):
            error = self._worker_error
            if error is not None:
                raise RuntimeError("MCP stdio worker failed to start") from error
            raise RuntimeError("MCP stdio worker failed to start")

        return loop, queue

    @staticmethod
    def _enqueue(loop, queue, request) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, request)

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        loop, queue = self._ensure_worker()
        future: Future[Any] = Future()
        self._enqueue(
            loop,
            queue,
            _ToolRequest(
                tool_name=tool_name,
                arguments=arguments or {},
                future=future,
            ),
        )
        return future.result(timeout=timeout_seconds)

    def ensure_connected(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        """Start the stdio subprocess independently of any Tool deadline."""

        loop, queue = self._ensure_worker()
        future: Future[None] = Future()
        self._enqueue(loop, queue, _ConnectRequest(future=future))
        future.result(timeout=timeout_seconds)

    def warmup_search_runtime(
        self,
        *,
        timeout_seconds: float = 120.0,
    ) -> bool:
        result = self.call_tool(
            "warmup_search_runtime",
            {},
            timeout_seconds=timeout_seconds,
        )

        if bool(
            getattr(result, "isError", False)
            or getattr(result, "is_error", False)
        ):
            raise RuntimeError("MCP search runtime warmup failed")

        payload = getattr(result, "structuredContent", None)
        if payload is None:
            payload = getattr(result, "structured_content", None)

        if not isinstance(payload, dict) or payload.get("ready") is not True:
            raise RuntimeError("MCP search runtime did not become ready")

        return True

    def close(self, *, timeout_seconds: float = 10.0) -> None:
        thread = self._thread
        loop = self._loop
        queue = self._queue

        if (
            thread is None
            or not thread.is_alive()
            or loop is None
            or queue is None
        ):
            self._thread = None
            self._loop = None
            self._queue = None
            return

        future: Future[None] = Future()
        self._enqueue(loop, queue, _StopRequest(future=future))
        future.result(timeout=timeout_seconds)
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise TimeoutError("MCP stdio worker shutdown timed out")

        self._thread = None
        self._loop = None
        self._queue = None

        error = self._worker_error
        self._worker_error = None
        if error is not None:
            raise RuntimeError("MCP stdio worker stopped unexpectedly") from error


_SHARED_MANAGER = McpStdioSessionManager()


def get_shared_mcp_session_manager() -> McpStdioSessionManager:
    return _SHARED_MANAGER


def warmup_shared_mcp_search_runtime() -> bool:
    return _SHARED_MANAGER.warmup_search_runtime()


def close_shared_mcp_session_manager() -> None:
    _SHARED_MANAGER.close()


def _close_at_exit() -> None:
    try:
        close_shared_mcp_session_manager()
    except BaseException:
        pass


atexit.register(_close_at_exit)
