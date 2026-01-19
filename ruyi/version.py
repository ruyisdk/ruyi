from typing import Final

from .i18n import d_

RUYI_SEMVER: Final = "0.46.0-alpha.20260119"
RUYI_USER_AGENT: Final = f"ruyi/{RUYI_SEMVER}"

COPYRIGHT_NOTICE: Final = d_(
    """\
Copyright (C) Institute of Software, Chinese Academy of Sciences (ISCAS).
All rights reserved.
License: Apache-2.0 <https://www.apache.org/licenses/LICENSE-2.0>
\
"""
)

MPL_REDIST_NOTICE: Final = d_(
    """\
This distribution of ruyi contains code licensed under the Mozilla Public
License 2.0 (https://mozilla.org/MPL/2.0/). You can get the respective
project's sources from the project's official website:

* certifi: https://github.com/certifi/python-certifi
\
"""
)
