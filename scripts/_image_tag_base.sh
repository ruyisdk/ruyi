# this file is meant to be sourced

image_tag_base() {
    local arch="$1"

    case "$arch" in
        amd64)
            echo "ruyi-python-dist:20231110"
            ;;
        riscv64)
            echo "ruyi-python-dist:20231031"
            ;;
        *)
            echo "error: unsupported arch $arch; supported are: amd64, riscv64" >&2
            return 1
            ;;
    esac
}
