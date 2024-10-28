FROM python:3.12
WORKDIR /app

# Install uv deps with pip.
RUN pip install uv
COPY pyproject.toml .
RUN uv export --no-dev >requirements.txt && pip install -Ur requirements.txt

# Copy the rest of the application code.
COPY . .

EXPOSE 80

# Command to run the FastAPI app using uvicorn.
CMD ["fastapi", "run", "deep_ice", "--port", "80"]
