"""Students related commands."""

import shutil

import click
import redis

from ..config import Config, pass_config
from ..lms.canvas import CanvasApi
from ..store import RedisStore
from .auth import update_canvas_token, update_redis_uri


@click.group(
    context_settings={"max_content_width": shutil.get_terminal_size().columns - 10}
)
def students() -> None:
    """Students management commands."""
    pass


@students.command(name="import")
@click.argument("canvas_course_id", type=str)
@click.argument("course_name", type=str)
@click.option("--force", "-f", type=bool, default=False, is_flag=True)
@pass_config
@click.pass_context
def import_students(
    ctx: click.Context,
    config: Config,
    canvas_course_id: str,
    course_name: str,
    force: bool,
) -> None:
    """Import students from Canvas' course with id = CANVAS_COURSE_ID into the system under the '#{COURSE_NAME}/students' key."""
    if not config.has_canvas_token():
        ctx.invoke(update_canvas_token)

    if not config.has_redis_uri():
        ctx.invoke(update_redis_uri)

    canvas = CanvasApi(token=config.canvas_token)
    students = canvas.get_students(canvas_course_id)
    if students is None:
        click.echo("[error]: Cannot retrive student list from Canvas.")
        ctx.exit(1)

    email_addresses = [s["user"]["email"] for s in students]
    click.echo(
        f"Found {len(email_addresses)} students in course id={canvas_course_id}."
    )

    with redis.from_url(config.redis_uri) as client:
        store = RedisStore(client)
        email_handles = sorted([item.split("@")[0] for item in email_addresses])

        click.echo("Importing students ...")
        try:
            store.add_course(course_name, email_handles, overwrite=force)
        except ValueError as e:
            click.echo(
                f"[error]: {e}. Use --force if you want to overwrite the existing data."
            )


@students.command(name="list-github-usernames")
@click.argument("course_name")
@pass_config
@click.pass_context
def list_github_usernames(
    ctx: click.Context,
    config: Config,
    course_name: str,
) -> None:
    """List GitHub usernames of all students in '#{COURSE_NAME}/students' key."""
    if not config.has_redis_uri():
        ctx.invoke(update_redis_uri)

    with redis.from_url(config.redis_uri) as client:
        store = RedisStore(client)
        mappings = store.get_github_username_mappings(course_name=course_name)
        for email_handle, github_username in mappings:
            print(f"{email_handle}:{github_username}")


@students.command(name="set-github-username")
@click.argument("email_handle")
@click.argument("github_username")
@click.option("--force", "-f", type=bool, default=False, is_flag=True)
@pass_config
@click.pass_context
def set_github_username(
    ctx: click.Context,
    config: Config,
    email_handle: str,
    github_username: str,
    force: bool,
) -> None:
    """Associate the student with EMAIL_HANDLE to GITHUB_USERNAME."""
    if not config.has_redis_uri():
        ctx.invoke(update_redis_uri)

    with redis.from_url(config.redis_uri) as client:
        store = RedisStore(client)
        try:
            store.set_student_github_username(
                email_handle, github_username, overwrite=force
            )
        except ValueError as e:
            click.echo(
                f"[error]: {e}. Use --force if you want to overwrite the existing data."
            )
