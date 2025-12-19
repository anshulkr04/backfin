"""
OpenAPI Spec Generator for Flask + Anshul Tools
Automatically generates OpenAPI 3.0 specification from Flask routes and @anshul decorated functions.
"""

import inspect
import json
from typing import get_type_hints, get_origin, get_args, Union
from flask import Flask
# from anshul_tools import MY_TOOLS


def get_python_type_to_openapi(python_type):
    """Convert Python type hints to OpenAPI schema types."""
    type_mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array", "items": {}},
        dict: {"type": "object"},
    }
    
    # Handle Optional types
    origin = get_origin(python_type)
    if origin is Union:
        args = get_args(python_type)
        # Remove NoneType from Union to get the actual type
        non_none_types = [arg for arg in args if arg is not type(None)]
        if non_none_types:
            python_type = non_none_types[0]
    
    return type_mapping.get(python_type, {"type": "string"})


def extract_parameters_from_function(func):
    """Extract parameters from a function's signature and type hints."""
    parameters = []
    
    try:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'cls']:
                continue
                
            param_schema = {
                "name": param_name,
                "in": "query",
                "required": param.default == inspect.Parameter.empty,
                "schema": get_python_type_to_openapi(type_hints.get(param_name, str))
            }
            
            # Add default value if exists
            if param.default != inspect.Parameter.empty:
                if param.default is not None:
                    param_schema["schema"]["default"] = param.default
            
            parameters.append(param_schema)
    except Exception as e:
        print(f"Warning: Could not extract parameters from {func.__name__}: {e}")
    
    return parameters


def generate_openapi_spec_from_flask(app: Flask, title="API", version="1.0.0", description=""):
    """Generate OpenAPI 3.0 specification from Flask app and @anshul tools."""
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": title,
            "version": version,
            "description": description
        },
        "servers": [
            {
                "url": "http://localhost:5001",
                "description": "Development server"
            }
        ],
        "paths": {},
        "components": {
            "schemas": {}
        }
    }
    
    # Extract routes from Flask app
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
            
        path = rule.rule
        # Convert Flask route parameters to OpenAPI format
        path = path.replace('<int:', '{').replace('<string:', '{').replace('<', '{').replace('>', '}')
        
        if path not in spec["paths"]:
            spec["paths"][path] = {}
        
        # Get the view function
        view_func = app.view_functions.get(rule.endpoint)
        if not view_func:
            continue
        
        # Get docstring
        docstring = inspect.getdoc(view_func) or "No description provided"
        
        # Process each HTTP method
        for method in rule.methods:
            if method in ['HEAD', 'OPTIONS']:
                continue
            
            method_lower = method.lower()
            
            operation = {
                "summary": f"{method} {rule.endpoint}",
                "description": docstring,
                "operationId": f"{method_lower}_{rule.endpoint}",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    }
                }
            }
            
            # Extract path parameters
            path_params = []
            for arg in rule.arguments:
                param_schema = {
                    "name": arg,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer" if "int:" in rule.rule else "string"}
                }
                path_params.append(param_schema)
            
            # Extract function parameters for query/body
            func_params = extract_parameters_from_function(view_func)
            
            # Determine if we need request body (for POST, PUT, PATCH)
            if method in ['POST', 'PUT', 'PATCH'] and func_params:
                # Create request body schema
                properties = {}
                required = []
                
                for param in func_params:
                    param_name = param["name"]
                    properties[param_name] = param["schema"]
                    if param["required"]:
                        required.append(param_name)
                
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": properties,
                                "required": required if required else None
                            }
                        }
                    }
                }
                # Remove None from required if empty
                if not required:
                    del operation["requestBody"]["content"]["application/json"]["schema"]["required"]
            else:
                # Add query parameters for GET requests
                operation["parameters"] = path_params + func_params
            
            if not operation.get("parameters"):
                operation["parameters"] = path_params if path_params else []
            
            if not operation["parameters"]:
                del operation["parameters"]
            
            spec["paths"][path][method_lower] = operation
    
    # Add tool schemas from @anshul decorated functions
    spec["components"]["schemas"]["AnshulTools"] = {
        "type": "object",
        "description": "Available AI tools registered with @anshul decorator",
        "properties": {}
    }
    
    for tool_info in MY_TOOLS:
        tool_name = tool_info["name"]
        tool_func = tool_info["original_func"]
        
        # Extract function parameters
        func_params = extract_parameters_from_function(tool_func)
        
        properties = {}
        required = []
        
        for param in func_params:
            properties[param["name"]] = param["schema"]
            if param["required"]:
                required.append(param["name"])
        
        spec["components"]["schemas"]["AnshulTools"]["properties"][tool_name] = {
            "type": "object",
            "description": inspect.getdoc(tool_func) or "No description",
            "properties": properties,
            "required": required if required else []
        }
    
    return spec


def save_openapi_spec(app: Flask, output_file="openapi.json", **kwargs):
    """Generate and save OpenAPI spec to a JSON file."""
    spec = generate_openapi_spec_from_flask(app, **kwargs)
    
    with open(output_file, 'w') as f:
        json.dump(spec, f, indent=2)
    
    print(f"OpenAPI specification saved to {output_file}")
    return spec


def save_openapi_spec_yaml(app: Flask, output_file="openapi.yaml", **kwargs):
    """Generate and save OpenAPI spec to a YAML file."""
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed. Install with: pip install pyyaml")
        return None
    
    spec = generate_openapi_spec_from_flask(app, **kwargs)
    
    with open(output_file, 'w') as f:
        yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
    
    print(f"OpenAPI specification saved to {output_file}")
    return spec


if __name__ == "__main__":
    import sys
    import os
    import importlib.util
    
    # Usage: python generate_openapi.py <backend_file.py> [output_file.json] [--title "API Title"] [--version "1.0.0"] [--description "API Description"]
    
    if len(sys.argv) < 2:
        print("Usage: python generate_openapi.py <backend_file.py> [output_file.json] [options]")
        print("\nOptions:")
        print("  --title        API title (default: 'API')")
        print("  --version      API version (default: '1.0.0')")
        print("  --description  API description (default: '')")
        print("  --app-name     Flask app variable name (default: 'app')")
        print("\nExample:")
        print("  python generate_openapi.py todo_backend.py openapi.json --title 'My API' --version '2.0.0'")
        sys.exit(1)
    
    # Parse arguments
    backend_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else "openapi.json"
    
    # Parse optional arguments
    title = "API"
    version = "1.0.0"
    description = ""
    app_name = "app"
    
    i = 2 if not sys.argv[2].startswith('--') else 1
    i += 1
    while i < len(sys.argv):
        if sys.argv[i] == "--title" and i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--version" and i + 1 < len(sys.argv):
            version = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--description" and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--app-name" and i + 1 < len(sys.argv):
            app_name = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    # Check if backend file exists
    if not os.path.exists(backend_file):
        print(f"Error: Backend file '{backend_file}' not found")
        sys.exit(1)
    
    # Dynamically import the backend module
    spec_from_file = importlib.util.spec_from_file_location("backend_module", backend_file)
    backend_module = importlib.util.module_from_spec(spec_from_file)
    
    try:
        spec_from_file.loader.exec_module(backend_module)
    except Exception as e:
        print(f"Error importing backend file: {e}")
        sys.exit(1)
    
    # Get the Flask app instance
    if not hasattr(backend_module, app_name):
        print(f"Error: Flask app variable '{app_name}' not found in {backend_file}")
        print(f"Available variables: {[name for name in dir(backend_module) if not name.startswith('_')]}")
        sys.exit(1)
    
    app = getattr(backend_module, app_name)
    
    if not isinstance(app, Flask):
        print(f"Error: '{app_name}' is not a Flask application instance")
        sys.exit(1)
    
    # Generate OpenAPI spec
    spec = save_openapi_spec(
        app,
        output_file=output_file,
        title=title,
        version=version,
        description=description
    )
    
    print(f"\nGenerated OpenAPI spec with {len(spec['paths'])} endpoints:")
    for path in spec["paths"]:
        methods = ', '.join(spec["paths"][path].keys()).upper()
        print(f"  [{methods}] {path}")
    
    if spec["components"]["schemas"]["AnshulTools"]["properties"]:
        print(f"\nGenerated {len(spec['components']['schemas']['AnshulTools']['properties'])} tool schemas:")
        for tool_name in spec["components"]["schemas"]["AnshulTools"]["properties"]:
            print(f"  {tool_name}")
