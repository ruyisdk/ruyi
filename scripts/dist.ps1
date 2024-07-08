# Activate the Poetry venv
& ((poetry env info --path) + "\Scripts\activate.ps1")

$Env:CLCACHE_DIR = "\clcache"
$Env:RUYI_DIST_BUILD_DIR = "\build"
$Env:RUYI_DIST_CACHE_DIR = "\ruyi-dist-cache"

python "scripts\dist-inner.py"
