from sdk.capture import capture_trace

# Simulate an agent trace
trace_id = capture_trace(
    user_input="How do I return my order from Germany?",
    final_output="You can return your order within 14 days. Visit returns.example.com",
    model_name="claude-sonnet-4-6",
    prompt_version_id="v1.0",
    token_count=250,
    cost_usd=0.003,
    latency_ms=1240,
)
print(f"Trace saved with ID: {trace_id}")

# Add a few more test traces
for i in range(5):
    capture_trace(
        user_input=f"Test question {i}: What is your return policy?",
        final_output=f"Test answer {i}: Our return policy is 30 days.",
        model_name="claude-sonnet-4-6",
        prompt_version_id="v1.0",
    )

print("Test traces saved. Check your database!")
