import app.api.helper_class as api_class


class CommonResponseCase(api_class.ResponseCaseCollector):
    ping_success = api_class.Response(
        description='PING works!',
        code=200, success=True,
        public_sub_code='ping.success',
        header=(('X-Recruit-Header', 'Oh, Hello! You\'ve found this!'), ),
        data={'ping': 'pong', })

    # Backend error related
    server_error = api_class.Response(
        description='Backend has some unknown issues now, try later.',
        code=500, success=False,
        private_sub_code='backend.uncaught_error',
        public_sub_code='backend.error')
    db_error = api_class.Response(
        description='Backend has some unknown issues now, try later (a).',
        # This must be shown as backend error, not a DB error
        # But also, this must be logged as a DB error
        code=500, success=False,
        private_sub_code='backend.db_error',
        public_sub_code='backend.error')

    # Common client-fault mistake related
    body_invalid = api_class.Response(
        description='This will be responsed when user-sent body data is not parsable.',
        code=400, success=False,
        public_sub_code='request.body.invalid')
    body_empty = api_class.Response(
        description='This will be responsed when user-sent body data is empty or not parsable.',
        code=400, success=False,
        public_sub_code='request.body.empty')
    body_required_omitted = api_class.Response(
        description='This will be responsed when some requirements are not given in user-sent body data.',
        code=400, success=False,
        public_sub_code='request.body.omitted',
        data={'lacks': ['']})
    body_bad_semantics = api_class.Response(
        description='This will be responsed when validation of user-sent body data is failed, '
                    'such as not a valid mail, etc.',
        code=422, success=False,
        public_sub_code='request.body.bad_semantics',
        data={'bad_semantics': [{
            'field': '',
            'reason': ''
        }, ]})

    header_invalid = api_class.Response(
        description='This will be responsed when header is not parsable.',
        code=400, success=False,
        public_sub_code='request.header.invalid')
    header_required_omitted = api_class.Response(
        description='This will be responsed when some requirements(like tokens) are not given in user-sent header.',
        code=400, success=False,
        public_sub_code='request.header.omitted',
        data={'lacks': ['']})
    path_required_omitted = api_class.Response(
        description='This will be responsed when some requirements are not given in request URL.',
        code=400, success=False,
        public_sub_code='request.path.omitted',
        data={'lacks': ['']})

    http_ok = api_class.Response(
        description='Normal plane HTTP OK response',
        code=200, success=True,
        public_sub_code='http.ok')
    http_mtd_forbidden = api_class.Response(
        description='Method you requested is not allowed on this route',
        code=405, success=False,
        public_sub_code='http.mtd_forbidden')
    http_not_found = api_class.Response(
        description='Route not found',
        code=404, success=False,
        public_sub_code='http.not_found')
    http_forbidden = api_class.Response(
        description='This request blocked because you don\'t have a permission to do this.',
        code=403, success=False,
        public_sub_code='http.forbidden')
    http_unsupported_content_type = api_class.Response(
        description='Requested response Content-Type is not accepted.',
        code=415, success=False,
        public_sub_code='http.content_type_unsupport')
