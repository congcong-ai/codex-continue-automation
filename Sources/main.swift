import Cocoa
import ApplicationServices
import Darwin

let fm = FileManager.default
let base = URL(fileURLWithPath:CommandLine.arguments[0]).resolvingSymlinksInPath().deletingLastPathComponent().deletingLastPathComponent()
let logDir = base.appendingPathComponent("logs")
try? fm.createDirectory(at:logDir,withIntermediateDirectories:true)
let stamp = ISO8601DateFormatter()
stamp.timeZone = .current
func log(_ event:String,_ info:[String:Any] = [:]) {
 var record=info; record["时间"]=stamp.string(from:Date());record["事件"]=event
 let data=try! JSONSerialization.data(withJSONObject:record,options:[.sortedKeys,.withoutEscapingSlashes])
 print(String(decoding:data,as:UTF8.self))
 let url=logDir.appendingPathComponent("执行.jsonl")
 if !fm.fileExists(atPath:url.path){fm.createFile(atPath:url.path,contents:nil,attributes:[.posixPermissions:0o600])}
 if let h=try? FileHandle(forWritingTo:url){h.seekToEndOfFile();h.write(data);h.write(Data([10]));try? h.close()}
}
struct Failure:Error,CustomStringConvertible {let description:String;init(_ s:String){description=s}}
func read(_ e:AXUIElement,_ key:String)->CFTypeRef? {var v:CFTypeRef?;return AXUIElementCopyAttributeValue(e,key as CFString,&v) == .success ? v:nil}
final class Node {
 let e:AXUIElement?;let role:String;let title:String;let value:String;let sub:String;let enabled:Bool;var children:[Node];weak var parent:Node?
 init(_ role:String,_ title:String="",_ value:String="",sub:String="",enabled:Bool=true,children:[Node]=[],e:AXUIElement?=nil){self.role=role;self.title=title;self.value=value;self.sub=sub;self.enabled=enabled;self.children=children;self.e=e;for c in children{c.parent=self}}
 var all:[Node]{[self]+children.flatMap{$0.all}}
}
func snapshot(_ e:AXUIElement, includeHistory:Bool = true)throws->Node {
 var count=0
 func visit(_ e:AXUIElement,_ depth:Int)throws->Node {
  count+=1;guard depth<100 && count<25000 else{throw Failure("辅助功能树超出安全边界")}
  guard let role=read(e,"AXRole") as? String else{throw Failure("辅助功能元素读取失败，取消本次快照")}
  let n=Node(role,read(e,"AXTitle") as? String ?? "",read(e,"AXValue") as? String ?? "",sub:read(e,"AXSubrole") as? String ?? "",enabled:(read(e,"AXEnabled") as? Bool) ?? false,e:e)
  let externalWeb = role == "AXWebArea" && !((read(e,"AXURL") as? URL)?.absoluteString ?? String(describing:read(e,"AXURL") ?? "" as CFString)).hasPrefix("app://-/")
  if !externalWeb && role != "AXStaticText" && (includeHistory || !(n.sub == "AXLandmarkRegion" && ["对话","Conversation"].contains(n.title))) {
   var raw:CFTypeRef?;let r=AXUIElementCopyAttributeValue(e,"AXChildren" as CFString,&raw)
   guard r == .success || r == .noValue || r == .attributeUnsupported else{throw Failure("子元素读取失败：\(r.rawValue)")}
   for c in raw as? [AXUIElement] ?? []{let child=try visit(c,depth+1);child.parent=n;n.children.append(child)}
  }
  return n
 }
 return try visit(e,0)
}
func sidebars(_ root:Node)->[Node] {
 root.all.filter{n in n.sub == "AXLandmarkComplementary" && n.all.contains{$0.sub == "AXLandmarkNavigation" && ["应用导航","App navigation"].contains($0.title)}}
}
let unpin:Set<String>=["取消置顶聊天","Unpin chat"]
let composerNames:Set<String>=["和 Codex 一起工作","随心输入","Work with Codex","Ask anything"]
let sendNames:Set<String>=["发送","发送消息","发送提示","Send","Send message","Send prompt"]
let stopNames:Set<String>=["停止","停止生成","停止响应","Stop","Stop generating","Stop response","排队","Queue"]
func exact(_ s:String)->Bool{s.trimmingCharacters(in:.whitespacesAndNewlines)=="继续"}
func one(_ list:[Node],_ reason:String)throws->Node{guard list.count==1 else{throw Failure("\(reason)：找到 \(list.count) 个")};return list[0]}
struct Pins {let reliable:Bool;let rows:[Node];let reason:String}
func pins(_ root:Node)->Pins {
 let sides=sidebars(root)
 guard sides.count==1 else{return Pins(reliable:false,rows:[],reason:"无法唯一识别侧边栏")}
 let sections=sides[0].all.filter{$0.children.contains{["置顶","Pinned"].contains($0.title) && $0.role=="AXButton"}}
 guard sections.count==1 else{return Pins(reliable:false,rows:[],reason:"无法唯一识别置顶分组")}
 let section=sections[0];let lists=section.all.filter{$0.role=="AXList"}
 guard lists.count==1 else{return Pins(reliable:false,rows:[],reason:"置顶分组折叠或列表结构未知")}
 let rows=lists[0].children.compactMap { item -> Node? in
  let candidates=item.children.filter{$0.role=="AXButton" && $0.all.contains{unpin.contains($0.title)}}
  return candidates.count==1 ? candidates[0]:nil
 }
 guard rows.count==lists[0].children.count,Set(rows.map{$0.title}).count==rows.count,rows.allSatisfy({!$0.title.isEmpty}) else{return Pins(reliable:false,rows:[],reason:"置顶列表存在未识别项或重名项")}
 return Pins(reliable:true,rows:rows,reason:"置顶分组内每一行均有明确取消置顶按钮")
}
func limitedTargets(_ requested:[String],_ inventory:Pins)throws->[String] {
 guard inventory.reliable else{throw Failure("限定目标要求可靠识别置顶列表，不允许降级")}
 var selected:[String]=[]
 for title in requested {
  guard inventory.rows.filter({$0.title==title}).count==1 else{throw Failure("限定目标不是唯一可确认的置顶会话：\(title)")}
  if !selected.contains(title){selected.append(title)}
 }
 return selected
}
func identity(_ root:Node)throws->String {
 let bar=try one(root.all.filter{$0.role=="AXToolbar" && ["聊天工具栏","Chat toolbar"].contains($0.title)},"当前活动会话工具栏不唯一")
 let labels=bar.all.filter{$0.role=="AXStaticText" && !$0.value.isEmpty}
 let title=try one(labels,"当前活动会话标题不唯一").value
 guard !title.isEmpty,root.title==title else{throw Failure("窗口与活动会话标题不一致")}
 let side=sidebars(root)
 guard side.count==1,side[0].all.filter({$0.role=="AXButton" && $0.title==title}).count==1 else{throw Failure("会话在侧边栏不唯一，无法安全绑定身份")}
 return title
}
struct Ready {let input:Node;let button:Node;let scope:Node}
func ready(_ root:Node)throws->Ready {
 let mains=root.all.filter{$0.sub=="AXLandmarkMain"};guard mains.count==1 else{throw Failure("主内容区域不唯一")}
 let main=mains[0]
 let input=try one(main.all.filter{$0.role=="AXTextArea" && composerNames.contains($0.title)},"消息 composer 不唯一")
 guard exact(input.value) else{throw Failure("composer 草稿不是恰好为继续")}
 guard input.enabled else{throw Failure("composer 被禁用或状态无法读取")}
 var parent=input.parent;var scope:Node?
 while let p=parent,p !== main {if p.all.contains(where:{$0.role=="AXButton" && (sendNames.contains($0.title)||stopNames.contains($0.title))}){scope=p;break};parent=p.parent}
 guard let scope=scope else{throw Failure("composer 周围没有可确认的发送按钮")}
 guard !scope.all.contains(where:{$0.role=="AXButton" && stopNames.contains($0.title)}) else{throw Failure("会话正在执行或显示排队按钮")}
 guard scope.all.filter({$0.role=="AXTextArea"}).count==1 else{throw Failure("发送区域有多个文本框")}
 let button=try one(scope.all.filter{$0.role=="AXButton" && sendNames.contains($0.title)},"发送按钮不唯一")
 guard button.enabled else{throw Failure("发送按钮不可用")}
 return Ready(input:input,button:button,scope:scope)
}
// 只数“你说”消息块里恰好为继续的正文；绝不扫描侧边栏或 composer。
func userMessages(_ root:Node)->Int {
 let regions=root.all.filter{$0.sub=="AXLandmarkRegion" && ["对话","Conversation"].contains($0.title)}
 guard regions.count==1 else{return -1}
 var matches=0
 for parent in regions[0].all {
  for (index,heading) in parent.children.enumerated() where heading.role == "AXHeading" && ["你说：","You said:"].contains(heading.title) {
   var body:Node?
   for sibling in parent.children.dropFirst(index+1) {
    if sibling.role == "AXHeading" {break}
    if sibling.role == "AXGroup" && sibling.sub != "AXApplicationStatus" &&
       !sibling.all.contains(where:{
        if $0.role == "AXButton" {return !["显示更多","显示更少","Show more","Show less"].contains($0.title)}
        return ["AXTextArea","AXTextField","AXCheckBox"].contains($0.role)
       }) &&
       sibling.all.contains(where:{$0.role == "AXStaticText" && !$0.value.isEmpty}) {body=sibling;break}
   }
   guard let body=body else{return -1}
   // 折叠长消息的展开按钮属于正文容器，不能让其它可读用户消息的基线失效。
   // 按钮标签不计入正文；若折叠内容恰好只暴露“继续”，仍拒绝猜测隐藏正文。
   func bodyText(_ node:Node)->String {
    if node.role == "AXButton" {return ""}
    if node.role == "AXStaticText" {return node.value}
    return node.children.map{bodyText($0)}.joined()
   }
   let text=bodyText(body)
   if exact(text){
    guard !body.all.contains(where:{$0.role == "AXButton" && ["显示更多","Show more"].contains($0.title)}) else{return -1}
    matches+=1
   }
  }
 }
 return matches
}
func press(_ n:Node)throws{guard let e=n.e else{throw Failure("元素不存在")};let r=AXUIElementPerformAction(e,kAXPressAction as CFString);guard r == .success else{throw Failure("AXPress 返回 \(r.rawValue)")}}
func selfTest()throws {
 func check(_ ok:Bool,_ name:String)throws{guard ok else{throw Failure("测试失败：\(name)")};log("测试通过",["项目":name])}
 try check(exact(" \n继续\t") && !exact("继续吧") && !exact(""),"草稿精确匹配")
 let history=Node("AXGroup","",children:[Node("AXStaticText","","继续")])
 do{_=try ready(history);throw Failure("测试失败：历史误识别")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"历史继续不能作为草稿")}
 let row=Node("AXButton","测试会话",children:[Node("AXButton","取消置顶聊天")])
 let list=Node("AXList",children:[Node("AXGroup",children:[row])])
 let section=Node("AXGroup",children:[Node("AXButton","置顶"),list])
 let root=Node("AXWindow",children:[Node("AXGroup",sub:"AXLandmarkComplementary",children:[Node("AXGroup","应用导航",sub:"AXLandmarkNavigation"),section])])
 try check(pins(root).reliable && pins(root).rows.count==1,"明确置顶状态")
 let multi=Pins(reliable:true,rows:[Node("AXButton","你好"),Node("AXButton","hello"),Node("AXButton","其它会话")],reason:"测试")
 try check(try limitedTargets(["你好","hello"],multi)==["你好","hello"],"批量限定只选择两条指定会话")
 try check(try limitedTargets(["你好","hello","你好"],multi)==["你好","hello"],"批量限定重复标题去重")
 do{_=try limitedTargets(["你好","未置顶"],multi);throw Failure("测试失败：无效限定目标")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"批量包含无效目标时整体拒绝")}

 list.children.append(Node("AXGroup",children:[Node("AXButton","普通会话")]))
 try check(!pins(root).reliable,"不完整置顶扫描必须降级")
 let input=Node("AXTextArea","和 Codex 一起工作","继续")
 let button=Node("AXButton","发送")
 let scope=Node("AXGroup",children:[input,button])
 let main=Node("AXGroup",sub:"AXLandmarkMain",children:[scope])
 let page=Node("AXWindow",children:[main])
 try check(try ready(page).input === input,"正确 composer 和发送按钮")
 scope.children.append(Node("AXButton","排队"))
 do{_=try ready(page);throw Failure("测试失败：运行状态")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"运行中禁止发送")}
 scope.children.removeLast();input.parent=scope
 let msg=Node("AXGroup",children:[Node("AXHeading","你说："),Node("AXGroup",children:[Node("AXStaticText","","继续")])])
 let conversation=Node("AXGroup","对话",sub:"AXLandmarkRegion",children:[msg]);main.children.append(conversation)
 try check(userMessages(page)==1,"用户消息块证据")
 try check(userMessages(root)==(-1),"缺失历史证据不得确认成功")
 let flat=Node("AXGroup",children:[Node("AXHeading","你说："),Node("AXGroup",children:[Node("AXStaticText","","你好")]),Node("AXStaticText","","7:57"),Node("AXHeading","ChatGPT 说："),Node("AXGroup",children:[Node("AXStaticText","","你好！")]),Node("AXHeading","你说："),Node("AXGroup",children:[Node("AXStaticText","","继续")]),Node("AXStaticText","","12:27"),Node("AXHeading","ChatGPT 说："),Node("AXGroup",children:[Node("AXStaticText","","你想继续哪件事？")])])
 let flatPage=Node("AXWindow",children:[Node("AXGroup","对话",sub:"AXLandmarkRegion",children:[flat])])
 try check(userMessages(flatPage)==1,"真实扁平多轮历史只计用户继续正文，不混入时间和助手回复")
 let collapsed=Node("AXGroup",children:[Node("AXGroup",children:[Node("AXHeading","较长任务说明",children:[Node("AXStaticText","","较长任务说明")]),Node("AXStaticText","","已经显示的长消息正文")]),Node("AXButton","显示更多",children:[Node("AXStaticText","","显示更多")])])
 let collapsedRows=Node("AXGroup",children:[Node("AXHeading","你说："),collapsed,Node("AXHeading","ChatGPT 说："),Node("AXGroup",children:[Node("AXStaticText","","答复")]),Node("AXHeading","你说："),Node("AXGroup",children:[Node("AXStaticText","","继续")])])
 let collapsedPage=Node("AXWindow",children:[Node("AXGroup","对话",sub:"AXLandmarkRegion",children:[collapsedRows])])
 try check(userMessages(collapsedPage)==1,"长消息含显示更多按钮不阻断后续继续消息基线")
 collapsedRows.children.removeLast(2)
 try check(userMessages(collapsedPage)==0,"只有折叠长消息时可建立零条继续基线")
 collapsed.children=[Node("AXStaticText","","继续"),Node("AXButton","显示更多")]
 try check(userMessages(collapsedPage)==(-1),"折叠后只暴露继续时不猜测隐藏正文")
 collapsed.children=[Node("AXStaticText","","其它正文"),Node("AXButton","未知操作")]
 try check(userMessages(collapsedPage)==(-1),"未知正文操作仍拒绝作为可靠基线")
 let fixture=base.appendingPathComponent("tests/真实AX消息历史.json")
 if fm.fileExists(atPath:fixture.path) {
  func decode(_ d:[String:Any])->Node {Node(d["role"] as? String ?? "",d["title"] as? String ?? "",d["value"] as? String ?? "",sub:d["sub"] as? String ?? "",children:(d["children"] as? [[String:Any]] ?? []).map{decode($0)})}
  let raw=try Data(contentsOf:fixture)
  let record=try JSONSerialization.jsonObject(with:raw) as! [String:Any]
  let captured=Node("AXWindow",children:[decode(record)])
  try check(userMessages(captured)==1,"真实发送后AX快照回放：恰好一条用户继续")
 }

 let externalSide=Node("AXGroup",sub:"AXLandmarkComplementary",children:[Node("AXGroup",sub:"AXLandmarkMain")])
 root.children.append(externalSide)
 let invalidRow=list.children.removeLast()
 try check(pins(root).reliable && pins(root).rows.count==1,"工作区侧栏不能冒充应用导航侧栏")
 list.children.append(invalidRow)

 scope.children.removeAll();scope.children=[Node("AXTextArea","和 Codex 一起工作","继续",enabled:false),button]
 for c in scope.children{c.parent=scope}
 do{_=try ready(page);throw Failure("测试失败：禁用输入框")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"禁用输入框禁止发送")}
 scope.children=[Node("AXTextArea","和 Codex 一起工作","继续吧"),button]
 for c in scope.children{c.parent=scope}
 do{_=try ready(page);throw Failure("测试失败：其它草稿")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"其它草稿禁止发送")}
 list.children=[]
 try check(pins(root).reliable && pins(root).rows.isEmpty,"可靠空置顶列表不得降级发送")
 section.children.removeLast()
 try check(!pins(root).reliable,"折叠置顶列表只能降级")
 let titleNode=Node("AXStaticText","","测试会话")
 let toolbar=Node("AXToolbar","聊天工具栏",children:[titleNode])
 let side=Node("AXGroup",sub:"AXLandmarkComplementary",children:[Node("AXGroup","应用导航",sub:"AXLandmarkNavigation"),Node("AXButton","测试会话")])
 let identified=Node("AXWindow","测试会话",children:[toolbar,side])
 try check(try identity(identified)=="测试会话","窗口工具栏侧边栏三方身份一致")
 side.children.append(Node("AXButton","测试会话"))
 do{_=try identity(identified);throw Failure("测试失败：重名身份")}catch let e as Failure{try check(!e.description.hasPrefix("测试失败"),"重名会话拒绝识别")}

}
// 权限预检只查询系统信任状态，不读取聊天、不激活目标应用。
func checkAccessibilityPermission(prompt:Bool)throws {
 let trusted = prompt
  ? AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary)
  : AXIsProcessTrusted()
 let executable=URL(fileURLWithPath:CommandLine.arguments[0]).resolvingSymlinksInPath().path
 log("辅助功能权限检查",["已授权":trusted,"程序路径":executable,"启动终端":ProcessInfo.processInfo.environment["TERM_PROGRAM"] ?? "未提供终端标识"])
 guard trusted else {
  if prompt,let url=URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
   let opened=NSWorkspace.shared.open(url)
   log("辅助功能授权引导",["已打开系统设置":opened])
  }
  print("请在 系统设置 → 隐私与安全性 → 辅助功能 中，开启实际运行命令的终端（例如 Terminal、iTerm 或 Codex）。")
  print("若系统列出 codex-continue，请开启它；需要手动添加时按 +、Command+Shift+G，输入：\(executable)")
  print("如果已经开启但仍失败，请移除对应旧条目后重新添加；重新编译或移动程序后可能需要重新授权。")
  print("授权后请回到同一个终端，重新运行 codex-continue.sh --check-permissions，通过后再预约。")
  throw Failure("缺少辅助功能权限；尚未建立预约，也未发送消息。授权必须由你在系统设置中完成")
 }
}
let args=Array(CommandLine.arguments.dropFirst())
do {
 if args==["--self-test"]{try selfTest();exit(0)}
 if args==["--check-permissions"] || args==["--request-permissions"] {
  try checkAccessibilityPermission(prompt:args==["--request-permissions"]);exit(0)
 }
 let allowed:Set<String>=["--inspect","--test","--run-now","--current-only","--expect-title","--pinned-title","--self-test"]
 for (i,arg) in args.enumerated() where !(i>0 && ["--expect-title","--pinned-title"].contains(args[i-1])) {guard allowed.contains(arg) else{throw Failure("未知参数：\(arg)")}}
 guard args.filter({["--inspect","--test","--run-now"].contains($0)}).count==1 else{throw Failure("诊断、测试、执行模式必须且只能选一个")}
 guard args.contains("--inspect") || args.contains("--test") || args.contains("--run-now") else{throw Failure("请使用入口脚本预约，或指定 --inspect / --test / --run-now")}
 let current=args.contains("--current-only")
 let pinnedIndices=args.indices.filter{args[$0]=="--pinned-title"}
 var pinnedTitles:[String]=[]
 for index in pinnedIndices {
  guard index+1<args.count,!args[index+1].hasPrefix("--"),!args[index+1].isEmpty else{throw Failure("置顶标题限定缺少有效标题")}
  pinnedTitles.append(args[index+1])
 }
 guard pinnedTitles.isEmpty || !current else{throw Failure("置顶标题限定不能与仅当前模式混用")}

 let guardIndex=args.firstIndex(of:"--expect-title")
 let expected=guardIndex.flatMap{ $0+1<args.count ? args[$0+1]:nil }
 guard !current || expected != nil else{throw Failure("仅当前会话模式必须提供 --expect-title 精确标题")}
 let lockPath=base.appendingPathComponent(".执行锁").path
 let fd=open(lockPath,O_CREAT|O_RDWR,0o600);guard fd>=0,flock(fd,LOCK_EX|LOCK_NB)==0 else{throw Failure("另一个实例正在执行")};defer{close(fd)}
 guard let session=CGSessionCopyCurrentDictionary() as? [String:Any],
       session[kCGSessionOnConsoleKey as String] as? Bool == true,
       session[kCGSessionLoginDoneKey as String] as? Bool == true,
       session["CGSSessionScreenIsLocked"] as? Bool != true else{throw Failure("当前不是已登录且未锁屏的控制台图形会话")}
 guard AXIsProcessTrusted() else{throw Failure("缺少辅助功能权限；请在同一个终端运行 codex-continue.sh --request-permissions 完成授权后重试")}
 let apps=NSRunningApplication.runningApplications(withBundleIdentifier:"com.openai.codex")
 guard apps.count==1 else{throw Failure("未找到唯一的 com.openai.codex 进程")}
 let app=apps[0];let ax=AXUIElementCreateApplication(app.processIdentifier);AXUIElementSetMessagingTimeout(ax,1)
 _=AXUIElementSetAttributeValue(ax,"AXManualAccessibility" as CFString,kCFBooleanTrue)
 _=AXUIElementSetAttributeValue(ax,"AXEnhancedUserInterface" as CFString,kCFBooleanTrue)
 if !args.contains("--inspect"){app.activate()}
 Thread.sleep(forTimeInterval:1)
 var windows:[AXUIElement]=[]
 for attempt in 0..<3 {
  windows=(read(ax,"AXChildren") as? [AXUIElement] ?? []).filter{read($0,"AXRole") as? String == "AXWindow"}
  if !windows.isEmpty{break}
  if attempt<2{Thread.sleep(forTimeInterval:0.5)}
 }
 log("运行环境",["进程":Int(app.processIdentifier),"名称":app.localizedName ?? "","架构":ProcessInfo.processInfo.machineArchitecture,"窗口数":windows.count])
 // 仅使用系统明确报告的焦点窗口，禁止按窗口数组顺序猜测。
 for w in windows{log("窗口",["标题":read(w,"AXTitle") as? String ?? ""])}
 guard !windows.isEmpty else{throw Failure("没有可操作窗口")}
 guard let focused=read(ax,"AXFocusedWindow"),let window=windows.first(where:{CFEqual($0,focused)}) else{throw Failure("当前活动会话无法可靠识别：AXFocusedWindow 不存在或不属于应用窗口")}

 func get(_ history:Bool = true)throws->Node {
  var last:Error=Failure("未读取快照")
  for attempt in 0..<3 {
   do{return try snapshot(window,includeHistory:history)}catch{last=error;if attempt<2{Thread.sleep(forTimeInterval:0.2)}}
  }
  throw last
 }
 var initial=try get(false)
 var p=current ? Pins(reliable:false,rows:[],reason:"仅当前会话限定，未枚举置顶目标") : pins(initial)
 if !current {
  for _ in 0..<5 where !p.reliable {
   Thread.sleep(forTimeInterval:0.3);initial=try get(false);p=pins(initial)
  }
 }
 log(current ? "仅当前会话限定，未扫描置顶会话" : (p.reliable ? "已可靠识别置顶会话":"无法可靠识别置顶，降级当前活动会话"),["原因":p.reason,"置顶会话":p.rows.map{$0.title}])
 if args.contains("--inspect") {
  let diagnostic=try get()
  do{log("当前活动会话",["标题":try identity(diagnostic)])}catch{log("当前活动会话无法可靠识别",["原因":"\(error)"])}
  do{_=try ready(diagnostic);log("当前提交条件满足，未发送")}catch{log("当前提交条件不满足",["原因":"\(error)"])}
  if current,let expected=expected {
   let full=diagnostic
   guard try identity(full)==expected else{throw Failure("只读历史核验会话不符合限定标题")}
   log("只读用户消息核验",["会话":expected,"用户继续消息数":userMessages(full),"说明":"未执行发送动作"])
  }
  for n in diagnostic.all where n.role=="AXTextArea"{log("输入框",["标签":n.title,"恰好继续":exact(n.value),"可用":n.enabled,"字符数":n.value.count])}
  exit(0)
 }
 let targets:[String]
 if !pinnedTitles.isEmpty {
  targets=try limitedTargets(pinnedTitles,p)
 }else if current || !p.reliable {
  do {let id=try identity(initial);guard expected == nil || expected==id else{throw Failure("当前会话不符合测试限定标题")};targets=[id]}catch{log("当前活动会话无法可靠识别",["原因":"\(error)"]);exit(2)}
 }else{targets=p.rows.map{$0.title}}
 var attempted=Set<String>()
 var checkedCount=0;var confirmedCount=0;var uncertainCount=0;var skippedCount=0
 for title in targets {
  do {
   var page=try get(false)
   if !current && p.reliable {
    var fresh=pins(page)
    for _ in 0..<3 where !fresh.reliable {
     Thread.sleep(forTimeInterval:0.3);page=try get(false);fresh=pins(page)
    }
    guard fresh.reliable else{throw Failure("置顶列表读取仍不可靠，跳过") }
    let row=try one(fresh.rows.filter{$0.title==title},"目标已取消置顶或不唯一")
    guard !row.all.contains(where:{$0.sub=="AXApplicationStatus" && ["处理中","In progress"].contains($0.title)}) else{throw Failure("侧边栏显示任务运行中")}
    if (try? identity(page)) != title {
     try press(row)
     for _ in 0..<8 {Thread.sleep(forTimeInterval:0.25);page=try get(false);if (try? identity(page))==title{break}}
    }
   }
   guard try identity(page)==title else{throw Failure("切换后会话身份不符，禁止操作")}
   page=try get()
   guard try identity(page)==title else{throw Failure("加载完整目标后身份发生变化")}
   do{_=try ready(page)}catch{
    log("目标输入框诊断",["会话":title,"输入框":page.all.filter{["AXTextArea","AXTextField"].contains($0.role)}.map{["标签":$0.title,"恰好继续":exact($0.value),"字符数":$0.value.count] as [String:Any]},"主区域数":page.all.filter{$0.sub=="AXLandmarkMain"}.count])
    throw error
   }
   let diagnosticBaseline=userMessages(page)
   guard diagnosticBaseline>=0 else{throw Failure("无法建立用户消息基线，未发送；请检查用户消息正文是否可读或包含未知控件")}
   if args.contains("--test"){checkedCount+=1;log("目标识别通过，未发送",["会话":title,"用户继续消息基线":diagnosticBaseline]);continue}
   guard NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier else{throw Failure("Codex 不在前台；为避免抢焦点未发送")}
   // 重建树并重新验证，绝不依赖之前保存的输入框或按钮。
   page=try get();guard try identity(page)==title else{throw Failure("提交前会话发生变化")}
   let r=try ready(page);let before=userMessages(page)
   guard before>=0 else{throw Failure("无法建立用户消息基线，未发送")}
   guard !attempted.contains(title) else{throw Failure("本次运行已经尝试过此会话")}
   guard NSWorkspace.shared.frontmostApplication?.processIdentifier==app.processIdentifier,
         let focused=read(ax,"AXFocusedWindow"),CFEqual(focused,window),
         let input=r.input.e,exact(read(input,"AXValue") as? String ?? ""),let b=r.button.e,(read(b,"AXEnabled") as? Bool)==true,read(window,"AXTitle") as? String==title else{throw Failure("提交前最后检查失败")}
   attempted.insert(title)
   log("准备单次提交",["会话":title,"原用户继续消息数":before])
   let result=AXUIElementPerformAction(b,kAXPressAction as CFString)
   log("操作已触发",["会话":title,"AX返回码":result.rawValue])
   var confirmed=false
   for _ in 0..<12 {
    Thread.sleep(forTimeInterval:0.25)
    guard let after=try? get(),(try? identity(after))==title else{break}
    if userMessages(after)>before {log("消息已提交至界面历史",["会话":title,"证据":"新增你说消息块且正文恰好继续","服务端接收":"无法由AX独立证明"]);confirmed=true;confirmedCount+=1;break}
   }
   if !confirmed{uncertainCount+=1;log("结果不确定，不重发",["会话":title,"原因":"未确认新增用户消息；输入框清空不能独立证明成功"])}
  } catch {skippedCount+=1;log("跳过",["会话":title,"原因":"\(error)"])}
 }
 let outcome = args.contains("--test") ? (checkedCount>0 ? "只读预检通过":"没有目标通过预检") : (attempted.isEmpty ? "未提交任何消息" : (uncertainCount>0 ? "存在不确定结果，请人工核对，勿重发":"已确认新增界面历史消息"))
 log("一次执行结束",["已尝试数":attempted.count,"已确认提交数":confirmedCount,"不确定数":uncertainCount,"跳过数":skippedCount,"预检通过数":checkedCount,"结果":outcome])
 if args.contains("--test") {exit(checkedCount>0 ? 0:3)}
 exit(attempted.isEmpty ? 3:(uncertainCount>0 ? 4:0))
} catch {log("失败",["原因":"\(error)"]);exit(2)}
extension ProcessInfo {var machineArchitecture:String {var info=utsname();uname(&info);return withUnsafePointer(to:&info.machine){$0.withMemoryRebound(to:CChar.self,capacity:1){String(cString:$0)}}}}
