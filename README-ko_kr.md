# FROST 백엔드 템플릿
> ***F***lask based  
  ***R***est-API  
  ***O***riented  
  ***S***erver  
  ***T***emplate

> [여기](README.md)에 영어 버전의 README가 있어요!  
> [Click here](README.md) to read a README written in English.  

Frost는 Flask를 기반으로 아래와 같은 기능을 구현한 템플릿입니다.  

- JWT를 사용한 Access / Refresh 토큰 인증
- Flask-Admin 인증
- 강제 토큰 무효화 기능
- HTTP 요청 필드 검증
- YAML 타입의 OpenAPI 3.0 문서 생성
- ER 다이어그램 생성
- 메일 주소 인증 및 이메일을 통한 비밀번호 초기화 기능

## 사용법
1. `app/api` 디렉토리에 `demo` 디렉토리를 생성합니다. 그리고 `__init__.py` 파일을 생성해서 아래의 내용을 적어주세요.
```PYTHON
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database.jwt as jwt_module


class DemoResponseCase(api_class.ResponseCaseCollector):
    demo_ok = api_class.Response(
        description='성공적으로 응답했어요!',
        code=200, success=True,
        public_sub_code='demo.ok')

    demo_authed_ok = api_class.Response(
        description='성공적으로 JWT로 인증했어요!',
        code=200, success=True,
        public_sub_code='demo.authed_ok')

    demo_error = api_class.Response(
        description='저런... 에러가 발생했어요.',
        code=500, success=False,
        private_sub_code='demo.some_serious_error',
        public_sub_code='demo.error')


class DemoRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        # `AuthType.Bearer: False`는 Access 토큰 인증이 반드시 필요하지는 않은 경우에 사용됩니다.
        # 예를 들면, 특정 게시판의 글 목록은 인증을 하지 않으면 공개된 글만 보이고,
        # 인증을 하면 본인이 쓴 비밀글도 목록에 포함되어 보이는 경우가 있겠네요.
        # 만약에 이 값을 True로 설정하면 이 라우트는 유효한 Access 토큰을 반드시 요구해요.
        # 만약 `auth` 매개변수를 빈칸으로 두거나 전달하지 않는 경우,
        # 이 라우트는 어떠한 인증도 요구하지 않아요.
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            demo_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: This is a demo route, write description here!
        responses:
            - demo_ok
            - demo_authed_ok
            - demo_error
        '''
        if access_token:
            return DemoResponseCase.demo_authed_ok.create_response()

        if demo_id % 2:
            return DemoResponseCase.demo_error.create_response()

        return DemoResponseCase.demo_ok.create_response(data=req_header)
```
2. 아래 내용을 `app/api/project_route.py`에 추가해주세요.  
이 내용은 방금 작성한 라우트를 프로젝트에 등록할거에요.  
```PYTHON
import app.api.demo as route_demo  # noqa
project_resource_routes['/demo/<int:demo_id>'] = route_demo.DemoRoute
```
3. ***끝이에요!*** 방금 막 새로운 라우트를 만드셨어요!  
환경 변수를 설정해서 서버를 실행시킨 후 `curl {your_domain}/api/dev/demo/42`로 테스트 해보세요!
4. `flask create-openapi-doc` 명령어를 사용해서 OpenAPI 3.0 문서를 생성할 수 있어요.  
[아래의 "도구들" 문단을 참고해주세요.](#도구들)  
![이렇게 생성한 문서를 Swagger로 보면 이렇게 보여요!](./.github/readme/demo_swagger_result.png)

## 설치 & 실행
### 설치
#### Windows
```POWERSHELL
# Github의 `Use this template`로 새 프로젝트를 만든 후, 클론 받아주세요!
cd {내-프로젝트-디렉토리}
python -m venv ./
./Scripts/activate
python -m pip install -U -r "requirements-dev.txt"
```
이 내용을 복사 후 Powershell에 붙여넣기 해 주세요.  
`git for windows`과 `Python3.9 (혹은 그 이상)`이 필요해요.  

#### Debian 기반 Linux(Ubuntu/Linux Mint/etc.)
```BASH
# Github의 `Use this template`로 새 프로젝트를 만든 후, 클론 받아주세요!
cd {내-프로젝트-디렉토리}
python3.9 -m venv ./
source ./bin/activate
python3.9 -m pip install -U -r "requirements-dev.txt"
```
이 내용을 복사 후 Bash 셸에 붙여넣기 해 주세요.  
`git`과 `python3.9 (혹은 그 이상)`, 그리고 설치한 Python 버전에 맞는 `pip`과 `venv`가 필요해요.  

### 환경 변수들
실행 전, 서버가 필요한 변수들을 반드시 설정해주셔야 합니다. 몇몇 변수는 Flask 변수를 참조하니 [Flask document](https://flask.palletsprojects.com/en/master/config/)를 참고해주세요. 또한, `env_collection` 디렉토리에 `env_creator.py`란 도구가 있습니다. 이 도구는 작성하신 변수를 `.sh`(Bash 셸 스크립트), `.ps1`(Powershell 스크립트), and `.vscode/launch.json`(VS Code에서 `실행-디버깅 시작` 시에 사용하는 설정 파일) 형식으로 내보냅니다.  
이 도구의 도움을 받으시려면 JSON 형태로 작성하셔야 합니다. `env_collection` 디렉토리의 `dev.json`를 수정 후, 해당 도구의 매개변수로 전달해주세요.  
ex) `python3.9 ./env_collection/env_creator.py ./env_collection/dev.json`

키                    | 필수 | 설명
| :----:               |  :----:  | :----
`PROJECT_NAME`         | O | 이 변수는 자동적으로 생성된 API 문서나 서버에서 렌더링 된 몇몇 페이지에 보여집니다.
`BACKEND_NAME`         |   | HTTP 응답 헤더의 `Server` 필드에 보여집니다. `Backend Core`가 기본 값입니다.
`SERVER_NAME`          | O | Flask의 `SERVER_NAME`과 같습니다. 도메인 이름을 적어주세요.
`HTTPS_ENABLE`         |   | 만약 이 `HTTPS_ENABLE` 환경 변수가 `false`일 경우, 쿠키의 `secure` 옵션이 비활성화됩니다. 기본 값은 `true` 이며, 이 환경 변수의 값이 `false`일때만 비활성화됩니다.
`HOST`                 |   | `flask run` 시의 HOST 주소입니다.
`PORT`                 |   | 이 API 서버가 열려서 요청을 기다릴 포트 주소입니다. `PORT` 환경 변수는 Gunicorn에서도 적용됩니다, https://docs.gunicorn.org/en/stable/settings.html#bind 를 참고해주세요.
`SECRET_KEY`           | O | JWT와 몇몇 Flask의 내장 기능 등에 사용될 비밀키입니다.값이 설정되지 않는다면 무작위 문자열이 설정됩니다. Flask의 `SECRET_KEY`와 같습니다.
`LOG_FILE_ENABLE`      |   | 로그 파일을 생성합니다. 기본 값은 `false`입니다.
`LOG_FILE_NAME`        |   | 로그 파일의 이름을 지정합니다. 지정되지 않는 경우, `SERVER_NAME`.log 가 파일 이름으로 사용됩니다.
`LOG_FILE_LEVEL`       |   | 로그 레벨을 지정합니다. `CRITICAL`, `FATAL`, `ERROR`, `WARN` or `WARNING`, `INFO`, `DEBUG`, and `NOTSET` 중 하나로 설정해주세요. 이것은 Python의 logging 라이브러리 레벨과 동일합니다.
`DEVELOPMENT_KEY`      |   | 만약 `RESTAPI_VERSION` 환경 변수의 값이 `dev`이고 이 환경 변수가 설정된다면, 헤더에 `X-Development-Key`에 같은 키 값이 있는 요청만이 허용됩니다.
`LOCAL_DEV_CLIENT_PORT`|   | 만약 `RESTAPI_VERSION` 환경 변수의 값이 `dev`이고 이 환경 변수가 설정된다면, `http://localhost:{LOCAL_DEV_CLIENT_PORT}`의 CORS 헤더값이 설정됩니다. 반드시 정수로만 설정해주세요.
`SERVER_IS_ON_PROXY`   |   | 이 변수가 설정되면, Frost는 Flask가 리버스 프록시 뒤에 있는 상황에서 요청자의 올바른 IP 주소를 가져오기 위해 ***Werkzeug의 X-Forwarded-For Proxy Fix***를 활성화합니다.<br>**보안 문제가 발생할 수 있으므로, 반드시 리버스 프록시 뒤에 이 서버 애플리케이션이 존재할 때에만 활성화하세요!!!** 더 자세한 내용은 https://werkzeug.palletsprojects.com/en/latest/middleware/proxy_fix/ 나 https://github.com/pallets/werkzeug/blob/main/src/werkzeug/middleware/proxy_fix.py 를 참고해주세요.
`X_FOR_LEVEL`          |   | werkzeug.middleware.proxy_fix.ProxyFix의 매개변수입니다.
`X_PROTO_LEVEL`        |   | werkzeug.middleware.proxy_fix.ProxyFix의 매개변수입니다.
`X_HOST_LEVEL`         |   | werkzeug.middleware.proxy_fix.ProxyFix의 매개변수입니다.
`X_PORT_LEVEL`         |   | werkzeug.middleware.proxy_fix.ProxyFix의 매개변수입니다.
`X_PREFIX_LEVEL`       |   | werkzeug.middleware.proxy_fix.ProxyFix의 매개변수입니다.
`FLASK_APP`            | O | Flask의 `FLASK_APP`과 같습니다. 특정한 상황이 아니면 반드시 `app`으로 설정해주세요.
`FLASK_ENV`            | O | Flask의 `FLASK_ENV`과 같습니다.
`RESTAPI_VERSION`      | O | 이 환경 변수는 URL에 포함됩니다. 지정되지 않으면 `dev`으로 설정됩니다.<br>예) `dev`일때 `api/dev/account/login`가 되고, `v2`일때 `api/v2/posts/123456`가 됩니다.
`ACCOUNT_ROUTE_ENABLE` |   | 회원가입/로그인/이메일 관련 라우트 등 계정과 관련된 라우트가 활성화됩니다. 기본 값은 `true` 이며, 이 환경 변수의 값이 `false`일때만 비활성화됩니다.
`FILE_MANAGEMENT_ROUTE_ENABLE`            |   | 파일 업로드/파일 삭제 등 파일 관리와 관련된 라우트가 활성화됩니다.
`FILE_UPLOAD_ALLOW_EXTENSION`             |   | 파일 업로드 시 허용할 확장자를 설정할 수 있습니다. 기본 값은 웹에서 허용되는 이미지 포맷을 포함하고 있습니다.
`FILE_UPLOAD_IMAGE_WEB_FRIENDLY_CHECK`    |   | 파일 업로드 시 업로드 된 이미지가 웹 친화적인지 (=웹 브라우저에서 볼 수 있는 파일인지) 검사합니다. 
`DROP_ALL_REFRESH_TOKEN_ON_LOAD`          |   | 만약 `RESTAPI_VERSION` 환경 변수의 값이 `dev`일때, 서버가 다시 켜지거나 Werkzeug debugger에 의해 재시작될 시 모든 Refresh 토큰을 무효화합니다. 기본 값은 `true` 이며, 이 환경 변수의 값이 `false`일때만 비활성화됩니다.
`DB_URL`               | O | 연결하실 DB 주소를 적어주세요, `RESTAPI_VERSION` 환경 변수가 `dev`인 경우 `sqlite:///:memory:`(SQLite DB가 메모리에 생성됩니다)로 설정됩니다.
`REDIS_HOST`           | O | Redis의 주소를 적어주세요.
`REDIS_PORT`           | O | Redis의 포트를 적어주세요. 반드시 정수로 적어주셔야 합니다.
`REDIS_DB`             | O | 사용하실 Redis의 DB 번호를 적어주세요. 반드시 정수로 적어주셔야 합니다.
`REDIS_PASSWORD`       |   | Redis의 비밀번호를 적어주세요. 비밀번호가 없다면 이 변수를 설정하지 마세요.
`MAIL_ENABLE`          |   | 이 환경 변수는 `가입 및 이메일 주소 확인 메일`과 `비밀번호 초기화 메일` 등과 같은 이메일 기능을 활성화합니다. 기본적으로 활성화되어 있으며, `false`로 값이 설정될때만 비활성화됩니다.
`MAIL_PROVIDER`        | O | 메일 서비스 제공자를 설정합니다. `AMAZON`이나 `GOOGLE`이 값으로 들어올 수 있습니다. 만약 `MAIL_ENABLE`값이 `false`일 경우 필요하지 않으며, 기본 값은 `AMAZON`입니다.
`MAIL_DOMAIN`          |   | 메일의 도메인을 적어주세요.
`SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION` |   | This blocks user from signing in when user didn't do email verification, but this will be not applied on first user as first account's `email_verified` will be set to `true` when signing up. Enabled by default. This will be disabled when this field or `MAIL_ENABLE` field is set to `false`.
`GOOGLE_CLIENT_ID`     |   | 메일 서비스의 제공자로 Google을 사용하실 때 설정해주세요.
`GOOGLE_CLIENT_SECRET` |   | 메일 서비스의 제공자로 Google을 사용하실 때 설정해주세요.
`GOOGLE_REFRESH_TOKEN` |   | 메일 서비스의 제공자로 Google을 사용하실 때 설정해주세요.


### 실행
Windows에선  ```python -m flask run```로, Linux에선 ```python3.9 -m flask run``` 로 실행해주세요.  


## 도구들
Frost는 편리한 도구 몇개를 내장하고 있어요. 이 도구들을 실행할 시 flask의 `app context`를 초기화해야 하기 때문에, 서버의 환경 변수가 반드시 설정되어야 하는 점 유의해주세요!  

사용법:
> `flask create-openapi-doc`  
  `flask draw-db-erd`  
  `flask drop-db`

  - create-openapi-doc  
YAML 타입의 OpenAPI 3.0 규격 문서를 생성합니다. [Swagger UI](https://swagger.io/tools/swagger-ui/)로 멋있게 렌더링 된 문서를 보실 수 있어요.  
  - draw-db-erd  
ER 다이어그램을 dot 파일 형태로 생성합니다. dot 파일을 PNG/JPG와 같은 이미지 파일로 렌더링 하시려면, Linux에서 `dot -Tpng input.dot > output.png`를 실행해주세요. (dot이 설치되어 있어야 합니다.)
  - drop-db  
DB의 모든 테이블을 드랍합니다. 최악의 사고를 방지하기 위해, 환경 변수의 `RESTAPI_VERSION`가 `dev`일때만 동작합니다.  


## 코딩 규칙
  - 줄의 최대 글자 길이를 `120`자 이상으로 해 주세요.
