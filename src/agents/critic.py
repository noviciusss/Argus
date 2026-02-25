from src.graph.state import ReasearchState
from langchain_core.messages import AIMessage

def critic_node(state:ReasearchState)->dict:
    #return empty gaps_identified tells supervisor to procees to writer
    return{
        "gaps_identified":[], #no gaps ->supervisor will route to writer
        "messages":[AIMessage(content="Critic : no gaps identified. Ready for final report.")],
    }