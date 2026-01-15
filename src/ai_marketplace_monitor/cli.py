"""Console script for ai-marketplace-monitor."""

import io
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated, List, Optional

import rich
import typer
from rich.console import Console
from rich.logging import RichHandler

from . import __version__
from .utils import CacheType, amm_home, cache, counter, hilight

app = typer.Typer()


def version_callback(value: bool) -> None:
    """Callback function for the --version option.

    Parameters:
        - value: The value provided for the --version option.

    Raises:
        - typer.Exit: Raises an Exit exception if the --version option is provided,
        printing the Awesome CLI version and exiting the program.
    """
    if value:
        typer.echo(f"AI Marketplace Monitor, version {__version__}")
        raise typer.Exit()


@app.command()
def main(
    config_files: Annotated[
        List[Path] | None,
        typer.Option(
            "-r",
            "--config",
            help="Path to one or more configuration files in TOML format. Configs are loaded in order: ~/.ai-marketplace-monitor/config.toml, ./config.toml (if present), then CLI-specified files.",
        ),
    ] = None,
    headless: Annotated[
        Optional[bool],
        typer.Option("--headless", help="If set to true, will not show the browser window."),
    ] = False,
    clear_cache: Annotated[
        Optional[str],
        typer.Option(
            "--clear-cache",
            help=(
                "Remove all or selected category of cached items and treat all queries as new. "
                f"""Allowed cache types are {", ".join([x.value for x in CacheType])} and all """
            ),
        ),
    ] = None,
    verbose: Annotated[
        Optional[bool],
        typer.Option("--verbose", "-v", help="If set to true, will show debug messages."),
    ] = False,
    items: Annotated[
        List[str] | None,
        typer.Option(
            "--check",
            help="""Check one or more cached items by their id or URL,
                and list why the item was accepted or denied.""",
        ),
    ] = None,
    for_item: Annotated[
        Optional[str],
        typer.Option(
            "--for",
            help="Item to check for URLs specified --check. You will be prmopted for each URL if unspecified and there are multiple items to search.",
        ),
    ] = None,
    once: Annotated[
        Optional[bool],
        typer.Option("--once", help="Run searches once without scheduling recurring searches."),
    ] = False,
    log_file: Annotated[
        Optional[str],
        typer.Option(
            "--log-file",
            help="Custom log file path. Supports {timestamp} placeholder (e.g., 'logs/run-{timestamp}.log'). Defaults to ~/.ai-marketplace-monitor/ai-marketplace-monitor.log",
        ),
    ] = None,
    version: Annotated[
        Optional[bool], typer.Option("--version", callback=version_callback, is_eager=True)
    ] = None,
) -> None:
    """Console script for AI Marketplace Monitor."""
    # Reconfigure stdout/stderr to use UTF-8 encoding on Windows to handle emoji characters
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    # Load config early to get default values for log_file and run_once
    from .config import Config
    default_config = amm_home / "config.toml"
    local_config = Path.cwd() / "config.toml"
    # Config files are merged in order (later values override earlier)
    # Priority: user home config -> local config -> CLI-specified configs
    config_file_paths = (
        ([default_config] if default_config.exists() else [])
        + ([local_config] if local_config.exists() else [])
        + [x.expanduser().resolve() for x in config_files or []]
    )

    # Try to load config to get monitor settings, but don't fail if config is invalid
    # (we'll fail later during actual monitor initialization if needed)
    monitor_config = None
    if config_file_paths:
        try:
            temp_logger = logging.getLogger("config_loader")
            temp_config = Config(config_file_paths, temp_logger)
            monitor_config = temp_config.monitor
        except Exception:
            pass  # Will be caught later during monitor initialization

    # Use config values as defaults if CLI arguments not provided
    if log_file is None and monitor_config and monitor_config.log_file:
        log_file = monitor_config.log_file

    if not once and monitor_config and monitor_config.run_once:
        once = monitor_config.run_once

    # Create a console without legacy Windows rendering to avoid emoji encoding issues
    console = Console(legacy_windows=False, force_terminal=True)

    # Determine log file path
    if log_file:
        # Support {timestamp} placeholder in custom log file path
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(log_file.format(timestamp=timestamp))
        # Create parent directories if they don't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Use regular FileHandler for custom log files (no rotation)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
    else:
        # Use default rotating log file
        log_path = amm_home / "ai-marketplace-monitor.log"
        file_handler = RotatingFileHandler(
            log_path,
            encoding="utf-8",
            maxBytes=1024 * 1024,
            backupCount=5,
        )

    logging.basicConfig(
        level="DEBUG",
        # format="%(name)s %(message)s",
        format="%(message)s",
        handlers=[
            RichHandler(
                console=console,
                markup=True,
                rich_tracebacks=True,
                show_path=False if verbose is None else verbose,
                level="DEBUG" if verbose else "INFO",
                show_level=True,
                show_time=True,
                omit_repeated_times=False,
                enable_link_path=False,
            ),
            file_handler,
        ],
    )

    # remove logging from other packages.
    for logger_name in (
        "asyncio",
        "openai._base_client",
        "httpcore.connection",
        "httpcore.http11",
        "httpx",
    ):
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    logger = logging.getLogger("monitor")
    logger.info(
        f"""{hilight("[VERSION]", "info")} AI Marketplace Monitor, version {hilight(__version__, "name")}"""
    )

    if clear_cache is not None:
        if clear_cache == "all":
            cache.clear()
        elif clear_cache in [x.value for x in CacheType]:
            cache.evict(tag=clear_cache)
        else:
            logger.error(
                f"""{hilight("[Clear Cache]", "fail")} {clear_cache} is not a valid cache type. Allowed cache types are {", ".join([x.value for x in CacheType])} and all """
            )
            sys.exit(1)
        logger.info(f"""{hilight("[Clear Cache]", "succ")} Cache cleared.""")
        sys.exit(0)

    # make --version a bit faster by lazy loading of MarketplaceMonitor
    from .monitor import MarketplaceMonitor

    if items is not None:
        try:
            monitor = MarketplaceMonitor(config_files, headless, logger)
            monitor.check_items(items, for_item)
        except Exception as e:
            logger.error(f"""{hilight("[Check]", "fail")} {e}""")
            raise
        finally:
            monitor.stop_monitor()

        sys.exit(0)

    try:
        monitor = MarketplaceMonitor(config_files, headless, logger)
        if once:
            monitor.run_once()
        else:
            monitor.start_monitor()
    except KeyboardInterrupt:
        rich.print("Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"""{hilight("[Monitor]", "fail")} {e}""")
        raise
        sys.exit(1)
    finally:
        monitor.stop_monitor()
        rich.print(counter)


if __name__ == "__main__":
    app()  # pragma: no cover
