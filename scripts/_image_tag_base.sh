# this file is meant to be sourced

image_tag_base() {
    local arch="$1"

    case "$arch" in
        ""|amd64|arm64|riscv64)
            echo "ghcr.io/ruyisdk/ruyi-python-dist:20240325"
            ;;
        *)
            echo "error: unsupported arch $arch; supported are: amd64, arm64, riscv64" >&2
            return 1
            ;;
    esac
}
