import Foundation
import FoundationModels

// One request per process: no conversation history or user text on disk.
private struct Request: Decodable {
    let action: String
    let prompt: String?
    let content: String?
}

private struct Reply: Encodable {
    let ok: Bool
    var code: String? = nil
    var content: String? = nil
}

@main
struct FoundationModelsHelper {
    static func main() async {
        let reply: Reply
        do {
            let input = FileHandle.standardInput.readDataToEndOfFile()
            let request = try JSONDecoder().decode(Request.self, from: input)
            if #available(macOS 26.0, *) {
                reply = await handle(request)
            } else {
                reply = Reply(ok: false, code: "os_unsupported")
            }
        } catch {
            reply = Reply(ok: false, code: "invalid_request")
        }
        // Errors contain stable codes only; never echo prompts or framework errors.
        if let data = try? JSONEncoder().encode(reply) {
            FileHandle.standardOutput.write(data)
        }
    }

    @available(macOS 26.0, *)
    private static func handle(_ request: Request) async -> Reply {
        guard request.action == "availability" || request.action == "generate" else {
            return Reply(ok: false, code: "invalid_request")
        }
        let model = SystemLanguageModel.default
        switch model.availability {
        case .available:
            break
        case .unavailable(let reason):
            switch reason {
            case .deviceNotEligible:
                return Reply(ok: false, code: "device_not_eligible")
            case .appleIntelligenceNotEnabled:
                return Reply(ok: false, code: "intelligence_disabled")
            case .modelNotReady:
                return Reply(ok: false, code: "model_not_ready")
            @unknown default:
                return Reply(ok: false, code: "unavailable")
            }
        @unknown default:
            return Reply(ok: false, code: "unavailable")
        }
        if request.action == "availability" {
            return Reply(ok: true)
        }
        guard let prompt = request.prompt, let content = request.content,
              !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return Reply(ok: false, code: "invalid_request")
        }
        do {
            let hasSelection = !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            let session = hasSelection
                ? LanguageModelSession(model: model, instructions: prompt)
                : LanguageModelSession(model: model)
            let response = try await session.respond(to: hasSelection ? content : prompt)
            guard !response.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return Reply(ok: false, code: "empty_response")
            }
            return Reply(ok: true, content: response.content)
        } catch LanguageModelSession.GenerationError.exceededContextWindowSize {
            return Reply(ok: false, code: "context_exceeded")
        } catch LanguageModelSession.GenerationError.guardrailViolation {
            return Reply(ok: false, code: "guardrail")
        } catch LanguageModelSession.GenerationError.refusal {
            return Reply(ok: false, code: "refusal")
        } catch LanguageModelSession.GenerationError.unsupportedLanguageOrLocale {
            return Reply(ok: false, code: "unsupported_language")
        } catch LanguageModelSession.GenerationError.assetsUnavailable {
            return Reply(ok: false, code: "model_not_ready")
        } catch {
            return Reply(ok: false, code: "generation_failed")
        }
    }
}
