import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import tempfile

from src.server import InterproServer, ServerSettings


@pytest.fixture
def server():
    settings = ServerSettings(
        interpro_path="mock_interproscan.sh",
        temp_dir=tempfile.gettempdir()
    )
    return InterproServer(settings)


@pytest.mark.asyncio
async def test_list_tools(server):
    tools = await server.server.list_tools()
    assert len(tools) > 0
    assert any(tool.name == "interpro_run" for tool in tools)


@pytest.mark.asyncio
async def test_run_interpro_missing_file(server):
    result = await server._run_interpro({
        "input_file": "/nonexistent/file.txt"
    })
    assert len(result) == 1
    assert result[0].text.startswith("Input file not found")


@pytest.mark.asyncio
async def test_run_interpro_success(server, tmp_path):
    # Create test FASTA input file
    input_file = tmp_path / "test_input.fasta"
    input_file.write_text(">test_protein\nMKVLLTGAPGVGKGTQA\n")
    
    # Mock subprocess execution
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"output data", b"")
        mock_exec.return_value = mock_process
        
        result = await server._run_interpro({
            "input_file": str(input_file)
        })
        
        assert len(result) == 1
        assert result[0].text == "output data"