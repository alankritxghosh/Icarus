import Foundation

/// What Icarus says OUT LOUD, derived from the answer it already wrote.
///
/// The spoken line is deliberately NOT a separately generated summary. A second
/// generation would be a second thing that can drift from the citations — a new way to
/// bluff, in a product whose whole claim is that it can't. Taking the first sentence of
/// the grounded answer means speech can never assert anything the written proof on
/// screen doesn't already support: it is a strict subset, not a paraphrase.
///
/// The screen carries the full answer and the evidence; the voice carries the headline.
public enum SpokenSummary {
    /// Upper bound on a spoken line — roughly two lines of speech. Past this, a listener
    /// has stopped tracking the sentence and should be reading the overlay instead.
    public static let maxCharacters = 220

    /// The first sentence of `answer`, bounded. Empty input yields empty output (nothing
    /// is ever invented to fill the silence).
    public static func summarize(_ answer: String) -> String {
        let text = answer.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return "" }

        if let end = firstSentenceEnd(in: text) {
            let sentence = String(text[text.startIndex...end])
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if sentence.count <= maxCharacters { return sentence }
        }
        return clip(text)
    }

    /// Index of the punctuation ending the first sentence, or nil if there isn't one.
    ///
    /// A bare "." is not enough: version numbers ("v1.2"), refs, and decimals all contain
    /// one. The terminator must be followed by whitespace-then-uppercase, or by the end of
    /// the string — which is what actually distinguishes a sentence break from a dot.
    private static func firstSentenceEnd(in text: String) -> String.Index? {
        let terminators: Set<Character> = [".", "!", "?"]
        var i = text.startIndex
        while i < text.endIndex {
            defer { i = text.index(after: i) }
            guard terminators.contains(text[i]) else { continue }

            var j = text.index(after: i)
            if j == text.endIndex { return i }               // ends the string
            guard text[j].isWhitespace else { continue }      // "v1.2" — not a break
            while j < text.endIndex, text[j].isWhitespace { j = text.index(after: j) }
            if j == text.endIndex { return i }
            if text[j].isUppercase { return i }               // next sentence starts
        }
        return nil
    }

    /// Trim to `maxCharacters` on a word boundary, marking the clip so a listener's
    /// transcript and the screen never disagree about whether more was said.
    private static func clip(_ text: String) -> String {
        guard text.count > maxCharacters else { return text }
        let cut = text.index(text.startIndex, offsetBy: maxCharacters)
        let head = text[text.startIndex..<cut]
        if let lastSpace = head.lastIndex(where: { $0.isWhitespace }) {
            return String(head[head.startIndex..<lastSpace]) + "…"
        }
        return String(head) + "…"
    }
}
