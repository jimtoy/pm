"""A stand-in for the OpenAI client, shared by the ai and chat tests.

Mirrors only the surface `app.ai` / `app.chat` actually touch:
`client.chat.completions.create(...)` returning an object with `.choices[0].message.content`.
"""


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        # A content of None models a response with no choices at all.
        self.choices = [FakeChoice(content)] if content is not None else []


class FakeCompletions:
    def __init__(self, contents=None, error=None):
        self._contents = list(contents) if contents is not None else []
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return FakeResponse(self._contents.pop(0))


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    """`contents` is one response body per expected call, consumed in order."""

    def __init__(self, contents=None, error=None):
        self.chat = FakeChat(FakeCompletions(contents=contents, error=error))
