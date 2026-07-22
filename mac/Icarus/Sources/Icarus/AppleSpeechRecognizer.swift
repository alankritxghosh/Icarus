import Foundation
import Speech
@preconcurrency import AVFoundation
import IcarusKit

/// Real-time speech-to-text via Apple's Speech framework — the engine behind macOS
/// dictation. Streams partial transcripts while the user holds the key and returns the
/// final transcript on release.
///
/// Privacy: recognition runs **on-device** (`requiresOnDeviceRecognition = true`)
/// whenever this Mac has the local speech model — then audio never leaves the machine.
/// macOS provides NO API to install that model from code (Apple DevForums 703770), so
/// to keep voice zero-setup on a fresh Mac we fall back to Apple's speech service when
/// the model is absent. Macs that have used Dictation/Siri stay fully on-device; only
/// ones missing the model use the network fallback. The Info.plist and the Privacy
/// surface state this honestly — the app never claims on-device-only when it isn't.
final class AppleSpeechRecognizer: NSObject, SpeechRecognizer, @unchecked Sendable {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    private let lock = NSLock()
    private var latestTranscript = ""
    private var finishContinuation: CheckedContinuation<String, Never>?

    /// Quietest level the waveform shows movement for, in dBFS. Speech into a built-in
    /// Mac mic sits roughly -40...-10 dBFS, room tone below -55, so -55 puts normal
    /// speech across most of the pill's height without amplifying silence into noise.
    /// This is the calibration knob: raise it if the waveform looks twitchy in a quiet
    /// room, lower it if a soft speaker barely moves the bars.
    private static let levelFloorDB: Float = -55

    /// Root-mean-square loudness of one buffer, mapped to 0...1 over `levelFloorDB`.
    /// RMS (not peak) because peak spikes on a single click and reads as noise; RMS
    /// tracks perceived loudness, so the bars follow the voice.
    private static func normalizedLevel(of buffer: AVAudioPCMBuffer) -> Float {
        guard let channel = buffer.floatChannelData?[0] else { return 0 }
        let count = Int(buffer.frameLength)
        guard count > 0 else { return 0 }
        var sumOfSquares: Float = 0
        for i in 0..<count { sumOfSquares += channel[i] * channel[i] }
        let rms = (sumOfSquares / Float(count)).squareRoot()
        guard rms > 0 else { return 0 }
        let db = 20 * log10(rms)
        guard db.isFinite else { return 0 }
        return min(max((db - levelFloorDB) / -levelFloorDB, 0), 1)
    }

    func start(onPartial: @escaping @Sendable (String) -> Void,
               onLevel: @escaping @Sendable (Float) -> Void) async throws {
        guard try await Self.authorizeSpeech() else { throw SpeechStartError.notAuthorized }
        guard await AVCaptureDevice.requestAccess(for: .audio) else { throw SpeechStartError.micDenied }
        guard let recognizer, recognizer.isAvailable else { throw SpeechStartError.unavailable }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        // Prefer on-device (audio stays on the Mac) when this Mac has the local speech
        // model; otherwise fall back to Apple's speech service so voice works with ZERO
        // setup. macOS has no API to install the on-device model from code (DevForums
        // 703770), so requiring on-device would dead-end a fresh Mac.
        request.requiresOnDeviceRecognition = recognizer.supportsOnDeviceRecognition
        self.request = request
        lock.withLock { latestTranscript = "" }

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)

        // installTap raises an ObjC NSException -- which Swift CANNOT catch, so it is a
        // hard crash, not a thrown error -- in two real situations. Both are handled
        // before the call rather than after, because after is too late.
        //
        // 1. A tap already on the bus. finish() removes it on the normal path, but a
        //    session that failed AFTER the install (see engine.start below) left one
        //    behind, and the NEXT hold of the talk key then crashed the app. Observed
        //    live 2026-07-20 (two crash reports, both aborting inside
        //    CreateRecordingTap). removeTap is safe when no tap is present.
        input.removeTap(onBus: 0)
        // 2. A degenerate input format (no channels / zero sample rate), which happens
        //    when the mic is unavailable or the input device changes mid-session --
        //    unplugged headphones, AirPods handing off. A typed error gives the user the
        //    honest "not available right now" path instead of killing the app.
        guard format.channelCount > 0, format.sampleRate > 0 else {
            throw SpeechStartError.unavailable
        }

        // ONE tap feeds both the recognizer and the waveform. Measuring here (rather than
        // via a second tap or a timer) is what makes the waveform provably real: the bars
        // are computed from the exact audio being transcribed.
        // Level updates are DECIMATED, the recogniser's are not. At 44.1kHz a 1024-frame
        // buffer arrives ~43x/sec, and each level crossed to the main actor and
        // invalidated the overlay — ~43 view updates/sec behind a live vibrancy blur,
        // which is what made the UI lag. Every 3rd buffer is ~14/sec: still visibly
        // reactive to speech, a third of the work. The audio itself is never dropped.
        var bufferIndex = 0
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.request?.append(buffer)
            bufferIndex &+= 1
            if bufferIndex % 3 == 0 {
                onLevel(Self.normalizedLevel(of: buffer))
            }
        }
        engine.prepare()
        do {
            try engine.start()
        } catch {
            // Never leave the tap installed on a failed start -- that stale tap is
            // exactly what crashed the next attempt.
            input.removeTap(onBus: 0)
            throw SpeechStartError.unavailable
        }

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                let text = result.bestTranscription.formattedString
                self.lock.withLock { self.latestTranscript = text }
                onPartial(text)
                if result.isFinal { self.resolveFinish(with: text) }
            }
            if error != nil {
                self.resolveFinish(with: self.lock.withLock { self.latestTranscript })
            }
        }
    }

    func finish() async -> String {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        request?.endAudio()

        let transcript = await withCheckedContinuation { (cont: CheckedContinuation<String, Never>) in
            lock.withLock { finishContinuation = cont }
            // Safety net: if the final result never arrives, resolve with the latest
            // partial after a short grace period so finish() never hangs.
            Task { [weak self] in
                try? await Task.sleep(nanoseconds: 1_500_000_000)
                guard let self else { return }
                self.resolveFinish(with: self.lock.withLock { self.latestTranscript })
            }
        }
        cleanup()
        return transcript
    }

    /// Resolve the pending finish continuation exactly once (callbacks can race the
    /// timeout).
    private func resolveFinish(with text: String) {
        let cont: CheckedContinuation<String, Never>? = lock.withLock {
            let c = finishContinuation
            finishContinuation = nil
            return c
        }
        cont?.resume(returning: text)
    }

    private func cleanup() {
        task?.cancel()
        task = nil
        request = nil
    }

    /// Wrap the callback-based Speech authorization in async. Returns true if granted.
    private static func authorizeSpeech() async throws -> Bool {
        await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { status in
                cont.resume(returning: status == .authorized)
            }
        }
    }
}
