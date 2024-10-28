# Deep Ice

###### E-commerce platform selling ice cream

Check out this [use-case](docs/use-case.md) to see how to quickly order some ice cream.

## Run

Run the service stack locally with Docker Compose:

```console
docker-compose up  # --build
```

Now go to http://localhost/docs to see the API docs. You can test it right in the browser.

> For APIs requiring authentication, make sure to click the "Authorize" button first and place inside any of the test [credentials](alembic/versions/ff861c79333d_preregistered_users.py) as following:
> - username: _\<e-mail address\>_ (`cmin764@gmail.com`)
> - password: _\<mocked password\>_ (`cosmin-password`)

To bring the stack down and cleanup resources:

```console
docker-compose down --rmi all --volumes --remove-orphans
```

## Development

Ensure you have Python 3 and `uv` installed, then in the project dir run the following below to install dependencies and run the API server.

```console
uv sync
uv run fastapi dev deep_ice  # app
```

The server requires PostgreSQL and Redis up and running.  
Ensure proper configuration by copying _[.env.template](.env.template)_ into _[.env](.env)_ first, then change the file
to suit your setup.

Don't forget to run migrations first and a task queue worker to deal with deferred tasks:

```console
uv run alembic upgrade head  # alembic
uv run arq deep_ice.TaskQueue --watch deep_ice  # worker
```

### Testing and linting

```console
uv run pytest
```

```console
uv run isort deep_ice
uv run black deep_ice
uv run ruff format deep_ice

uv run pep8 deep_ice
uv run flake8 deep_ice
uv run ruff check deep_ice

uv run mypy deep_ice
```

Check this [ToDo](docs/TODO.md) list for further improvements and known caveats.
