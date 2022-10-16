import typing

import app.api.helper_class as api_class

# Import and add project routes here.
# If you want to make git not to track this file anymore,
# use `git update-index --skip-worktree app/api/project_route.py`
project_resource_routes: dict[str, typing.Type[api_class.MethodViewMixin]] = dict()
