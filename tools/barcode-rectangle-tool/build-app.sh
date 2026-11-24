#!/bin/zsh
set -euo pipefail
script_dir="${0:A:h}"
app_path="$script_dir/Barcode Rectangle Tool.app"
rm -rf "$app_path"
mkdir -p "$app_path/Contents/MacOS" "$app_path/Contents/Resources"
cp "$script_dir/Info.plist" "$app_path/Contents/Info.plist"
cp "$script_dir/paint_barcode.py" "$app_path/Contents/Resources/paint_barcode.py"
clang -fobjc-arc -framework Cocoa "$script_dir/BarcodeRectangleTool.m" -o "$app_path/Contents/MacOS/BarcodeRectangleTool"
codesign --force --deep --sign - "$app_path"
print "Built: $app_path"
