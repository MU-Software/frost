import json
import pathlib
import traceback
import typing


def get_traceback_msg(err):
    return ''.join(traceback.format_exception(
                   etype=type(err),
                   value=err,
                   tb=err.__traceback__))


def json_to_envfiles(output_file: pathlib.Path):
    try:
        output_name: str = output_file.stem

        input_env_file_content: str = output_file.read_text()
        input_env_data: dict[str, typing.Union[str, dict[str, str]]] = json.loads(input_env_file_content)

        template_launch_json_file: typing.Optional[pathlib.Path] = pathlib.Path('template/launch.json')
        if not template_launch_json_file.exists():
            print('There\'s no launch.json template file for VS Code.\n'
                  'Place file on template/launch.json')
            template_launch_json_file = None
        else:
            template_launch_json_file_content: dict[str, object] = json.loads(template_launch_json_file.read_text())

        output_docker_file: pathlib.Path = pathlib.Path(output_name+'.env')
        output_bash_file: pathlib.Path = pathlib.Path(output_name+'.sh')
        output_ps_file: pathlib.Path = pathlib.Path(output_name+'.ps1')
        output_launch_json_file: pathlib.Path = pathlib.Path('../.vscode/launch.json')

        output_docker_file.unlink(missing_ok=True)
        output_bash_file.unlink(missing_ok=True)
        output_ps_file.unlink(missing_ok=True)

        if template_launch_json_file is not None:
            if not output_launch_json_file.parent.exists():
                output_launch_json_file.parent.mkdir()
            output_launch_json_file.unlink(missing_ok=True)

        with output_docker_file.open('w') as docker_fp,\
             output_bash_file.open('w') as bash_fp,\
             output_ps_file.open('w') as ps_fp:

            # Add Shebang
            bash_fp.write('#!/usr/bin/env bash\n')
            ps_fp.write('#!/usr/bin/env pwsh\n')

            for env_name, env_value in input_env_data.items():
                if env_name.startswith('__comment'):
                    comment_line = f'# {env_value}\n'
                    docker_fp.write(comment_line)
                    bash_fp.write(comment_line)
                    ps_fp.write(comment_line)
                    continue
                elif env_name.startswith('__line_break'):
                    docker_fp.write('\n')
                    bash_fp.write('\n')
                    ps_fp.write('\n')
                    continue

                docker_line = f'{env_name}='
                bash_line = f'export {env_name}='
                ps_line = f'$env:{env_name}='

                # We'll change all values to json-competable strings,
                # as bash variables don't have types and those are just string type,
                # and python's os.environ returns all values as string.
                if isinstance(env_value, dict):
                    bash_line += f'"{env_value["bash"]}"\n'
                    ps_line += f'"{env_value["powershell"]}"\n'
                    docker_line += f'"{env_value["vscode_launch"].format(**input_env_data)}"\n'
                else:
                    value_str = env_value
                    if not isinstance(value_str, str):
                        value_str = json.dumps(value_str)
                    value_str = json.dumps(value_str) + '\n'

                    bash_line += value_str
                    ps_line += value_str
                    docker_line += value_str

                docker_fp.write(docker_line)
                bash_fp.write(bash_line)
                ps_fp.write(ps_line)

        if template_launch_json_file is not None:
            with output_launch_json_file.open('w') as launch_json_fp:
                launch_json_env = dict()
                for k, v in input_env_data.items():
                    if k.startswith('__comment') or k.startswith('__line_break'):
                        continue
                    elif isinstance(v, dict):
                        launch_json_env[k] = v['vscode_launch'].format(**input_env_data)
                    else:
                        launch_json_env[k] = v

                template_launch_json_file_content['configurations'][0]['env'] = launch_json_env
                launch_json_fp.write(json.dumps(template_launch_json_file_content, indent=4))
    except Exception as e:
        print('Exception raised!')
        print(get_traceback_msg(e))


if __name__ == '__main__':
    import os
    import sys
    if len(sys.argv) <= 1:
        print('Need to specify target environment variables collection file(.json)')
        os._exit(1)

    target_file = pathlib.Path(sys.argv[1]).absolute()
    if not target_file.exists():
        # Ignore just now. We'll retry this after changing paths
        target_file = None

    os.chdir(pathlib.Path(__file__).parents[0])
    if target_file is None:
        target_file = pathlib.Path(sys.argv[1]).absolute()
        if not target_file.exists():
            raise FileNotFoundError()

    json_to_envfiles(target_file)
