import imp
import os

from labonneboite.conf.common import settings_common

# Settings
# --------

# Default settings of the application are defined in `labonneboite/conf/common/settings_common.py`.
# A specific environment (staging, production...) can define its custom settings by:
# - creating a specific `settings` file, e.g. `lbb_staging_settings.py`
# - defining an environment variable containing the path to this specific `settings` file
#
# Specific and default settings will be merged, and values found in specific settings will take precedence.
# When no specific settings are found, `labonneboite/conf/local_settings.py` is used.

# The name of the environment variable that contains the path to the specific settings of an environment.
ENVIRONMENT_VARIABLE = 'LBB_SETTINGS'

# Dynamically import ENVIRONMENT_VARIABLE as the `settings` module, or import `local_settings.py`
# as the `settings` module if ENVIRONMENT_VARIABLE does not exist.
settings = imp.load_source(
    'settings',
    os.environ.get(ENVIRONMENT_VARIABLE, os.path.join(os.path.dirname(__file__), 'local_settings.py'))
)

# Iterate over each setting defined in the `settings_common` module and add them to the dynamically
# imported `settings` module if they don't already exist.
for setting in dir(settings_common):
    if not hasattr(settings, setting):
        setattr(settings, setting, getattr(settings_common, setting))
