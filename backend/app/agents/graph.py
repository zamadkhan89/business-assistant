"""
LangGraph StateGraph wiring for the business assistant.

Pipeline (linear for data queries):
  supervisor → schema_agent → sql_agent --[interrupt]--> [HITL] --[resume]--> analysis_agent → END

For non-data intents (greetings, off-topic), supervisor routes directly to END.
The checkpointer (MemorySaver in dev, AsyncPostgresSaver in prod) persists full graph
state between the interrupt and the resume so conversation context is never lost.
"""
from langgraph.graph import END, StateGraph

from app.agents.analysis_agent import analysis_agent_node
from app.agents.schema_agent import schema_agent_node
from app.agents.sql_agent import sql_agent_node
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node


def _route_supervisor(state: AgentState) -> str:
    """Route to schema_agent for data queries; end for off-topic replies.

    Both 'schema' (SQL query) and 'schema_only' (list available tables) go to
    schema_agent — it handles the distinction internally via current_step.
    """
    return "schema_agent" if state.get("current_step") in ("schema", "schema_only") else END


def _route_schema(state: AgentState) -> str:
    """Route to sql_agent once relevant tables have been identified."""
    return "sql_agent" if state.get("current_step") == "schema_done" else END


def _route_sql(state: AgentState) -> str:
    """Route to analysis_agent only after the user approves the SQL (HITL resume)."""
    return "analysis_agent" if state.get("current_step") == "approved" else END


def build_graph(checkpointer):
    """
    Compile and return the LangGraph StateGraph.

    Args:
        checkpointer: A LangGraph checkpointer (MemorySaver or AsyncPostgresSaver).
                      Persists AgentState across the HITL interrupt/resume boundary
                      and across HTTP requests on the same thread_id.

    Returns:
        CompiledStateGraph: ready for ainvoke() / astream() calls.
    """
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("sql_agent", sql_agent_node)
    graph.add_node("analysis_agent", analysis_agent_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", _route_supervisor)
    graph.add_conditional_edges("schema_agent", _route_schema)
    graph.add_conditional_edges("sql_agent", _route_sql)
    graph.add_edge("analysis_agent", END)

    return graph.compile(checkpointer=checkpointer)


async def make_postgres_checkpointer(postgres_url: str):
    """Return (pool, checkpointer); caller is responsible for closing the pool."""
    from psycopg_pool import AsyncConnectionPool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    pool = AsyncConnectionPool(postgres_url, open=False)
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return pool, checkpointer
