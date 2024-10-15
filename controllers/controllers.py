# -*- coding: utf-8 -*-

from py4web import action, request, abort, redirect, URL
from yatl.helpers import A
from ..core.common import (
    db,
    session,
    T,
    cache,
    auth,
    logger,
    authenticated,
    unauthenticated,
    flash,
)


@action("index")
@action.uses("index.html", auth, T)
def index():
    message = T("Hello World from {name}").format(name='py4web')
    return dict(message=message)
