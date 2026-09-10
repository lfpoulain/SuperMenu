import Foundation
import Speech
@preconcurrency import AVFAudio

// PCM and transcripts travel exclusively over inherited private pipes.
private enum SpeechError: Error {
    case unavailable, language, missingModel, invalidAudio, backlog
}

private enum Output {
    static let lock = NSLock()
    static func send(_ value: [String: Any], sessionID: String? = nil) {
        var message = value
        if let sessionID { message["session_id"] = sessionID }
        guard var data = try? JSONSerialization.data(withJSONObject: message) else { return }
        data.append(10)
        lock.lock()
        defer { lock.unlock() }
        FileHandle.standardOutput.write(data)
    }
}

@main
struct SpeechHelper {
    static func main() async {
        guard #available(macOS 26.0, *) else {
            Output.send(["event": "error", "code": "os_unsupported",
                         "message": "Apple Speech nécessite macOS 26 ou une version ultérieure."])
            return
        }
        var sessionID: String?
        var warm = false
        do {
            while let line = readLine() {
                guard let data = line.data(using: .utf8),
                      let request = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw SpeechError.invalidAudio
                }
                let action = request["action"] as? String ?? "start"
                // A late cancellation can cross the completion of its session.
                if action == "cancel" || action == "stop" { continue }
                sessionID = request["session_id"] as? String
                try await run(request, warm: warm)
                if request["keep_alive"] as? Bool != true { break }
                if action == "start" { warm = true }
            }
        } catch {
            let message: String
            switch error {
            case SpeechError.unavailable:
                message = "Apple Speech n’est pas disponible sur ce Mac."
            case SpeechError.language:
                message = "Cette langue n’est pas prise en charge par Apple Speech. Choisissez une autre langue."
            case SpeechError.missingModel:
                message = "Téléchargez le modèle Apple Speech dans les réglages de dictée avant de commencer."
            case SpeechError.backlog:
                message = "Apple Speech ne suit plus le microphone. Réessayez après avoir fermé les tâches lourdes."
            default:
                message = "Apple Speech n’a pas pu terminer l’opération. Vérifiez le modèle de langue puis réessayez."
            }
            Output.send(["event": "error", "message": message], sessionID: sessionID)
        }
    }

    @available(macOS 26.0, *)
    private static func run(_ request: [String: Any], warm: Bool) async throws {
        let sessionID = request["session_id"] as? String
        guard SpeechTranscriber.isAvailable else { throw SpeechError.unavailable }
        guard let language = request["language"] as? String, !language.isEmpty,
              let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language)) else {
            throw SpeechError.language
        }
        let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [],
                                            reportingOptions: [.volatileResults], attributeOptions: [])
        let action = request["action"] as? String ?? "start"
        if action == "download" {
            Output.send(["event": "progress", "phase": "download", "message": "Téléchargement et installation du modèle Apple Speech pour \(locale.identifier)…"], sessionID: sessionID)
            if let installation = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
                try await installation.downloadAndInstall()
            }
        }
        let installed = await SpeechTranscriber.installedLocales
        let cached = installed.contains { $0.identifier == locale.identifier }
        if action == "probe" || action == "download" {
            Output.send(["event": "result", "data": ["cached": cached,
                         "device": "Apple Speech sur ce Mac · \(locale.identifier)"]], sessionID: sessionID)
            return
        }
        guard action == "start", cached else { throw SpeechError.missingModel }
        Output.send(["event": "progress", "phase": warm ? "reuse" : "load",
                     "message": warm ? "Le modèle Apple Speech est déjà en mémoire. Ouverture d’une nouvelle dictée…" : "Chargement du modèle Apple Speech installé en mémoire…"], sessionID: sessionID)
        guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber]),
              let inputFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000,
                                              channels: 1, interleaved: false),
              let converter = AVAudioConverter(from: inputFormat, to: format) else {
            throw SpeechError.invalidAudio
        }
        converter.primeMethod = .none
        // Keep Apple's model cache alive across fresh analyzers. The shared
        // supervisor exits this helper at the configured idle deadline.
        let retention: SpeechAnalyzer.Options.ModelRetention =
            request["keep_alive"] as? Bool == true ? .processLifetime : .whileInUse
        let analyzer = SpeechAnalyzer(modules: [transcriber],
                                      options: .init(priority: .userInitiated, modelRetention: retention))
        try await analyzer.prepareToAnalyze(in: format)
        let (inputs, continuation) = AsyncStream<AnalyzerInput>.makeStream(bufferingPolicy: .bufferingOldest(64))
        let results = Task {
            var finalized = ""
            var provisional = ""
            do {
                for try await result in transcriber.results {
                    let text = String(result.text.characters)
                    if result.isFinal {
                        finalized += text
                        provisional = ""
                    } else {
                        provisional = text
                    }
                    Output.send(["event": "transcript", "text": finalized + provisional], sessionID: sessionID)
                }
                return finalized + provisional
            } catch {
                Output.send(["event": "error", "message": "Apple Speech a interrompu la transcription. Réessayez."], sessionID: sessionID)
                throw error
            }
        }
        try await analyzer.start(inputSequence: inputs)
        Output.send(["event": "ready"], sessionID: sessionID)
        let producer = Task.detached {
            defer { continuation.finish() }
            var bytes = 0
            while let line = readLine() {
                guard line.utf8.count < 100_000, let data = line.data(using: .utf8),
                      let event = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    throw SpeechError.invalidAudio
                }
                if event["session_id"] as? String != sessionID { continue }
                if event["action"] as? String == "stop" { return true }
                if event["action"] as? String == "cancel" { return false }
                guard let encoded = event["audio"] as? String,
                      let pcm = Data(base64Encoded: encoded), !pcm.isEmpty, pcm.count % 2 == 0 else {
                    throw SpeechError.invalidAudio
                }
                bytes += pcm.count
                guard bytes <= 16000 * 2 * 302 else { throw SpeechError.invalidAudio }
                let frames = AVAudioFrameCount(pcm.count / 2)
                guard let input = AVAudioPCMBuffer(pcmFormat: inputFormat, frameCapacity: frames),
                      let destination = input.int16ChannelData?[0] else { throw SpeechError.invalidAudio }
                input.frameLength = frames
                pcm.withUnsafeBytes { raw in
                    if let address = raw.baseAddress { memcpy(destination, address, pcm.count) }
                }
                let capacity = AVAudioFrameCount(ceil(Double(frames) * format.sampleRate / 16000)) + 32
                guard let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: capacity) else {
                    throw SpeechError.invalidAudio
                }
                var consumed = false
                var conversionError: NSError?
                let status = converter.convert(to: output, error: &conversionError) { _, inputStatus in
                    if consumed { inputStatus.pointee = .noDataNow; return nil }
                    consumed = true
                    inputStatus.pointee = .haveData
                    return input
                }
                guard status != .error, conversionError == nil else { throw SpeechError.invalidAudio }
                if output.frameLength > 0 {
                    if case .dropped = continuation.yield(AnalyzerInput(buffer: output)) {
                        throw SpeechError.backlog
                    }
                }
            }
            return false
        }
        do {
            let stopped = try await producer.value
            try await analyzer.finalizeAndFinishThroughEndOfInput()
            let text = try await results.value
            Output.send(stopped ? ["event": "complete", "text": text] : ["event": "cancelled"], sessionID: sessionID)
        } catch {
            await analyzer.cancelAndFinishNow()
            results.cancel()
            throw error
        }
    }
}
