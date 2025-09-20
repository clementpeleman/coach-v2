from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

# Define the state for the graph
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]

# Define the nodes for the graph
def agent_node(state):
    # For now, the agent just echoes the last message
    last_message = state['messages'][-1]
    return {"messages": [f"Agent echo: {last_message}"]}

# Create the graph
workflow = StateGraph(AgentState)

# Add the nodes
workflow.add_node("agent", agent_node)

# Set the entrypoint
workflow.set_entry_point("agent")

# Add the edges
workflow.add_edge('agent', END)

# Compile the graph
app = workflow.compile()

# Example of how to run the graph
if __name__ == '__main__':
    inputs = {"messages": ["Hello, agent!"]}
    for output in app.stream(inputs):
        # stream() yields dictionaries with output from the node that just ran
        for key, value in output.items():
            print(f"Output from node '{key}': {value}")
        print("\n---\n")
