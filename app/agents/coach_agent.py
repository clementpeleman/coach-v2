from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import handle_garmin_credentials

# Login graph
login_graph = StateGraph(AgentState)
login_graph.add_node("handle_garmin_credentials", handle_garmin_credentials)
login_graph.set_entry_point("handle_garmin_credentials")
login_graph.add_edge("handle_garmin_credentials", END)
login_app = login_graph.compile()
