#!/bin/bash
# requires icotool, imagemagick & pngcrush to work

set -e

my_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$my_dir"

sizes=( 16 32 48 64 128 )

input_file=ruyi-logo-256.png
tmpdir="$(mktemp -d)"
cp "$input_file" "$tmpdir/256.png"

size_files=()
pushd "$tmpdir" > /dev/null
    for size in "${sizes[@]}"; do
        convert 256.png -resize "${size}x${size}" "${size}.tmp.png"
        pngcrush "${size}.tmp.png" "${size}.png"
        size_files+=( "${size}.png" )
    done

    size_files+=( 256.png )
    icotool -c -o "$my_dir/ruyi.ico" "${size_files[@]}"
popd > /dev/null

rm "$tmpdir"/*.png
rmdir "$tmpdir"
