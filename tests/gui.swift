import Cocoa
import ApplicationServices
func a(_ e:AXUIElement,_ k:String)->CFTypeRef?{var v:CFTypeRef?;return AXUIElementCopyAttributeValue(e,k as CFString,&v) == .success ? v:nil}
let app=NSRunningApplication.runningApplications(withBundleIdentifier:"com.openai.codex").first!
let root=AXUIElementCreateApplication(app.processIdentifier)
AXUIElementSetMessagingTimeout(root,2)
for k in ["AXManualAccessibility","AXEnhancedUserInterface"]{let r=AXUIElementSetAttributeValue(root,k as CFString,kCFBooleanTrue);print(k,r.rawValue)}
func find(_ e:AXUIElement,_ title:String)->AXUIElement?{if a(e,"AXTitle") as? String == title  {return e};for c in a(e,"AXChildren") as? [AXUIElement] ?? [] {if let x=find(c,title){return x}};return nil}
app.activate();Thread.sleep(forTimeInterval:0.5)
if CommandLine.arguments.count>1,let e=find(root,CommandLine.arguments[1]){print("操作",CommandLine.arguments[1],AXUIElementPerformAction(e,kAXPressAction as CFString).rawValue)}
