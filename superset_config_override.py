"""
# Superset specific config
Overrides para la configuración de Superset
"""
import os

# Disable CSP completely to allow images from any source
TALISMAN_ENABLED = False

# Alternative configuration if you want to keep some security
# but allow images from any source
TALISMAN_CONFIG = {
    'force_https': False,
    'content_security_policy': None
}

# Allow iframe embedding
FEATURE_FLAGS = {
    'ALLOW_DASHBOARD_DOMAIN_SHARDING': True,
    'EMBEDDED_SUPERSET': True,
    'ENABLE_TEMPLATE_PROCESSING': True,
}

# Enable markdown to render HTML
ENABLE_UNSAFE_MARKDOWN_HTML = True
HTML_SANITIZATION = False

# Log that this config file is being loaded
print("Loading custom Superset configuration from superset_config_override.py")