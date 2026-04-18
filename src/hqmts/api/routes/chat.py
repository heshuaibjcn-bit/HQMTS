"""Chat API routes with SSE streaming."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.db.models.chat import ChatMessageORM, ChatSessionORM
from hqmts.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from hqmts.llm.context_builder import build_system_prompt
from hqmts.llm.factory import LLMFactory

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    title: str = ""
    model_provider: str = "openai"  # openai | ollama | claude


class SendMessageRequest(BaseModel):
    content: str


def _session_to_dict(s: ChatSessionORM) -> dict:
    return {
        "chat_session_id": s.chat_session_id,
        "user_id": s.user_id,
        "title": s.title,
        "model_provider": s.model_provider,
        "environment": s.environment,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m: ChatMessageORM) -> dict:
    return {
        "chat_message_id": m.chat_message_id,
        "chat_session_id": m.chat_session_id,
        "role": m.role,
        "content": m.content,
        "metadata_json": m.metadata_json,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Create a new chat session."""
    repo = ChatSessionRepository(db)

    session_id = f"chat_{uuid.uuid4().hex[:12]}"
    session = ChatSessionORM(
        chat_session_id=session_id,
        user_id=user.user_id,
        title=req.title or "New Chat",
        model_provider=req.model_provider,
        environment="research",  # Default; will be updated from settings
    )
    await repo.create(session)
    return _session_to_dict(session)


@router.get("/sessions")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """List chat sessions for the current user."""
    repo = ChatSessionRepository(db)
    sessions = await repo.get_user_sessions(user.user_id, limit=limit, offset=offset)
    return {
        "sessions": [_session_to_dict(s) for s in sessions],
        "total": len(sessions),
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Get chat message history for a session."""
    session_repo = ChatSessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_repo = ChatMessageRepository(db)
    messages = await msg_repo.get_session_messages(session_id, limit=limit, offset=offset)
    return {
        "messages": [_message_to_dict(m) for m in messages],
        "total": len(messages),
    }


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    req: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    """Send a message and receive SSE-streamed AI response."""
    session_repo = ChatSessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = request.app.state.settings

    # Validate model provider for environment
    factory = LLMFactory(
        openai_api_key=getattr(settings, "openai_api_key", ""),
        ollama_base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
    )
    if not factory.validate_provider(session.environment, session.model_provider):
        raise HTTPException(
            status_code=400,
            detail=f"Model provider '{session.model_provider}' not allowed in {session.environment} environment",
        )

    # Save user message
    msg_repo = ChatMessageRepository(db)
    user_msg = ChatMessageORM(
        chat_message_id=f"msg_{uuid.uuid4().hex[:12]}",
        chat_session_id=session_id,
        role="user",
        content=req.content,
    )
    await msg_repo.create(user_msg)

    # Get adapter
    adapter = factory.get_adapter(session.environment, session.model_provider)

    # Build message history
    history = await msg_repo.get_session_messages(session_id, limit=20)
    messages = [{"role": "system", "content": build_system_prompt(session.environment)}]
    for m in history:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})

    async def _stream_response():
        """SSE stream: yield assistant response chunks."""
        full_response = []
        try:
            async for chunk in adapter.stream(messages):
                full_response.append(chunk)
                data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_data}\n\n"
            return

        # Save assistant message
        assistant_msg = ChatMessageORM(
            chat_message_id=f"msg_{uuid.uuid4().hex[:12]}",
            chat_session_id=session_id,
            role="assistant",
            content="".join(full_response),
        )
        await msg_repo.create(assistant_msg)
        await db.commit()

        # Send done event
        done_data = json.dumps({
            "type": "done",
            "message_id": assistant_msg.chat_message_id,
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        _stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Archive a chat session."""
    session_repo = ChatSessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    await session_repo.update_status(session_id, "archived")
