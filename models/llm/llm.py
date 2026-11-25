from __future__ import annotations

import json
from dify_plugin import LargeLanguageModel
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import AIModelEntity, FetchFrom, ModelFeature, ModelPropertyKey, ModelType, ParameterRule, ParameterType
from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk, LLMResultChunkDelta, LLMUsage
from dify_plugin.entities.model.message import AssistantPromptMessage
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError

from cenmax.store import ConnectionStore, catalogue
from cenmax.transport import invoke, response_json, events


def selected_model(model, credentials):
    store = ConnectionStore(credentials.get("connection_id"))
    selected = next((item for item in catalogue(store) if item["id"] == model), None)
    if selected is None:
        raise ValueError("Choose a model available to this Cenmax AI account.")
    return store, selected


def schema(item):
    features = []
    if item["tools"]:
        features += [ModelFeature.TOOL_CALL, ModelFeature.MULTI_TOOL_CALL, ModelFeature.STREAM_TOOL_CALL]
    if item["vision"]:
        features.append(ModelFeature.VISION)
    return AIModelEntity(model=item["id"], label=I18nObject(en_us=item["name"]), model_type=ModelType.LLM,
        fetch_from=FetchFrom.CUSTOMIZABLE_MODEL, features=features,
        model_properties={ModelPropertyKey.MODE: "chat", ModelPropertyKey.CONTEXT_SIZE: item["context"]},
        parameter_rules=[
            ParameterRule(name="temperature", label=I18nObject(en_us="Temperature"), type=ParameterType.FLOAT, default=0.2, min=0, max=2),
            ParameterRule(name="max_tokens", label=I18nObject(en_us="Maximum output tokens"), type=ParameterType.INT, default=min(2048, item["output"]), min=1, max=item["output"]),
        ])


def prompt_message(message, vision=False):
    role = message.role.value
    if role not in {"system", "developer", "user", "assistant", "tool"}:
        raise ValueError("Unsupported Cenmax AI message role.")
    result = {"role": role, "content": message.content}
    if isinstance(message.content, list):
        parts = []
        for part in message.content:
            if part.type == "text":
                parts.append({"type": "text", "text": part.data})
            elif part.type == "image" and vision:
                parts.append({"type": "image_url", "image_url": {"url": part.data}})
            else:
                raise ValueError("This Cenmax AI model does not support the attachment type.")
        result["content"] = parts
    if role == "assistant" and getattr(message, "tool_calls", None):
        result["tool_calls"] = [call.model_dump() for call in message.tool_calls]
    if role == "tool":
        result["tool_call_id"] = message.tool_call_id
    return result


def usage(value):
    value = value or {}
    counts = {}
    for public, target in [("prompt_tokens", "prompt_tokens"), ("completion_tokens", "completion_tokens")]:
        count = value.get(public, 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Invalid Cenmax AI usage response.")
        counts[target] = count
    counts["total_tokens"] = counts["prompt_tokens"] + counts["completion_tokens"]
    return LLMUsage.empty_usage().model_copy(update=counts)


def assistant(value):
    content = value.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError("Invalid Cenmax AI response.")
    calls = value.get("tool_calls") or []
    if not isinstance(calls, list) or len(calls) > 256:
        raise ValueError("Invalid Cenmax AI tool response.")
    result = []
    for call in calls:
        function = call.get("function")
        if not isinstance(function, dict) or not isinstance(call.get("id"), str) or not call["id"] or not isinstance(function.get("name"), str) or not isinstance(function.get("arguments"), str):
            raise ValueError("Invalid Cenmax AI tool response.")
        result.append(AssistantPromptMessage.ToolCall(id=call["id"], type="function", function={"name": function["name"], "arguments": function["arguments"]}))
    if len({call.id for call in result}) != len(result):
        raise ValueError("Invalid Cenmax AI tool response.")
    return AssistantPromptMessage(content=content or "", tool_calls=result)


class CenmaxAILargeLanguageModel(LargeLanguageModel):
    def remote_models(self, credentials):
        try:
            return [schema(item) for item in catalogue(ConnectionStore(credentials.get("connection_id")))]
        except Exception:
            raise InvokeError("Cenmax AI model discovery failed. Check the connection.") from None

    def get_customizable_model_schema(self, model, credentials):
        try:
            return schema(selected_model(model, credentials)[1])
        except Exception:
            raise InvokeError("Choose a model available to this Cenmax AI account.") from None

    def validate_credentials(self, model, credentials):
        try:
            selected_model(model, credentials)
        except Exception:
            raise CredentialsValidateFailedError("Cenmax AI model access could not be verified.") from None

    def get_num_tokens(self, model, credentials, prompt_messages, tools=None):
        # This is a conservative local estimate, not a model tokenizer.
        size = sum(len(message.get_text_content().encode("utf-8")) for message in prompt_messages)
        size += sum(len(tool.model_dump_json().encode("utf-8")) for tool in (tools or []))
        return size + len(prompt_messages) * 8

    @property
    def _invoke_error_mapping(self):
        return {}

    def _invoke(self, model, credentials, prompt_messages, model_parameters, tools=None, stop=None, stream=True, user=None):
        try:
            store, selected = selected_model(model, credentials)
            if tools and not selected["tools"]:
                raise ValueError()
            payload = {"model": model, "messages": [prompt_message(item, selected["vision"]) for item in prompt_messages], "stream": stream}
            for key in ["temperature", "top_p", "max_tokens"]:
                if key in model_parameters:
                    payload[key] = model_parameters[key]
            maximum = payload.get("max_tokens", min(2048, selected["output"]))
            if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= selected["output"]:
                raise ValueError()
            payload["max_tokens"] = maximum
            if tools:
                payload["tools"] = [{"type": "function", "function": tool.model_dump()} for tool in tools]
            if stop:
                payload["stop"] = stop
            if stream:
                payload["stream_options"] = {"include_usage": True}
            response = invoke(store, payload, stream)
            if stream:
                return self._stream(model, response)
            body = response_json(response)
            if body.get("model") != model or not body.get("choices"):
                raise ValueError()
            return LLMResult(model=model, message=assistant(body["choices"][0]["message"]), usage=usage(body.get("usage")))
        except Exception:
            raise InvokeError("Cenmax AI request failed. Check the connection, model access, and allowance.") from None

    def _stream(self, model, response):
        calls = {}
        last_usage = {}
        finish = None
        index = 0
        try:
            for event in events(response):
                if event.get("model") not in (None, model):
                    raise ValueError()
                if event.get("usage") is not None:
                    last_usage = event["usage"]
                for choice in event.get("choices", []):
                    delta = choice.get("delta", {})
                    text = delta.get("content")
                    if text:
                        if not isinstance(text, str):
                            raise ValueError()
                        yield LLMResultChunk(model=model, delta=LLMResultChunkDelta(index=index, message=AssistantPromptMessage(content=text)))
                        index += 1
                    for fragment in delta.get("tool_calls", []):
                        position = fragment.get("index")
                        if isinstance(position, bool) or not isinstance(position, int) or not 0 <= position < 256:
                            raise ValueError()
                        call = calls.setdefault(position, {"id": "", "function": {"name": "", "arguments": ""}})
                        if fragment.get("id"):
                            call["id"] = fragment["id"]
                        function = fragment.get("function", {})
                        for key in ["name", "arguments"]:
                            if function.get(key):
                                call["function"][key] += function[key]
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
                        if finish not in {"stop", "length", "tool_calls", "function_call", "content_filter"}:
                            raise ValueError()
            if finish is None:
                raise ValueError()
            message = assistant({"content": "", "tool_calls": [calls[key] for key in sorted(calls)]})
            yield LLMResultChunk(model=model, delta=LLMResultChunkDelta(index=index, message=message, finish_reason=finish, usage=usage(last_usage)))
        except Exception:
            raise InvokeError("Cenmax AI stream could not complete. Retry the request.") from None
