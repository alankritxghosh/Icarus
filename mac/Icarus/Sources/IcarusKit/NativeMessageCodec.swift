import Foundation

public enum NativeMessageCodecError: Error, Equatable {
    case malformedFrame
    case messageTooLarge
}

/// Chrome native messaging uses a four-byte little-endian length followed by
/// one UTF-8 JSON object. Icarus bounds the body before allocating it.
public enum NativeMessageCodec {
    public static let maximumBodySize = 64 * 1024

    public static func frame(_ body: Data) throws -> Data {
        guard body.count <= maximumBodySize else {
            throw NativeMessageCodecError.messageTooLarge
        }
        let count = UInt32(body.count)
        var framed = Data([
            UInt8(count & 0xff),
            UInt8((count >> 8) & 0xff),
            UInt8((count >> 16) & 0xff),
            UInt8((count >> 24) & 0xff),
        ])
        framed.append(body)
        return framed
    }

    /// Read exactly one message from Chrome without waiting for stdin to close.
    /// The helper process exits after its one response, so later messages cannot
    /// share its credential-bearing lifetime.
    public static func readMessage(from handle: FileHandle) throws -> Data {
        let header = try readExactly(4, from: handle)
        let bytes = [UInt8](header)
        let count = Int(bytes[0])
            | (Int(bytes[1]) << 8)
            | (Int(bytes[2]) << 16)
            | (Int(bytes[3]) << 24)
        guard count <= maximumBodySize else {
            throw NativeMessageCodecError.messageTooLarge
        }
        return try readExactly(count, from: handle)
    }

    private static func readExactly(_ count: Int, from handle: FileHandle) throws -> Data {
        var output = Data()
        while output.count < count {
            guard let chunk = try handle.read(upToCount: count - output.count),
                  !chunk.isEmpty else {
                throw NativeMessageCodecError.malformedFrame
            }
            output.append(chunk)
        }
        return output
    }
}

public enum NativeBridgeAction: String, Decodable, Sendable {
    case ping
    case status
    case explain
}

public struct NativeBridgeExplainPayload: Decodable, Sendable {
    public let repo: String
    public let path: String
    public let start: Int
    public let end: Int
    public let question: String?
}

public struct NativeBridgeRequest: Decodable, Sendable {
    public let action: NativeBridgeAction
    public let payload: NativeBridgeExplainPayload?
}
