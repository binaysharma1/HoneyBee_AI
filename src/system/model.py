import asyncio

from langchain_openai import ChatOpenAI

from . import config


class ModelError(RuntimeError):
    """Raised when the local model cannot answer a request."""


def _client() -> ChatOpenAI:
	return ChatOpenAI(
		model=config.MODEL,
		base_url=config.MODEL_URL,
		api_key=config.API_KEY,
		temperature=0.2,
	)


async def ask_model(message: str) -> str:
	return await ask_messages([{"role": "user", "content": message}])


async def ask_messages(messages: list[dict[str, str]]) -> str:
	from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

	role_map = {"user": HumanMessage, "assistant": AIMessage, "system": SystemMessage}
	lc_messages = [role_map[m["role"]](content=m["content"]) for m in messages]
	try:
		result = await asyncio.to_thread(_client().invoke, lc_messages)
	except Exception as error:
		raise ModelError(
			"The local model is unavailable. Start an OpenAI-compatible model on port 1234."
		) from error

	content = result.content
	if not isinstance(content, str) or not content.strip():
		raise ModelError("The local model returned an empty response")
	return content.strip()
