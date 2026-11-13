// macOS Vision 얼굴 상자 찾기(위치만 잰다). 사용: swift 도구/부품/얼굴찾기.swift <그림> -> JSON [[x,y,w,h],...] (왼쪽 위 기준 px)
import Foundation
import Vision
import AppKit

let 경로 = CommandLine.arguments[1]
guard let 그림 = NSImage(contentsOfFile: 경로),
      let cg = 그림.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("그림을 못 읽었습니다: \(경로)\n".data(using: .utf8)!); exit(1)
}
let W = Double(cg.width), H = Double(cg.height)
let 요청 = VNDetectFaceRectanglesRequest()
try VNImageRequestHandler(cgImage: cg).perform([요청])
let 상자 = (요청.results ?? []).map { f -> [Int] in
    let b = f.boundingBox  // 0~1, 왼쪽 아래 기준
    return [Int(b.minX * W), Int((1 - b.maxY) * H), Int(b.width * W), Int(b.height * H)]
}
print(String(data: try JSONSerialization.data(withJSONObject: 상자), encoding: .utf8)!)
