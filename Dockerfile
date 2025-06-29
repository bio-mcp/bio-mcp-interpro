# Use biocontainers base image with InterProScan
FROM biocontainers/interproscan:v5.63-95.0_cv1 AS tool

# Build MCP server layer
FROM python:3.11-slim

# Copy InterProScan from biocontainer
COPY --from=tool /opt/interproscan/ /opt/interproscan/
# Copy Java runtime if needed
COPY --from=tool /usr/lib/jvm/ /usr/lib/jvm/
# Copy required libraries
COPY --from=tool /usr/local/lib/ /usr/local/lib/

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .

# Copy server code
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    mkdir -p /tmp/mcp-work && \
    chown -R mcp:mcp /app /tmp/mcp-work

USER mcp

# Set environment variables
ENV BIO_MCP_TEMP_DIR=/tmp/mcp-work
ENV BIO_MCP_INTERPRO_PATH=/opt/interproscan/interproscan.sh
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH=$PATH:/opt/interproscan

# Run the server with queue support by default
CMD ["python", "-m", "src.server_with_queue"]