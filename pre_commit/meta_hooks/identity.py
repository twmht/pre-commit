import sys

from pre_commit import output
from pre_commit.meta_hooks.helpers import make_meta_entry

HOOK_DICT = {
    'id': 'identity',
    'name': 'identity',
    'language': 'system',
    'verbose': True,
    'entry': make_meta_entry(__name__),
}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    for arg in argv:
        output.write_line(arg)


if __name__ == '__main__':
    exit(main())
