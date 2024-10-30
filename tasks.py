from invoke import task


PACKAGES = "deep_ice alembic"


# Helper function to run commands with 'uv run' and provide CI-friendly logging.
def uv_run(ctx, command, task_name):
    """Run a command with 'uv run' and log results for CI visibility."""
    try:
        ctx.run(f"uv run {command}", pty=True)
    except Exception as exc:
        print(f"❌ {task_name} failed: {exc}")
        raise
    else:
        print(f"✔ {task_name} completed successfully.")


@task
def sync_deps(ctx):
    """Synchronize dependencies using `uv sync`."""
    try:
        print("Synchronizing dependencies...")
        ctx.run("uv sync")
        print("✔ Dependencies synchronized successfully.")
    except Exception as exc:
        print(f"❌ Dependency synchronization failed: {exc}")
        raise


@task(pre=[sync_deps])
def test(ctx):
    """Run tests with pytest and ensure they pass."""
    uv_run(ctx, "pytest", "Testing")


@task(pre=[sync_deps])
def format_check(ctx, format_code: bool = False):
    """Check code formatting with black and ruff.

    This has the ability to run checks for CI/CD automated purposes, but switching the
    `format_code` on will also fix the code in place.
    """
    action = "checking"
    try:
        if not format_code:
            # Both ruff `check` and `format` commands can do checks and as well
            #  auto-formatting, just that each one covers different purposes.
            ruff_commands = ["ruff check --diff", "ruff format --check --diff"]
        else:
            ruff_commands = ["ruff check --fix", "ruff format"]
            action = "formatting"
            # isort checking/formatting never agrees with black's, so use it for
            #  formatting only.
            uv_run(ctx, f"isort {PACKAGES}", f"isort {action}")
        uv_run(
            ctx,
            f"black {'--check' if not format_code else ''} {PACKAGES}",
            f"black {action}",
        )
        for ruff_command in ruff_commands:
            task_name = " ".join(ruff_command.split()[0:2]) + f" {action}"
            uv_run(ctx, f"{ruff_command} {PACKAGES}", task_name)
    except Exception as exc:
        print(f"❌ Code {action} failed. Please fix the issues and try again: {exc}")
        raise


@task(pre=[sync_deps])
def lint(ctx):
    """Lint code using flake8 and ruff, failing if any issues are found."""
    uv_run(ctx, f"flake8 {PACKAGES}", "flake8 linting")
    # Ruff's checking here takes into account additional linting issues compared to the
    #  `--diff` option in the check-only formatting task.
    uv_run(ctx, f"ruff check --no-fix {PACKAGES}", "ruff linting")


@task(pre=[sync_deps])
def type_check(ctx):
    """Run type checks with mypy."""
    uv_run(ctx, f"mypy {PACKAGES}", "Type checking")


@task(pre=[test, format_check, lint, type_check])
def check_all(ctx):
    """Run all non-intrusive tasks.

    Testing, format checking, linting and type checking, with fast-fail behavior.
    """
    print("All checks complete!")
