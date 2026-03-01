"""
Graph visualization — render the workflow as a Mermaid diagram and save as PNG.

Role: Save a visual representation of the insurance cancellation graph to disk (default
paths.OUTPUTS_DIR). Uses a custom Mermaid string so the intake self-loop and all
conditional edges are visible; set use_custom_mermaid=False to use the compiled graph's
built-in diagram. Called from main after the workflow completes.
"""
from typing import Callable, Dict, Any
from langgraph.graph import StateGraph
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.graph_mermaid import draw_mermaid_png
import os

from codes.llm import get_llm
from codes.paths import OUTPUTS_DIR

# Custom Mermaid diagram that explicitly shows the intake self-loop and all conditional edges.
# LangGraph's auto-generated Mermaid often omits or hides self-loops (e.g. intake -> intake).
INSURANCE_CANCELLATION_MERMAID = """
flowchart TD
    START --> intake
    intake -->|"loop until policy confirmed"| intake
    intake -->|"ready_for_analysis"| analysis
    intake --> END
    analysis -->|"eligible"| eligibility_hitl
    analysis --> END
    eligibility_hitl -->|"approved"| refund
    eligibility_hitl -->|"rejected"| END
    refund --> refund_hitl
    refund --> END
    refund_hitl -->|"approved"| log_refund
    refund_hitl -->|"rejected"| END
    log_refund --> summary
    summary --> END
"""


def with_llm_node(
    llm_model: str,
    handler_factory: Callable[[Any], Callable[[Dict[str, Any]], Dict[str, Any]]],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Create a LangGraph node by injecting an LLM into a handler factory.

    Args:
        llm_model: Model name for get_llm.
        handler_factory: Function (llm) -> node_function(state) -> state_updates.

    Returns:
        A node function (state) -> dict for use with graph.add_node.
    """
    llm = get_llm(llm_model)
    return handler_factory(llm)


def save_graph_visualization(
    graph: StateGraph,
    save_dir: str = OUTPUTS_DIR,
    graph_name: str = "graph",
    use_custom_mermaid: bool = True,
) -> None:
    """
    Render the graph as a Mermaid-based PNG and save to save_dir/graph_name.png.

    For insurance_cancellation_graph, use_custom_mermaid=True (default) uses
    INSURANCE_CANCELLATION_MERMAID so the intake self-loop and all edges are visible.
    """
    save_path = os.path.join(os.path.abspath(save_dir), f"{graph_name}.png")
    os.makedirs(save_dir, exist_ok=True)
    mermaid_src = INSURANCE_CANCELLATION_MERMAID if (use_custom_mermaid and graph_name == "insurance_cancellation_graph") else None

    for draw_method in (MermaidDrawMethod.API, MermaidDrawMethod.PYPPETEER):
        try:
            if mermaid_src is not None:
                png = draw_mermaid_png(mermaid_src, draw_method=draw_method)
            else:
                png = graph.get_graph().draw_mermaid_png(draw_method=draw_method)
            with open(save_path, "wb") as f:
                f.write(png)
            print("\n")
            print(f"✅ Graph saved to {save_path}")
            return
        except Exception as e:
            if draw_method == MermaidDrawMethod.API:
                print(f"⚠️ Graph PNG (API): {e}")
            else:
                print(f"⚠️ Graph PNG (pyppeteer): {e}")
            continue

    # Fallback: write Mermaid source so user can render elsewhere (e.g. mermaid.live)
    mmd_path = save_path.replace(".png", ".mmd")
    try:
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write(mermaid_src or graph.get_graph().draw_mermaid())
        print(f"⚠️ PNG render failed (network/local browser). Mermaid source saved to {mmd_path}")
    except Exception as e:
        print(f"⚠️ Could not save graph image or Mermaid source: {e}")
