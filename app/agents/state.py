from typing import TypedDict, Annotated, List, Optional
import operator

class AgentState(TypedDict):
    user_id: Optional[str]
    garmin_credentials: Optional[dict]
    activities: Optional[List[dict]]
    analysis: Optional[dict]
    fit_file_path: Optional[str]
    messages: Annotated[list, operator.add]
