"""Explicit, audited business-data corrections outside ordinary workflow gates."""


def can_correct_business_data(user):
    from ..organization_privileges import has_full_platform_authority
    return bool(user and getattr(user, "enabled", False) and has_full_platform_authority(user))


def init_app(app):
    from .web import bp
    app.register_blueprint(bp)
