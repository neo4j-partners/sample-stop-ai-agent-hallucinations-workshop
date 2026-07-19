# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Amazon Bedrock providers for neo4j-graphrag.

Replaces OpenAI dependencies with:
- Amazon Nova 2 Multimodal Embeddings for embeddings
- Amazon Bedrock Claude for LLM entity extraction

No OpenAI API key required — uses AWS credentials only.
"""

import json
import os
import boto3
from neo4j_graphrag.llm.base import LLMInterface, LLMResponse
from neo4j_graphrag.embeddings.base import Embedder


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if the model added one.

    neo4j-graphrag parses entity-extraction responses as raw JSON, but Claude
    commonly wraps JSON in ```json ... ``` fences. Left in place, every chunk
    fails with "LLM response has improper format" and the graph comes out empty.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text

    lines = stripped.splitlines()
    if lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines[1:]).strip()


class BedrockEmbeddings(Embedder):
    """Amazon Bedrock embeddings using Nova 2 Multimodal Embeddings."""

    def __init__(
        self,
        model_id: str = "amazon.nova-2-multimodal-embeddings-v1:0",
        region_name: str = os.environ.get("AWS_REGION", "us-east-1"),
        dimensions: int = 1024,
    ):
        self.model_id = model_id
        self.dimensions = dimensions
        self.client = boto3.client("bedrock-runtime", region_name=region_name)

    def embed_query(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "taskType": "SINGLE_EMBEDDING",
                "singleEmbeddingParams": {
                    "embeddingPurpose": "GENERIC_INDEX",
                    "embeddingDimension": self.dimensions,
                    "text": {"truncationMode": "END", "value": text},
                },
            }),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embeddings"][0]["embedding"]


class BedrockLLM(LLMInterface):
    """Amazon Bedrock LLM using Claude via the Converse API."""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-5",
        region_name: str = os.environ.get("AWS_REGION", "us-east-1"),
        temperature: float | None = None,
        max_tokens: int = 4096,
    ):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, input: str, message_history=None, system_instruction=None) -> LLMResponse:
        messages = []

        if message_history:
            for msg in message_history:
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", str(msg))
                messages.append({"role": role, "content": [{"text": content}]})

        messages.append({"role": "user", "content": [{"text": input}]})

        inference_config = {"maxTokens": self.max_tokens}

        # Sonnet 5 rejects `temperature` outright ("deprecated for this model"),
        # so only send it when a caller explicitly asks for one.
        if self.temperature is not None:
            inference_config["temperature"] = self.temperature

        kwargs = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": inference_config,
        }

        if system_instruction:
            kwargs["system"] = [{"text": system_instruction}]

        response = self.client.converse(**kwargs)
        blocks = response["output"]["message"]["content"]

        # Sonnet 5 puts a reasoningContent block before the answer, so take the
        # first block that actually carries text instead of assuming index 0.
        content = next((b["text"] for b in blocks if "text" in b), None)
        if content is None:
            raise ValueError(f"No text block in Bedrock response: {[list(b) for b in blocks]}")

        return LLMResponse(content=_strip_code_fence(content))

    async def ainvoke(self, input: str, message_history=None, system_instruction=None) -> LLMResponse:
        return self.invoke(input, message_history, system_instruction)
