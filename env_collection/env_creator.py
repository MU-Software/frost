import json
import pathlib
import traceback
import typing


def get_traceback_msg(err):
    return ''.join(traceback.format_exception(
                   etype=type(err),
                   value=err,
                   tb=err.__traceback__))


def json_to_envfiles(json_path: str, output_name: str):
    try:
        input_env_file_content: str = pathlib.Path(json_path).read_text()
        input_env: dict[str, typing.Union[str, dict[str, str]]] = json.loads(input_env_file_content)

        template_launch_json_file: pathlib.Path = pathlib.Path('template/launch.json')
        template_launch_json_file_content: dict[str, object] = json.loads(template_launch_json_file.read_text())

        output_docker_file: pathlib.Path = pathlib.Path(output_name+'.env')
        output_bash_file: pathlib.Path = pathlib.Path(output_name+'.sh')
        output_ps_file: pathlib.Path = pathlib.Path(output_name+'.ps1')
        output_launch_json_file: pathlib.Path = pathlib.Path('../.vscode/launch.json')

        if output_docker_file.exists():
            output_docker_file.unlink()

        if output_bash_file.exists():
            output_bash_file.unlink()

        if output_ps_file.exists():
            output_ps_file.unlink()

        if not output_launch_json_file.parent.exists():
            output_launch_json_file.parent.mkdir()
        if output_launch_json_file.exists():
            output_launch_json_file.unlink()

        with output_docker_file.open('w') as docker_fp,\
             output_bash_file.open('w') as bash_fp,\
             output_ps_file.open('w') as ps_fp:

            # Add Shebang
            bash_fp.write('#!/usr/bin/env bash\n')
            ps_fp.write('#!/usr/bin/env pwsh\n')

            for env_name, env_value in input_env.items():
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

                if type(env_value) == dict:
                    bash_line += f'"{env_value["bash"]}"\n'
                    ps_line += f'"{env_value["powershell"]}"\n'
                    docker_line += f'"{env_value["vscode_launch"].format(**input_env)}"\n'
                else:
                    bash_line += f'"{env_value}"\n'
                    ps_line += f'"{env_value}"\n'
                    docker_line += f'"{env_value}"\n'

                docker_fp.write(docker_line)
                bash_fp.write(bash_line)
                ps_fp.write(ps_line)

        with output_launch_json_file.open('w') as launch_json_fp:
            launch_json_env = dict()
            for k, v in input_env.items():
                if k.startswith('__comment') or k.startswith('__line_break'):
                    continue
                elif type(v) == str:
                    launch_json_env[k] = v
                else:
                    launch_json_env[k] = v['vscode_launch'].format(**input_env)

            template_launch_json_file_content['configurations'][0]['env'] = launch_json_env
            launch_json_fp.write(json.dumps(template_launch_json_file_content, indent=4))
    except Exception as e:
        print('Exception raised!')
        print(get_traceback_msg(e))


if __name__ == '__main__':
    import os
    import sys
    os.chdir(pathlib.Path(__file__).parents[0])
    if len(sys.argv) > 1:
        target_file: str = sys.argv[1]
    else:
        print('Need to specify target environment variables collection file(.json)')
        os._exit(1)

    json_to_envfiles(target_file, target_file.replace('.json', ''))
