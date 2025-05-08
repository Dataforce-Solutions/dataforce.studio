# import asyncio
import httpx
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    async def generate(self, messages: list, out_schema) -> str:
        pass

    @abstractmethod
    async def batch_generate(
        self,
        messages: list,
        temperature: float = 0.0,
        n_responses: int = 1,
    ) -> list[str]:
        pass

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        raise NotImplementedError()


class OpenAIProvider(LLM):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com",
        model="gpt-4o-mini",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict | None = None,
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
            "stream": False,
            **kwargs,
        }

        print("Headers", headers)
        print("Payload", payload)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print("Status Code:", e.response.status_code)
                print("Response Text:", e.response.text)
                raise

    async def generate(self, messages: list, out_schema) -> str:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "OutputSchema",
                "schema": out_schema.model_json_schema(),
                "strict": True,
            },
        }

        out = await self.chat(
            model=self.model, messages=messages, response_format=response_format
        )

        return out["choices"][0]["message"]["content"]  # type: ignore

    async def batch_generate(
        self, messages: list, temperature: float = 0, n_responses: int = 1
    ):
        out = await self.chat(
            model=self.model,
            messages=messages,
            temperature=temperature,
            n=n_responses,
        )

        print(
            [
                out["choices"][i]["message"]["content"]  # type: ignore
                for i in range(len(out["choices"]))
            ]
        )

        return [
            out["choices"][i]["message"]["content"]  # type: ignore
            for i in range(len(out["choices"]))
        ]


# class OllamaProvider(LLM):
#     def __init__(self, base_url: str = "http://localhost:11434"):
#         self.base_url = base_url

#     async def chat(
#         self,
#         model: str,
#         messages: list[dict[str, str]],
#         temperature: float = 0.0,
#         response_format: dict | None = None,
#         **kwargs,
#     ) -> dict[str, str]:
#         url = f"{self.base_url}/api/chat"

#         headers = {"Content-Type": "application/json", "Accept": "application/json"}

#         payload = {
#             "model": model,
#             "messages": messages,
#             "stream": False,
#             "format": response_format,
#             "options": {
#                 "temperature": temperature,
#                 **kwargs,
#             },
#         }

#         async with httpx.AsyncClient() as client:
#             response = await client.post(url, json=payload, headers=headers)
#             response.raise_for_status()
#             return response.json()


# async def openai_provider_structured():
#     api_key = "api-key"
#     provider = OpenAIProvider(api_key=api_key)

#     math_schema = {
#         "type": "json_schema",
#         "json_schema": {
#             "name": "math_reasoning",
#             "schema": {
#                 "type": "object",
#                 "properties": {
#                     "steps": {
#                         "type": "array",
#                         "items": {
#                             "type": "object",
#                             "properties": {
#                                 "explanation": {"type": "string"},
#                                 "output": {"type": "string"},
#                             },
#                             "required": ["explanation", "output"],
#                             "additionalProperties": False,
#                         },
#                     },
#                     "final_answer": {"type": "string"},
#                 },
#                 "required": ["steps", "final_answer"],
#                 "additionalProperties": False,
#             },
#             "strict": True,
#         },
#     }

#     response = await provider.chat(
#         model="gpt-4o-mini",
#         messages=[
#             {
#                 "role": "user",
#                 "content": "Solve this math problem step by step: If a train travels at 120 km/h and covers a distance of 450 km, how long does the journey take in hours and minutes?",
#             }
#         ],
#         temperature=0.2,
#         response_format=math_schema,
#     )

#     return response


# async def call_ollama_chat():
#     provider = OllamaProvider()

#     response = await provider.chat(
#         model="llama3.2:1b",
#         messages=[
#             {
#                 "role": "user",
#                 "content": "Ollama is 22 years old and busy saving the world.",
#             }
#         ],
#         temperature=0,
#         response_format={
#             "type": "object",
#             "properties": {
#                 "age": {"type": "integer"},
#                 "available": {"type": "boolean"},
#             },
#             "required": ["age", "available"],
#         },
#         stream=False,
#     )

#     return response


# if __name__ == "__main__":
#     result = asyncio.run(call_ollama_chat())
#     print(result)
#     result = asyncio.run(openai_provider_structured())
#     print(result)
