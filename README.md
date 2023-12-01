# ruyi

The WIP package manager for [RuyiSDK](https://github.com/ruyisdk).

## Example usage

You can get pre-built binaries of `ruyi` from [the RuyiSDK mirror][mirror-testing]
for easier testing. Rename the downloaded file to `ruyi`, make it executable,
put inside your `$PATH` and you're ready to go.

[mirror-testing]: https://mirror.iscas.ac.cn/ruyisdk/ruyi/testing/

```sh
# Sync the RuyiSDK package repo to local storage
# By default the repo is cloned to $XDG_CACHE_HOME/ruyi/packages-index
# if XDG_CACHE_HOME is unset, it defaults to ~/.cache
ruyi update

# List all available packages
ruyi list

# And the details
ruyi list -v

# Install a package
# Either way is okay and equivalent to each other:
ruyi install plct
ruyi install name:plct
ruyi install slug:plct-20231026

# TODO: remove a package
#ruyi remove plct-20231026

# list available profiles
ruyi list profiles

# TODO: setup a project
#cd path/to/your/project
#ruyi setup --profile=milkv-duo .

# TODO: enjoy your build!
#source ./.ruyirc
#./configure --host=riscv64-plct-linux-gnu && make

# TODO: cmake & meson support
```

## Configuration

Various aspects of `ruyi` can be configured with files or environment variables.

### Config search path

`ruyi` respects `$XDG_CONFIG_HOME` and `$XDG_CONFIG_DIRS` settings, and will
look up its config accordingly. If these are not explicitly set though, as in
typical use cases, the default config directory is most likely `~/.config/ruyi`.

### Config file

Currently `ruyi` will look for an optional `config.toml` in its XDG config
directory. The file, if present, looks like this, with all values being default:

```toml
[packages]
# Consider pre-release versions when matching packages in repositories.
prereleases = false
```

### Environment variables

Currently the following environment variables are supported by `ruyi`:

* `RUYI_VENV` -- explicitly specifies the Ruyi virtual environment to use.

## License

Copyright &copy; 2023 Institute of Software, Chinese Academy of Sciences (ISCAS).
All rights reserved.

`ruyi` is licensed under the [Apache 2.0 license](./LICENSE-Apache.txt).

All trademarks referenced herein are property of their respective holders.
