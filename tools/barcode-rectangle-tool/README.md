# Barcode Rectangle Tool

Run `./install-app.sh` once to copy the app to `/Applications` and register it with Finder. (Finder does not register applications stored directly on external volumes.) To open one or more images, select them in Finder, right-click, choose **Open With**, and select `Barcode Rectangle Tool.app` (or drag them onto the running app). If Finder was already open when the app was installed, reopen the Finder window once to refresh its menu.

Each image opens in its own window. Use the **−**, **100%**, **+**, or zoom slider controls (or a trackpad pinch) to inspect the barcode; scrolling pans around a zoomed image. Drag a rectangle over the barcode, then press **Apply, Save & Close**. The original JPG is replaced after drawing the darkest image color over the selected rectangle and the lightest color inside an evenly inset border. The inset on each edge is `round(image_width × 0.005 ÷ 2)`, so a 986 px-wide image uses a 2 px border.
