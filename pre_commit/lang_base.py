from __future__ import annotations

import contextlib
import os
import random
import re
import shlex
from collections.abc import Generator
from collections.abc import Sequence
from typing import Any
from typing import ContextManager
from typing import NoReturn
from typing import Protocol

import pre_commit.constants as C
from pre_commit import parse_shebang
from pre_commit import xargs
from pre_commit.prefix import Prefix
from pre_commit.util import cmd_output_b

FIXED_RANDOM_SEED = 1542676187

SHIMS_RE = re.compile(r'[/\\]shims[/\\]')


class Language(Protocol):
    # Use `None` for no installation / environment
    @property
    def ENVIRONMENT_DIR(self) -> str | None: ...
    # return a value to replace `'default` for `language_version`
    def get_default_version(self) -> str: ...
    # return whether the environment is healthy (or should be rebuilt)
    def health_check(self, prefix: Prefix, version: str) -> str | None: ...

    # install a repository for the given language and language_version
    def install_environment(
            self,
            prefix: Prefix,
            version: str,
            additional_dependencies: Sequence[str],
    ) -> None:
        ...

    # install a repository for the given language and language_version
    def clone_environment(
            self,
            prefix: Prefix,
            version: str,
            additional_dependencies: Sequence[str],
    ) -> None:
        ...

    # modify the environment for hook execution
    def in_env(self, prefix: Prefix, version: str) -> ContextManager[None]: ...

    # execute a hook and return the exit code and output
    def run_hook(
            self,
            prefix: Prefix,
            entry: str,
            args: Sequence[str],
            file_args: Sequence[str],
            *,
            is_local: bool,
            require_serial: bool,
            color: bool,
    ) -> tuple[int, bytes]:
        ...


def exe_exists(exe: str) -> bool:
    found = parse_shebang.find_executable(exe)
    if found is None:  # exe exists
        return False

    homedir = os.path.expanduser('~')
    try:
        common: str | None = os.path.commonpath((found, homedir))
    except ValueError:  # on windows, different drives raises ValueError
        common = None

    return (
        # it is not in a /shims/ directory
        not SHIMS_RE.search(found) and
        (
            # the homedir is / (docker, service user, etc.)
            os.path.dirname(homedir) == homedir or
            # the exe is not contained in the home directory
            common != homedir
        )
    )


def setup_cmd(prefix: Prefix, cmd: tuple[str, ...], **kwargs: Any) -> None:
    cmd_output_b(*cmd, cwd=prefix.prefix_dir, **kwargs)


def environment_dir(prefix: Prefix, d: str, language_version: str) -> str:
    return prefix.path(f'{d}-{language_version}')


def assert_version_default(binary: str, version: str) -> None:
    if version != C.DEFAULT:
        raise AssertionError(
            f'for now, pre-commit requires system-installed {binary} -- '
            f'you selected `language_version: {version}`',
        )


def assert_no_additional_deps(
        lang: str,
        additional_deps: Sequence[str],
) -> None:
    if additional_deps:
        raise AssertionError(
            f'for now, pre-commit does not support '
            f'additional_dependencies for {lang} -- '
            f'you selected `additional_dependencies: {additional_deps}`',
        )


def basic_get_default_version() -> str:
    return C.DEFAULT


def basic_health_check(prefix: Prefix, language_version: str) -> str | None:
    return None


def no_install(
        prefix: Prefix,
        version: str,
        additional_dependencies: Sequence[str],
) -> NoReturn:
    raise AssertionError('This language is not installable')


@contextlib.contextmanager
def no_env(prefix: Prefix, version: str) -> Generator[None, None, None]:
    yield


def target_concurrency() -> int:
    if 'PRE_COMMIT_NO_CONCURRENCY' in os.environ:
        return 1
    else:
        # Travis appears to have a bunch of CPUs, but we can't use them all.
        if 'TRAVIS' in os.environ:
            return 2
        else:
            return xargs.cpu_count()


def _shuffled(seq: Sequence[str]) -> list[str]:
    """Deterministically shuffle"""
    fixed_random = random.Random()
    fixed_random.seed(FIXED_RANDOM_SEED, version=1)

    seq = list(seq)
    fixed_random.shuffle(seq)
    return seq


def run_xargs(
        cmd: tuple[str, ...],
        file_args: Sequence[str],
        *,
        require_serial: bool,
        color: bool,
) -> tuple[int, bytes]:
    if require_serial:
        jobs = 1
    else:
        # Shuffle the files so that they more evenly fill out the xargs
        # partitions, but do it deterministically in case a hook cares about
        # ordering.
        file_args = _shuffled(file_args)
        jobs = target_concurrency()
    return xargs.xargs(cmd, file_args, target_concurrency=jobs, color=color)


def hook_cmd(entry: str, args: Sequence[str]) -> tuple[str, ...]:
    return (*shlex.split(entry), *args)


def basic_run_hook(
        prefix: Prefix,
        entry: str,
        args: Sequence[str],
        file_args: Sequence[str],
        *,
        is_local: bool,
        require_serial: bool,
        color: bool,
) -> tuple[int, bytes]:
    return run_xargs(
        hook_cmd(entry, args),
        file_args,
        require_serial=require_serial,
        color=color,
    )
