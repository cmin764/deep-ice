FROM python:3.12
WORKDIR /app

# Install deps with uv.
COPY pyproject.toml .
RUN pip install uv && uv sync

# Copy the rest of the application code.
COPY . .

EXPOSE 80

# Command to run the FastAPI app using uvicorn.
CMD ["uv", "run", "fastapi", "run", "deep_ice", "--port", "80"]
