

from typing import Dict, List, Optional
import inspect
import copy
from pydantic import BaseModel
from dataclasses import is_dataclass, asdict
from enum import Enum
from typing import get_origin, get_args
from src.utils.helper.common import MyJSON

def fetch_function_definitions(fn_map: Dict, fn_names: List[str]) -> str:
    """
    Fetches the documentation for a list of functions from a function map.
    
    Args:
        fn_map (Dict): Dictionary mapping function names to their callable objects.
        fn_names (List[str]): List of function names to fetch definitions for.
    
    Returns:
        str: A string containing function names and their docstrings, joined by a separator.
    """
    defs = []
    for fn in fn_names:
        try:
            doc = inspect.getdoc(fn_map.get(fn)) or "No documentation available"
            defs.append(f"{fn}: {doc}")
        except Exception as e:
            defs.append(f"{fn}: Error fetching docstring - {str(e)}")
    return "\n<===***********======>\n".join(defs)

def fetch_function_defaults(fn_map: Dict, fn_names: List[str]) -> Dict:
    """
    Fetches the default parameter values for a list of functions from a function map.
    Handles complex types like Pydantic models, dataclasses, and nested structures.
    
    Args:
        fn_map (Dict): Dictionary mapping function names to their callable objects.
        fn_names (List[str]): List of function names to fetch defaults for.
    
    Returns:
        Dict: A dictionary mapping function names to their default parameter values.
    """
    def extract_model_schema(model: type[BaseModel]) -> Dict:
        """Helper function to extract schema from a Pydantic model."""
        schema = {}
        from pydantic_core import PydanticUndefined
        for name, field in model.model_fields.items():
            default = field.default
            is_required = default is PydanticUndefined
            annotation = field.annotation

            # # Handle Enum
            # if isinstance(annotation, type) and issubclass(annotation, Enum):
            #     options = [e.value for e in annotation]
            #     schema[name] = f'"{default.value}", // options: {options}' if not is_required else "<required>"
                
            if isinstance(annotation, type) and issubclass(annotation, Enum):
                options = [e.value for e in annotation]
                schema[name] = default.value if not is_required else "<required>"
                schema[f"{name}__options"] = options   # store separately


            # Handle nested BaseModel
            elif isinstance(default, BaseModel):
                schema[name] = extract_model_schema(type(default))

            # Handle list of BaseModels
            elif get_origin(annotation) is list:
                args = get_args(annotation)
                if args and issubclass(args[0], BaseModel):
                    schema[name] = [extract_model_schema(args[0])]
                else:
                    schema[name] = [default] if not is_required else ["<required>"]

            # Simple field
            else:
                schema[name] = default if not is_required else "<required>"
        return schema

    defs = {}
    for fn in fn_names:
        func = fn_map.get(fn)
        if not func:
            defs[fn] = None
            continue

        sig = inspect.signature(func)
        param_with_default = None
        for param in sig.parameters.values():
            if param.default is not inspect._empty:
                param_with_default = param
                break

        if param_with_default is None:
            defs[fn] = None
            continue

        default_val = param_with_default.default

        # Case A: Default is None, try to instantiate from annotation
        if default_val is None:
            ann = param_with_default.annotation
            candidate = None

            if isinstance(ann, str):
                try:
                    ann = eval(ann, func.__globals__)
                except Exception:
                    pass

            origin = get_origin(ann)
            if origin is not None and origin is __import__('typing').Union:
                args = [a for a in get_args(ann) if a is not type(None)]
                if args:
                    ann = args[0]

            try:
                if isinstance(ann, type) and issubclass(ann, BaseModel):
                    candidate = extract_model_schema(ann)
                elif isinstance(ann, type) and is_dataclass(ann):
                    candidate = asdict(ann())
                elif ann is dict or get_origin(ann) is dict:
                    candidate = {}
                elif ann is list or get_origin(ann) is list:
                    candidate = []
            except Exception:
                candidate = None

            defs[fn] = candidate

        # Case B: Default is an actual object
        else:
            if isinstance(default_val, BaseModel):
                defs[fn] = extract_model_schema(type(default_val))
            elif is_dataclass(default_val):
                defs[fn] = asdict(type(default_val)())
            elif isinstance(default_val, list) and default_val and isinstance(default_val[0], BaseModel):
                defs[fn] = [extract_model_schema(type(default_val[0]))]
            else:
                try:
                    defs[fn] = copy.deepcopy(default_val)
                except Exception:
                    defs[fn] = default_val
                    
    # print("_fetch_fn_defaults ", MyJSON.dumps(defs))
    return defs


def format_actions_with_docs_and_defaults(fn_map: dict) -> str:
    """
    Renders actions in a readable, sequential format:
    - Action name
    - Docstring
    - Default params
    """

    blocks = []

    for name, fn in fn_map.items():
        # --- Docstring ---
        doc = inspect.getdoc(fn) or "No documentation available."

        # --- Defaults ---
        defaults = fetch_function_defaults({name: fn}, [name]).get(name)
        defaults_str = MyJSON.dumps(defaults, indent=2) if defaults is not None else "None"

        block = f"""
            🔧 Action: {name}
            {'-' * (10 + len(name))}

            {doc}

            Default Params:
            {defaults_str}
            """
        blocks.append(block.strip())

    return "\n\n" + ("\n\n" + "=" * 80 + "\n\n").join(blocks)
