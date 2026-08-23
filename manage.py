#!/usr/bin/env python
"""Django command-line utility for the Fabiano Polloni site."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "polloniflow.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
