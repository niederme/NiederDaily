import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count == 2 else {
    fputs("usage: generate_niederdaily_icon.swift <iconset-dir>\n", stderr)
    exit(2)
}

let outputDir = URL(fileURLWithPath: args[1], isDirectory: true)
try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

let accent = NSColor(calibratedRed: 1.0, green: 0.2706, blue: 0.2275, alpha: 1.0)
let ink = NSColor(calibratedRed: 0.0706, green: 0.0706, blue: 0.0706, alpha: 1.0)
let paper = NSColor(calibratedRed: 0.988, green: 0.984, blue: 0.972, alpha: 1.0)
let line = NSColor(calibratedRed: 0.839, green: 0.816, blue: 0.776, alpha: 1.0)

let sizes: [(Int, String)] = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

func savePNG(size: Int, name: String) throws {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()

    let rect = NSRect(x: 0, y: 0, width: size, height: size)
    paper.setFill()
    NSBezierPath(rect: rect).fill()

    let inset = CGFloat(size) * 0.055
    let radius = CGFloat(size) * 0.22
    let boxRect = rect.insetBy(dx: inset, dy: inset)
    let box = NSBezierPath(roundedRect: boxRect, xRadius: radius, yRadius: radius)
    paper.setFill()
    box.fill()
    line.setStroke()
    box.lineWidth = max(2, CGFloat(size) * 0.018)
    box.stroke()

    let dividerX = boxRect.midX
    let gutter = CGFloat(size) * 0.015
    let leftRect = NSRect(
        x: boxRect.minX + CGFloat(size) * 0.05,
        y: boxRect.minY + CGFloat(size) * 0.06,
        width: dividerX - boxRect.minX - gutter - CGFloat(size) * 0.05,
        height: boxRect.height - CGFloat(size) * 0.12
    )
    let rightRect = NSRect(
        x: dividerX + gutter,
        y: leftRect.minY,
        width: boxRect.maxX - dividerX - gutter - CGFloat(size) * 0.05,
        height: leftRect.height
    )

    let fontSize = CGFloat(size) * 0.56
    let font = NSFont.systemFont(ofSize: fontSize, weight: .bold)
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center

    let leftAttrs: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: ink,
        .paragraphStyle: paragraph,
    ]
    let rightAttrs: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: accent,
        .paragraphStyle: paragraph,
    ]

    let baselineAdjust = CGFloat(size) * 0.015
    NSAttributedString(string: "N", attributes: leftAttrs)
        .draw(in: leftRect.offsetBy(dx: 0, dy: baselineAdjust))
    NSAttributedString(string: "D", attributes: rightAttrs)
        .draw(in: rightRect.offsetBy(dx: 0, dy: baselineAdjust))

    image.unlockFocus()

    guard
        let tiff = image.tiffRepresentation,
        let rep = NSBitmapImageRep(data: tiff),
        let png = rep.representation(using: .png, properties: [:])
    else {
        throw NSError(domain: "NiederDailyIcon", code: 1)
    }

    try png.write(to: outputDir.appendingPathComponent(name))
}

for (size, name) in sizes {
    try savePNG(size: size, name: name)
}
