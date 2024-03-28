from __future__ import annotations

import contextlib
import os
import shlex
from collections.abc import Generator
from collections.abc import Sequence

from pre_commit import lang_base
from pre_commit.envcontext import envcontext
from pre_commit.envcontext import PatchesT
from pre_commit.envcontext import Var
from pre_commit.prefix import Prefix

ENVIRONMENT_DIR = 'perl_env'
get_default_version = lang_base.basic_get_default_version
health_check = lang_base.basic_health_check
run_hook = lang_base.basic_run_hook


def get_env_patch(venv: str) -> PatchesT:
    return (
        ('PATH', (os.path.join(venv, 'bin'), os.pathsep, Var('PATH'))),
        ('PERL5LIB', os.path.join(venv, 'lib', 'perl5')),
        ('PERL_MB_OPT', f'--install_base {shlex.quote(venv)}'),
        (
            'PERL_MM_OPT', (
                f'INSTALL_BASE={shlex.quote(venv)} '
                f'INSTALLSITEMAN1DIR=none INSTALLSITEMAN3DIR=none'
            ),
        ),
    )


@contextlib.contextmanager
def in_env(prefix: Prefix, version: str) -> Generator[None, None, None]:
    envdir = lang_base.environment_dir(prefix, ENVIRONMENT_DIR, version)
    with envcontext(get_env_patch(envdir)):
        yield


def clone_environment(
        prefix: Prefix, version: str, additional_dependencies: Sequence[str],
) -> None:
    raise NotImplementedError


def install_environment(
        prefix: Prefix, version: str, additional_dependencies: Sequence[str],
) -> None:
    lang_base.assert_version_default('perl', version)

    with in_env(prefix, version):
        lang_base.setup_cmd(
            prefix, ('cpan', '-T', '.', *additional_dependencies),
        )
