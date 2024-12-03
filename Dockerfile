FROM python:3.12
WORKDIR /app

# Install uv deps with pip.
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system -Ur pyproject.toml

# Copy the rest of the application code and install the project too.
COPY . .
RUN uv pip install --system -e .

# Run the FastAPI app using uvicorn on default port.
EXPOSE 80
CMD ["fastapi", "run", "deep_ice", "--port", "80"]
