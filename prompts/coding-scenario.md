---
title: "Code Review Scenario: Fragile API Fetch"
models: [gpt, glm, deepseek, mimo]
system_prompt: |
  You are a senior software engineer reviewing a colleague's code. Respond with:
  1. A one-paragraph assessment of the problems.
  2. A corrected code snippet in a fenced python block.
  3. A short mermaid sequence diagram (fenced ```mermaid block) showing the improved
     error-handling flow.
---

A teammate wrote this Python function that fetches user data from an API and caches it.
It runs in a background job that must not crash overnight:

```python
def get_user(user_id):
    r = requests.get(f"https://api.example.com/users/{user_id}")
    return r.json()["data"]
```

What are the problems with this function, and what would you change?
