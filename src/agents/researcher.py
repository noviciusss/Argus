from src.graph.state import ReasearchState
from langchain_core.messages import AIMessage

def researcher_node(state:ReasearchState)->dict:
    #phase 1 only boiler plate
    iteration = state.get("research_iterations",0) + 1
    return{
        "research_findings":state.get("research_findings",[])+[
            f"[Stub finding {iteration}] Research result for: {state['query']}"
        ],
        "research_iterations": iteration,
        "messages" :[AIMessage(content=f"Researcher : completed iteration {iteration} of research. ")],
    }