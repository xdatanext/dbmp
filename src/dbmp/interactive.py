# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

import argparse
import io
import os
import re
import shlex
import subprocess
import sys

import prompt_toolkit as pt
# from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name

print = pt.print_formatted_text
HISTORY = os.path.expanduser("~/.dbmp_history")
# session = pt.PromptSession(history=pt.history.FileHistory(HISTORY))
session = pt.PromptSession()
bindings = pt.key_binding.KeyBindings()
VI = pt.enums.EditingMode.VI
EMACS = pt.enums.EditingMode.EMACS

VPROMPT = r"""prefix: my-test
count: 1
size(GB): 1
replica: 3
template: None
object: False
placement_mode: hybrid
placement_policy: None
read_iops_max: 0
write_iops_max: 0
total_iops_max: 0
read_bandwidth_max: 0
write_bandwidth_max: 0
total_bandwidth_max: 0
login: False
mount: False"""

VPROMPT_RE = re.compile(r"""prefix:\s*(?P<prefix>[\w\-]+)
count:\s*(?P<count>\d+)
size\(GB\):\s*(?P<size>\d+)
replica:\s*(?P<replica>\d+)
template:\s*(?P<template>\w+)
object:\s*(?P<object>([Tt]rue|[Ff]alse))
placement_mode:\s*(?P<placement_mode>[\w\-]+)
placement_policy:\s*(?P<placement_policy>[\w\-]+)
read_iops_max:\s*(?P<read_iops_max>\d+)
write_iops_max:\s*(?P<write_iops_max>\d+)
total_iops_max:\s*(?P<total_iops_max>\d+)
read_bandwidth_max:\s*(?P<read_bandwidth_max>\d+)
write_bandwidth_max:\s*(?P<write_bandwidth_max>\d+)
total_bandwidth_max:\s*(?P<total_bandwidth_max>\d+)
login:\s*(?P<login>[Tt]rue|[Ff]alse)
mount:\s*(?P<mount>[Tt]rue|[Ff]alse)""")

PPPROMPT = r"""name: my-placement-policy
max(';' separates): all-flash;hybrid
min(';' separates): hybrid
descr: This is my new policy"""

PPPROMPT_RE = re.compile(r"""name:\s*(?P<name>[\w\-]+)
max\(';' separates\):\s*(?P<max>[\w\-;]+)
min\(';' separates\):\s*(?P<min>[\w\-;]+)
descr:\s*(?P<descr>.*)""")

MPPROMPT = r"""name: my-media-policy
priority: 1
descr: This is my new policy"""

MPPROMPT_RE = re.compile(r"""name:\s*(?P<name>[\w\-]+)
priority:\s*(?P<priority>\d+)
descr:\s*(?P<descr>.*)""")


# @bindings.add('c-k')
# def _(event):
#     " Toggle between Emacs and Vi mode. "
#     app = event.app

#     if app.editing_mode == VI:
#         app.editing_mode = EMACS
#     else:
#         app.editing_mode = VI

QUIT = {"q", "quit", "exit", ":q"}
DRY_RUN = False


def app_exit(code):
    print("Thanks for playing!")
    sys.exit(code)


def convert_opts(opts):
    for k, v in opts.items():
        if v == "None" or v == "none" or v.strip() == "":
            v = None
            opts[k] = v
            continue
        if v in ("True", "true"):
            opts[k] = True
            continue
        if v in ("False", "false"):
            opts[k] = False
            continue
        if ';' in v:
            opts[k] = v.split(';')
            continue
        try:
            opts[k] = int(v)
        except ValueError:
            opts[k] = v


@bindings.add('s-down')
def _(event):
    "Accept input during multiline mode"
    get_by_name("accept-line")(event)


# @bindings.add('q q')
# def _(event):
#     "Quit app at any time"
#     app_exit(0)


# def bottom_toolbar():
#     " Display the current input mode. "
#     text = 'Vi' if get_app().editing_mode == VI else 'Emacs'
#     return [
#         ('class:toolbar', ' [s-down] %s ' % text)
#     ]

def print_header(tp, color):
    print(pt.HTML(
        "<u><b>Please fill out the following <{}>{}</{}> attributes"
        "</b></u>".format(color, tp, color)))
    print(pt.HTML(
        "<u><i>Press <yellow>S-down</yellow> (Shift-&lt;down-arrow&gt;) "
        "when done</i></u>"))
    print()


def print_dict(d):
    for k, v in sorted(d.items()):
        print('{0:<25} {1:<15} '.format(k, v))


def interactive(python):
    """ Main entrypoint into dbmp interactive mode """
    args = ''
    if not os.path.exists(HISTORY):
        io.open(HISTORY, 'w+').close()
    while True:
        pt.shortcuts.clear()
        pt.shortcuts.set_title("Datera Bare-Metal Provisioner")
        print("Welcome to the DBMP Interactive Session")
        print("Would you like to provison, or clean up?")
        out = session.prompt("choices: [(p)rovision, (c)lean]> ",
                             default="provision").strip().lower()
        print()
        if out in {"p", "provision"}:
            args = provision()
        if out in {"c", "clean"}:
            args = clean()
        if out in QUIT:
            if args:
                print(args)
            app_exit(0)
        dbmp_exe(python, args)


def provision():
    pt.shortcuts.clear()
    print("Please type everything you'd like to provision (<space> separated)")
    print(pt.HTML(
        "Options are: ["
        "<red>volumes</red> "
        "<green>placement_policies</green> "
        "<blue>media_policies</blue>]"))
    print(pt.HTML(
        "You can use abbreviations like ["
        "<red>v</red> "
        "<green>pp</green> "
        "<blue>mp</blue>]"))
    print("If you would like to provision multiple different types of the ")
    print("same resource, enter it multiple times")
    print("Press ENTER when finished")
    out = session.prompt("> ", default="v pp mp")
    volumes = []
    pp = []
    mp = []
    for choice in out.strip().split():
        print(choice)
        if choice.lower() in {"volumes", "volume", "v", "vol", "vols"}:
            volumes.append(volume())
        if choice.lower() in {"placement_policies", "placement_policy", "pp",
                              "placement", "pl", "placement-policies",
                              "placement-policy"}:
            pp.append(placement_policy())
        if choice.lower() in {"media_policies", "media_policy", "mp",
                              "media", "md", "media-policies",
                              "media-policy"}:
            mp.append(media_policy())
        if choice.lower() in QUIT:
            app_exit(0)
    return create_dbmp_command(volumes=volumes,
                               placement_policies=pp,
                               media_policies=mp)


def clean():
    pt.shortcuts.clear()
    print("Please fill in everything you'd like to clean")
    session.prompt()
    create_dbmp_command(clean={})


def _dprompt(tp, color, prompt, prompt_re):
    dprompt = prompt
    while True:
        pt.shortcuts.clear()
        print_header(tp, color)
        og_data = session.prompt("",
                                 default=dprompt,
                                 multiline=True,
                                 key_bindings=bindings)
        data = "\n".join(filter(bool, og_data.splitlines())).strip()
        match = prompt_re.match(data)
        if not match:
            print(pt.HTML("<red><b>Invalid data</b></red>"))
            dprompt = og_data
            session.prompt("Press Enter To Retry", multiline=False)
            continue
        opts = match.groupdict()
        convert_opts(opts)
        print()
        print("-----------------------------")
        print("Recieved the following config")
        print("-----------------------------")
        print_dict(opts)
        print()
        if pt.shortcuts.confirm("Is this correct?"):
            return opts
        dprompt = og_data


def volume():
    return _dprompt("VOLUME", "red", VPROMPT, VPROMPT_RE)


def placement_policy():
    return _dprompt("PLACEMENT_POLICY", "green", PPPROMPT, PPPROMPT_RE)


def media_policy():
    return _dprompt("MEDIA_POLICY", "blue", MPPROMPT, MPPROMPT_RE)


def create_dbmp_command(**kwargs):
    args = []
    for vol in kwargs.get("volumes", []):
        mount = vol.pop('mount', '')
        if mount:
            args.append('--mount')
        login = vol.pop('login', '')
        if login:
            args.append('--login')
        arg = ",".join(["=".join((k, str(v))) for k, v in vol.items()])
        args.append("--volume='{}'".format(arg))
    for pp in kwargs.get("placement_policies", []):
        mx = pp.get('max', [])
        pp['max'] = ";".join(mx) if type(mx) == list else mx
        mn = pp.get('min', [])
        pp['min'] = ";".join(mn) if type(mn) == list else mn
        arg = ",".join(["=".join((k, str(v))) for k, v in pp.items()])
        args.append("--placement-policy='{}'".format(arg))
    for mp in kwargs.get("media_policies", []):
        arg = ",".join(["=".join((k, str(v))) for k, v in mp.items()])
        args.append("--media-policy='{}'".format(arg))
    return args


def dbmp_exe(python, args):
    if DRY_RUN:
        print("{} {}".format(python, "\n".join(args)))
        sys.exit(0)
    print(subprocess.check_output([python, shlex.split(args)]))


def main(args):
    interactive(args.python)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("python", help="Python executable to use")
    parser.add_argument("--dry-run", action='store_true',
                        help="Don't run any commands, just print them")
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    main(args)