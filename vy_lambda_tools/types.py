from typing import TypedDict, Literal, Any, Optional

Statuses = Literal["RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]


class StepFunctionsEventType(TypedDict):
    executionArn: str
    stateMachineArn: str
    name: str
    status: Statuses
    startDate: int
    stopDate: Optional[int]
    input: str
    inputDetails: dict[str, Any]
    output: Optional[str]
    outputDetails: Optional[dict[str, Any]]
    cause: Optional[str]
