import json
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.chat.api.chat import question_answer_inner
from apps.chat.curd.chat import create_chat
from apps.chat.models.chat_model import ChatQuestion, Chat, CreateChat
from apps.datasource.crud.datasource import get_datasource_list
from apps.system.crud.user import authenticate, get_user_info, get_user_by_account
from apps.system.schemas.system_schema import BaseUserDTO, UserInfoDTO
from common.core.security import create_access_token
from common.core.config import settings
from common.core.deps import SessionDep

router = APIRouter(tags=["open"], prefix="/open")


class OpenAuthPayload(BaseModel):
    username: Optional[str] = Field(default=None, description="SQLBot 用户名")
    password: Optional[str] = Field(default=None, description="SQLBot 密码")


class OpenDatasourceRequest(OpenAuthPayload):
    pass


class OpenAskRequest(OpenAuthPayload):
    question: str = Field(description="自然语言问题")
    datasource_id: Optional[int | str] = Field(default=None, description="数据源 ID，可选")
    chat_id: Optional[int] = Field(default=None, description="会话 ID，可选")
    stream: bool = Field(default=False, description="是否流式返回")


def _verify_open_api_key(x_sqlbot_open_key: Optional[str]):
    expected_key = settings.OPEN_API_KEY.strip()
    if not expected_key:
        return
    if x_sqlbot_open_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-SQLBOT-OPEN-KEY",
        )


def _resolve_credentials(payload: OpenAuthPayload) -> tuple[str, str]:
    username = payload.username or settings.OPEN_API_USERNAME
    password = payload.password or settings.OPEN_API_PASSWORD
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Missing credentials. Provide username/password in request body, or configure "
                "OPEN_API_USERNAME and OPEN_API_PASSWORD."
            ),
        )
    return username, password


async def _authenticate_user(session: SessionDep, payload: OpenAuthPayload) -> UserInfoDTO:
    username, password = _resolve_credentials(payload)
    user = authenticate(session=session, account=username, password=password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect account or password")
    user_info = await get_user_info(session=session, user_id=user.id)
    if not user_info:
        raise HTTPException(status_code=400, detail="User not found")
    if isinstance(user_info, dict):
        user_info = UserInfoDTO.model_validate(user_info)
    if not user_info.oid or user_info.oid == 0:
        raise HTTPException(status_code=400, detail="No associated workspace")
    return user_info


@router.post("/public-token", summary="公开访问 Token")
async def public_token(session: SessionDep):
    if not getattr(settings, "OPEN_PUBLIC_ENABLED", False):
        raise HTTPException(status_code=403, detail="Public access disabled")
    username = getattr(settings, "OPEN_PUBLIC_USERNAME", "") or "admin"
    user = get_user_by_account(session=session, account=username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.oid or user.oid == 0:
        raise HTTPException(status_code=400, detail="No associated workspace")
    if user.status != 1:
        raise HTTPException(status_code=400, detail="User disabled")
    if user.origin is not None and user.origin != 0:
        raise HTTPException(status_code=400, detail="User origin invalid")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.to_dict(), expires_delta=access_token_expires)
    return JSONResponse(content={"access_token": token})


def _parse_datasource_id(datasource_id: Optional[int | str]) -> Optional[int]:
    if datasource_id is None:
        return None
    if isinstance(datasource_id, int):
        return datasource_id
    if isinstance(datasource_id, str):
        if datasource_id.strip() == "":
            return None
        try:
            return int(datasource_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datasource_id")
    raise HTTPException(status_code=400, detail="Invalid datasource_id")


def _normalize_json_response(response: Any) -> Any:
    if isinstance(response, JSONResponse):
        body = response.body.decode() if isinstance(response.body, (bytes, bytearray)) else response.body
        try:
            return json.loads(body)
        except Exception:
            return body
    return response


@router.post("/datasources", summary="统一数据源列表接口")
async def datasources(
    session: SessionDep,
    payload: OpenDatasourceRequest,
    x_sqlbot_open_key: Optional[str] = Header(default=None, alias="X-SQLBOT-OPEN-KEY"),
):
    _verify_open_api_key(x_sqlbot_open_key)
    user = await _authenticate_user(session, payload)

    ds_list = get_datasource_list(session=session, user=user)
    result = []
    for item in ds_list:
        dic = item.model_dump()
        dic.pop("embedding", None)
        dic.pop("table_relation", None)
        dic.pop("recommended_config", None)
        dic.pop("configuration", None)
        result.append(dic)
    return JSONResponse(content={"datasources": jsonable_encoder(result)})


@router.post("/ask", summary="统一智能问数接口")
async def ask(
    session: SessionDep,
    payload: OpenAskRequest,
    x_sqlbot_open_key: Optional[str] = Header(default=None, alias="X-SQLBOT-OPEN-KEY"),
):
    _verify_open_api_key(x_sqlbot_open_key)
    user = await _authenticate_user(session, payload)
    datasource_id = _parse_datasource_id(payload.datasource_id)

    if payload.chat_id is not None:
        chat = session.get(Chat, payload.chat_id)
        if not chat or chat.create_by != user.id:
            raise HTTPException(status_code=404, detail="Chat not found")
        chat_id = payload.chat_id
    else:
        chat = create_chat(session, user, CreateChat(origin=1, datasource=datasource_id), False)
        chat_id = chat.id

    request_question = ChatQuestion(
        chat_id=chat_id,
        question=payload.question,
        datasource_id=datasource_id,
    )
    result = await question_answer_inner(
        session=session,
        current_user=user,
        request_question=request_question,
        in_chat=False,
        stream=payload.stream,
    )

    if payload.stream:
        if hasattr(result, "headers"):
            result.headers["X-SQLBOT-CHAT-ID"] = str(chat_id)
        return result

    if isinstance(result, JSONResponse):
        answer = _normalize_json_response(result)
        return JSONResponse(status_code=result.status_code, content={"chat_id": chat_id, "answer": answer})

    return JSONResponse(content={"chat_id": chat_id, "answer": result})
