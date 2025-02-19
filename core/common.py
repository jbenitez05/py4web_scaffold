# -*- coding: utf-8 -*-

import os
import sys
from py4web import Session, Cache, Translator, Flash, DAL, Field, action
from py4web.server_adapters.logging_utils import make_logger
from py4web.utils.mailer import Mailer
from py4web.utils.auth import Auth
from py4web.utils.downloader import downloader
from pydal.tools.tags import Tags
from pydal.tools.scheduler import Scheduler
from py4web.utils.factories import ActionFactory
from . import settings
from pydal.validators import CRYPT

# #######################################################
# implement custom loggers form settings.LOGGERS
# #######################################################
logger = make_logger("py4web:" + settings.APP_NAME, settings.LOGGERS)

# #######################################################
# connect to db
# #######################################################

db = DAL(
    settings.DB_URI,
    folder=settings.DB_FOLDER,
    pool_size=settings.DB_POOL_SIZE,
    migrate=True,
    fake_migrate=False,
    check_reserved=['all']
)

# #######################################################
# define global objects that may or may not be used by the actions
# #######################################################
cache = Cache(size=1000)
T = Translator(settings.T_FOLDER)

# #######################################################
# pick the session type that suits you best
# #######################################################
if settings.SESSION_TYPE == "cookies":
    session = Session(secret=settings.SESSION_SECRET_KEY)

elif settings.SESSION_TYPE == "redis":
    import redis

    host, port = settings.REDIS_SERVER.split(":")
    # for more options: https://github.com/andymccurdy/redis-py/blob/master/redis/client.py
    conn = redis.Redis(host=host, port=int(port))
    conn.set = (
        lambda k, v, e, cs=conn.set, ct=conn.ttl: cs(k, v, ct(k))
        if ct(k) >= 0
        else cs(k, v, e)
    )
    session = Session(secret=settings.SESSION_SECRET_KEY, storage=conn)

elif settings.SESSION_TYPE == "memcache":
    import memcache, time

    conn = memcache.Client(settings.MEMCACHE_CLIENTS, debug=0)
    session = Session(secret=settings.SESSION_SECRET_KEY, storage=conn)

elif settings.SESSION_TYPE == "database":
    from py4web.utils.dbstore import DBStore

    session = Session(secret=settings.SESSION_SECRET_KEY, storage=DBStore(db))

# #######################################################
# Instantiate the object and actions that handle auth
# #######################################################
auth = Auth(session, db, define_tables=False)
auth.use_username = False
auth.param.registration_requires_confirmation = settings.VERIFY_EMAIL
auth.param.registration_requires_approval = settings.REQUIRES_APPROVAL
auth.param.login_after_registration = settings.LOGIN_AFTER_REGISTRATION
auth.param.allowed_actions = settings.ALLOWED_ACTIONS
auth.param.login_expiration_time = 3600
auth.param.password_complexity = {"entropy": settings.PASSWORD_ENTROPY}
auth.param.block_previous_password_num = 3
auth.param.default_login_enabled = settings.DEFAULT_LOGIN_ENABLED
auth.define_tables()
auth.fix_actions()

flash = auth.flash

# #######################################################
# Configure email sender for auth
# #######################################################
if settings.SMTP_SERVER:
    auth.sender = Mailer(
        server=settings.SMTP_SERVER,
        sender=settings.SMTP_SENDER,
        login=settings.SMTP_LOGIN,
        tls=True,
        ssl=False,
    )

# #######################################################
# Create a table to tag users as group members
# #######################################################
if auth.db:
    groups = Tags(db.auth_user, "groups")

# #######################################################
# Enable optional auth plugin
# #######################################################
if settings.USE_PAM:
    from py4web.utils.auth_plugins.pam_plugin import PamPlugin

    auth.register_plugin(PamPlugin())

if settings.USE_LDAP:
    from py4web.utils.auth_plugins.ldap_plugin import LDAPPlugin

    auth.register_plugin(LDAPPlugin(db=db, groups=groups, **settings.LDAP_SETTINGS))

if settings.OAUTH2GOOGLE_CLIENT_ID:
    from py4web.utils.auth_plugins.oauth2google import OAuth2Google  # TESTED

    auth.register_plugin(
        OAuth2Google(
            client_id=settings.OAUTH2GOOGLE_CLIENT_ID,
            client_secret=settings.OAUTH2GOOGLE_CLIENT_SECRET,
            callback_url="auth/plugin/oauth2google/callback",
        )
    )

if settings.OAUTH2GOOGLE_SCOPED_CREDENTIALS_FILE:
    from py4web.utils.auth_plugins.oauth2google_scoped import (
        OAuth2GoogleScoped,
    )  # TESTED

    auth.register_plugin(
        OAuth2GoogleScoped(
            secrets_file=settings.OAUTH2GOOGLE_SCOPED_CREDENTIALS_FILE,
            scopes=[],  # Put here any scopes you want in addition to login
            db=db,  # Needed to store credentials in auth_credentials
        )
    )

if settings.OAUTH2GITHUB_CLIENT_ID:
    from py4web.utils.auth_plugins.oauth2github import OAuth2Github  # TESTED

    auth.register_plugin(
        OAuth2Github(
            client_id=settings.OAUTH2GITHUB_CLIENT_ID,
            client_secret=settings.OAUTH2GITHUB_CLIENT_SECRET,
            callback_url="auth/plugin/oauth2github/callback",
        )
    )

if settings.OAUTH2FACEBOOK_CLIENT_ID:
    from py4web.utils.auth_plugins.oauth2facebook import OAuth2Facebook  # UNTESTED

    auth.register_plugin(
        OAuth2Facebook(
            client_id=settings.OAUTH2FACEBOOK_CLIENT_ID,
            client_secret=settings.OAUTH2FACEBOOK_CLIENT_SECRET,
            callback_url="auth/plugin/oauth2facebook/callback",
        )
    )

if settings.OAUTH2OKTA_CLIENT_ID:
    from py4web.utils.auth_plugins.oauth2okta import OAuth2Okta  # TESTED

    auth.register_plugin(
        OAuth2Okta(
            client_id=settings.OAUTH2OKTA_CLIENT_ID,
            client_secret=settings.OAUTH2OKTA_CLIENT_SECRET,
            callback_url="auth/plugin/oauth2okta/callback",
        )
    )

# #######################################################
# Define a convenience action to allow users to download
# files uploaded and reference by Field(type='upload')
# #######################################################
if settings.UPLOAD_FOLDER:

    @action("download/<filename>")
    @action.uses(db)
    def download(filename):
        return downloader(db, settings.UPLOAD_FOLDER, filename)

    # To take advantage of this in Form(s)
    # for every field of type upload you MUST specify:
    #
    # field.upload_path = settings.UPLOAD_FOLDER
    # field.download_url = lambda filename: URL('download/%s' % filename)

# #######################################################
# Define and optionally start the scheduler
# #######################################################
if settings.USE_SCHEDULER:
    scheduler = Scheduler(
        db, logger=logger, max_concurrent_runs=settings.SCHEDULER_MAX_CONCURRENT_RUNS
    )
    scheduler.start()
else:
    scheduler = None

# #######################################################
# Enable authentication
# #######################################################
auth.enable(uses=(session, T, db), env=dict(T=T))

# #######################################################
# Define convenience decorators
# They can be used instead of @action and @action.uses
# They should NEVER BE MIXED with @action and @action.uses
# #######################################################
unauthenticated = ActionFactory(db, session, T, flash, auth)
authenticated = ActionFactory(db, session, T, flash, auth.user)

# Default user credentials
if db(db.auth_user).count() == 0:
    db.auth_user.insert(
        first_name = settings.DEFAULT_USER_FIRST_NAME,
        last_name = settings.DEFAULT_USER_LAST_NAME,
        email = settings.DEFAULT_USER_EMAIL,
        password = CRYPT()(settings.DEFAULT_USER_PASSWORD)[0]
    )
    db.commit()