import enum
import json
import pathlib
import traceback
import typing


class EnvOutputFileType(enum.StrEnum):
    docker_dotenv = "{}.env"
    flask_dotenv = "{}.flaskenv"
    shell = "{}.sh"
    powershell = "{}.ps1"
    vscode_launch = ".vscode/launch.json"


class EnvOutputFileDataType(typing.TypedDict):
    datatype: type
    appender: typing.Callable


ENV_DATA_TYPE_HANDLER: dict[EnvOutputFileType, EnvOutputFileDataType] = {
    EnvOutputFileType.docker_dotenv: EnvOutputFileDataType(datatype=str, appender=str.__add__),
    EnvOutputFileType.flask_dotenv: EnvOutputFileDataType(datatype=str, appender=str.__add__),
    EnvOutputFileType.shell: EnvOutputFileDataType(datatype=str, appender=str.__add__),
    EnvOutputFileType.powershell: EnvOutputFileDataType(datatype=str, appender=str.__add__),
    EnvOutputFileType.vscode_launch: EnvOutputFileDataType(datatype=dict, appender=lambda x, y: {**x, **y}),
}

ENV_DATA_HANDLER_COLLECTION: dict[EnvOutputFileType, dict[str, typing.Any]] = {
    EnvOutputFileType.docker_dotenv: {
        "__shebang": lambda k=None, v=None, d=None: "",
        "__comment": lambda k, v=None, d=None: f"# {k}\n",
        "__line_break": lambda k=None, v=None, d=None: "\n",
        "define_var": lambda k, v, d=None: (
            f"{k}=\"{v['env'].format(**(d or {}))}\"\n"
            if isinstance(v, dict)
            else f'{k}="{v}"\n'
            if isinstance(v, str)
            else f"{k}='{json.dumps(v)}'\n"
        ),
    },
    EnvOutputFileType.flask_dotenv: {
        "__shebang": lambda k=None, v=None, d=None: "",
        "__comment": lambda k, v=None, d=None: f"# {k}\n",
        "__line_break": lambda k=None, v=None, d=None: "\n",
        "define_var": lambda k, v, d=None: (
            f"{k}=\"{v['flaskenv'].format(**(d or {}))}\"\n"
            if isinstance(v, dict)
            else f'{k}="{v}"\n'
            if isinstance(v, str)
            else f"{k}='{json.dumps(v)}'\n"
        ),
    },
    EnvOutputFileType.shell: {
        "__shebang": lambda k=None, v=None, d=None: "#!/usr/bin/env bash\n",
        "__comment": lambda k, v=None, d=None: f"# {k}\n",
        "__line_break": lambda k=None, v=None, d=None: "\n",
        "define_var": lambda k, v, d=None: (
            f"{k}=\"{v['shell'].format(**(d or {}))}\"\n"
            if isinstance(v, dict)
            else f'{k}="{v}"\n'
            if isinstance(v, str)
            else f"{k}='{json.dumps(v)}'\n"
        ),
    },
    EnvOutputFileType.powershell: {
        "__shebang": lambda k=None, v=None, d=None: "#!/usr/bin/env pwsh\n",
        "__comment": lambda k, v=None, d=None: f"# {k}\n",
        "__line_break": lambda k=None, v=None, d=None: "\n",
        "define_var": lambda k, v, d=None: (
            f"{k}=\"{v['powershell'].format(**(d or {}))}\"\n"
            if isinstance(v, dict)
            else f'{k}="{v}"\n'
            if isinstance(v, str)
            else f"{k}='{json.dumps(v)}'\n"
        ),
    },
    EnvOutputFileType.vscode_launch: {
        "__shebang": lambda k=None, v=None, d=None: {},
        "__comment": lambda k=None, v=None, d=None: {},
        "__line_break": lambda k=None, v=None, d=None: {},
        "define_var": lambda k, v, d=None: (
            {k: v["vscode_launch"].format(**(d or {}))}
            if isinstance(v, dict)
            else {k: v.format(d or {})}
            if isinstance(v, str)
            else {k: json.dumps(v)}
        ),
    },
}

VSCODE_LAUNCH_DEFAULT_DATA = {
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Frost",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {},
            "args": ["run"],
            "jinja": True,
        }
    ],
}


def handler(input_file: pathlib.Path, base_filename: str | None = None, overwrite_all: bool = False):  # noqa: C901
    try:
        output_base_name = (
            input_file.stem if base_filename == "true" else "" if base_filename is None else base_filename
        )
        output_file_name = {e: e.value.format(output_base_name) for e in EnvOutputFileType}

        input_env_file_content: str = input_file.read_text()
        input_env_data: dict[str, typing.Union[str, dict[str, str]]] = json.loads(input_env_file_content)

        output_files: dict[EnvOutputFileType, pathlib.Path] = {e: pathlib.Path(n) for e, n in output_file_name.items()}

        # Backup vscode launch.json data if possible
        # We need these data as launch.json does not only contain env data,
        # but also contains another variables related to launch.
        if output_files[EnvOutputFileType.vscode_launch].exists():
            vscode_launch_data = json.loads(output_files[EnvOutputFileType.vscode_launch].read_text())
        else:
            vscode_launch_data = VSCODE_LAUNCH_DEFAULT_DATA

        for e in output_files:
            if not overwrite_all:
                if output_files[e].exists():
                    while True:
                        check_yn = input(
                            f'"{output_files[e].name}" file exists, ' "do you want to overwrite? [y/N] "
                        ).strip()

                        if check_yn.lower() in ("y", "yes"):
                            if e == EnvOutputFileType.vscode_launch:
                                vscode_launch_backup = output_files[e].with_suffix(".json.bak")
                                vscode_launch_backup.unlink(missing_ok=True)
                                pathlib.Path(output_files[e]).rename(vscode_launch_backup)
                            output_files[e].unlink(missing_ok=True)
                        elif check_yn.lower() in ("n", "no"):
                            output_files[e] = None
                        else:
                            continue
                        break
                else:
                    output_files[e].parent.mkdir(parents=True, exist_ok=True)

            elif overwrite_all:
                output_files[e].parent.mkdir(parents=True, exist_ok=True)
                output_files[e].unlink(missing_ok=True)

        # Generate environment files data
        output_files_data: dict[EnvOutputFileType, str | dict] = {
            e: ENV_DATA_TYPE_HANDLER[e]["datatype"]() for e in EnvOutputFileType
        }

        # Add shebang first
        for e in EnvOutputFileType:
            appender = ENV_DATA_TYPE_HANDLER[e]["appender"]
            output_files_data[e] = appender(output_files_data[e], ENV_DATA_HANDLER_COLLECTION[e]["__shebang"]())

        # Handle JSON file
        for env_name, env_value in input_env_data.items():
            for e in EnvOutputFileType:
                appender = ENV_DATA_TYPE_HANDLER[e]["appender"]

                if env_name.startswith("__comment"):
                    output_files_data[e] = appender(
                        output_files_data[e], ENV_DATA_HANDLER_COLLECTION[e]["__comment"](env_value)
                    )
                elif env_name.startswith("__line_break"):
                    output_files_data[e] = appender(
                        output_files_data[e], ENV_DATA_HANDLER_COLLECTION[e]["__line_break"](env_value)
                    )
                else:
                    # We'll change all values to json-competable strings,
                    # as bash variables don't have types and those are just string type,
                    # and python's os.environ returns all values as string.
                    output_files_data[e] = appender(
                        output_files_data[e],
                        ENV_DATA_HANDLER_COLLECTION[e]["define_var"](
                            env_name, env_value, output_files_data[EnvOutputFileType.vscode_launch]
                        ),
                    )

        for e, p in output_files.items():
            if not p:
                continue

            with p.open("w") as fp:

                if e == EnvOutputFileType.vscode_launch:
                    vscode_launch_data["configurations"][0]["env"] = output_files_data[e]
                    data = json.dumps(vscode_launch_data, indent=4)
                else:
                    data = str(output_files_data[e])

                fp.write(data)

    except Exception as exc:
        print("Exception raised!")
        print("".join(traceback.format_exception(exc)))


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Environment file builder for Frost")
    parser.add_argument(
        "json_path",
        help="JSON file that describes environment variables.",
    )
    parser.add_argument(
        "-n",
        "--name",
        help=(
            "Set name of output files. "
            "default name will be set if not specified, "
            'and filename will be used if argument is set to "true".'
        ),
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help='Overwrite files if exists, Defaults to "false".',
    )
    args = parser.parse_args()

    target_file = pathlib.Path(args.json_path).absolute()
    if not target_file.exists():
        # Ignore just now. We'll retry this after changing paths
        target_file = None

    os.chdir(pathlib.Path(__file__).parents[0])
    if target_file is None:
        target_file = pathlib.Path(args.json_path).absolute()
        if not target_file.exists():
            raise FileNotFoundError()

    os.chdir(pathlib.Path(__file__).parents[1])
    handler(input_file=target_file, base_filename=args.name, overwrite_all=args.overwrite)
