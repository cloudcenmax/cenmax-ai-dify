"""Run only in an isolated actual SDK runtime with a test authorization.

The connection reference is read from a private file; neither reference nor
OAuth credentials are printed. This script performs real metered inference.
"""
import argparse
import json
import secrets
from pathlib import Path
import sys

from dify_plugin.entities.model.message import UserPromptMessage, ToolPromptMessage, PromptMessageTool
from models.llm.llm import CenmaxAILargeLanguageModel
from cenmax.store import ConnectionStore, catalogue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection-file", required=True)
    parser.add_argument("--model")
    args = parser.parse_args()
    reference = Path(args.connection_file).read_text().strip()
    credentials = {"connection_id": reference}
    available = catalogue(ConnectionStore(reference))
    chosen = next((item for item in available if item["id"] == args.model), None) if args.model else next((item for item in available if item["tools"]), None)
    if chosen is None:
        raise RuntimeError("An entitled tool-capable Cenmax AI model is required.")
    model = CenmaxAILargeLanguageModel([])
    model.validate_credentials(chosen["id"], credentials)
    schema = model.get_customizable_model_schema(chosen["id"], credentials)
    assert schema.model == chosen["id"]
    tools = [PromptMessageTool(name="get_verification_marker", description="Fetch the current unknown verification marker from the local qualification tool.", parameters={
        "type": "object", "properties": {}, "required": [], "additionalProperties": False,
    })]
    prompts = [UserPromptMessage(content="Call get_verification_marker now. Its result is only available by actually calling it. Do not invent a result or answer until the tool responds.")]
    first = model.invoke(model=chosen["id"], credentials=credentials, prompt_messages=prompts,
        model_parameters={"temperature": 0, "max_tokens": min(512, chosen["output"])}, tools=tools, stream=False)
    assert first.model == chosen["id"] and first.system_fingerprint is None
    assert first.message.tool_calls, "Model did not call the test tool."
    prompts.append(first.message)
    marker = "CENMAX-" + secrets.token_hex(6)
    for call in first.message.tool_calls:
        assert call.function.name == "get_verification_marker"
        values = json.loads(call.function.arguments)
        assert values == {}
        prompts.append(ToolPromptMessage(content=marker, tool_call_id=call.id))
    chunks = list(model.invoke(model=chosen["id"], credentials=credentials, prompt_messages=prompts,
        model_parameters={"temperature": 0, "max_tokens": min(256, chosen["output"])}, stream=True))
    assert all(chunk.model == chosen["id"] and chunk.system_fingerprint is None for chunk in chunks)
    assert marker in "".join(chunk.delta.message.content or "" for chunk in chunks)
    assert chunks[-1].delta.finish_reason
    print(json.dumps({"sdk_model_loaded": True, "model": chosen["id"], "tool_round_trip": True, "streaming_followup": True}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Cenmax AI actual-runtime qualification failed.", file=sys.stderr)
        raise SystemExit(1)
