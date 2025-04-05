import asyncio

import httpx


class LLMProvider:
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict | None = None,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, str]:
        raise NotImplementedError()


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com"):
        self.api_key = api_key
        self.base_url = base_url

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict = None,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": response_format,
            "stream": stream,
            **kwargs,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict = None,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/api/chat"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "format": response_format,
            "options": {
                "temperature": temperature,
                **kwargs,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


async def openai_provider_structured():
    api_key = "api-key"
    provider = OpenAIProvider(api_key=api_key)

    math_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "math_reasoning",
            "schema": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "explanation": {"type": "string"},
                                "output": {"type": "string"},
                            },
                            "required": ["explanation", "output"],
                            "additionalProperties": False,
                        },
                    },
                    "final_answer": {"type": "string"},
                },
                "required": ["steps", "final_answer"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    response = await provider.chat(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Solve this math problem step by step: If a train travels at 120 km/h and covers a distance of 450 km, how long does the journey take in hours and minutes?",
            }
        ],
        temperature=0.2,
        response_format=math_schema,
    )

    return response


async def call_ollama_chat():
    provider = OllamaProvider()

    response = await provider.chat(
        model="llama3.2:1b",
        messages=[
            {
                "role": "user",
                "content": "Ollama is 22 years old and busy saving the world.",
            }
        ],
        temperature=0,
        response_format={
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
                "available": {"type": "boolean"},
            },
            "required": ["age", "available"],
        },
        stream=False,
    )

    return response


if __name__ == "__main__":
    result = asyncio.run(call_ollama_chat())
    print(result)
    result = asyncio.run(openai_provider_structured())
    print(result)
