from typing import TypedDict


class SessionState(TypedDict):
    """
    Design note (deliberate, not an oversight): `history` accumulates every
    turn's (question, agent, result), but only the Report Agent consumes
    it. Routing and narration only ever see the CURRENT question -- each
    turn is resolved independently. This matches the original proposal,
    which only specifies history being handed to the Report Agent at the
    end of a session, not being fed back into per-turn routing/generation.
    Multi-turn reference resolution ("what about last year?") is out of
    scope; see docs/architecture.md Future Extensions.
    """
    question: str
    route: str
    result: dict
    history: list
