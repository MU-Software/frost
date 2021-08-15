# Add custom plugins here.
# If you want to make git not to track this file anymore,
# use `git update-index --skip-worktree app/admin/project_modelview.py`
import flask_admin.contrib.sqla as fadmin_sqla
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

target_flask_admin_modelview: list[fadmin_sqla.ModelView] = [
    fadmin_sqla.ModelView(user.User, db_module.db.session),
    fadmin_sqla.ModelView(user.EmailToken, db_module.db.session),
    fadmin_sqla.ModelView(jwt_module.RefreshToken, db_module.db.session),
]
