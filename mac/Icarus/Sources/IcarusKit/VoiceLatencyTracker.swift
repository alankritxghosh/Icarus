import Foundation
import Observation

/// In-memory timing for the real push-to-talk path.
///
/// It records durations only—never audio, transcripts, questions, answers,
/// repositories, or identities—and keeps at most the newest 50 completed asks.
/// Main-actor isolation matches the voice and overlay models that feed it.
@MainActor
@Observable
public final class VoiceLatencyTracker {
    public struct Sample: Equatable, Sendable {
        public let hold: TimeInterval
        public let transcription: TimeInterval
        public let brain: TimeInterval
        public let speechQueue: TimeInterval
        public let releaseToFirstWord: TimeInterval
        public let total: TimeInterval
    }

    private struct Journey {
        let started: TimeInterval
        var released: TimeInterval?
        var transcript: TimeInterval?
        var answer: TimeInterval?
    }

    public static let sampleLimit = 50
    public private(set) var samples: [Sample] = []

    @ObservationIgnored private let now: () -> TimeInterval
    @ObservationIgnored private var journey: Journey?

    public init(now: @escaping () -> TimeInterval = {
        ProcessInfo.processInfo.systemUptime
    }) {
        self.now = now
    }

    public var latest: Sample? { samples.last }
    public var releaseToFirstWordP50: TimeInterval? { percentile(0.50) }
    public var releaseToFirstWordP95: TimeInterval? { percentile(0.95) }

    public func begin() {
        journey = Journey(started: now())
    }

    public func released() {
        guard var current = journey, current.released == nil else { return }
        let timestamp = now()
        guard timestamp >= current.started else {
            journey = nil
            return
        }
        current.released = timestamp
        journey = current
    }

    public func transcriptReady() {
        guard var current = journey,
              let released = current.released,
              current.transcript == nil else { return }
        let timestamp = now()
        guard timestamp >= released else {
            journey = nil
            return
        }
        current.transcript = timestamp
        journey = current
    }

    public func answerReady() {
        guard var current = journey,
              let transcript = current.transcript,
              current.answer == nil else { return }
        let timestamp = now()
        guard timestamp >= transcript else {
            journey = nil
            return
        }
        current.answer = timestamp
        journey = current
    }

    public func firstWordStarted() {
        guard let current = journey,
              let released = current.released,
              let transcript = current.transcript,
              let answer = current.answer else { return }
        let spoken = now()
        guard spoken >= answer else {
            journey = nil
            return
        }
        samples.append(Sample(
            hold: released - current.started,
            transcription: transcript - released,
            brain: answer - transcript,
            speechQueue: spoken - answer,
            releaseToFirstWord: spoken - released,
            total: spoken - current.started
        ))
        if samples.count > Self.sampleLimit {
            samples.removeFirst(samples.count - Self.sampleLimit)
        }
        journey = nil
    }

    public func cancel() {
        journey = nil
    }

    private func percentile(_ fraction: Double) -> TimeInterval? {
        guard !samples.isEmpty else { return nil }
        let values = samples.map(\.releaseToFirstWord).sorted()
        let rank = max(1, Int(ceil(fraction * Double(values.count))))
        return values[rank - 1]
    }
}
