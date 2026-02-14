import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import inspect
from langgraph.prebuilt import create_react_agent

sig = inspect.signature(create_react_agent)
print(f"Signature: {sig}")
print(f"Docstring: {create_react_agent.__doc__}")
