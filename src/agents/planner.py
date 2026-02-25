import os
from langchain_groq import ChatGroq
from src.graph.state import ReasearchState        
from langchain_core.messages import AIMessage,SystemMessage,HumanMessage


_DEPTH_QUESTION = {"quick":2,"standard":3,"deep":5}
_SYSTEM_PROMPT = """
You are a research planning expert. Given a research query , break it down into specific, 
focus sub-questions that togehter would fully answer the origibal query.

Rules:
-Each sub-question must be answerable via web search
- sub questions should cover : background/context, current state, key challenges, future directions
- Output only numbered list of sub-questions, one per line, no preamble
-Example output:
1. What is history and background of X?
2. What are the most recent breakthroughs in X?
3. What are the main limitations of current X approaches?
"""


def planner_node(state: ReasearchState) -> dict: 
    n_questions = _DEPTH_QUESTION.get(state.get("depth","standard"),3)
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,  
    )
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Research query:{state['query']}\nGenerate {n_questions} sub-questions.")
    ])
    #parse numbered list 
    lines = response.content.strip().split("\n")
    sub_questions = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            # Strip "1. " or "- " prefix
            cleaned = line.lstrip("0123456789.-) ").strip()
            if cleaned:
                sub_questions.append(cleaned)

    # Fallback if parsing fails
    if not sub_questions:
        sub_questions = [state["query"]]

    return {
        "sub_questions": sub_questions,
        "messages": [AIMessage(content=f"Planner: generated {len(sub_questions)} sub-questions.")],
    }