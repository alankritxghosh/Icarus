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

    func start(onPartial: @escaping @Sendable (String) -> Void) async throws {
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
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.request?.append(buffer)
        }
        engine.prepare()
        try engine.start()

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
