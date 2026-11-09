"""Optional macOS distribution support; importing this loads no frameworks."""

from .mode import distribution_name, is_appstore_build

__all__ = ['distribution_name', 'is_appstore_build']
