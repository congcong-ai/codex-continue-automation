import Cocoa
import ApplicationServices
func attr(_ e: AXUIElement,_ k:String)->CFTypeRef? {var v:CFTypeRef?; let r=AXUIElementCopyAttributeValue(e,k as CFString,&v); return r == .success ? v:nil}
print("辅助功能权限",AXIsProcessTrusted())
let apps=NSRunningApplication.runningApplications(withBundleIdentifier:"com.openai.codex")
for app in apps {
 print("进程",app.processIdentifier,app.localizedName ?? "")
 let root=AXUIElementCreateApplication(app.processIdentifier)
 for k in ["AXManualAccessibility","AXEnhancedUserInterface"] { print(k, AXUIElementSetAttributeValue(root,k as CFString,kCFBooleanTrue)) }; Thread.sleep(forTimeInterval:1)
 func walk(_ e:AXUIElement,_ d:Int){
  if d>60{return}
  let keys=["AXRole","AXSubrole","AXTitle","AXDescription","AXIdentifier","AXValue","AXPlaceholderValue","AXURL"]
  print(String(repeating:" ",count:d)+keys.compactMap{k in attr(e,k).map{"\(k)=\(String(describing:$0).prefix(250))"}}.joined(separator:" | "))
  for c in attr(e,"AXChildren") as? [AXUIElement] ?? [] {walk(c,d+1)}
 }
 if CommandLine.arguments.count>1 { for w in attr(root,"AXChildren") as? [AXUIElement] ?? [] where attr(w,"AXRole") as? String == "AXWindow" && attr(w,"AXTitle") as? String == CommandLine.arguments[1] {walk(w,0)} } else {walk(root,0)}
}
