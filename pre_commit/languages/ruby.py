from __future__ import annotations

import contextlib
import functools
import importlib.resources
import os.path
import shutil
import tarfile
from collections.abc import Generator
from collections.abc import Sequence
from typing import IO

import pre_commit.constants as C
from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.envcontext import PatchesT
from pre_commit.envcontext import UNSET
from pre_commit.envcontext import Var
from pre_commit.prefix import Prefix
from pre_commit.util import CalledProcessError

ENVIRONMENT_DIR = 'rbenv'
health_check = lang_base.basic_health_check
run_hook = lang_base.basic_run_hook


def _resource_bytesio(filename: str) -> IO[bytes]:
    files = importlib.resources.files('pre_commit.resources')
    return files.joinpath(filename).open('rb')


@functools.lru_cache(maxsize=1)
def get_default_version() -> str:
    if all(lang_base.exe_exists(exe) for exe in ('ruby', 'gem')):
        return 'system'
    else:
        return C.DEFAULT


def get_env_patch(
        venv: str,
        language_version: str,
) -> PatchesT:
    patches: PatchesT = (
        ('GEM_HOME', os.path.join(venv, 'gems')),
        ('GEM_PATH', UNSET),
        ('BUNDLE_IGNORE_CONFIG', '1'),
    )
    if language_version == 'system':
        patches += (
            (
                'PATH', (
                    os.path.join(venv, 'gems', 'bin'), os.pathsep,
                    Var('PATH'),
                ),
            ),
        )
    else:  # pragma: win32 no cover
        patches += (
            ('RBENV_ROOT', venv),
            (
                'PATH', (
                    os.path.join(venv, 'gems', 'bin'), os.pathsep,
                    os.path.join(venv, 'shims'), os.pathsep,
                    os.path.join(venv, 'bin'), os.pathsep, Var('PATH'),
                ),
            ),
        )
    if language_version not in {'system', 'default'}:  # pragma: win32 no cover
        patches += (('RBENV_VERSION', language_version),)

    return patches


@contextlib.contextmanager
def in_env(prefix: Prefix, version: str) -> Generator[None, None, None]:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    with envcontext(get_env_patch(envdir, version)):
        yield


def _extract_resource(filename: str, dest: str) -> None:
    with _resource_bytesio(filename) as bio:
        with tarfile.open(fileobj=bio) as tf:
            tf.extractall(dest)


def _install_rbenv(
        prefix: Prefix,
        version: str,
) -> None:  # pragma: win32 no cover
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)

    _extract_resource('rbenv.tar.gz', prefix.path('.'))
    shutil.move(prefix.path('rbenv'), envdir)

    # Only install ruby-build if the version is specified
    if version != C.DEFAULT:
        plugins_dir = os.path.join(envdir, 'plugins')
        _extract_resource('ruby-download.tar.gz', plugins_dir)
        _extract_resource('ruby-build.tar.gz', plugins_dir)


def _install_ruby(
        prefix: Prefix,
        version: str,
) -> None:  # pragma: win32 no cover
    try:
        lang_base.setup_cmd(prefix, ('rbenv', 'download', version))
    except CalledProcessError:  # pragma: no cover (usually find with download)
        # Failed to download from mirror for some reason, build it instead
        lang_base.setup_cmd(prefix, ('rbenv', 'install', version))


def clone_environment(
        prefix: Prefix, version: str, additional_dependencies: Sequence[str],
) -> None:
    raise NotImplementedError


def install_environment(
        prefix: Prefix, version: str, additional_dependencies: Sequence[str],
) -> None:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)

    if version != 'system':  # pragma: win32 no cover
        _install_rbenv(prefix, version)
        with in_env(prefix, version):
            # Need to call this before installing so rbenv's directories
            # are set up
            lang_base.setup_cmd(prefix, ('rbenv', 'init', '-'))
            if version != C.DEFAULT:
                _install_ruby(prefix, version)
            # Need to call this after installing to set up the shims
            lang_base.setup_cmd(prefix, ('rbenv', 'rehash'))

    with in_env(prefix, version):
        lang_base.setup_cmd(
            prefix, ('gem', 'build', *prefix.star('.gemspec')),
        )
        lang_base.setup_cmd(
            prefix,
            (
                'gem', 'install',
                '--no-document', '--no-format-executable',
                '--no-user-install',
                '--install-dir', os.path.join(envdir, 'gems'),
                '--bindir', os.path.join(envdir, 'gems', 'bin'),
                *prefix.star('.gem'), *additional_dependencies,
            ),
        )
