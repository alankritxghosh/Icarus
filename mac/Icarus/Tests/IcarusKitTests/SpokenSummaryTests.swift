import XCTest
@testable import IcarusKit

/// The spoken line must be a strict SUBSET of the grounded answer — never a
/// re-generated summary. These tests pin that property, because the moment speech
/// says something the written proof doesn't support, the product has bluffed out loud.
final class SpokenSummaryTests: XCTestCase {

    func testSpeaksOnlyTheFirstSentence() {
        let answer = "Three retries rides out a node restart. Five masked a dead node for a "
            + "full staging week, so the count was lowered in PR 1482."
        XCTAssertEqual(SpokenSummary.summarize(answer),
                       "Three retries rides out a node restart.")
    }

    /// Whatever is spoken must appear verbatim in the answer — the subset property.
    func testSpokenTextIsAlwaysContainedInTheAnswer() {
        let answers = [
            "Three retries rides out a node restart. Five masked a dead node.",
            "The scheduler picks the highest-scoring node.",
            "Retries were capped at 3 because v1.2 of the client already backs off internally.",
        ]
        for answer in answers {
            let spoken = SpokenSummary.summarize(answer)
            XCTAssertFalse(spoken.isEmpty)
            XCTAssertTrue(answer.contains(spoken.replacingOccurrences(of: "…", with: "")),
                          "spoken text must be a subset of the answer: \(spoken)")
        }
    }

    /// A dot inside "v1.2" is not a sentence break — splitting there would speak a
    /// fragment that reads as a complete claim.
    func testVersionNumberIsNotASentenceBreak() {
        let answer = "Retries were capped at 3 because v1.2 of the client already backs off. "
            + "Earlier versions did not."
        XCTAssertEqual(SpokenSummary.summarize(answer),
                       "Retries were capped at 3 because v1.2 of the client already backs off.")
    }

    func testSingleSentenceAnswerIsSpokenWhole() {
        let answer = "The scheduler picks the highest-scoring node."
        XCTAssertEqual(SpokenSummary.summarize(answer), answer)
    }

    /// A first "sentence" longer than the spoken budget is clipped on a word boundary
    /// and MARKED, so the listener knows there is more on screen.
    func testOverlongFirstSentenceIsClippedAndMarked() {
        let answer = String(repeating: "retry ", count: 80) + "finally."
        let spoken = SpokenSummary.summarize(answer)
        XCTAssertLessThanOrEqual(spoken.count, SpokenSummary.maxCharacters + 1)
        XCTAssertTrue(spoken.hasSuffix("…"))
        XCTAssertFalse(spoken.contains("retr…"), "should clip at a word boundary")
    }

    /// No sentence-ending punctuation at all still yields something speakable.
    func testUnpunctuatedAnswerStillProducesSpeech() {
        let spoken = SpokenSummary.summarize("three retries rides out a node restart")
        XCTAssertEqual(spoken, "three retries rides out a node restart")
    }

    func testEmptyAndBlankAnswersSpeakNothing() {
        XCTAssertEqual(SpokenSummary.summarize(""), "")
        XCTAssertEqual(SpokenSummary.summarize("   \n  "), "")
    }
}
