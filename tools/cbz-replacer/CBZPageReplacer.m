#import <Cocoa/Cocoa.h>

@interface DropView : NSView
@property(nonatomic, weak) NSTextField *status;
@end

@implementation DropView
- (instancetype)initWithFrame:(NSRect)frame {
    if ((self = [super initWithFrame:frame])) {
        self.wantsLayer = YES;
        self.layer.backgroundColor = NSColor.windowBackgroundColor.CGColor;
        [self registerForDraggedTypes:@[NSPasteboardTypeFileURL]];
    }
    return self;
}
- (NSDragOperation)draggingEntered:(id<NSDraggingInfo>)sender { return NSDragOperationCopy; }
- (BOOL)performDragOperation:(id<NSDraggingInfo>)sender {
    NSArray<NSURL *> *urls = [sender.draggingPasteboard readObjectsForClasses:@[NSURL.class]
                                                                       options:@{NSPasteboardURLReadingFileURLsOnlyKey: @YES}];
    NSURL *archive = nil;
    NSMutableArray<NSURL *> *pages = NSMutableArray.array;
    for (NSURL *url in urls) {
        if ([[url.pathExtension lowercaseString] isEqualToString:@"cbz"]) archive = url;
        else [pages addObject:url];
    }
    if (!archive || pages.count == 0) {
        self.status.textColor = NSColor.systemRedColor;
        self.status.stringValue = @"Drop one .cbz archive and at least one replacement file together.";
        return NO;
    }
    self.status.textColor = NSColor.secondaryLabelColor;
    self.status.stringValue = @"Replacing pages…";
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSTask *task = NSTask.new;
        task.executableURL = [NSURL fileURLWithPath:@"/Library/Frameworks/Python.framework/Versions/Current/bin/python3"];
        NSURL *script = [NSBundle.mainBundle URLForResource:@"replace_cbz" withExtension:@"py"];
        NSMutableArray *args = [NSMutableArray arrayWithObjects:script.path, archive.path, nil];
        for (NSURL *page in pages) [args addObject:page.path];
        task.arguments = args;
        NSPipe *pipe = NSPipe.pipe;
        task.standardOutput = pipe;
        task.standardError = pipe;
        NSError *error = nil;
        BOOL launched = [task launchAndReturnError:&error];
        if (launched) [task waitUntilExit];
        NSData *data = [pipe.fileHandleForReading readDataToEndOfFile];
        NSString *output = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding] ?: @"Archive operation failed.";
        output = [output stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
        dispatch_async(dispatch_get_main_queue(), ^{
            self.status.textColor = (launched && task.terminationStatus == 0) ? NSColor.systemGreenColor : NSColor.systemRedColor;
            self.status.stringValue = launched ? output : error.localizedDescription;
        });
    });
    return YES;
}
@end

@interface AppDelegate : NSObject <NSApplicationDelegate>
@end

@implementation AppDelegate
- (void)applicationDidFinishLaunching:(NSNotification *)note {
    NSWindow *window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 640, 380)
                                                    styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable)
                                                      backing:NSBackingStoreBuffered defer:NO];
    window.title = @"CBZ Page Replacer";
    DropView *view = [[DropView alloc] initWithFrame:window.contentView.bounds];
    view.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    NSTextField *title = [NSTextField labelWithString:@"CBZ Page Replacer"];
    title.font = [NSFont systemFontOfSize:25 weight:NSFontWeightBold];
    NSTextField *instruction = [NSTextField wrappingLabelWithString:@"Drag one .cbz archive and its replacement image file(s) into this window. Only files whose names already exist exactly once in the archive will be replaced."];
    instruction.textColor = NSColor.secondaryLabelColor;
    NSTextField *status = [NSTextField wrappingLabelWithString:@"The archive is rebuilt in a temporary file and swapped in only after validation succeeds."];
    status.textColor = NSColor.secondaryLabelColor;
    status.alignment = NSTextAlignmentCenter;
    view.status = status;
    for (NSTextField *field in @[title, instruction, status]) { field.translatesAutoresizingMaskIntoConstraints = NO; [view addSubview:field]; }
    [NSLayoutConstraint activateConstraints:@[
        [title.leadingAnchor constraintEqualToAnchor:view.leadingAnchor constant:40],
        [title.topAnchor constraintEqualToAnchor:view.topAnchor constant:68],
        [instruction.leadingAnchor constraintEqualToAnchor:view.leadingAnchor constant:40],
        [instruction.trailingAnchor constraintEqualToAnchor:view.trailingAnchor constant:-40],
        [instruction.topAnchor constraintEqualToAnchor:title.bottomAnchor constant:22],
        [status.leadingAnchor constraintEqualToAnchor:view.leadingAnchor constant:40],
        [status.trailingAnchor constraintEqualToAnchor:view.trailingAnchor constant:-40],
        [status.bottomAnchor constraintEqualToAnchor:view.bottomAnchor constant:-72]
    ]];
    window.contentView = view;
    [window center]; [window makeKeyAndOrderFront:nil]; [NSApp activateIgnoringOtherApps:YES];
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
@end

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        app.delegate = AppDelegate.new;
        [app run];
    }
    return 0;
}
