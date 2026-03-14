"""
LLM factory — single place to obtain the chat model used by agent nodes.

Role: Map model name (from config) to a LangChain BaseChatModel instance. Used by
main (to pass LLM to graph), and by nodes (intake, summary) for prompt-based calls.
Requires .env with API keys for the provider (OPENAI_*, GROQ_*, GOOGLE_* as per LangChain).
"""
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def get_llm(
    model_name: str,
    temperature: float = 0.3,
    request_timeout: float | None = None,
) -> BaseChatModel:
    """
    Return a chat model instance for the given model name.

    Args:
        model_name: One of "gpt-4o-mini", "llama-3.3-70b-versatile", "gemini-2.5-flash".
        temperature: Sampling temperature (default 0.3).
        request_timeout: Optional HTTP request timeout in seconds. Prevents indefinite hangs.

    Returns:
        Configured BaseChatModel (ChatOpenAI, ChatGroq, or ChatGoogleGenerativeAI).

    Raises:
        ValueError: If model_name is not supported.
    """
    common = {"temperature": temperature}
    if request_timeout is not None:
        common["request_timeout"] = request_timeout
    if model_name == "gpt-4o-mini":
        return ChatOpenAI(model="gpt-4o-mini", **common)
    elif model_name == "llama-3.3-70b-versatile":
        return ChatGroq(model="llama-3.3-70b-versatile", **common)
    elif model_name == "gemini-2.5-flash":
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", **common)
    else:
        raise ValueError(f"Unknown model name: {model_name}")