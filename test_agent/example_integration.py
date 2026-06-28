"""
Example: How to add TraceFly to any existing agent.

BEFORE TraceFly (your existing agent code):
    response = my_agent.run(user_message)
    print(response)

AFTER adding TraceFly (add 5 lines):
    from sdk.capture import capture_trace, trace_timer

    with trace_timer() as timer:
        response = my_agent.run(user_message)

    capture_trace(
        user_input=user_message,
        final_output=str(response),
        model_name="claude-sonnet-4-6",
        prompt_version_id="v1.0",
        latency_ms=timer.latency_ms
    )

    print(response)

Your agent behaviour is completely unchanged.
TraceFly silently records what happened.
"""
import time
from sdk.capture import capture_trace, trace_timer


def my_fake_agent(user_message: str) -> str:
    """A placeholder agent — replace with your real agent."""
    time.sleep(0.1)  # simulate processing
    return f"I received your message: '{user_message}'. Here is my response."


def run_agent_with_tracefly(user_message: str) -> str:
    """
    Wraps your agent with TraceFly capture.
    Copy this pattern into your own agent code.
    """
    with trace_timer() as timer:
        response = my_fake_agent(user_message)

    capture_trace(
        user_input=user_message,
        final_output=str(response),
        model_name="claude-sonnet-4-6",
        prompt_version_id="v1.0",
        latency_ms=timer.latency_ms
    )

    return response


if __name__ == "__main__":
    result = run_agent_with_tracefly("How do I track my order?")
    print(f"Agent response: {result}")
