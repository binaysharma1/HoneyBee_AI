import asyncio
import os

from langchain_openai import ChatOpenAI


class ModelError(RuntimeError):
	"""Raised when the local model cannot answer a request."""


def _client() -> ChatOpenAI:
	return ChatOpenAI(
		model=os.getenv("HONEYBEE_MODEL", "local-model"),
		base_url=os.getenv("HONEYBEE_MODEL_URL", "http://127.0.0.1:1234/v1"),
		api_key=os.getenv("HONEYBEE_API_KEY", "lm-studio"),
		temperature=0.2,
	)


async def ask_model(message: str) -> str:
	try:
		result = await asyncio.to_thread(_client().invoke, message)
	except Exception as error:
		raise ModelError(
			"The local model is unavailable. Start an OpenAI-compatible model on port 1234."
		) from error

	content = result.content
	if not isinstance(content, str) or not content.strip():
		raise ModelError("The local model returned an empty response")
	return content.strip()
#write code to send request from frontend to the ai model runnign on port:1234 adn send reponse through fastapi
#endpoint /ai to frontend .

#Note:Use langchain here,