import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, ErrorContent
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class ServerSettings(BaseSettings):
    max_file_size: int = Field(default=100_000_000, description="Maximum input file size in bytes")
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory for processing")
    timeout: int = Field(default=1800, description="Command timeout in seconds")
    interpro_path: str = Field(default="interproscan.sh", description="Path to InterProScan executable")
    
    class Config:
        env_prefix = "BIO_MCP_"


class InterproServer:
    def __init__(self, settings: Optional[ServerSettings] = None):
        self.settings = settings or ServerSettings()
        self.server = Server("bio-mcp-interpro")
        self._setup_handlers()
        
    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="interpro_run",
                    description="Run InterProScan protein domain and family analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "input_file": {
                                "type": "string", 
                                "description": "Path to input file"
                            },
                            # Add tool-specific parameters here
                            "databases": {
                                "type": "string",
                                "description": "Comma-separated list of databases to search (optional)"
                            },
                            "output_format": {
                                "type": "string",
                                "description": "Output format (tsv, xml, json, gff3)",
                                "default": "tsv"
                            },
                        },
                        "required": ["input_file"]
                    }
                ),
                # Add more tool functions as needed
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent | ErrorContent]:
            if name == "interpro_run":
                return await self._run_interpro(arguments)
            else:
                return [ErrorContent(text=f"Unknown tool: {name}")]
    
    async def _run_interpro(self, arguments: dict) -> list[TextContent | ErrorContent]:
        try:
            # Validate input file
            input_path = Path(arguments["input_file"])
            if not input_path.exists():
                return [ErrorContent(text=f"Input file not found: {input_path}")]
            
            if input_path.stat().st_size > self.settings.max_file_size:
                return [ErrorContent(text=f"File too large. Maximum size: {self.settings.max_file_size} bytes")]
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory(dir=self.settings.temp_dir) as tmpdir:
                # Copy input file to temp directory
                temp_input = Path(tmpdir) / input_path.name
                temp_input.write_bytes(input_path.read_bytes())
                
                # Build command
                output_file = Path(tmpdir) / f"{temp_input.stem}_interpro"
                output_format = arguments.get("output_format", "tsv")
                
                cmd = [
                    self.settings.interpro_path,
                    "-i", str(temp_input),
                    "-o", str(output_file),
                    "-f", output_format,
                    "--disable-precalc"  # Disable precalculated matches for better error handling
                ]
                
                # Add databases if specified
                if "databases" in arguments and arguments["databases"]:
                    cmd.extend(["-appl", arguments["databases"]])
                
                # Add additional parameters for better performance/output
                cmd.extend([
                    "--goterms",  # Include GO term annotations
                    "--pathways"  # Include pathway annotations
                ])
                
                # Execute command
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.settings.timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    return [ErrorContent(text=f"Command timed out after {self.settings.timeout} seconds")]
                
                if process.returncode != 0:
                    return [ErrorContent(text=f"Command failed: {stderr.decode()}"
                )]
                
                # Process output
                output = stdout.decode()
                
                # Return results
                return [TextContent(text=output)]
                
        except Exception as e:
            logger.error(f"Error running interpro: {e}", exc_info=True)
            return [ErrorContent(text=f"Error: {str(e)}")]
    
    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)


async def main():
    logging.basicConfig(level=logging.INFO)
    server = InterproServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())