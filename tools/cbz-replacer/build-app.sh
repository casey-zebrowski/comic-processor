#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
app_path="$script_dir/CBZ Page Replacer.app"

rm -rf "$app_path"
mkdir -p "$app_path/Contents/MacOS" "$app_path/Contents/Resources"
cp "$script_dir/Info.plist" "$app_path/Contents/Info.plist"
clang -fobjc-arc -framework Cocoa "$script_dir/CBZPageReplacer.m" -o "$app_path/Contents/MacOS/CBZPageReplacer"
cp "$script_dir/replace_cbz.py" "$app_path/Contents/Resources/replace_cbz.py"
codesign --force --deep --sign - "$app_path"
print "Built: $app_path"
