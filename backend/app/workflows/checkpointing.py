from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


@dataclass
class CheckpointerResource:
    checkpointer: Any | None
    _exit_stack: ExitStack | None = None

    def close(self) -> None:
        if self._exit_stack is not None:
            self._exit_stack.close()
            self._exit_stack = None


def graph_thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    if not thread_id.strip():
        raise ValueError("LangGraph thread_id is required")
    return {"configurable": {"thread_id": thread_id}}


def device_ad_thread_id(task_id: str) -> str:
    return f"device_ad_binding:{task_id}"


def upload_item_thread_id(task_id: str, item_id: str) -> str:
    return f"ad_upload_item:{task_id}:{item_id}"


def create_checkpointer_resource(
    kind: str = "memory",
    *,
    postgres_url: str = "",
    run_postgres_setup: bool = False,
) -> CheckpointerResource:
    normalized = kind.strip().lower()
    if normalized in {"", "memory", "in_memory", "in-memory"}:
        return CheckpointerResource(checkpointer=InMemorySaver())
    if normalized in {"none", "off", "disabled"}:
        return CheckpointerResource(checkpointer=None)
    if normalized in {"postgres", "supabase"}:
        return _create_postgres_checkpointer(postgres_url, run_postgres_setup=run_postgres_setup)
    raise ValueError(f"Unsupported LANGGRAPH_CHECKPOINTER value: {kind}")


def _create_postgres_checkpointer(postgres_url: str, *, run_postgres_setup: bool) -> CheckpointerResource:
    if not postgres_url.strip():
        raise ValueError("LANGGRAPH_POSTGRES_URL is required when LANGGRAPH_CHECKPOINTER=postgres")
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "Postgres LangGraph checkpointing requires langgraph-checkpoint-postgres and psycopg[binary]."
        ) from exc

    stack = ExitStack()
    checkpointer = stack.enter_context(PostgresSaver.from_conn_string(postgres_url))
    if run_postgres_setup:
        checkpointer.setup()
    return CheckpointerResource(checkpointer=checkpointer, _exit_stack=stack)
