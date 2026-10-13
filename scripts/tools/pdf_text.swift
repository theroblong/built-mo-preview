import PDFKit
let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1]))!
var s = ""
for i in 0..<doc.pageCount { s += doc.page(at: i)?.string ?? "" }
print(doc.pageCount)
print(s)
