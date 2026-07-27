"""Fixed-system-prompt target agent for Inspect Petri.

This module imports Inspect/Petri lazily so configuration smoke checks work in
an environment that has not installed the optional Petri dependencies.
"""

from __future__ import annotations


def build_fixed_prompt_target(system_prompt: str):
    """Return an Inspect Agent with an immutable, transcript-redacted prompt.

    The auditor controls user messages, prefills, synthetic tool results, and
    rollback branches. It never sees the frozen prompt content: the target's
    private model input and the public Petri transcript are separate lists.
    """
    if not system_prompt.strip():
        raise ValueError("fixed Petri target requires a non-empty system prompt")

    from inspect_ai.agent import agent
    from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, get_model
    from inspect_petri.target import ExitSignal, TOOL_RESULT

    @agent(name="fixed_prompt_target")
    def fixed_prompt_target(*, cache=False):
        async def execute(state, context):
            target_model = get_model(role="target", required=True)
            generate = context.replayable(target_model.generate, surface_errors=True)
            target_cache = context.scoped_cache(cache)

            try:
                await context.wait_for_resume()
                # Consume and discard any staged system message. The public
                # timeline gets a redacted placeholder, never the real prompt.
                await context.system_message(required=False)
                initial_user = await context.user_message()
                model_messages = [
                    ChatMessageSystem(content=system_prompt),
                    initial_user,
                ]
                state.messages[:] = [
                    ChatMessageSystem(
                        content="[fixed target system prompt redacted]",
                        metadata={"fixed_prompt_redacted": True},
                    ),
                    initial_user,
                ]

                while True:
                    if prefill := context.prefill():
                        prefill_message = ChatMessageAssistant(
                            content=prefill,
                            metadata={"prefill": True},
                        )
                        model_messages.append(prefill_message)
                        state.messages.append(prefill_message)

                    state.output = await generate(
                        input=model_messages,
                        tools=context.tools,
                        cache=target_cache,
                    )
                    model_messages.append(state.output.message)
                    state.messages.append(state.output.message)

                    if tool_calls := state.output.message.tool_calls:
                        context.expect({TOOL_RESULT: {tc.id for tc in tool_calls}})
                        await context.send_output(state.output)
                        tool_messages = await context.tool_results(tool_calls)
                        model_messages.extend(tool_messages)
                        state.messages.extend(tool_messages)
                        if user_message := await context.user_message(required=False):
                            model_messages.append(user_message)
                            state.messages.append(user_message)
                    else:
                        context.expect({TOOL_RESULT: set()})
                        await context.send_output(state.output)
                        user_message = await context.user_message()
                        model_messages.append(user_message)
                        state.messages.append(user_message)
            except ExitSignal:
                return state

        return execute

    return fixed_prompt_target(cache=False)
