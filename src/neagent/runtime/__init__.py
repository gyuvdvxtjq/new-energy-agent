"""Runtime: state machine + approval gate + tool gateway (code-enforced)."""
from .state import (LOCAL_SHORTCUTS, TERMINAL_STATES, TRANSITIONS, IllegalTransitionError,
                    TaskState, TaskStore)
from .gate import ApprovalGate, GateBlockedError
from .gateway import ToolGateway, ToolSpec, UnknownToolError, WrongStateError
