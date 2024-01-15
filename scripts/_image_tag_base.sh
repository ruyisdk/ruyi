# this file is meant to be sourced

image_tag_base() {
    local arch="$1"

    case "$arch" in
        amd64)
            echo "ruyi-python-dist:20240115"
            ;;
        arm64)
            echo "ruyi-python-dist:20240115"
            ;;
        riscv64)
            echo "ruyi-python-dist:20240115"
            ;;
        *)
            echo "error: unsupported arch $arch; supported are: amd64, arm64, riscv64" >&2
            return 1
            ;;
    esac
}
