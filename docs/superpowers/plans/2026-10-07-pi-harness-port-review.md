# Code Review: Pi-Harness Port (45e14df..139c06a)

## Critical
1. **Steering Queue Thread-Safety (`session.py`)**
   `AgentSession.send_steering` uses `self._steering_queue.put_nowait(msg)` on a standard `asyncio.Queue`. If `send_steering` is called from the UI thread (or any thread other than the one running `asyncio.run`), it is not thread-safe. This can lead to corrupted queue state or failure to wake up the event loop. It should use `call_soon_threadsafe` or a thread-safe mechanism to bridge the Qt thread and the asyncio loop.

## Important
1. **Missing Cancellation Token Propagation (`workers.py`)**
   In `GenerationWorker._async_harness_run`, you check `if self._is_cancelled: break` inside the `async for` loop. However, you do not pass a `cancellation_token` (an `asyncio.Event`) to `session.prompt(self.prompt)`. This means if a user cancels during a long network hang or slow generation, the HTTP client (`stream_chat`) won't be interrupted immediately. To fix this, create an `asyncio.Event` in the worker, pass it to `session.prompt`, and have the `cancel()` method set it (again, taking care to use `call_soon_threadsafe` since `cancel()` runs on the UI thread).
2. **Missing Central Pydantic Validation (`loop.py` / `tools`)**
   When `json.loads` fails during streaming fragment stitching, you elegantly fallback to `{"_raw": raw_args}`. However, `AgentTool` classes define a `parameters_schema` but don't automatically validate incoming `tc.arguments` against it before calling `execute()`. Tools like `BashTool` manually call `args.get("command")`. While they handle empty arguments gracefully (so the loop doesn't crash), centralizing the `parameters_schema.model_validate(args)` step would provide stronger typing and better error messages back to the LLM when args are malformed.

## Minor
1. **Tool execution error handling (`loop.py`)**
   Excellent implementation. The `try/except` wrapper around `tool.execute()` correctly yields a `ToolResult(is_error=True)` instead of crashing the loop.
2. **Safety Hooks error handling (`loop.py`)**
   Both `before_tool_call` and `after_tool_call` are appropriately wrapped in `try/except` and won't crash the agent loop if user-provided hook callbacks raise an exception.
3. **Fragmented Tool Call Parsing (`stream.py`)**
   The approach of accumulating `delta["tool_calls"]` by index and joining the JSON fragments works correctly. Handling of `json.JSONDecodeError` correctly prevents crashes on malformed LLM outputs.
