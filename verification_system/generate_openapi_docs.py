"""
Advanced OpenAPI Specification Tools
- Export OpenAPI spec in multiple formats
- Generate Markdown documentation
- Compare API versions
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))


class OpenAPIExporter:
    """Export and manage OpenAPI specifications"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).parent
        self.output_dir.mkdir(exist_ok=True)
        
    def get_openapi_schema(self) -> Dict[str, Any]:
        """Get OpenAPI schema from FastAPI app"""
        from app import app
        return app.openapi()
    
    def export_json(self, filename: str = "openapi.json") -> Path:
        """Export OpenAPI spec as JSON"""
        schema = self.get_openapi_schema()
        output_file = self.output_dir / filename
        
        with open(output_file, "w") as f:
            json.dump(schema, f, indent=2)
        
        print(f"✅ Exported JSON: {output_file}")
        return output_file
    
    def export_yaml(self, filename: str = "openapi.yaml") -> Path:
        """Export OpenAPI spec as YAML"""
        try:
            import yaml
            schema = self.get_openapi_schema()
            output_file = self.output_dir / filename
            
            with open(output_file, "w") as f:
                yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
            
            print(f"✅ Exported YAML: {output_file}")
            return output_file
        except ImportError:
            print("⚠️  PyYAML not installed. Skipping YAML export.")
            return None
    
    def export_markdown(self, filename: str = "API_DOCUMENTATION.md") -> Path:
        """Generate Markdown documentation from OpenAPI spec"""
        schema = self.get_openapi_schema()
        output_file = self.output_dir / filename
        
        with open(output_file, "w") as f:
            # Header
            f.write(f"# {schema.get('info', {}).get('title', 'API Documentation')}\n\n")
            f.write(f"**Version:** {schema.get('info', {}).get('version', '1.0.0')}\n\n")
            
            description = schema.get('info', {}).get('description', '')
            if description:
                f.write(f"{description}\n\n")
            
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            # Table of Contents
            f.write("## Table of Contents\n\n")
            paths = schema.get('paths', {})
            for path in sorted(paths.keys()):
                anchor = path.replace('/', '-').replace('{', '').replace('}', '').strip('-')
                f.write(f"- [{path}](#{anchor})\n")
            f.write("\n---\n\n")
            
            # Endpoints
            f.write("## Endpoints\n\n")
            
            for path, methods in sorted(paths.items()):
                anchor = path.replace('/', '-').replace('{', '').replace('}', '').strip('-')
                f.write(f"### {path}\n\n")
                
                for method, details in methods.items():
                    if method.upper() not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']:
                        continue
                    
                    f.write(f"#### {method.upper()}\n\n")
                    
                    # Summary and description
                    summary = details.get('summary', '')
                    description = details.get('description', '')
                    
                    if summary:
                        f.write(f"**Summary:** {summary}\n\n")
                    if description:
                        f.write(f"{description}\n\n")
                    
                    # Tags
                    tags = details.get('tags', [])
                    if tags:
                        f.write(f"**Tags:** {', '.join(tags)}\n\n")
                    
                    # Security
                    security = details.get('security', [])
                    if security:
                        f.write("**Authentication Required:** Yes\n\n")
                    
                    # Parameters
                    parameters = details.get('parameters', [])
                    if parameters:
                        f.write("**Parameters:**\n\n")
                        f.write("| Name | In | Type | Required | Description |\n")
                        f.write("|------|-----|------|----------|-------------|\n")
                        for param in parameters:
                            name = param.get('name', '')
                            location = param.get('in', '')
                            param_type = param.get('schema', {}).get('type', 'string')
                            required = 'Yes' if param.get('required', False) else 'No'
                            desc = param.get('description', '')
                            f.write(f"| {name} | {location} | {param_type} | {required} | {desc} |\n")
                        f.write("\n")
                    
                    # Request Body
                    request_body = details.get('requestBody', {})
                    if request_body:
                        f.write("**Request Body:**\n\n")
                        content = request_body.get('content', {})
                        for content_type, content_details in content.items():
                            f.write(f"Content-Type: `{content_type}`\n\n")
                            schema_ref = content_details.get('schema', {}).get('$ref', '')
                            if schema_ref:
                                schema_name = schema_ref.split('/')[-1]
                                f.write(f"Schema: `{schema_name}`\n\n")
                        f.write("\n")
                    
                    # Responses
                    responses = details.get('responses', {})
                    if responses:
                        f.write("**Responses:**\n\n")
                        for status_code, response_details in responses.items():
                            desc = response_details.get('description', '')
                            f.write(f"- **{status_code}**: {desc}\n")
                        f.write("\n")
                    
                    f.write("---\n\n")
            
            # Schemas
            components = schema.get('components', {})
            schemas = components.get('schemas', {})
            
            if schemas:
                f.write("## Data Models\n\n")
                for schema_name, schema_details in sorted(schemas.items()):
                    f.write(f"### {schema_name}\n\n")
                    
                    description = schema_details.get('description', '')
                    if description:
                        f.write(f"{description}\n\n")
                    
                    properties = schema_details.get('properties', {})
                    required = schema_details.get('required', [])
                    
                    if properties:
                        f.write("**Properties:**\n\n")
                        f.write("| Name | Type | Required | Description |\n")
                        f.write("|------|------|----------|-------------|\n")
                        
                        for prop_name, prop_details in properties.items():
                            prop_type = prop_details.get('type', 'string')
                            is_required = 'Yes' if prop_name in required else 'No'
                            prop_desc = prop_details.get('description', '')
                            f.write(f"| {prop_name} | {prop_type} | {is_required} | {prop_desc} |\n")
                        f.write("\n")
                    
                    f.write("---\n\n")
        
        print(f"✅ Exported Markdown: {output_file}")
        return output_file
    
    def print_summary(self):
        """Print summary of API"""
        schema = self.get_openapi_schema()
        
        print("\n" + "="*70)
        print(f"📊 API Summary: {schema.get('info', {}).get('title', 'Unknown')}")
        print("="*70)
        
        paths = schema.get('paths', {})
        print(f"\n📍 Total Endpoints: {len(paths)}")
        
        # Count by method
        method_counts = {}
        for path, methods in paths.items():
            for method in methods.keys():
                if method.upper() in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                    method_counts[method.upper()] = method_counts.get(method.upper(), 0) + 1
        
        print("\n📈 Endpoints by Method:")
        for method, count in sorted(method_counts.items()):
            print(f"   {method:8} - {count}")
        
        # Count schemas
        schemas = schema.get('components', {}).get('schemas', {})
        print(f"\n📋 Data Models: {len(schemas)}")
        
        # Security schemes
        security_schemes = schema.get('components', {}).get('securitySchemes', {})
        if security_schemes:
            print(f"\n🔐 Authentication Methods:")
            for scheme_name in security_schemes.keys():
                print(f"   - {scheme_name}")
        
        print("\n" + "="*70)


def main():
    """Main function to export OpenAPI spec in multiple formats"""
    print("🚀 OpenAPI Specification Exporter")
    print("="*70)
    
    exporter = OpenAPIExporter()
    
    try:
        # Export all formats
        exporter.export_json()
        exporter.export_yaml()
        exporter.export_markdown()
        
        # Print summary
        exporter.print_summary()
        
        print("\n✨ Export Complete!")
        print("\n💡 Access the API documentation:")
        print("   - Swagger UI: http://localhost:5002/docs")
        print("   - ReDoc: http://localhost:5002/redoc")
        print("   - OpenAPI JSON: http://localhost:5002/openapi.json")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
