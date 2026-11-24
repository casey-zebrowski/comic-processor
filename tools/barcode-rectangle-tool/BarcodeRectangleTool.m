#import <Cocoa/Cocoa.h>

@interface ImageCanvas : NSView
@property(nonatomic) NSImage *image;
@property(nonatomic) NSRect selection; // Image pixels, top-left origin.
@property(nonatomic) BOOL selecting;
@end

@implementation ImageCanvas {
    NSPoint dragStart;
}
- (NSRect)imageFrame {
    return self.bounds;
}
- (NSPoint)imagePoint:(NSPoint)point {
    NSRect frame = self.imageFrame;
    CGFloat x = (point.x - frame.origin.x) / frame.size.width * self.image.size.width;
    CGFloat y = (frame.size.height - (point.y - frame.origin.y)) / frame.size.height * self.image.size.height;
    return NSMakePoint(MAX(0, MIN(self.image.size.width, x)), MAX(0, MIN(self.image.size.height, y)));
}
- (void)drawRect:(NSRect)dirtyRect {
    [[NSColor blackColor] setFill]; NSRectFill(self.bounds);
    [self.image drawInRect:self.imageFrame];
    if (!NSEqualRects(self.selection, NSZeroRect)) {
        NSRect frame = self.imageFrame;
        CGFloat sx = frame.size.width / self.image.size.width, sy = frame.size.height / self.image.size.height;
        NSRect visible = NSMakeRect(frame.origin.x + self.selection.origin.x * sx,
                                    frame.origin.y + frame.size.height - (self.selection.origin.y + self.selection.size.height) * sy,
                                    self.selection.size.width * sx, self.selection.size.height * sy);
        [[NSColor systemRedColor] setStroke];
        NSBezierPath *path = [NSBezierPath bezierPathWithRect:visible]; path.lineWidth = 2; [path stroke];
    }
}
- (void)mouseDown:(NSEvent *)event { dragStart = [self imagePoint:[self convertPoint:event.locationInWindow fromView:nil]]; self.selecting = YES; self.selection = NSZeroRect; }
- (void)mouseDragged:(NSEvent *)event {
    NSPoint end = [self imagePoint:[self convertPoint:event.locationInWindow fromView:nil]];
    self.selection = NSMakeRect(MIN(dragStart.x, end.x), MIN(dragStart.y, end.y), fabs(end.x - dragStart.x), fabs(end.y - dragStart.y));
    [self setNeedsDisplay:YES];
}
- (void)mouseUp:(NSEvent *)event { self.selecting = NO; }
@end

@class AppDelegate;
@interface ImageController : NSObject <NSWindowDelegate>
@property(nonatomic) NSWindow *window;
@property(nonatomic) NSURL *url;
@property(nonatomic) ImageCanvas *canvas;
@property(nonatomic) NSScrollView *scrollView;
@property(nonatomic) NSSlider *zoomSlider;
@property(nonatomic) NSTextField *zoomLabel;
@property(nonatomic, weak) AppDelegate *owner;
- (instancetype)initWithURL:(NSURL *)url owner:(AppDelegate *)owner;
@end

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic) NSMutableArray<ImageController *> *controllers;
- (void)openURL:(NSURL *)url;
- (void)discard:(ImageController *)controller;
@end

@implementation ImageController
- (instancetype)initWithURL:(NSURL *)url owner:(AppDelegate *)owner {
    if ((self = [super init])) {
        _url = url; _owner = owner;
        NSImage *image = [[NSImage alloc] initWithContentsOfURL:url];
        if (!image) return nil;
        _window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 900, 760)
                                               styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
                                                 backing:NSBackingStoreBuffered defer:NO];
        // Avoid AppKit's close animation for these document-style image windows.
        _window.animationBehavior = NSWindowAnimationBehaviorNone;
        _window.delegate = self;
        _window.title = url.lastPathComponent;
        NSView *root = NSView.new;
        _canvas = [[ImageCanvas alloc] initWithFrame:NSMakeRect(0, 0, image.size.width, image.size.height)]; _canvas.image = image;
        _scrollView = NSScrollView.new; _scrollView.translatesAutoresizingMaskIntoConstraints = NO;
        _scrollView.documentView = _canvas; _scrollView.hasVerticalScroller = YES; _scrollView.hasHorizontalScroller = YES;
        _scrollView.allowsMagnification = YES; _scrollView.minMagnification = 0.25; _scrollView.maxMagnification = 8.0; _scrollView.magnification = 1.0;
        NSTextField *help = [NSTextField labelWithString:@"Drag over the barcode. Zoom with the controls or trackpad pinch. The outer rectangle becomes the image's darkest color; a 0.25%-of-width inset becomes its lightest color."];
        help.textColor = NSColor.secondaryLabelColor; help.translatesAutoresizingMaskIntoConstraints = NO;
        NSButton *save = [NSButton buttonWithTitle:@"Apply, Save & Close" target:self action:@selector(apply:)]; save.translatesAutoresizingMaskIntoConstraints = NO; save.keyEquivalent = @"\r";
        NSButton *zoomOut = [NSButton buttonWithTitle:@"−" target:self action:@selector(zoomOut:)]; zoomOut.translatesAutoresizingMaskIntoConstraints = NO;
        NSButton *actual = [NSButton buttonWithTitle:@"100%" target:self action:@selector(actualSize:)]; actual.translatesAutoresizingMaskIntoConstraints = NO;
        NSButton *zoomIn = [NSButton buttonWithTitle:@"+" target:self action:@selector(zoomIn:)]; zoomIn.translatesAutoresizingMaskIntoConstraints = NO;
        _zoomSlider = [NSSlider sliderWithValue:1.0 minValue:0.25 maxValue:8.0 target:self action:@selector(zoomChanged:)]; _zoomSlider.translatesAutoresizingMaskIntoConstraints = NO; _zoomSlider.continuous = YES;
        _zoomLabel = [NSTextField labelWithString:@"100%"] ; _zoomLabel.translatesAutoresizingMaskIntoConstraints = NO; _zoomLabel.alignment = NSTextAlignmentRight;
        [root addSubview:_scrollView]; [root addSubview:help]; [root addSubview:save]; [root addSubview:zoomOut]; [root addSubview:actual]; [root addSubview:zoomIn]; [root addSubview:_zoomSlider]; [root addSubview:_zoomLabel];
        [NSLayoutConstraint activateConstraints:@[
            [_scrollView.leadingAnchor constraintEqualToAnchor:root.leadingAnchor constant:18], [_scrollView.trailingAnchor constraintEqualToAnchor:root.trailingAnchor constant:-18],
            [_scrollView.topAnchor constraintEqualToAnchor:root.topAnchor constant:18], [_scrollView.bottomAnchor constraintEqualToAnchor:help.topAnchor constant:-14],
            [help.leadingAnchor constraintEqualToAnchor:root.leadingAnchor constant:18], [help.bottomAnchor constraintEqualToAnchor:root.bottomAnchor constant:-18],
            [save.trailingAnchor constraintEqualToAnchor:root.trailingAnchor constant:-18], [save.centerYAnchor constraintEqualToAnchor:help.centerYAnchor],
            [zoomOut.trailingAnchor constraintEqualToAnchor:actual.leadingAnchor constant:-4], [actual.trailingAnchor constraintEqualToAnchor:zoomIn.leadingAnchor constant:-4],
            [zoomIn.trailingAnchor constraintEqualToAnchor:_zoomSlider.leadingAnchor constant:-8], [_zoomSlider.trailingAnchor constraintEqualToAnchor:_zoomLabel.leadingAnchor constant:-8],
            [_zoomLabel.trailingAnchor constraintEqualToAnchor:save.leadingAnchor constant:-16], [zoomOut.centerYAnchor constraintEqualToAnchor:help.centerYAnchor], [actual.centerYAnchor constraintEqualToAnchor:help.centerYAnchor], [zoomIn.centerYAnchor constraintEqualToAnchor:help.centerYAnchor], [_zoomSlider.centerYAnchor constraintEqualToAnchor:help.centerYAnchor], [_zoomLabel.centerYAnchor constraintEqualToAnchor:help.centerYAnchor],
            [_zoomSlider.widthAnchor constraintEqualToConstant:130], [_zoomLabel.widthAnchor constraintEqualToConstant:48],
            [help.trailingAnchor constraintLessThanOrEqualToAnchor:zoomOut.leadingAnchor constant:-14]
        ]];
        _window.contentView = root; [_window center]; [_window makeKeyAndOrderFront:nil];
    }
    return self;
}
- (void)setZoom:(CGFloat)zoom {
    zoom = MAX(self.scrollView.minMagnification, MIN(self.scrollView.maxMagnification, zoom));
    NSPoint center = NSMakePoint(NSMidX(self.scrollView.documentVisibleRect), NSMidY(self.scrollView.documentVisibleRect));
    [self.scrollView setMagnification:zoom centeredAtPoint:center];
    self.zoomSlider.doubleValue = zoom;
    self.zoomLabel.stringValue = [NSString stringWithFormat:@"%.0f%%", zoom * 100];
}
- (void)zoomChanged:(NSSlider *)sender { [self setZoom:sender.doubleValue]; }
- (void)zoomIn:(id)sender { [self setZoom:self.scrollView.magnification * 1.25]; }
- (void)zoomOut:(id)sender { [self setZoom:self.scrollView.magnification / 1.25]; }
- (void)actualSize:(id)sender { [self setZoom:1.0]; }
- (void)apply:(id)sender {
    NSRect r = self.canvas.selection;
    if (r.size.width < 1 || r.size.height < 1) { NSBeep(); return; }
    NSTask *task = NSTask.new;
    task.executableURL = [NSURL fileURLWithPath:@"/Library/Frameworks/Python.framework/Versions/Current/bin/python3"];
    NSURL *script = [NSBundle.mainBundle URLForResource:@"paint_barcode" withExtension:@"py"];
    task.arguments = @[script.path, self.url.path, [NSString stringWithFormat:@"%.0f", r.origin.x], [NSString stringWithFormat:@"%.0f", r.origin.y], [NSString stringWithFormat:@"%.0f", r.size.width], [NSString stringWithFormat:@"%.0f", r.size.height]];
    NSPipe *pipe = NSPipe.pipe; task.standardOutput = pipe; task.standardError = pipe;
    NSError *error = nil; if (![task launchAndReturnError:&error]) { NSBeep(); return; }
    [task waitUntilExit];
    if (task.terminationStatus == 0) { [self.window close]; }
    else { NSAlert *alert = NSAlert.new; alert.messageText = @"Image was not saved"; alert.informativeText = [[NSString alloc] initWithData:[pipe.fileHandleForReading readDataToEndOfFile] encoding:NSUTF8StringEncoding]; [alert runModal]; }
}
@end

@implementation AppDelegate
- (instancetype)init { if ((self = [super init])) _controllers = NSMutableArray.array; return self; }
- (void)application:(NSApplication *)app openFiles:(NSArray<NSString *> *)files { for (NSString *file in files) [self openURL:[NSURL fileURLWithPath:file]]; }
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
- (void)openURL:(NSURL *)url { ImageController *controller = [[ImageController alloc] initWithURL:url owner:self]; if (controller) [self.controllers addObject:controller]; }
- (void)discard:(ImageController *)controller { [self.controllers removeObject:controller]; }
@end

int main(int argc, const char * argv[]) { @autoreleasepool { NSApplication *app = NSApplication.sharedApplication; AppDelegate *delegate = AppDelegate.new; app.delegate = delegate; [app run]; } return 0; }
