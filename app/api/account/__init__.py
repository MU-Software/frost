import app.api.account.signup as signup
import app.api.account.signin as signin
import app.api.account.signout as signout
import app.api.account.deactivate as deactivate
import app.api.account.refresh as refresh
import app.api.account.duplicate_check as duplicate_check
import app.api.account.email_action as email_action
import app.api.account.password_reset as password_reset
import app.api.account.password_change as password_change
import app.api.account.account_manage as account_manage
import app.api.account.profile_img_manage as profile_img_mgr

resource_route = {
    '/account': account_manage.AccountInformationChangeRoute,
    '/account/signup': signup.SignUpRoute,
    '/account/signin': signin.SignInRoute,
    '/account/signout': signout.SignOutRoute,
    '/account/refresh': refresh.AccessTokenIssueRoute,
    '/account/deactivate': deactivate.AccountDeactivationRoute,
    '/account/duplicate': duplicate_check.AccountDuplicateCheckRoute,
    '/account/email/<string:email_token>': email_action.EmailActionRoute,
    '/account/reset-password': password_reset.PasswordResetRoute,
    # Both routes for PasswordChangeRoute are needed.
    '/account/change-password/<string:email_token>': {
        'view_func': password_change.PasswordChangeRoute,
        'base_path': '/account/change-password/',
        'defaults': {'email_token': None},
    },
    '/account/profile-image': profile_img_mgr.ProfileImageRoute,
}
