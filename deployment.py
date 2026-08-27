"""One public WSGI service for Render.

The customer app lives at `/`; the separate internal License Admin portal is
mounted at `/license-admin`.  Both applications use the same PostgreSQL URL,
but their session-cookie names remain different.
"""

from werkzeug.middleware.dispatcher import DispatcherMiddleware

from app import create_app as create_icu_predict_app
from license_admin.app import create_app as create_license_admin_app


icu_predict_app = create_icu_predict_app()
license_admin_app = create_license_admin_app()

application = DispatcherMiddleware(
    icu_predict_app,
    {"/license-admin": license_admin_app},
)
