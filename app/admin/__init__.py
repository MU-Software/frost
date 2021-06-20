import flask
import flask_admin as fadmin
import flask_admin.contrib.sqla as fadmin_sqla


def init_app(app: flask.Flask, add_model_to_view: bool = True):
    app_name = app.config.get('BACKEND_NAME', 'Backend Core')
    restapi_version = app.config.get('RESTAPI_VERSION')
    admin = fadmin.Admin(
                app,
                name=app_name,
                url=f'/api/{restapi_version}/admin',
                template_mode='bootstrap4')

    if add_model_to_view:
        import app.database as db_module
        import app.database.user as user
        import app.database.jwt as jwt_module

        admin.add_view(fadmin_sqla.ModelView(user.User, db_module.db.session))
        admin.add_view(fadmin_sqla.ModelView(user.EmailToken, db_module.db.session))
        admin.add_view(fadmin_sqla.ModelView(jwt_module.RefreshToken, db_module.db.session))

    import app.admin.token_revoke as token_revoke
    admin.add_view(token_revoke.Admin_TokenRevoke_View(name='Token Revoke', endpoint='token-revoke'))
