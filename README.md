# Deep Ice

E-commerce platform selling ice cream

## Run

Run the service stack locally with Docker Compose:

```console
docker-compose up
```

Now go to http://localhost/docs to see the API docs. You can test it right in the browser.

> For APIs requiring authentication, make sure to click the "Authorize" button first and place inside the
> test [credentials](alembic/versions/ff861c79333d_preregistered_users.py) as following:
> - username: e-mail address
> - password: mocked password

To bring the stack down and cleanup images:

```console
docker-compose down --rmi all --volumes --remove-orphans
```

## Development

Ensure you have `uv` installed, then in the project dir run the following below to install and run the API server.

```console
uv sync
uv run fastapi dev deep_ice
```

The server requires PostgreSQL and Redis up and running.  
Ensure proper configuration by copying _[.env.template](.env.template)_ into _[.env](.env)_ first, then change the file
to suit your setup.

Don't forget to run migrations first:

```console
uv run alembic upgrade head
```

### Testing and linting

```console
uv run pytest
```

```console
uv run black deep_ice
uv run ruff format deep_ice

uv run pep8 deep_ice
uv run flake8 deep_ice
uv run ruff check deep_ice

uv run mypy deep_ice
```

Check this [ToDo](docs/TODO.md) items list for further improvements and known caveats.
