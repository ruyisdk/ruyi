<!-- markdownlint-capture -->
<!-- markdownlint-disable MD033 MD041 -->
<div align="center">
<img alt="RuyiSDK Logo" src="resources/ruyi-logo-256.png" height="128" />
<h3>Ruyi</h3>
<p>The package manager for <a href="https://ruyisdk.org/en/">RuyiSDK</a>.</p>
<p><a href="https://ruyisdk.org/en/">Official website</a> |
<a href="https://ruyisdk.cn">Developer community</a> |
<a href="https://github.com/ruyisdk">Open-source</a></p>
</div>
<!-- markdownlint-restore -->

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ruyisdk/ruyi/ci.yml)
![GitHub License](https://img.shields.io/github/license/ruyisdk/ruyi)
![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![GitHub Tag](https://img.shields.io/github/v/tag/ruyisdk/ruyi?label=latest%20tag)
![PyPI - Version](https://img.shields.io/pypi/v/ruyi)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/ruyisdk/ruyi/total?label=all%20github%20dl)
![PyPI - Downloads](https://img.shields.io/pypi/dm/ruyi?label=pypi%20dl)

🌍 English | [简体中文](./README.zh.md)

## ⬇️ Installation

`ruyi` is available in two forms: the PyPI package or the one-file binary
distribution. Performance of various `ruyi` operations will be better with the
PyPI installation, but the one-file distribution is a bit easier to set up
because one doesn't have to first configure a Python environment. Either way,
the feature set should be the same.

Detailed installation instructions are also available [at our documentation site](https://ruyisdk.org/en/docs/Package-Manager/installation).

### ✅ Recommended: Install from PyPI

This is the recommended way to install `ruyi` on your machine. In any Python
virtual environment, simply type:

```sh
pip install ruyi
```

Or the equivalent with any other Python package manager you prefer. After the
installation completes, the `ruyi` command will then show up in the Python
virtual environment's `bin` directory; if you have already activated the
environment, you may now start using `ruyi`.

### Alternative: Use the one-file distribution

You can get pre-built binaries of `ruyi` from [GitHub Releases][ghr] or
[the RuyiSDK mirror][mirror-iscas] for easier testing.
Rename the downloaded file to `ruyi`, make it executable,
put inside your `$PATH` and you're ready to go.

[ghr]: https://github.com/ruyisdk/ruyi/releases
[mirror-iscas]: https://mirror.iscas.ac.cn/ruyisdk/ruyi/tags/

### Platform compatibility notes

Because `ruyi` is written in platform-independent Python, you may be able to
install `ruyi` on any system with a Python package manager. However, you may
not be able to install binary packages from the official RuyiSDK Software Repository
if you are on a system not listed on
[RuyiSDK's platform support documentation][ruyisdk-plat-support-en]
([中文][ruyisdk-plat-support-zh]), due to the packages being only built for the
officially supported systems. You may be able to obtain community-provided
support from [the RuyiSDK developer community][ruyisdk-community] in such cases.

[ruyisdk-plat-support-en]: https://ruyisdk.org/en/docs/Other/platform-support/
[ruyisdk-plat-support-zh]: https://ruyisdk.org/docs/Other/platform-support/
[ruyisdk-community]: https://ruyisdk.cn/

## 🖥️ Usage

You can browse our documentation at [the dedicated RuyiSDK docs site][docs-en]
([中文][docs-zh]). In case you need any assistance, feel
free to search and post on [our community forum][ruyisdk-community].

[docs-en]: https://ruyisdk.org/en/docs/intro/
[docs-zh]: https://ruyisdk.org/docs/intro/

## ⚙️ Configuration

Various aspects of `ruyi` can be configured with files or environment variables.

### Config search path

`ruyi` respects `$XDG_CONFIG_HOME` and `$XDG_CONFIG_DIRS` settings, and will
look up its config accordingly. If these are not explicitly set though, as in
typical use cases, the default config directory is most likely `~/.config/ruyi`.

GNU/Linux distribution packagers and system administrators will find that the
directories `/usr/share/ruyi` and `/usr/local/share/ruyi` are searched for the
config file on such systems.

### Config file

Currently `ruyi` will look for an optional `config.toml` in its XDG config
directory. The file, if present, looks like this, with all values being default:

```toml
[packages]
# Consider pre-release versions when matching packages in repositories.
prereleases = false

[repo]
# Path to the local RuyiSDK metadata repository. Must be absolute or the setting
# will be ignored.
# If unset or empty, $XDG_CACHE_HOME/ruyi/packages-index is used.
local = ""
# Remote location of RuyiSDK metadata repository.
# If unset or empty, this default value is used.
remote = "https://github.com/ruyisdk/packages-index.git"
# Name of the branch to use.
# If unset or empty, this default value is used.
branch = "main"

[telemetry]
# Whether to collect telemetry information for improving RuyiSDK's developer
# experience, and whether to send the data periodically to RuyiSDK team.
# Valid values are `local`, `off` and `on` -- see the documentation for
# details.
#
# If unset or empty, this default value is used: data will be collected and
# stored locally; nothing will be uploaded automatically.
mode = "local"
# The time the user's consent is given to telemetry data uploading. If the
# system time is later than the time given here, telemetry consent banner will
# not be displayed any more each time `ruyi` is executed. The exact consent
# time is also useful should the telemetry policy get updated in the future.
#
# To hide the consent banner, set it to the current local time, for example:
#
#     upload_consent = 2024-12-02T15:61:00+08:00
#
# The timestamp is intentionally invalid for you to notice and modify to your
# need.
upload_consent = ""
# Override the telemetry server URL of the RuyiSDK package manager scope.
# If unset, the repo-configured default is used; if set to empty, telemetry
# uploading is disabled.
#pm_telemetry_url = ""
```

### Environment variables

Currently the following environment variables are supported by `ruyi`:

* `RUYI_TELEMETRY_OPTOUT` -- boolean, whether to opt-out of telemetry.
* `RUYI_VENV` -- string, explicitly specifies the Ruyi virtual environment to use.

For boolean variables, the values `1`, `true`, `x`, `y` or `yes` (all case-insensitive)
are all treated as "true".

## 📞 Telemetry

The Ruyi package manager collects usage data in order to help us improve your
experience. It is collected by the RuyiSDK team and shared with the community.
You can opt-out of telemetry by setting the `RUYI_TELEMETRY_OPTOUT`
environment variable to any of `1`, `true`, `x`, `y` or `yes` using your
favorite shell. Opting out of telemetry is equivalent to the `off` mode
described below.

There are 3 telemetry modes available:

* `local`: data will be collected but not uploaded without user action.
* `off`: data will not be collected nor uploaded.
* `on`: data will be collected and periodically uploaded.

By default the `local` mode is active from `ruyi` 0.42.0 (inclusive) on, which
means every `ruyi` invocation will record some non-sensitive information locally
alongside various other states of `ruyi`, but collected data will not be
uploaded automatically unless you explicitly request so (for example by
switching to the `on` mode, or by executing `ruyi telemetry upload`).

In case the `on` mode is active, collected data will be periodically uploaded
to servers managed by the RuyiSDK team in the People's Republic of China, in a
weekly fashion. The upload will happen on a random weekday which is determined
by the installation's anonymous ID alone.

You can change the telemetry mode by editing `ruyi`'s config file, or simply
disable telemetry altogether by setting the `RUYI_TELEMETRY_OPTOUT` environment
variable to any of the values accepted as truthy.

We collect the following information with `ruyi`:

* the running machine's basic information:
    * architecture and OS
    * if architecture is RISC-V:
        * ISA capabilities
        * model name of the board
        * number of logical CPUs
    * OS release ID (roughly equals the distribution type)
    * type and version of libc
    * type of the shell (bash, fish, zsh, etc.)
* the version of `ruyi` on data upload time
* invocation patterns of various `ruyi` subcommands:
    * without exposing any parameters
    * invocation time is recorded with a granularity of 1 minute

You can see [our Privacy Policy][privacy-policy-en] ([中文][privacy-policy-zh])
on the RuyiSDK website.

[privacy-policy-en]: https://ruyisdk.org/en/docs/legal/privacyPolicy/
[privacy-policy-zh]: https://ruyisdk.org/docs/legal/privacyPolicy/

## 🙋 Contributing

We welcome contributions to RuyiSDK! Please see our [contribution guidelines](./CONTRIBUTING.md)
([中文](./CONTRIBUTING.zh.md)) for details on how to get started.

## ⚖️ License

Copyright &copy; Institute of Software, Chinese Academy of Sciences (ISCAS).
All rights reserved.

`ruyi` is licensed under the [Apache 2.0 license](./LICENSE-Apache.txt).

The one-file binary distribution of `ruyi` contains code licensed under the
[Mozilla Public License 2.0](https://mozilla.org/MPL/2.0/).
You can get the respective project's sources from the project's official
website:

* [`certifi`](https://github.com/certifi/python-certifi): used unmodified

All trademarks referenced herein are property of their respective holders.
