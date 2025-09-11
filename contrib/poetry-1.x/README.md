# Poetry 1.x project metadata files

If you are a packager packaging `ruyi` for old distros that only provide
Poetry 1.x, here are project metadata files ready for use.

Just drop in the files to replace the Poetry 2.x metadata:

```sh
# at project root
mv contrib/poetry-1.x/{pyproject.toml,poetry.lock} .
```

Then you should be able to continue building with Poetry 1.x.
